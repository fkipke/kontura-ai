"""JWT-Codec: Tokens signieren und validieren.

Senior-Pattern: Wir kapseln die JWT-Library (PyJWT) hinter einer schmalen
eigenen API. Vorteile:
- Wenn wir spaeter auf jose, authlib oder einen externen IdP wechseln,
  aendert sich nur diese Datei.
- Aufrufer sehen kontura-eigene Datentypen (TokenPayload), nicht jwt-Internas.

Sicherheit:
- HS256 mit langem Secret (>= 32 Zeichen). Kein 'none'-Algorithm akzeptieren!
- 'exp'-Claim Pflicht - alte Tokens laufen ab.
- 'iat' fuer Replay-Detection moeglich (spaeter).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from pydantic import BaseModel, ConfigDict, Field

from kontura.core.config import settings


class TokenPayload(BaseModel):
    """Inhalt eines JWT - nur das, was wir auch wirklich rausgeben."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sub: str = Field(description="Subject = User-UUID als String")
    tenant_id: str = Field(description="Tenant-Slug")
    email: str = Field(description="Email des Users (Convenience-Claim)")
    exp: int = Field(description="Expiry-Zeit als Unix-Timestamp")


class TokenError(Exception):
    """Wird geworfen, wenn ein Token ungueltig, abgelaufen oder gefaelscht ist."""


def encode_token(*, sub: str, tenant_id: str, email: str) -> str:
    """Erzeugt einen signierten JWT mit Standard-TTL aus Settings."""
    now = dt.datetime.now(dt.UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "tenant_id": tenant_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=settings.jwt_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """Validiert einen JWT und gibt das Payload zurueck.

    Raises:
        TokenError: bei abgelaufenem, gefaelschtem oder ungueltigem Token.
    """
    try:
        raw = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "tenant_id"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token ist abgelaufen.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"Token ungueltig: {exc}") from exc

    try:
        return TokenPayload(
            sub=raw["sub"],
            tenant_id=raw["tenant_id"],
            email=raw.get("email", ""),
            exp=int(raw["exp"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("Token-Payload unvollstaendig.") from exc
