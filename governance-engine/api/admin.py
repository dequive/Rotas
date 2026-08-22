"""
Admin API — taxonomy CRUD + API key management.
All mutations use request bodies (never query params) to avoid leaking
sensitive data into access logs, proxies, and referrer headers.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.admin_schemas import (
    CreateApiKeyRequest,
    CreateCaseTypeRequest,
    CreateDomainRequest,
    CreatePromotionRequest,
    CreateTenantRequest,
    CreateTransitionRuleRequest,
    CreateTypeRequest,
)
from core.auth import Principal, generate_api_key
from core.deps import get_session, require_scope
from core.models import (
    CaseTransitionRule,
    TaxonomyCaseType,
    TaxonomyDomain,
    TaxonomyType,
    TaxonomyTypePromotion,
)
from core.models_auth import ApiKey, Tenant

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Tenants ───────────────────────────────────────────────────────────────────


@router.post("/tenants", status_code=201)
async def create_tenant(
    body: CreateTenantRequest,
    _principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    existing = await db.scalar(select(Tenant).where(Tenant.slug == body.slug))
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": f"Slug '{body.slug}' already exists."},
        )
    tenant = Tenant(name=body.name, slug=body.slug)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return {"id": tenant.id, "name": tenant.name, "slug": tenant.slug}


# ── API Keys ──────────────────────────────────────────────────────────────────


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)

    full_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        tenant_id=UUID(principal.tenant_id),
        label=body.label,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return {
        "id": api_key.id,
        "label": api_key.label,
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "expires_at": api_key.expires_at,
        "full_key": full_key,  # returned ONCE — never retrievable again
    }


@router.get("/api-keys")
async def list_api_keys(
    principal: Principal = Depends(require_scope("admin:read")),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.tenant_id == UUID(principal.tenant_id),
            ApiKey.is_active.is_(True),
        )
    )
    return [
        {
            "id": k.id,
            "label": k.label,
            "key_prefix": k.key_prefix,
            "scopes": k.scopes,
            "expires_at": k.expires_at,
            "last_used_at": k.last_used_at,
        }
        for k in result.scalars()
    ]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    api_key = await db.get(ApiKey, key_id)
    if api_key and api_key.tenant_id == UUID(principal.tenant_id):
        api_key.is_active = False
        await db.commit()


# ── Taxonomy Domains ──────────────────────────────────────────────────────────


@router.post("/taxonomy/domains", status_code=201)
async def create_domain(
    body: CreateDomainRequest,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    domain = TaxonomyDomain(
        tenant_id=UUID(principal.tenant_id),
        code=body.code,
        name=body.name,
        description=body.description,
    )
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return {"id": domain.id, "code": domain.code, "name": domain.name}


@router.get("/taxonomy/domains")
async def list_domains(
    _principal: Principal = Depends(require_scope("admin:read")),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(TaxonomyDomain))
    return [
        {"id": d.id, "code": d.code, "name": d.name, "is_active": d.is_active}
        for d in result.scalars()
    ]


# ── Taxonomy Case Types ───────────────────────────────────────────────────────


@router.post("/taxonomy/case-types", status_code=201)
async def create_case_type(
    body: CreateCaseTypeRequest,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    ct = TaxonomyCaseType(
        tenant_id=UUID(principal.tenant_id),
        domain_id=body.domain_id,
        code=body.code,
        name=body.name,
        initial_status=body.initial_status,
        sla_hours=body.sla_hours,
    )
    db.add(ct)
    await db.commit()
    await db.refresh(ct)
    return {"id": ct.id, "code": ct.code, "name": ct.name, "initial_status": ct.initial_status}


# ── Taxonomy Types ────────────────────────────────────────────────────────────


@router.post("/taxonomy/types", status_code=201)
async def create_type(
    body: CreateTypeRequest,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    t = TaxonomyType(
        tenant_id=UUID(principal.tenant_id),
        domain_id=body.domain_id,
        code=body.code,
        name=body.name,
        description=body.description,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": t.id, "code": t.code, "name": t.name}


@router.get("/taxonomy/types")
async def list_types(
    _principal: Principal = Depends(require_scope("admin:read")),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(TaxonomyType))
    return [
        {"id": t.id, "code": t.code, "name": t.name, "is_active": t.is_active}
        for t in result.scalars()
    ]


# ── Promotion Rules ───────────────────────────────────────────────────────────


@router.post("/taxonomy/promotions", status_code=201)
async def create_promotion(
    body: CreatePromotionRequest,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    p = TaxonomyTypePromotion(
        tenant_id=UUID(principal.tenant_id),
        type_id=body.type_id,
        case_type_id=body.case_type_id,
        min_severity=body.min_severity,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {
        "id": p.id,
        "type_id": p.type_id,
        "case_type_id": p.case_type_id,
        "min_severity": p.min_severity,
    }


# ── Transition Rules ──────────────────────────────────────────────────────────


@router.post("/taxonomy/transition-rules", status_code=201)
async def create_transition_rule(
    body: CreateTransitionRuleRequest,
    principal: Principal = Depends(require_scope("admin:write")),
    db: AsyncSession = Depends(get_session),
):
    rule = CaseTransitionRule(
        tenant_id=UUID(principal.tenant_id),
        case_type_id=body.case_type_id,
        from_status=body.from_status,
        to_status=body.to_status,
        required_fields=body.required_fields,
        required_attachments=body.required_attachments,
        sla_hours=body.sla_hours,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {
        "id": rule.id,
        "case_type_id": rule.case_type_id,
        "from_status": rule.from_status,
        "to_status": rule.to_status,
        "required_fields": rule.required_fields,
        "required_attachments": rule.required_attachments,
        "sla_hours": rule.sla_hours,
    }


@router.get("/taxonomy/transition-rules")
async def list_transition_rules(
    case_type_id: UUID | None = None,
    _principal: Principal = Depends(require_scope("admin:read")),
    db: AsyncSession = Depends(get_session),
):
    q = select(CaseTransitionRule)
    if case_type_id:
        q = q.where(CaseTransitionRule.case_type_id == case_type_id)
    result = await db.execute(q)
    return [
        {
            "id": r.id,
            "case_type_id": r.case_type_id,
            "from_status": r.from_status,
            "to_status": r.to_status,
            "required_fields": r.required_fields,
            "required_attachments": r.required_attachments,
            "sla_hours": r.sla_hours,
        }
        for r in result.scalars()
    ]
