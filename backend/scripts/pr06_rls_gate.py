"""Read-only PR-06 audit for PostgreSQL tenant isolation and runtime roles."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg


def _asyncpg_url(value: str) -> str:
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


def _required_url(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required; PR-06 fails closed without both roles.")
    return _asyncpg_url(value)


async def audit() -> dict[str, Any]:
    restricted = await asyncpg.connect(_required_url("PR06_RESTRICTED_DATABASE_URL"))
    admin = await asyncpg.connect(_required_url("PR06_ADMIN_DATABASE_URL"))
    try:
        app_role = dict(
            await restricted.fetchrow(
                "SELECT current_user AS role_name, rolsuper, rolbypassrls, rolcanlogin "
                "FROM pg_roles WHERE rolname = current_user"
            )
        )
        admin_role = dict(
            await admin.fetchrow(
                "SELECT current_user AS role_name, rolsuper, rolbypassrls, rolcanlogin "
                "FROM pg_roles WHERE rolname = current_user"
            )
        )

        tenant_tables = [
            dict(row)
            for row in await admin.fetch(
                """
                SELECT relation.relname AS table_name,
                       relation.relrowsecurity AS rls_enabled,
                       relation.relforcerowsecurity AS rls_forced
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relkind IN ('r', 'p')
                  AND NOT relation.relispartition
                  AND EXISTS (
                      SELECT 1 FROM pg_attribute AS attribute
                      WHERE attribute.attrelid = relation.oid
                        AND attribute.attname = 'tenant_id'
                        AND NOT attribute.attisdropped
                  )
                ORDER BY relation.relname
                """
            )
        ]
        policies = [
            dict(row)
            for row in await admin.fetch(
                """
                SELECT tablename AS table_name, policyname, roles, qual, with_check
                FROM pg_policies
                WHERE schemaname = 'public'
                ORDER BY tablename, policyname
                """
            )
        ]
        tenant_names = {row["table_name"] for row in tenant_tables}
        policies_by_table: dict[str, list[dict[str, Any]]] = {
            table_name: [] for table_name in tenant_names
        }
        for policy in policies:
            if policy["table_name"] in policies_by_table:
                policies_by_table[policy["table_name"]].append(policy)

        missing_app_grants = [
            dict(row)
            for row in await admin.fetch(
                """
                SELECT relation.relname AS table_name, privilege.privilege
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'))
                    AS privilege(privilege)
                WHERE namespace.nspname = 'public'
                  AND relation.relkind IN ('r', 'p')
                  AND NOT relation.relispartition
                  AND EXISTS (
                      SELECT 1 FROM pg_attribute AS attribute
                      WHERE attribute.attrelid = relation.oid
                        AND attribute.attname = 'tenant_id'
                        AND NOT attribute.attisdropped
                  )
                  AND NOT has_table_privilege(
                      'rotas_app', format('%I.%I', namespace.nspname, relation.relname),
                      privilege.privilege
                  )
                ORDER BY relation.relname, privilege.privilege
                """
            )
        ]
        missing_admin_grants = [
            dict(row)
            for row in await admin.fetch(
                """
                SELECT relation.relname AS table_name, privilege.privilege
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'))
                    AS privilege(privilege)
                WHERE namespace.nspname = 'public'
                  AND relation.relkind IN ('r', 'p')
                  AND NOT relation.relispartition
                  AND relation.relname <> 'alembic_version'
                  AND NOT has_table_privilege(
                      'rotas_admin', format('%I.%I', namespace.nspname, relation.relname),
                      privilege.privilege
                  )
                ORDER BY relation.relname, privilege.privilege
                """
            )
        ]
        control_plane = dict(
            await admin.fetchrow(
                """
                SELECT
                    has_schema_privilege('rotas_app', 'public', 'USAGE') AS schema_usage,
                    has_schema_privilege('rotas_app', 'public', 'CREATE') AS schema_create,
                    has_table_privilege('rotas_app', 'tenants', 'SELECT') AS tenant_select,
                    has_table_privilege('rotas_app', 'tenants', 'INSERT') AS tenant_insert,
                    has_table_privilege('rotas_app', 'platform_users', 'SELECT') AS platform_read,
                    has_table_privilege('rotas_app', 'alembic_version', 'SELECT') AS alembic_read
                """
            )
        )

        rls_gaps = [
            row["table_name"]
            for row in tenant_tables
            if not row["rls_enabled"] or not row["rls_forced"]
        ]
        policy_gaps: list[str] = []
        for table_name, table_policies in policies_by_table.items():
            if len(table_policies) != 1:
                policy_gaps.append(table_name)
                continue
            policy = table_policies[0]
            if (
                policy["policyname"] != "tenant_isolation"
                or policy["roles"] != ["rotas_app"]
                or "app.tenant_id" not in (policy["qual"] or "")
                or "app.tenant_id" not in (policy["with_check"] or "")
            ):
                policy_gaps.append(table_name)

        blockers: list[str] = []
        if app_role != {
            "role_name": "rotas_app",
            "rolsuper": False,
            "rolbypassrls": False,
            "rolcanlogin": True,
        }:
            blockers.append("rotas_app role attributes are not fail-closed")
        if admin_role != {
            "role_name": "rotas_admin",
            "rolsuper": False,
            "rolbypassrls": True,
            "rolcanlogin": True,
        }:
            blockers.append("rotas_admin role attributes do not match worker contract")
        if not tenant_tables:
            blockers.append("no tenant-scoped tables discovered")
        if rls_gaps:
            blockers.append("tenant tables missing ENABLE/FORCE RLS")
        if policy_gaps:
            blockers.append("tenant tables missing one canonical read/write policy")
        if missing_app_grants:
            blockers.append("rotas_app is missing tenant-table CRUD grants")
        if missing_admin_grants:
            blockers.append("rotas_admin is missing application-table CRUD grants")
        if control_plane != {
            "schema_usage": True,
            "schema_create": False,
            "tenant_select": True,
            "tenant_insert": False,
            "platform_read": False,
            "alembic_read": False,
        }:
            blockers.append("rotas_app control-plane privileges are not least-privilege")

        return {
            "gate": "PR-06",
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "database": await admin.fetchval("SELECT current_database()"),
            "server_version": await admin.fetchval("SHOW server_version"),
            "application_role": app_role,
            "administrative_role": admin_role,
            "tenant_table_count": len(tenant_tables),
            "rls_gap_count": len(rls_gaps),
            "rls_gaps": rls_gaps,
            "policy_gap_count": len(policy_gaps),
            "policy_gaps": sorted(policy_gaps),
            "missing_app_grant_count": len(missing_app_grants),
            "missing_app_grants": missing_app_grants,
            "missing_admin_grant_count": len(missing_admin_grants),
            "missing_admin_grants": missing_admin_grants,
            "control_plane_privileges": control_plane,
            "blockers": blockers,
            "decision": "PASS" if not blockers else "FAIL",
        }
    finally:
        await restricted.close()
        await admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(audit())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
    print(rendered, end="")
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
