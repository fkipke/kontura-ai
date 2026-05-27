"""HTTP-Endpoints fuer Authentication."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.auth.repository import TenantRepository, UserRepository
from kontura.api.auth.schemas import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from kontura.api.auth.service import AuthService
from kontura.api.dependencies import EmailSenderDep, TokenDep
from kontura.api.rate_limit import ip_key, limiter
from kontura.core.config import settings
from kontura.core.exceptions import ConflictError, DomainValidationError
from kontura.core.jwt import encode_token
from kontura.core.security.disposable_emails import is_disposable_email
from kontura.infra.db import get_session
from kontura.infra.email import build_verification_email

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _build_token_response(user_id: str, tenant_id: str, email: str) -> TokenResponse:
    token = encode_token(sub=user_id, tenant_id=tenant_id, email=email)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.jwt_ttl_minutes * 60,
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_verification_url(token: str) -> str:
    return f"{settings.app_base_url}/verify-email?token={token}"


async def _send_verification_mail(
    email_sender: EmailSenderDep, recipient_email: str, token: str
) -> None:
    verification_url = _build_verification_url(token)
    subject, body_text, body_html = build_verification_email(
        recipient_email=recipient_email,
        verification_url=verification_url,
    )
    await email_sender.send(
        to=recipient_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Legt einen neuen Tenant + ersten Admin-User an",
    responses={
        409: {"description": "Tenant-Slug existiert bereits"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_register_per_ip, key_func=ip_key)
async def register(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    response: Response,  # noqa: ARG001 - von slowapi gebraucht
    payload: RegisterRequest,
    session: SessionDep,
    email_sender: EmailSenderDep,
) -> RegisterResponse:
    if is_disposable_email(payload.email):
        raise DomainValidationError(
            "Wegwerf-E-Mail-Adressen sind nicht zugelassen. Bitte verwende eine reguläre E-Mail."
        )

    now = datetime.now(tz=UTC)
    token_plain = secrets.token_urlsafe(48)
    token_hash = _hash_token(token_plain)

    service = AuthService(
        tenant_repo=TenantRepository(session),
        user_repo=UserRepository(session),
    )
    try:
        user = await service.register(
            payload,
            email_verification_token_hash=token_hash,
            email_verification_expires_at=now
            + timedelta(hours=settings.email_verification_token_ttl_hours),
            email_verification_sent_at=None,
        )
        await session.commit()
    except ConflictError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("User existiert bereits in diesem Tenant.") from exc

    try:
        await _send_verification_mail(email_sender, user.email, token_plain)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "verification_mail_send_failed",
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            email=user.email,
            error=repr(exc),
        )

    return RegisterResponse(email_verification_required=True)


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Bestaetigt die E-Mail-Adresse per Verifikationslink",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def verify_email(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    response: Response,  # noqa: ARG001 - von slowapi gebraucht
    payload: VerifyEmailRequest,
    session: SessionDep,
) -> VerifyEmailResponse:
    repo = UserRepository(session)
    token_hash = _hash_token(payload.token)
    user = await repo.get_by_verification_token_hash(token_hash)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültiger oder bereits verwendeter Verifikationslink.",
        )

    if user.email_verified_at is not None:
        return VerifyEmailResponse(already_verified=True)

    now = datetime.now(tz=UTC)
    if user.email_verification_expires_at is not None and user.email_verification_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verifikationslink abgelaufen. Bitte fordere einen neuen an.",
        )

    user.email_verified_at = now
    user.email_verification_expires_at = None
    await session.commit()
    return VerifyEmailResponse(verified=True)


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    summary="Sendet einen neuen Verifikationslink",
)
@limiter.limit(settings.rate_limit_resend_verification, key_func=ip_key)
async def resend_verification(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    response: Response,  # noqa: ARG001 - von slowapi gebraucht
    payload: ResendVerificationRequest,
    session: SessionDep,
    email_sender: EmailSenderDep,
) -> ResendVerificationResponse:
    repo = UserRepository(session)
    user = await repo.get_by_tenant_and_email(payload.tenant_slug, str(payload.email))
    if user is None or user.email_verified_at is not None:
        return ResendVerificationResponse(sent=True)

    now = datetime.now(tz=UTC)
    if (
        user.email_verification_sent_at is not None
        and (now - user.email_verification_sent_at).total_seconds()
        < settings.email_verification_resend_cooldown_seconds
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bitte warte vor einer erneuten Anforderung.",
        )

    token_plain = secrets.token_urlsafe(48)
    user.email_verification_token_hash = _hash_token(token_plain)
    user.email_verification_expires_at = now + timedelta(
        hours=settings.email_verification_token_ttl_hours
    )
    # `sent_at` tracks cooldown across explicit resend requests only.
    # The initial registration mail must not start the resend cooldown.
    user.email_verification_sent_at = now
    await session.commit()

    try:
        await _send_verification_mail(email_sender, user.email, token_plain)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "verification_mail_resend_failed",
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            email=user.email,
            error=repr(exc),
        )

    return ResendVerificationResponse(sent=True)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login: gibt einen JWT zurueck",
    responses={
        401: {"description": "Email oder Passwort ungueltig"},
        429: {"description": "Rate-Limit ueberschritten"},
    },
)
@limiter.limit(settings.rate_limit_login_per_ip, key_func=ip_key)
async def login(
    request: Request,  # noqa: ARG001 - von slowapi gebraucht
    response: Response,  # noqa: ARG001 - von slowapi gebraucht (Rate-Limit-Header)
    payload: LoginRequest,
    session: SessionDep,
) -> TokenResponse:
    service = AuthService(
        tenant_repo=TenantRepository(session),
        user_repo=UserRepository(session),
    )
    user = await service.login(payload)
    return _build_token_response(
        user_id=str(user.id),
        tenant_id=user.tenant_id,
        email=user.email,
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Liefert den aktuell eingeloggten User (aus JWT)",
    responses={
        401: {"description": "JWT fehlt, ungueltig oder abgelaufen"},
    },
)
async def me(token: TokenDep) -> MeResponse:
    return MeResponse(
        user_id=token.sub,
        tenant_id=token.tenant_id,
        email=token.email,
        token_expires_at=token.exp,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (clientseitig: Token verwerfen)",
)
async def logout(token: TokenDep) -> None:  # noqa: ARG001
    return None
