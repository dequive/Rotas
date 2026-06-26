from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.checklists import schemas, service
from app.modules.checklists.exporters import render_checklist_report
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.drivers.models import Driver
from app.modules.tenants.models import TenantDocumentProfile
from app.modules.vehicles.models import Vehicle

router = APIRouter(tags=["checklists"])


@router.get("/checklist-templates")
async def list_templates(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    type: str | None = None,
    is_active: bool | None = True,
):
    return await service.list_templates(
        db,
        principal.tenant_id,
        type_filter=type,
        is_active=is_active,
    )


@router.post("/checklist-templates")
async def create_template(
    payload: schemas.ChecklistTemplateCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="checklists.template.create",
        entity_type="checklist_template",
        payload=payload,
        handler=lambda: service.create_template(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/checklists")
async def list_checklists(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_checklists(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        limit=limit,
        offset=offset,
    )


@router.post("/checklists")
async def create_checklist(
    payload: schemas.ChecklistCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        driver_id=principal.driver_id,
        device_id=principal.device_id,
        idempotency_key=idempotency_key,
        operation="checklists.create",
        entity_type="checklist",
        payload=payload,
        handler=lambda: service.create_checklist(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
            driver_actor_id=principal.driver_id,
        ),
    )


@router.patch("/checklists/{checklist_id}")
async def patch_checklist(
    checklist_id: UUID,
    payload: schemas.ChecklistPatch,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_checklist(
        db,
        principal.tenant_id,
        checklist_id,
        payload,
        actor_id=principal.user_id,
        driver_actor_id=principal.driver_id,
    )


@router.post("/checklists/{checklist_id}/complete")
async def complete_checklist(
    checklist_id: UUID,
    payload: schemas.CompleteChecklistRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.complete_checklist(
        db,
        principal.tenant_id,
        checklist_id,
        payload,
        actor_id=principal.user_id,
        driver_actor_id=principal.driver_id,
    )


@router.post("/checklists/{checklist_id}/resolve-failure")
async def resolve_checklist_failure(
    checklist_id: UUID,
    payload: schemas.ResolveChecklistFailureRequest,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.resolve_checklist_failure(
        db,
        principal.tenant_id,
        checklist_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/checklists/{checklist_id}/pdf")
async def download_checklist_pdf(
    checklist_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    chk_row = await db.execute(
        select(Checklist).where(
            Checklist.id == checklist_id, Checklist.tenant_id == principal.tenant_id
        )
    )
    checklist = chk_row.scalar_one_or_none()
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist not found")

    template = None
    if checklist.template_id:
        t_row = await db.execute(
            select(ChecklistTemplate).where(ChecklistTemplate.id == checklist.template_id)
        )
        template = t_row.scalar_one_or_none()

    vehicle = None
    if checklist.vehicle_id:
        v_row = await db.execute(select(Vehicle).where(Vehicle.id == checklist.vehicle_id))
        vehicle = v_row.scalar_one_or_none()

    driver = None
    if checklist.driver_id:
        d_row = await db.execute(select(Driver).where(Driver.id == checklist.driver_id))
        driver = d_row.scalar_one_or_none()

    prof_row = await db.execute(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == principal.tenant_id)
    )
    prof_obj = prof_row.scalar_one_or_none()
    profile = (
        {
            "legal_name": prof_obj.legal_name,
            "address_line1": prof_obj.address_line1,
            "address_line2": prof_obj.address_line2,
            "city": prof_obj.city,
            "phone": prof_obj.phone,
            "email": prof_obj.email,
        }
        if prof_obj
        else None
    )

    vehicle_dict = (
        {"plate": vehicle.plate, "brand": vehicle.brand, "model": vehicle.model}
        if vehicle
        else None
    )
    driver_dict = (
        {"full_name": driver.full_name, "license_number": driver.license_number} if driver else None
    )

    pdf_bytes = render_checklist_report(
        checklist,
        template=template,
        vehicle=vehicle_dict,
        driver=driver_dict,
        profile=profile,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=inspecao-viatura-{checklist_id}.pdf"
        },
    )
