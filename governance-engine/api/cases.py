from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import Principal
from core.deps import get_session, require_scope
from core.domain.fsm import CaseFSM
from core.models import Case, CaseTransition, TaxonomyCaseType
from core.schemas import CaseCreate, TransitionRequest

router = APIRouter(prefix="/cases", tags=["cases"])


def _serialize_case(case: Case, case_type_code: str) -> dict:
    return {
        "id": case.id,
        "reference": case.reference,
        "case_type_code": case_type_code,
        "status": case.status,
        "assignee_id": case.assignee_id,
        "payload": case.payload,
        "sla_due_at": case.sla_due_at,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


async def _case_type_code(db: AsyncSession, case_type_id: UUID) -> str:
    ct = await db.get(TaxonomyCaseType, case_type_id)
    return ct.code if ct else ""


@router.post("/", status_code=201)
async def create_case(
    body: CaseCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: Principal = Depends(require_scope("cases:write")),
    db: AsyncSession = Depends(get_session),
):
    tenant_id = UUID(principal.tenant_id)
    actor_id = UUID(principal.actor_id)

    case_type = await db.scalar(
        select(TaxonomyCaseType).where(
            TaxonomyCaseType.tenant_id == tenant_id,
            TaxonomyCaseType.code == body.case_type_code,
            TaxonomyCaseType.is_active.is_(True),
        )
    )
    if case_type is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": f"CaseType '{body.case_type_code}' not found."},
        )

    fsm = CaseFSM(db, tenant_id)
    case_id = await fsm.open_case(
        case_type_id=case_type.id,
        initial_status=case_type.initial_status,
        occurrence_ids=body.occurrence_ids,
        payload=body.payload,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )
    await db.commit()

    case = await db.get(Case, case_id)
    return _serialize_case(case, body.case_type_code)


@router.get("/types/")
async def list_active_case_types(
    _principal: Principal = Depends(require_scope("cases:read")),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(TaxonomyCaseType)
        .where(TaxonomyCaseType.is_active.is_(True))
        .order_by(TaxonomyCaseType.name.asc())
    )
    return [
        {
            "id": ct.id,
            "code": ct.code,
            "name": ct.name,
            "initial_status": ct.initial_status,
            "sla_hours": ct.sla_hours,
        }
        for ct in result.scalars()
    ]


@router.get("/{case_id}")
async def get_case(
    case_id: UUID,
    _principal: Principal = Depends(require_scope("cases:read")),
    db: AsyncSession = Depends(get_session),
):
    case = await db.scalar(select(Case).where(Case.id == case_id))
    if case is None:
        raise HTTPException(
            status_code=404, detail={"code": "not_found", "message": "Case not found."}
        )
    code = await _case_type_code(db, case.case_type_id)
    return _serialize_case(case, code)


@router.get("/")
async def list_cases(
    status: str | None = Query(None),
    case_type_code: str | None = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _principal: Principal = Depends(require_scope("cases:read")),
    db: AsyncSession = Depends(get_session),
):
    base = select(Case)
    if status:
        base = base.where(Case.status == status)
    if case_type_code:
        ct = await db.scalar(
            select(TaxonomyCaseType).where(TaxonomyCaseType.code == case_type_code)
        )
        if ct:
            base = base.where(Case.case_type_id == ct.id)

    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = await db.execute(base.order_by(Case.created_at.desc()).limit(limit).offset(offset))

    items = []
    for c in rows.scalars():
        code = await _case_type_code(db, c.case_type_id)
        items.append(_serialize_case(c, code))

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/{case_id}/transitions", status_code=201)
async def apply_transition(
    case_id: UUID,
    body: TransitionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: Principal = Depends(require_scope("cases:write")),
    db: AsyncSession = Depends(get_session),
):
    fsm = CaseFSM(db, UUID(principal.tenant_id))
    transition = await fsm.apply_transition(
        case_id=case_id,
        to_status=body.to_status,
        payload=body.payload,
        attachments_present=body.attachments_present,
        actor_id=UUID(principal.actor_id),
        reason=body.reason,
        idempotency_key=idempotency_key,
    )
    await db.commit()
    return {
        "id": transition.id,
        "case_id": transition.case_id,
        "from_status": transition.from_status,
        "to_status": transition.to_status,
        "actor_id": transition.actor_id,
        "reason": transition.reason,
        "transitioned_at": transition.transitioned_at,
    }


@router.get("/{case_id}/transitions")
async def list_transitions(
    case_id: UUID,
    _principal: Principal = Depends(require_scope("cases:read")),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(CaseTransition)
        .where(CaseTransition.case_id == case_id)
        .order_by(CaseTransition.transitioned_at.asc())
    )
    return [
        {
            "id": t.id,
            "from_status": t.from_status,
            "to_status": t.to_status,
            "actor_id": t.actor_id,
            "reason": t.reason,
            "transitioned_at": t.transitioned_at,
        }
        for t in result.scalars()
    ]


@router.get("/{case_id}/transitions/available")
async def available_transitions(
    case_id: UUID,
    principal: Principal = Depends(require_scope("cases:read")),
    db: AsyncSession = Depends(get_session),
):
    fsm = CaseFSM(db, UUID(principal.tenant_id))
    return await fsm.get_available_transitions(case_id)
