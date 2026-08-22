from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.passwords import hash_password
from app.database import AsyncSessionLocal, import_all_models
from app.modules.checklists.models import ChecklistTemplate
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

TENANT_SLUG = "rotas-piloto-maputo"
CONTRACT_REFERENCE = "CTR-PILOTO-001"
VEHICLE_PLATE = "MPT-00-RT"
DRIVER_PHONE = "258840000001"
CHECKLIST_TEMPLATE_NAME = "Pre-partida pesado piloto"


def serialize_id(value: Any) -> str:
    return str(value)


async def seed() -> dict[str, Any]:
    import_all_models()

    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        if tenant is None:
            tenant = Tenant(
                name="ROTAS Piloto Maputo",
                slug=TENANT_SLUG,
                plan="trial",
                max_vehicles=10,
                max_drivers=15,
                max_users=5,
                is_active=True,
                is_trial=True,
                trial_ends_at=datetime.now(UTC) + timedelta(days=30),
                whatsapp_number="258840000000",
                timezone="Africa/Maputo",
                currency="MZN",
            )
            db.add(tenant)
            await db.flush()

        vehicle = await db.scalar(
            select(Vehicle).where(
                Vehicle.tenant_id == tenant.id,
                Vehicle.plate == VEHICLE_PLATE,
            )
        )
        if vehicle is None:
            vehicle = Vehicle(
                tenant_id=tenant.id,
                plate=VEHICLE_PLATE,
                chassis="ROTAS-PILOT-CHASSIS-001",
                brand="Mercedes-Benz",
                model="Actros",
                year=2019,
                color="Branco",
                category="pesado",
                status="active",
                current_km=125000,
                fuel_type="gasoleo",
                documents={
                    "insurance": {"number": "SEG-PILOTO-001", "valid_until": "2026-12-31"},
                    "inatter": {"number": "INA-PILOTO-001", "valid_until": "2026-11-30"},
                    "dua": {"number": "DUA-PILOTO-001", "valid_until": None},
                },
                avg_consumption_target=Decimal("32.50"),
                fuel_limit_daily=Decimal("350.00"),
            )
            db.add(vehicle)
            await db.flush()

        driver = await db.scalar(
            select(Driver).where(
                Driver.tenant_id == tenant.id,
                Driver.phone == DRIVER_PHONE,
            )
        )
        if driver is None:
            driver = Driver(
                tenant_id=tenant.id,
                full_name="Joao Manuel",
                phone=DRIVER_PHONE,
                email="joao.manuel@rotas.local",
                emergency_contact_name="Maria Manuel",
                emergency_contact_phone="258840000002",
                license_number="C-PILOTO-001",
                license_category="C",
                license_valid_until=date(2027, 5, 31),
                employment_type="efectivo",
                status="active",
                score=100,
            )
            db.add(driver)
            await db.flush()

        contract = await db.scalar(
            select(Contract).where(
                Contract.tenant_id == tenant.id,
                Contract.contract_reference == CONTRACT_REFERENCE,
            )
        )
        if contract is None:
            contract = Contract(
                tenant_id=tenant.id,
                client_name="Cliente Industrial Piloto",
                contract_reference=CONTRACT_REFERENCE,
                title="Transporte mensal de carga Maputo-Beira",
                status="active",
                service_type="cargo_transport",
                billing_cycle="monthly",
                billing_basis="trip",
                currency="MZN",
                default_unit_price=Decimal("12500.00"),
                requires_load_permit=True,
                requires_delivery_proof=True,
                requires_cargo_manifest_for_manufactured_goods=True,
                pricing_rules={
                    "route": "Maputo-Beira",
                    "loaded_empty": 12500,
                    "loaded_loaded": 18000,
                    "billing_month_basis": "delivery_proof.delivered_at",
                },
                starts_at=datetime(2026, 6, 1, tzinfo=UTC),
                notes=(
                    "Contrato piloto: Load Permit emitido pelo cliente; guia de descarga "
                    "validada manualmente antes da cobranca mensal."
                ),
            )
            db.add(contract)
            await db.flush()

        user = await db.scalar(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == "admin@rotas.local",
            )
        )
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email="admin@rotas.local",
                password_hash=hash_password("rotas2026"),
                full_name="Administrador ROTAS",
                role="admin",
                is_active=True,
            )
            db.add(user)
            await db.flush()

        checklist_template = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.tenant_id == tenant.id,
                ChecklistTemplate.name == CHECKLIST_TEMPLATE_NAME,
                ChecklistTemplate.type == "pre_partida",
            )
        )
        if checklist_template is None:
            checklist_template = ChecklistTemplate(
                tenant_id=tenant.id,
                name=CHECKLIST_TEMPLATE_NAME,
                type="pre_partida",
                category="pesado",
                is_active=True,
                items=[
                    {
                        "id": "oil_level",
                        "label": "Nivel de oleo",
                        "type": "boolean",
                        "is_blocking": True,
                        "requires_photo": False,
                        "category": "mecanico",
                    },
                    {
                        "id": "tires",
                        "label": "Estado dos pneus",
                        "type": "boolean",
                        "is_blocking": True,
                        "requires_photo": True,
                        "category": "seguranca",
                    },
                    {
                        "id": "load_documents",
                        "label": "Documentos de carga presentes",
                        "type": "boolean",
                        "is_blocking": True,
                        "requires_photo": True,
                        "category": "documental",
                    },
                ],
            )
            db.add(checklist_template)
            await db.flush()

        await db.commit()

        return {
            "tenant": {"id": serialize_id(tenant.id), "slug": tenant.slug},
            "user": {"id": serialize_id(user.id), "email": user.email, "password": "rotas2026"},
            "vehicle": {"id": serialize_id(vehicle.id), "plate": vehicle.plate},
            "driver": {"id": serialize_id(driver.id), "phone": driver.phone},
            "contract": {
                "id": serialize_id(contract.id),
                "reference": contract.contract_reference,
            },
            "checklist_template": {
                "id": serialize_id(checklist_template.id),
                "name": checklist_template.name,
            },
        }


async def main() -> None:
    result = await seed()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
