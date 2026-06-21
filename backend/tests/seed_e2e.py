"""
E2E seed script — creates test tenant and owner user for Playwright tests.

Run with:
    python -m pytest tests/seed_e2e.py -v

Or directly:
    python tests/seed_e2e.py

The script is IDEMPOTENT — safe to run multiple times. If the tenant or user
already exists it will skip creation (or refresh the password hash) and succeed.

Credentials created:
    Email:    e2e@rotas.local
    Password: E2eP@ss2024!
    Role:     owner
    Tenant:   E2E Test (slug: e2e-test)
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.passwords import hash_password
from app.database import engine
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

E2E_EMAIL = os.getenv("E2E_EMAIL", "e2e@rotas.local")
E2E_PASSWORD = os.getenv("E2E_PASSWORD", "E2eP@ss2024!")
E2E_TENANT_SLUG = "e2e-test"
E2E_TENANT_NAME = "E2E Test"


async def _seed() -> None:
    async with AsyncSession(engine) as db:
        # --- Tenant ---
        result = await db.execute(select(Tenant).where(Tenant.slug == E2E_TENANT_SLUG))
        tenant = result.scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(
                id=uuid.uuid4(),
                name=E2E_TENANT_NAME,
                slug=E2E_TENANT_SLUG,
                plan="basic",
                is_active=True,
                is_trial=False,
                max_vehicles=50,
                max_drivers=50,
                max_users=20,
            )
            db.add(tenant)
            await db.flush()
            print(f"[seed_e2e] Created tenant: {tenant.name} ({tenant.id})")
        else:
            print(f"[seed_e2e] Tenant already exists: {tenant.name} ({tenant.id})")

        # --- User ---
        result = await db.execute(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == E2E_EMAIL,
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                email=E2E_EMAIL,
                password_hash=hash_password(E2E_PASSWORD),
                full_name="E2E Test User",
                role="owner",
                is_active=True,
                mfa_enabled=False,  # must be False — MFA challenge would break auth.setup.ts
            )
            db.add(user)
            await db.flush()
            print(f"[seed_e2e] Created user: {user.email} (role=owner, mfa_enabled=False)")
        else:
            # Ensure password is correct and MFA is disabled even if user exists
            user.password_hash = hash_password(E2E_PASSWORD)
            user.is_active = True
            user.mfa_enabled = False  # keep MFA disabled on repeat runs
            print("[seed_e2e] User already exists — refreshed password hash, mfa_enabled=False")

        await db.commit()
        print(f"[seed_e2e] Seed complete. Email={E2E_EMAIL} Password={E2E_PASSWORD}")


@pytest.mark.asyncio
async def test_seed_e2e_user() -> None:
    """Idempotent seed — run as a pytest test so CI can invoke with pytest."""
    await _seed()

    # Verify the user exists and can be found
    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(User)
            .join(Tenant, User.tenant_id == Tenant.id)
            .where(
                User.email == E2E_EMAIL,
                Tenant.slug == E2E_TENANT_SLUG,
            )
        )
        user = result.scalar_one_or_none()
        assert user is not None, f"E2E user {E2E_EMAIL} was not created"
        assert user.role == "owner", f"Expected role='owner', got '{user.role}'"
        assert user.is_active is True, "E2E user must be active"
        assert user.mfa_enabled is False, "E2E user must have MFA disabled"


if __name__ == "__main__":
    asyncio.run(_seed())
