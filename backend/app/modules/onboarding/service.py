import re
import unicodedata
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.core.modules import MODULE_TMS
from app.core.passwords import hash_password
from app.core.tokens import create_opaque_token, hash_token
from app.modules.accounting.seed import seed_pgc_nirf
from app.modules.audit.service import record_audit_log
from app.modules.auth.models import EmailVerificationToken
from app.modules.auth.service import create_dashboard_tokens
from app.modules.notifications.schemas import EmailNotificationCreate
from app.modules.notifications.service import enqueue_email
from app.modules.onboarding.schemas import EmailVerificationRequest, OnboardingRegisterRequest
from app.modules.tenants.models import Tenant, TenantDocumentProfile
from app.modules.users.models import User

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_RE.sub("-", ascii_value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80] or "tenant"


async def _ensure_available(db: AsyncSession, *, slug: str, email: str) -> None:
    existing_tenant = await db.scalar(select(Tenant.id).where(Tenant.slug == slug))
    if existing_tenant:
        raise ApiError(
            "tenant_slug_conflict",
            "Company slug is already in use.",
            status_code=status.HTTP_409_CONFLICT,
            details={"slug": slug},
        )
    existing_user = await db.scalar(select(User.id).where(User.email == email))
    if existing_user:
        raise ApiError(
            "owner_email_conflict",
            "Owner email is already registered.",
            status_code=status.HTTP_409_CONFLICT,
            details={"email": email},
        )


def _tenant_payload(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "product_modules": tenant.product_modules or ["tms"],
        "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
    }


def _owner_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "email_verified_at": (
            user.email_verified_at.isoformat() if user.email_verified_at else None
        ),
    }


async def _enqueue_email_verification(
    db: AsyncSession,
    *,
    user: User,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    active_tokens = await db.scalars(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
    )
    for token in active_tokens:
        token.consumed_at = now

    token_value = create_opaque_token()
    token = EmailVerificationToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=hash_token(token_value),
        expires_at=now + timedelta(hours=24),
        created_by_ip=ip_address,
        user_agent=user_agent,
    )
    db.add(token)
    await db.flush()

    manager_url = get_settings().manager_public_url.rstrip("/")
    verify_url = f"{manager_url}/verify-email?token={token_value}"
    await enqueue_email(
        db,
        user.tenant_id,
        EmailNotificationCreate(
            request_reference=f"email_verify:{token.id}",
            recipient=user.email,
            subject="Confirme o seu email no ROTAS",
            body_text=(
                "Bem-vindo ao ROTAS.\n\n"
                f"Confirme o seu email nas proximas 24 horas: {verify_url}\n\n"
                "Se nao criou esta conta, ignore esta mensagem."
            ),
            body_html=(
                "<p>Bem-vindo ao ROTAS.</p>"
                f'<p><a href="{verify_url}">Confirmar email</a></p>'
                "<p>Este link expira em 24 horas. "
                "Se nao criou esta conta, ignore esta mensagem.</p>"
            ),
            template="email_verification",
            payload={"user_id": str(user.id), "verification_token_id": str(token.id)},
        ),
        actor_id=user.id,
    )
    return token_value, verify_url


async def register_tenant(
    db: AsyncSession,
    payload: OnboardingRegisterRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    slug = _slugify(payload.company_slug or payload.company_name)
    email = payload.owner_email.strip().lower()
    await _ensure_available(db, slug=slug, email=email)

    trial_ends_at = datetime.now(UTC) + timedelta(days=14)
    tenant = Tenant(
        name=payload.company_name.strip(),
        slug=slug,
        plan="trial",
        # Public onboarding receives only the baseline entitlement. Commercial
        # modules are granted later by an authenticated platform administrator.
        product_modules=[MODULE_TMS],
        is_trial=True,
        trial_ends_at=trial_ends_at,
        whatsapp_number=payload.phone,
        timezone=payload.timezone,
        currency=payload.currency,
        compliance_policy={
            "company_profile": {
                "nuit": payload.company_nuit,
                "phone": payload.phone,
                "self_service_onboarded_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    db.add(tenant)
    await db.flush()

    owner = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(payload.owner_password),
        full_name=payload.owner_full_name.strip(),
        phone=payload.phone,
        role="owner",
    )
    db.add(owner)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            "onboarding_conflict",
            "Company slug or owner email is already registered.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    await record_audit_log(
        db,
        tenant_id=tenant.id,
        user_id=owner.id,
        action="tenant.self_registered",
        entity_type="tenant",
        entity_id=tenant.id,
        new_values=_tenant_payload(tenant),
    )
    await record_audit_log(
        db,
        tenant_id=tenant.id,
        user_id=owner.id,
        action="user.owner_created",
        entity_type="user",
        entity_id=owner.id,
        new_values=_owner_payload(owner),
    )
    verification_token, verification_url = await _enqueue_email_verification(
        db,
        user=owner,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    tokens = await create_dashboard_tokens(
        db,
        owner,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Hooks de Provisionamento Automático
    await seed_pgc_nirf(db, tenant.id)

    # Criar perfil de PDFs por omissão
    doc_profile = TenantDocumentProfile(
        tenant_id=tenant.id,
        legal_name=payload.company_name.strip(),
        country="Moçambique",
    )
    db.add(doc_profile)

    await db.commit()
    await db.refresh(tenant)
    await db.refresh(owner)
    response = {
        "tenant": _tenant_payload(tenant),
        "owner": _owner_payload(owner),
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": tokens["token_type"],
        "expires_in": tokens["expires_in"],
    }
    if get_settings().environment != "production":
        response["verification_token"] = verification_token
        response["verification_url"] = verification_url
    return response


async def verify_email(db: AsyncSession, payload: EmailVerificationRequest) -> dict:
    now = datetime.now(UTC)
    token = await db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(payload.token),
            EmailVerificationToken.consumed_at.is_(None),
        )
    )
    if not token or token.expires_at <= now:
        raise ApiError(
            "invalid_verification_token",
            "Verification token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = await db.get(User, token.user_id)
    tenant = await db.get(Tenant, token.tenant_id)
    if not user or not tenant or not user.is_active or not tenant.is_active:
        raise ApiError(
            "invalid_verification_token",
            "Verification token is invalid or expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token.consumed_at = now
    if not user.email_verified_at:
        user.email_verified_at = now
    await record_audit_log(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="user.email_verified",
        entity_type="user",
        entity_id=user.id,
        new_values={"email": user.email, "email_verified_at": user.email_verified_at},
    )
    await db.commit()
    return {"ok": True, "email_verified_at": user.email_verified_at.isoformat()}
