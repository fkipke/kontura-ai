"""Pydantic-Schemas fuer den Auth-Endpoint."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """POST /auth/register: legt einen neuen Tenant + ersten Admin-User an."""

    tenant_slug: str = Field(
        ...,
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9_-]{2,64}$",
        description="URL-safer Slug (lowercase). Wird zur tenant_id.",
    )
    tenant_display_name: str = Field(
        ..., min_length=1, max_length=255, description="Anzeigename des Tenants"
    )
    email: EmailStr = Field(description="Email des Admin-Users")
    password: str = Field(..., min_length=8, max_length=128, description="Passwort")
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """POST /auth/login: tenant_slug + email + passwort."""

    tenant_slug: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """JWT-Antwort fuer Login/Register."""

    access_token: str = Field(description="JWT, im Header 'Authorization: Bearer ...'")
    token_type: str = Field(default="bearer", description="Immer 'bearer'")
    expires_in_seconds: int = Field(description="Gueltigkeitsdauer in Sekunden")


class UserResponse(BaseModel):
    """Antwort fuer GET /auth/me."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    email: str
    full_name: str | None
    created_at: datetime
