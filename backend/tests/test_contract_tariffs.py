import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contracts.models import Contract, ContractTariff
from app.modules.trips.models import KnownRoute


@pytest.fixture
async def sample_contract(db, tenant_id):
    contract = Contract(
        tenant_id=tenant_id,
        client_name="Test Client Lda",
        contract_reference=f"CTR-TARIFF-{uuid.uuid4().hex[:6]}",
        status="active",
        billing_basis="trip",
        default_unit_price=Decimal("1500.00"),
    )
    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    return contract


@pytest.fixture
async def sample_route(db, tenant_id):
    route = KnownRoute(
        tenant_id=tenant_id,
        origin="Maputo",
        destination="Matola",
        distance_km=Decimal("20.5"),
        avg_fuel_liters=Decimal("5.0"),
        is_active=True,
    )
    db.add(route)
    await db.commit()
    await db.refresh(route)
    return route


@pytest.mark.asyncio
async def test_contract_tariff_crud(async_client, auth_headers, sample_contract, sample_route):
    # 1. Create a tariff
    payload = {
        "known_route_id": str(sample_route.id),
        "rate_basis": "km",
        "unit_price": "75.50",
        "currency": "MZN",
    }
    response = await async_client.post(
        f"/api/v1/contracts/{sample_contract.id}/tariffs",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["rate_basis"] == "km"
    assert Decimal(data["unit_price"]) == Decimal("75.50")
    tariff_id = data["id"]

    # 2. List tariffs
    response = await async_client.get(
        f"/api/v1/contracts/{sample_contract.id}/tariffs",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    tariffs = response.json()
    assert len(tariffs) >= 1
    assert any(t["id"] == tariff_id for t in tariffs)

    # 3. Patch tariff
    response = await async_client.patch(
        f"/api/v1/contracts/{sample_contract.id}/tariffs/{tariff_id}",
        json={"unit_price": "80.00"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert Decimal(response.json()["unit_price"]) == Decimal("80.00")

    # 4. Delete tariff
    response = await async_client.delete(
        f"/api/v1/contracts/{sample_contract.id}/tariffs/{tariff_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    # Verify deleted
    response = await async_client.get(
        f"/api/v1/contracts/{sample_contract.id}/tariffs",
        headers=auth_headers,
    )
    tariffs = response.json()
    assert not any(t["id"] == tariff_id for t in tariffs)


@pytest.mark.asyncio
async def test_contract_tariff_rbac_write_denied(async_client, viewer_headers, sample_contract, sample_route):
    # viewer only has BILLING_READ, not BILLING_WRITE
    payload = {
        "known_route_id": str(sample_route.id),
        "rate_basis": "trip",
        "unit_price": "1000.00",
        "currency": "MZN",
    }
    response = await async_client.post(
        f"/api/v1/contracts/{sample_contract.id}/tariffs",
        json=payload,
        headers=viewer_headers,
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_contract_tariff_multi_tenant_isolation(async_client, auth_headers, sample_contract, sample_route, db):
    # Create another tenant and its auth headers
    from app.modules.tenants.models import Tenant
    from app.modules.users.models import User
    import jwt
    from app.config import get_settings

    settings = get_settings()
    other_tenant = Tenant(name="Tenant B", slug=f"tenant-b-{uuid.uuid4().hex[:6]}")
    db.add(other_tenant)
    await db.commit()
    await db.refresh(other_tenant)

    other_user = User(
        tenant_id=other_tenant.id,
        email=f"owner-{uuid.uuid4().hex[:6]}@tenant-b.local",
        password_hash="$argon2id$test",
        full_name="Owner B",
        role="owner",  # owner role has BILLING_WRITE
        is_active=True,
    )
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    token = jwt.encode(
        {
            "typ": "access",
            "sub": f"user:{other_user.id}",
            "role": "owner",
            "scope": "dashboard",
            "tenant_id": str(other_tenant.id),
            "user_id": str(other_user.id),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    other_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": str(other_tenant.id),
    }

    # Tenant B tries to create a tariff in Tenant A's contract
    payload = {
        "known_route_id": str(sample_route.id),
        "rate_basis": "trip",
        "unit_price": "1000.00",
    }
    response = await async_client.post(
        f"/api/v1/contracts/{sample_contract.id}/tariffs",
        json=payload,
        headers=other_headers,
    )
    # Since tenant isolation / RLS prevents reading/matching other tenant's contract, it should return 404
    assert response.status_code == 404, response.text
