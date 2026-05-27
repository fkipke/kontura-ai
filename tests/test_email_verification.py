from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.core.security import hash_password
from kontura.infra.models.user import User


def _extract_token(body_text: str) -> str:
    match = re.search(r"token=([^\s]+)", body_text)
    assert match is not None
    return match.group(1)


@pytest.mark.asyncio
async def test_register_verify_login_happy_path(
    client: AsyncClient,
    fake_email_sender: Any,
) -> None:
    register_payload = {
        "tenant_slug": "verify-happy",
        "tenant_display_name": "Verify Happy GmbH",
        "email": "happy@example.com",
        "password": "supersecret123",
    }

    register_response = await client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201
    assert len(fake_email_sender.sent_emails) == 1
    email = fake_email_sender.sent_emails[0]
    token = _extract_token(email.body_text)

    verify_response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 200
    assert verify_response.json() == {"verified": True, "already_verified": False}

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": register_payload["tenant_slug"],
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


@pytest.mark.asyncio
async def test_login_before_verification_returns_403(client: AsyncClient) -> None:
    register_payload = {
        "tenant_slug": "verify-login-block",
        "tenant_display_name": "Verify Block GmbH",
        "email": "blocked@example.com",
        "password": "supersecret123",
    }
    await client.post("/api/v1/auth/register", json=register_payload)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": register_payload["tenant_slug"],
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    assert login_response.status_code == 403
    body = login_response.json()
    assert body["code"] == "email_not_verified"


@pytest.mark.asyncio
async def test_register_disposable_email_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "disposable-case",
            "tenant_display_name": "Disposable GmbH",
            "email": "xyz@mailinator.com",
            "password": "supersecret123",
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "Wegwerf-E-Mail-Adressen sind nicht zugelassen. Bitte verwende eine reguläre E-Mail."
    )


@pytest.mark.asyncio
async def test_verify_twice_returns_already_verified(
    client: AsyncClient,
    fake_email_sender: Any,
) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "double-verify",
            "tenant_display_name": "Double Verify GmbH",
            "email": "double@example.com",
            "password": "supersecret123",
        },
    )
    token = _extract_token(fake_email_sender.sent_emails[0].body_text)

    first = await client.post("/api/v1/auth/verify-email", json={"token": token})
    second = await client.post("/api/v1/auth/verify-email", json={"token": token})

    assert first.status_code == 200
    assert first.json()["verified"] is True
    assert second.status_code == 200
    assert second.json()["already_verified"] is True


@pytest.mark.asyncio
async def test_verify_expired_token_returns_400(
    client: AsyncClient,
    fake_email_sender: Any,
    session: AsyncSession,
) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "tenant_slug": "expired-verify",
            "tenant_display_name": "Expired Verify GmbH",
            "email": "expired@example.com",
            "password": "supersecret123",
        },
    )
    token = _extract_token(fake_email_sender.sent_emails[0].body_text)

    user = (
        await session.execute(select(User).where(User.email == "expired@example.com"))
    ).scalar_one()
    user.email_verification_expires_at = datetime.now(tz=UTC) - timedelta(hours=1)
    await session.commit()

    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 400
    assert (
        response.json()["detail"] == "Verifikationslink abgelaufen. Bitte fordere einen neuen an."
    )


@pytest.mark.asyncio
async def test_resend_cooldown_returns_429(client: AsyncClient) -> None:
    payload = {
        "tenant_slug": "cooldown-verify",
        "tenant_display_name": "Cooldown Verify GmbH",
        "email": "cooldown@example.com",
        "password": "supersecret123",
    }
    await client.post("/api/v1/auth/register", json=payload)

    first = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": payload["email"], "tenant_slug": payload["tenant_slug"]},
    )
    second = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": payload["email"], "tenant_slug": payload["tenant_slug"]},
    )

    assert first.status_code == 200
    assert first.json() == {"sent": True}
    assert second.status_code == 429
    assert second.json()["detail"] == "Bitte warte vor einer erneuten Anforderung."


@pytest.mark.asyncio
async def test_resend_unknown_or_verified_returns_generic_success(
    client: AsyncClient,
    fake_email_sender: Any,
) -> None:
    unknown = await client.post(
        "/api/v1/auth/resend-verification",
        json={"tenant_slug": "unknown-tenant", "email": "unknown@example.com"},
    )
    assert unknown.status_code == 200
    assert unknown.json() == {"sent": True}

    payload = {
        "tenant_slug": "verified-resend",
        "tenant_display_name": "Verified Resend GmbH",
        "email": "verified@example.com",
        "password": "supersecret123",
    }
    await client.post("/api/v1/auth/register", json=payload)
    token = _extract_token(fake_email_sender.sent_emails[0].body_text)
    await client.post("/api/v1/auth/verify-email", json={"token": token})

    verified = await client.post(
        "/api/v1/auth/resend-verification",
        json={"tenant_slug": payload["tenant_slug"], "email": payload["email"]},
    )
    assert verified.status_code == 200
    assert verified.json() == {"sent": True}


@pytest.mark.asyncio
async def test_login_existing_verified_user_still_works(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    session.add(
        User(
            id=uuid.uuid4(),
            tenant_id="acme-corp",
            email="legacy@example.com",
            password_hash=hash_password("legacy-password-123"),
            email_verified_at=datetime.now(tz=UTC),
        )
    )
    await session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "acme-corp",
            "email": "legacy@example.com",
            "password": "legacy-password-123",
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
