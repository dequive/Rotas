from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token, create_opaque_token, hash_token
from app.core.totp import build_otpauth_uri, generate_totp_secret, verify_totp_code
from app.modules.audit.service import record_audit_log
from app.modules.auth.models import MfaChallenge, PasswordResetToken, RefreshToken
from app.modules.auth.schemas import (
    DriverPairRequest,
    LoginRequest,
    LogoutRequest,
    MfaCodeRequest,
    MfaVerifyRequest,
    PasswordResetCompleteRequest,
    PasswordResetRequest,
    RefreshRequest,
)
from app.modules.drivers.models import Driver, DriverDevice, DriverSession
from app.modules.notifications.schemas import EmailNotificationCreate
from app.modules.notifications.service import enqueue_email
from app.modules.tenants.models import Tenant
from app.modules.users.models import User


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "full_name": user.full_name,
    }


def _driver_payload(driver: Driver) -> dict:
    return {"id": driver.id, "tenant_id": driver.tenant_id, "full_name": driver.full_name}


async def _create_user_tokens(
    db: AsyncSession,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    settings = get_settings()
    refresh_token = create_opaque_token()
    db.add(
        RefreshToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
            created_by_ip=ip_address,
            user_agent=user_agent,
        )
    )
    access_token, expires_in = create_access_token(
        tenant_id=user.tenant_id,
        user_id=user.id,
        scope="dashboard",
        role=user.role,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": _user_payload(user),
    }


async def create_dashboard_tokens(
    db: AsyncSession,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    return await _create_user_tokens(db, user, ip_address=ip_address, user_agent=user_agent)


async def _create_driver_tokens(db: AsyncSession, driver: Driver, device_id: str) -> dict:
    settings = get_settings()
    refresh_token = create_opaque_token()
    db.add(
        DriverSession(
            tenant_id=driver.tenant_id,
            driver_id=driver.id,
            device_id=device_id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    access_token, expires_in = create_access_token(
        tenant_id=driver.tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        scope="driver_app",
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "driver": _driver_payload(driver),
    }


async def login(
    db: AsyncSession,
    payload: LoginRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    query = select(User).join(Tenant).where(
        User.email == payload.email.strip().lower(),
        User.is_active.is_(True),
        Tenant.is_active.is_(True),
    )
    if payload.tenant_slug:
        query = query.where(Tenant.slug == payload.tenant_slug)
    users = list((await db.scalars(query)).all())
    if len(users) != 1 or not verify_password(payload.password, users[0].password_hash):
        raise ApiError("invalid_credentials", "Invalid credentials.", status_code=401)
    user = users[0]
    user.last_login_at = datetime.now(UTC)
    if user.mfa_enabled and user.mfa_secret:
        challenge_token = create_opaque_token()
        db.add(
            MfaChallenge(
                tenant_id=user.tenant_id,
                user_id=user.id,
                token_hash=hash_token(challenge_token),
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                created_by_ip=ip_address,
                user_agent=user_agent,
            )
        )
        await db.commit()
        return {
            "mfa_required": True,
            "mfa_challenge": challenge_token,
            "expires_in": 300,
        }
    response = await _create_user_tokens(db, user, ip_address=ip_address, user_agent=user_agent)
    await db.commit()
    return response


async def refresh(
    db: AsyncSession,
    payload: RefreshRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    token_hash = hash_token(payload.refresh_token)
    user_token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if user_token:
        if user_token.revoked_at or user_token.expires_at <= now:
            raise ApiError("invalid_refresh_token", "Refresh token is invalid.", status_code=401)
        user = await db.get(User, user_token.user_id)
        tenant = await db.get(Tenant, user_token.tenant_id)
        if not user or not tenant or not user.is_active or not tenant.is_active:
            raise ApiError("invalid_refresh_token", "Refresh token is invalid.", status_code=401)
        user_token.revoked_at = now
        response = await _create_user_tokens(db, user, ip_address=ip_address, user_agent=user_agent)
        await db.commit()
        return response
    driver_token = await db.scalar(
        select(DriverSession).where(DriverSession.token_hash == token_hash)
    )
    if driver_token:
        if driver_token.revoked_at or driver_token.expires_at <= now:
            raise ApiError("invalid_refresh_token", "Refresh token is invalid.", status_code=401)
        driver = await db.get(Driver, driver_token.driver_id)
        if not driver or driver.status != "active":
            raise ApiError("invalid_refresh_token", "Refresh token is invalid.", status_code=401)
        driver_token.revoked_at = now
        response = await _create_driver_tokens(db, driver, driver_token.device_id)
        await db.commit()
        return response
    raise ApiError("invalid_refresh_token", "Refresh token is invalid.", status_code=401)


async def verify_mfa_challenge(
    db: AsyncSession,
    payload: MfaVerifyRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    now = datetime.now(UTC)
    challenge = await db.scalar(
        select(MfaChallenge).where(
            MfaChallenge.token_hash == hash_token(payload.challenge_token),
            MfaChallenge.consumed_at.is_(None),
        )
    )
    if not challenge or challenge.expires_at <= now:
        raise ApiError(
            "invalid_mfa_challenge",
            "MFA challenge is invalid or expired.",
            status_code=401,
        )
    user = await db.get(User, challenge.user_id)
    tenant = await db.get(Tenant, challenge.tenant_id)
    if (
        not user
        or not tenant
        or not user.is_active
        or not tenant.is_active
        or not user.mfa_enabled
        or not user.mfa_secret
        or not verify_totp_code(user.mfa_secret, payload.code)
    ):
        raise ApiError("invalid_mfa_code", "MFA code is invalid.", status_code=401)
    challenge.consumed_at = now
    user.last_login_at = now
    response = await _create_user_tokens(db, user, ip_address=ip_address, user_agent=user_agent)
    await db.commit()
    return response


async def logout(db: AsyncSession, payload: LogoutRequest) -> dict:
    if not payload.refresh_token:
        return {"logged_out": True}
    now = datetime.now(UTC)
    token_hash = hash_token(payload.refresh_token)
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if not token:
        token = await db.scalar(select(DriverSession).where(DriverSession.token_hash == token_hash))
    if token and not token.revoked_at:
        token.revoked_at = now
        await db.commit()
    return {"logged_out": True}


async def get_mfa_status(db: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> dict:
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise ApiError("user_not_found", "User not found.", status_code=404)
    return {
        "enabled": bool(user.mfa_enabled),
        "confirmed_at": user.mfa_confirmed_at,
    }


async def setup_mfa(db: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> dict:
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise ApiError("user_not_found", "User not found.", status_code=404)
    if user.mfa_enabled and user.mfa_secret:
        return {
            "enabled": True,
            "confirmed_at": user.mfa_confirmed_at,
            "secret": None,
            "otpauth_uri": None,
        }
    secret = generate_totp_secret()
    user.mfa_secret = secret
    user.mfa_enabled = False
    user.mfa_confirmed_at = None
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="auth.mfa_setup_started",
        entity_type="user",
        entity_id=user_id,
    )
    await db.commit()
    return {
        "enabled": False,
        "confirmed_at": None,
        "secret": secret,
        "otpauth_uri": build_otpauth_uri(secret=secret, account_name=user.email),
    }


async def confirm_mfa(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    payload: MfaCodeRequest,
) -> dict:
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id or not user.mfa_secret:
        raise ApiError("mfa_not_configured", "MFA is not configured.", status_code=400)
    if not verify_totp_code(user.mfa_secret, payload.code):
        raise ApiError("invalid_mfa_code", "MFA code is invalid.", status_code=401)
    user.mfa_enabled = True
    user.mfa_confirmed_at = datetime.now(UTC)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="auth.mfa_enabled",
        entity_type="user",
        entity_id=user_id,
        new_values={"mfa_enabled": True, "mfa_confirmed_at": user.mfa_confirmed_at},
    )
    await db.commit()
    return {"enabled": True, "confirmed_at": user.mfa_confirmed_at}


async def disable_mfa(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    payload: MfaCodeRequest,
) -> dict:
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise ApiError("user_not_found", "User not found.", status_code=404)
    if not user.mfa_enabled or not user.mfa_secret:
        return {"enabled": False, "confirmed_at": None}
    if not verify_totp_code(user.mfa_secret, payload.code):
        raise ApiError("invalid_mfa_code", "MFA code is invalid.", status_code=401)
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_confirmed_at = None
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="auth.mfa_disabled",
        entity_type="user",
        entity_id=user_id,
        new_values={"mfa_enabled": False},
    )
    await db.commit()
    return {"enabled": False, "confirmed_at": None}


async def request_password_reset(
    db: AsyncSession,
    payload: PasswordResetRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    query = select(User).join(Tenant).where(
        User.email == payload.email,
        User.is_active.is_(True),
        Tenant.is_active.is_(True),
    )
    if payload.tenant_slug:
        query = query.where(Tenant.slug == payload.tenant_slug)
    users = list((await db.scalars(query)).all())
    response: dict = {"ok": True}
    if len(users) != 1:
        return response

    now = datetime.now(UTC)
    user = users[0]
    active_tokens = await db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    for token in active_tokens:
        token.consumed_at = now

    reset_token_value = create_opaque_token()
    reset_token = PasswordResetToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=hash_token(reset_token_value),
        expires_at=now + timedelta(minutes=30),
        created_by_ip=ip_address,
        user_agent=user_agent,
    )
    db.add(reset_token)
    await db.flush()

    settings = get_settings()
    manager_url = settings.manager_public_url.rstrip("/")
    reset_url = f"{manager_url}/reset-password?token={reset_token_value}"
    await enqueue_email(
        db,
        user.tenant_id,
        EmailNotificationCreate(
            request_reference=f"password_reset:{reset_token.id}",
            recipient=user.email,
            subject="Recuperar acesso ao ROTAS",
            body_text=(
                "Recebemos um pedido para recuperar o acesso ao ROTAS.\n\n"
                f"Use este link nos proximos 30 minutos: {reset_url}\n\n"
                "Se nao fez este pedido, ignore esta mensagem."
            ),
            body_html=(
                "<p>Recebemos um pedido para recuperar o acesso ao ROTAS.</p>"
                f"<p><a href=\"{reset_url}\">Definir nova palavra-passe</a></p>"
                "<p>Este link expira em 30 minutos. "
                "Se nao fez este pedido, ignore esta mensagem.</p>"
            ),
            template="password_reset",
            payload={"user_id": str(user.id), "reset_token_id": str(reset_token.id)},
        ),
        actor_id=user.id,
    )
    await record_audit_log(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="auth.password_reset_requested",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()

    if settings.environment != "production":
        response["reset_token"] = reset_token_value
        response["reset_url"] = reset_url
    return response


async def complete_password_reset(
    db: AsyncSession,
    payload: PasswordResetCompleteRequest,
) -> dict:
    now = datetime.now(UTC)
    reset_token = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(payload.token),
            PasswordResetToken.consumed_at.is_(None),
        )
    )
    if not reset_token or reset_token.expires_at <= now:
        raise ApiError("invalid_reset_token", "Reset token is invalid or expired.", status_code=401)

    user = await db.get(User, reset_token.user_id)
    tenant = await db.get(Tenant, reset_token.tenant_id)
    if not user or not tenant or not user.is_active or not tenant.is_active:
        raise ApiError("invalid_reset_token", "Reset token is invalid or expired.", status_code=401)

    user.password_hash = hash_password(payload.new_password)
    reset_token.consumed_at = now
    refresh_tokens = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    for refresh_token in refresh_tokens:
        refresh_token.revoked_at = now
    await record_audit_log(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="auth.password_reset_completed",
        entity_type="user",
        entity_id=user.id,
    )
    await db.commit()
    return {"ok": True}


def _session_payload(token: RefreshToken) -> dict:
    return {
        "id": token.id,
        "tenant_id": token.tenant_id,
        "user_id": token.user_id,
        "expires_at": token.expires_at,
        "revoked_at": token.revoked_at,
        "created_at": token.created_at,
        "created_by_ip": token.created_by_ip,
        "user_agent": token.user_agent,
        "active": token.revoked_at is None and token.expires_at > datetime.now(UTC),
    }


async def list_sessions(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    actor_role: str | None,
    user_id: UUID | None = None,
) -> list[dict]:
    target_user_id = user_id or actor_user_id
    if target_user_id != actor_user_id and actor_role not in {"owner", "admin"}:
        raise ApiError("forbidden", "Insufficient permissions for this operation.", status_code=403)
    query = (
        select(RefreshToken)
        .where(RefreshToken.tenant_id == tenant_id, RefreshToken.user_id == target_user_id)
        .order_by(RefreshToken.created_at.desc())
        .limit(100)
    )
    return [_session_payload(token) for token in (await db.scalars(query)).all()]


async def revoke_session(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    actor_role: str | None,
    session_id: UUID,
) -> dict:
    token = await db.get(RefreshToken, session_id)
    if not token or token.tenant_id != tenant_id:
        raise ApiError("session_not_found", "Session not found.", status_code=404)
    if token.user_id != actor_user_id and actor_role not in {"owner", "admin"}:
        raise ApiError("forbidden", "Insufficient permissions for this operation.", status_code=403)
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="auth.session_revoked",
            entity_type="refresh_token",
            entity_id=token.id,
            new_values=_session_payload(token),
        )
        await db.commit()
    return {"revoked": True}


async def pair_driver_device(db: AsyncSession, payload: DriverPairRequest) -> dict:
    now = datetime.now(UTC)
    driver = await db.scalar(
        select(Driver).where(
            Driver.pairing_code_hash == hash_token(payload.pairing_code),
            Driver.pairing_code_expires_at > now,
            Driver.status == "active",
        )
    )
    if not driver:
        raise ApiError(
            "invalid_pairing_code",
            "Pairing code is invalid or expired.",
            status_code=401,
        )
    device = await db.scalar(
        select(DriverDevice).where(
            DriverDevice.tenant_id == driver.tenant_id,
            DriverDevice.driver_id == driver.id,
            DriverDevice.device_id == payload.device_id,
        )
    )
    if not device:
        device = DriverDevice(
            tenant_id=driver.tenant_id,
            driver_id=driver.id,
            device_id=payload.device_id,
        )
        db.add(device)
    device.device_name = payload.device_name
    device.last_seen_at = now
    device.is_active = True
    driver.pairing_code_hash = None
    driver.pairing_code_expires_at = None
    response = await _create_driver_tokens(db, driver, payload.device_id)
    await db.commit()
    return response
