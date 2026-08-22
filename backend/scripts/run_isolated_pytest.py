"""Create, migrate, use, and remove one disposable PostgreSQL test database."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from scripts.test_database_guard import validate_test_database_url

_SAFE_DATABASE_NAME = re.compile(r"^rotas_test_[a-z0-9_]+$")


class IsolatedPytestError(RuntimeError):
    """Raised when the isolated runner cannot guarantee safe execution."""


@dataclass(frozen=True)
class DisposableDatabase:
    name: str
    test_url: str
    maintenance_url: str

    def __post_init__(self) -> None:
        if _SAFE_DATABASE_NAME.fullmatch(self.name) is None:
            raise IsolatedPytestError("Refusing an unsafe disposable database name.")

    def create(self) -> None:
        with psycopg.connect(self.maintenance_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(self.name)
                )
            )

    def drop(self) -> None:
        with psycopg.connect(self.maintenance_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (self.name,),
            )
            connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(self.name))
            )


def _safe_run_id(run_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", run_id.lower()).strip("_")
    if not normalized:
        raise IsolatedPytestError("The disposable database run id is empty or invalid.")
    return normalized[:52].rstrip("_")


def build_disposable_database(
    admin_url: str,
    *,
    run_id: str,
    environment: Mapping[str, str] | None = None,
) -> DisposableDatabase:
    """Derive safe test and maintenance targets without connecting to PostgreSQL."""
    database_name = f"rotas_test_{_safe_run_id(run_id)}"
    parsed_admin_url = make_url(admin_url)
    test_url = parsed_admin_url.set(
        drivername="postgresql+asyncpg",
        database=database_name,
    ).render_as_string(hide_password=False)
    maintenance_url = parsed_admin_url.set(
        drivername="postgresql",
        database="postgres",
    ).render_as_string(hide_password=False)

    validation_environment = dict(environment or {})
    validation_environment["TEST_DATABASE_URL"] = test_url
    validate_test_database_url(validation_environment)

    return DisposableDatabase(
        name=database_name,
        test_url=test_url,
        maintenance_url=maintenance_url,
    )


def _assert_serial_pytest(pytest_args: Sequence[str]) -> None:
    for index, argument in enumerate(pytest_args):
        if argument == "-n" or argument == "--numprocesses":
            raise IsolatedPytestError(
                "The isolated runner does not yet support parallel workers; omit xdist -n."
            )
        if argument.startswith("-n") and argument != "-n":
            raise IsolatedPytestError(
                "The isolated runner does not yet support parallel workers; omit xdist -n."
            )
        if argument.startswith("--numprocesses="):
            raise IsolatedPytestError(
                "The isolated runner does not yet support parallel workers; omit xdist -n."
            )
        if index > 0 and pytest_args[index - 1] in {"-n", "--numprocesses"}:
            raise IsolatedPytestError(
                "The isolated runner does not yet support parallel workers; omit xdist -n."
            )


def run_isolated_pytest(
    database: DisposableDatabase,
    pytest_args: Sequence[str],
    *,
    base_environment: Mapping[str, str],
) -> int:
    """Run Alembic and pytest against one new database, then always clean it up."""
    _assert_serial_pytest(pytest_args)
    pytest_environment = dict(base_environment)
    pytest_environment["TEST_DATABASE_URL"] = database.test_url
    migration_environment = dict(pytest_environment)
    migration_environment.update(
        {
            "DATABASE_URL": database.test_url,
            "ADMIN_DATABASE_URL": database.test_url,
            "ALEMBIC_DATABASE_URL": database.test_url,
        }
    )

    database_created = False
    return_code = 1
    cleanup_failed = False
    try:
        database.create()
        database_created = True
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=migration_environment,
            check=False,
        )
        return_code = migration.returncode
        if migration.returncode == 0:
            tests = subprocess.run(
                [sys.executable, "-m", "pytest", *pytest_args],
                env=pytest_environment,
                check=False,
            )
            return_code = tests.returncode
    finally:
        if database_created:
            try:
                database.drop()
            except Exception:
                cleanup_failed = True
                print(
                    f"ERROR: disposable database orphan requires controlled cleanup: {database.name}",
                    file=sys.stderr,
                )

    return 1 if cleanup_failed else return_code


def main(argv: Sequence[str] | None = None) -> int:
    pytest_args = list(argv if argv is not None else sys.argv[1:])
    try:
        from app.config import get_settings

        settings = get_settings()
        admin_url = os.environ.get(
            "TEST_DATABASE_ADMIN_URL",
            settings.resolved_alembic_database_url,
        )
        now = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run_id = f"{now}_{os.getpid()}_{uuid4().hex[:8]}"
        database = build_disposable_database(
            admin_url,
            run_id=run_id,
            environment=os.environ,
        )
        return run_isolated_pytest(
            database,
            pytest_args,
            base_environment=os.environ,
        )
    except Exception as exc:
        print(
            f"ERROR: isolated pytest provisioning failed ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
