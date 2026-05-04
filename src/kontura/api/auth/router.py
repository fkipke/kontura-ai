"""HTTP-Endpoints fuer Authentication.

Rate-Limiting (Brute-Force-Schutz):
- /register: 5/min pro IP
- /login: 10/min pro IP

slowapi-Detail: der `request: Request` Parameter MUSS in der Endpoint-Signatur
stehen, damit slowapi auf den Request zugreifen kann (Decorator inspiziert Args).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.auth.repository import TenantRepository, UserRepository
from kontura.api.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from kontura.api.auth.service import AuthService
from kontura.api.rate_limit import ip_key, limiter
from kontura.core.config import settings
from kontura.core.exceptions import ConflictError
from kontura.core.jwt import encode_token
from kontura.infra.db import get_session

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _build_token_response(user_id: str, tenant_id: str, email: str) -> TokenResponse:
    token = encode_token(sub=user_id, tenant_id=tenant_id, email=email)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.jwt_ttl_minutes * 60,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
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
    payload: RegisterRequest,
    session: SessionDep,
) -> TokenResponse:
    service = AuthService(
        tenant_repo=TenantRepository(session),
        user_repo=UserRepository(session),
    )
    try:
        user = await service.register(payload)
        await session.commit()
    except ConflictError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("User existiert bereits in diesem Tenant.") from exc

    return _build_token_response(
        user_id=str(user.id),
        tenant_id=user.tenant_id,
        email=user.email,
    )


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
