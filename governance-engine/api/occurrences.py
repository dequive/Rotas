from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import Principal
from core.deps import get_session, require_scope
from core.models import EntityCatalog, EntityInstance, Occurrence, OccurrenceLink
from core.schemas import OccurrenceCreate, OccurrenceReverseRequest
from core.services.occurrences import LinkInput, OccurrenceService

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


async def _load_links(db: AsyncSession, occurrence_id: UUID) -> list[dict]:
    """Single JOIN query — eliminates N+1 on occurrence detail."""
    rows = await db.execute(
        select(OccurrenceLink, EntityInstance, EntityCatalog)
        .outerjoin(EntityInstance, EntityInstance.id == OccurrenceLink.instance_id)
        .outerjoin(EntityCatalog, EntityCatalog.id == EntityInstance.catalog_id)
        .where(OccurrenceLink.occurrence_id == occurrence_id)
    )
    result = []
    for lnk, inst, cat in rows:
        result.append(
            {
                "instance_id": lnk.instance_id,
                "entity_type": cat.entity_type if cat else "",
                "external_id": inst.external_id if inst else "",
                "role": lnk.role,
                "display_name": inst.display_name if inst else "",
                "snapshot": lnk.snapshot,
            }
        )
    return result


def _serialize(
    occ: Occurrence,
    links: list[dict],
    case_id: UUID | None = None,
    case_reference: str | None = None,
) -> dict:
    return {
        "id": occ.id,
        "numero": occ.numero,
        "type_id": occ.type_id,
        "severity": occ.severity,
        "title": occ.title,
        "description": occ.description,
        "occurred_at": occ.occurred_at,
        "recorded_at": occ.recorded_at,
        "supersedes_id": occ.supersedes_id,
        "links": links,
        "case_id": case_id,
        "case_reference": case_reference,
    }


@router.post("/", status_code=201)
async def create_occurrence(
    body: OccurrenceCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: Principal = Depends(require_scope("occurrences:write")),
    db: AsyncSession = Depends(get_session),
):
    svc = OccurrenceService(db, UUID(principal.tenant_id), UUID(principal.actor_id))
    result = await svc.create(
        type_code=body.type_code,
        severity=body.severity,
        title=body.title,
        description=body.description,
        occurred_at=body.occurred_at,
        links=[
            LinkInput(
                entity_type=lnk.entity_type,
                external_id=lnk.external_id,
                role=lnk.role,
                display_name=lnk.display_name,
                snapshot=lnk.snapshot,
            )
            for lnk in body.links
        ],
        location_text=body.location_text,
        latitude=body.latitude,
        longitude=body.longitude,
        supersedes_id=body.supersedes_id,
        idempotency_key=idempotency_key,
        payload=body.payload,
    )
    await db.commit()
    return {
        "occurrence_id": result.occurrence_id,
        "numero": result.numero,
        "case_id": result.case_id,
        "case_reference": result.case_reference,
    }


@router.get("/{occurrence_id}")
async def get_occurrence(
    occurrence_id: UUID,
    _principal: Principal = Depends(require_scope("occurrences:read")),
    db: AsyncSession = Depends(get_session),
):
    occ = await db.scalar(select(Occurrence).where(Occurrence.id == occurrence_id))
    if occ is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Occurrence not found."}
        )
    links = await _load_links(db, occurrence_id)
    return _serialize(occ, links)


@router.get("/")
async def list_occurrences(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    severity: str | None = Query(None),
    type_code: str | None = Query(None, alias="type"),
    _principal: Principal = Depends(require_scope("occurrences:read")),
    db: AsyncSession = Depends(get_session),
):
    base = select(Occurrence)
    if severity:
        base = base.where(Occurrence.severity == severity)

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    rows = await db.execute(
        base.order_by(Occurrence.recorded_at.desc()).limit(limit).offset(offset)
    )
    items = [
        {
            "id": o.id,
            "numero": o.numero,
            "severity": o.severity,
            "title": o.title,
            "occurred_at": o.occurred_at,
            "recorded_at": o.recorded_at,
        }
        for o in rows.scalars()
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/{occurrence_id}/reverse", status_code=201)
async def reverse_occurrence(
    occurrence_id: UUID,
    body: OccurrenceReverseRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: Principal = Depends(require_scope("occurrences:write")),
    db: AsyncSession = Depends(get_session),
):
    svc = OccurrenceService(db, UUID(principal.tenant_id), UUID(principal.actor_id))
    result = await svc.reverse(
        original_id=occurrence_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
    )
    await db.commit()
    return {
        "occurrence_id": result.occurrence_id,
        "numero": result.numero,
        "case_id": result.case_id,
        "case_reference": result.case_reference,
    }
