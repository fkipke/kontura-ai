"""HTTP-Endpoints fuer Authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.auth.repository import TenantRepository, UserRepository
from kontura.api.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from kontura.api.auth.service import AuthError, AuthService
from kontura.core.config import settings
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
    },
)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenResponse:
    service = AuthService(
        tenant_repo=TenantRepository(session),
        user_repo=UserRepository(session),
    )
    try:
        user = await service.register(payload)
        await session.commit()
    except AuthError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User existiert bereits in diesem Tenant.",
        ) from exc

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
    },
)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    service = AuthService(
        tenant_repo=TenantRepository(session),
        user_repo=UserRepository(session),
    )
    try:
        user = await service.login(payload)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    return _build_token_response(
        user_id=str(user.id),
        tenant_id=user.tenant_id,
        email=user.email,
    )