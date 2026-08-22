import contextlib
import io
import os
import subprocess
import unittest
from unittest.mock import MagicMock, call, patch

from scripts.run_isolated_pytest import (
    DisposableDatabase,
    IsolatedPytestError,
    build_disposable_database,
    run_isolated_pytest,
)

ADMIN_URL = "postgresql+asyncpg://admin:private@localhost:55432/rotas"


class BuildDisposableDatabaseTests(unittest.TestCase):
    def test_builds_unique_safe_target_without_mutating_the_source_database(self) -> None:
        database = build_disposable_database(ADMIN_URL, run_id="ABC-123")

        self.assertEqual(database.name, "rotas_test_abc_123")
        self.assertTrue(database.test_url.endswith("/rotas_test_abc_123"))
        self.assertTrue(database.maintenance_url.endswith("/postgres"))
        self.assertTrue(database.maintenance_url.startswith("postgresql://"))
        self.assertFalse(database.test_url.endswith("/rotas"))

    def test_rejects_parallel_workers_until_each_worker_has_its_own_database(self) -> None:
        database = build_disposable_database(ADMIN_URL, run_id="serial")

        with self.assertRaisesRegex(IsolatedPytestError, "parallel workers"):
            run_isolated_pytest(database, ["-n", "2"], base_environment={})


class RunIsolatedPytestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = build_disposable_database(ADMIN_URL, run_id="unit")

    @patch("scripts.run_isolated_pytest.subprocess.run")
    @patch.object(DisposableDatabase, "drop")
    @patch.object(DisposableDatabase, "create")
    def test_migrates_then_runs_pytest_with_only_the_disposable_target(
        self,
        create: MagicMock,
        drop: MagicMock,
        run: MagicMock,
    ) -> None:
        run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0),
            subprocess.CompletedProcess(args=[], returncode=0),
        ]
        environment = {
            "DATABASE_URL": ADMIN_URL,
            "ADMIN_DATABASE_URL": ADMIN_URL,
            "ALEMBIC_DATABASE_URL": ADMIN_URL,
        }

        return_code = run_isolated_pytest(
            self.database,
            ["tests/test_driver_app_api.py", "-q"],
            base_environment=environment,
        )

        self.assertEqual(return_code, 0)
        create.assert_called_once_with()
        drop.assert_called_once_with()
        expected_pytest_environment = {
            **environment,
            "TEST_DATABASE_URL": self.database.test_url,
        }
        expected_migration_environment = {
            **expected_pytest_environment,
            "DATABASE_URL": self.database.test_url,
            "ADMIN_DATABASE_URL": self.database.test_url,
            "ALEMBIC_DATABASE_URL": self.database.test_url,
        }
        self.assertEqual(
            run.call_args_list,
            [
                call(
                    [os.sys.executable, "-m", "alembic", "upgrade", "head"],
                    env=expected_migration_environment,
                    check=False,
                ),
                call(
                    [
                        os.sys.executable,
                        "-m",
                        "pytest",
                        "tests/test_driver_app_api.py",
                        "-q",
                    ],
                    env=expected_pytest_environment,
                    check=False,
                ),
            ],
        )

    @patch("scripts.run_isolated_pytest.subprocess.run")
    @patch.object(DisposableDatabase, "drop")
    @patch.object(DisposableDatabase, "create")
    def test_does_not_run_pytest_when_migrations_fail_but_still_drops_database(
        self,
        create: MagicMock,
        drop: MagicMock,
        run: MagicMock,
    ) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=7)

        return_code = run_isolated_pytest(self.database, [], base_environment={})

        self.assertEqual(return_code, 7)
        self.assertEqual(run.call_count, 1)
        create.assert_called_once_with()
        drop.assert_called_once_with()

    @patch("scripts.run_isolated_pytest.subprocess.run")
    @patch.object(DisposableDatabase, "drop", side_effect=RuntimeError("drop failed"))
    @patch.object(DisposableDatabase, "create")
    def test_reports_orphan_without_disclosing_credentials_when_cleanup_fails(
        self,
        create: MagicMock,
        drop: MagicMock,
        run: MagicMock,
    ) -> None:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            return_code = run_isolated_pytest(self.database, [], base_environment={})

        self.assertEqual(return_code, 1)
        self.assertIn("rotas_test_unit", stderr.getvalue())
        self.assertIn("orphan", stderr.getvalue().lower())
        self.assertNotIn("private", stderr.getvalue())
        create.assert_called_once_with()
        drop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
