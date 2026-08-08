import os
from unittest.mock import AsyncMock

import asyncpg
import pytest
from sqlalchemy import text

from app import database
from app.database import AdminSessionLocal, DatabaseRoleSecurity


@pytest.mark.asyncio
async def test_rotas_app_direct_login_is_restricted():
    restricted_url = os.environ.get("PR06_RESTRICTED_DATABASE_URL")
    assert restricted_url, (
        "PR06_RESTRICTED_DATABASE_URL is required; the restricted-role gate "
        "must never skip when rotas_app cannot be reached."
    )

    connection = await asyncpg.connect(restricted_url)
    try:
        role = await connection.fetchrow(
            "SELECT current_user AS role_name, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"
        )
    finally:
        await connection.close()

    assert role is not None
    assert role["role_name"] == "rotas_app"
    assert role["rolsuper"] is False
    assert role["rolbypassrls"] is False


def test_database_role_security_classifies_restricted_role():
    restricted = DatabaseRoleSecurity(
        role_name="rotas_app",
        is_superuser=False,
        bypasses_rls=False,
    )
    assert restricted.is_restricted is True


@pytest.mark.asyncio
async def test_production_guard_rejects_privileged_database_role(monkeypatch):
    privileged = DatabaseRoleSecurity(
        role_name="database_owner",
        is_superuser=True,
        bypasses_rls=False,
    )
    monkeypatch.setattr(
        database,
        "inspect_application_database_role",
        AsyncMock(return_value=privileged),
    )

    with pytest.raises(RuntimeError, match="rotas_app"):
        await database.validate_application_database_role(require_restricted=True)


@pytest.mark.asyncio
async def test_production_guard_accepts_restricted_database_role(monkeypatch):
    restricted = DatabaseRoleSecurity(
        role_name="rotas_app",
        is_superuser=False,
        bypasses_rls=False,
    )
    monkeypatch.setattr(
        database,
        "inspect_application_database_role",
        AsyncMock(return_value=restricted),
    )

    result = await database.validate_application_database_role(require_restricted=True)
    assert result == restricted


@pytest.mark.asyncio
async def test_rotas_app_cannot_mutate_control_plane_tables():
    async with AdminSessionLocal() as db:
        tenant_select = await db.scalar(
            text("SELECT has_table_privilege('rotas_app', 'tenants', 'SELECT')")
        )
        tenant_insert = await db.scalar(
            text("SELECT has_table_privilege('rotas_app', 'tenants', 'INSERT')")
        )
        platform_read = await db.scalar(
            text("SELECT has_table_privilege('rotas_app', 'platform_users', 'SELECT')")
        )

    assert tenant_select is True
    assert tenant_insert is False
    assert platform_read is False


@pytest.mark.asyncio
async def test_database_roles_have_expected_security_attributes():
    async with AdminSessionLocal() as db:
        roles = {
            row.rolname: row
            for row in (
                await db.execute(
                    text(
                        "SELECT rolname, rolsuper, rolbypassrls, rolcanlogin "
                        "FROM pg_roles WHERE rolname IN ('rotas_app', 'rotas_admin')"
                    )
                )
            )
        }

    assert set(roles) == {"rotas_app", "rotas_admin"}
    assert roles["rotas_app"].rolsuper is False
    assert roles["rotas_app"].rolbypassrls is False
    assert roles["rotas_app"].rolcanlogin is True
    assert roles["rotas_admin"].rolsuper is False
    assert roles["rotas_admin"].rolbypassrls is True
    assert roles["rotas_admin"].rolcanlogin is True


@pytest.mark.asyncio
async def test_rotas_app_has_crud_on_every_tenant_table_but_cannot_create_objects():
    async with AdminSessionLocal() as db:
        missing_grants = (
            await db.execute(
                text(
                    """
                    SELECT relation.relname AS table_name, privilege.privilege
                    FROM pg_class AS relation
                    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                    CROSS JOIN (
                        VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
                    ) AS privilege(privilege)
                    WHERE namespace.nspname = 'public'
                      AND relation.relkind IN ('r', 'p')
                      AND NOT relation.relispartition
                      AND EXISTS (
                          SELECT 1
                          FROM pg_attribute AS attribute
                          WHERE attribute.attrelid = relation.oid
                            AND attribute.attname = 'tenant_id'
                            AND NOT attribute.attisdropped
                      )
                      AND NOT has_table_privilege(
                          'rotas_app',
                          format('%I.%I', namespace.nspname, relation.relname),
                          privilege.privilege
                      )
                    ORDER BY relation.relname, privilege.privilege
                    """
                )
            )
        ).all()
        schema_usage = await db.scalar(
            text("SELECT has_schema_privilege('rotas_app', 'public', 'USAGE')")
        )
        schema_create = await db.scalar(
            text("SELECT has_schema_privilege('rotas_app', 'public', 'CREATE')")
        )

    assert missing_grants == []
    assert schema_usage is True
    assert schema_create is False


@pytest.mark.asyncio
async def test_rotas_admin_worker_role_can_operate_across_all_application_tables():
    async with AdminSessionLocal() as db:
        missing_grants = (
            await db.execute(
                text(
                    """
                    SELECT relation.relname AS table_name, privilege.privilege
                    FROM pg_class AS relation
                    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                    CROSS JOIN (
                        VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
                    ) AS privilege(privilege)
                    WHERE namespace.nspname = 'public'
                      AND relation.relkind IN ('r', 'p')
                      AND NOT relation.relispartition
                      AND relation.relname <> 'alembic_version'
                      AND NOT has_table_privilege(
                          'rotas_admin',
                          format('%I.%I', namespace.nspname, relation.relname),
                          privilege.privilege
                      )
                    ORDER BY relation.relname, privilege.privilege
                    """
                )
            )
        ).all()

    assert missing_grants == []
