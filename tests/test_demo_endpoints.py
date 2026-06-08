"""Tests fuer Cluster 4: Demo-Endpoints (demo-login + reset-demo)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dependencies import get_settings
from kontura.core.config import Settings
from kontura.main import app


def _demo_settings(**overrides: object) -> Settings:
    """Erstellt eine Settings-Instanz mit Demo-Modus."""
    base = Settings(
        jwt_secret="ci-test-secret-do-not-use-in-production-please",
        demo_mode=True,
        demo_tenant_id="demo-tenant",
        demo_user_email="demo@kontura.ai",
        demo_user_password="demo",
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


def _disabled_settings() -> Settings:
    return Settings(
        jwt_secret="ci-test-secret-do-not-use-in-production-please",
        demo_mode=False,
    )


# ========================== demo-login ==========================


@pytest.mark.asyncio
async def test_demo_login_returns_403_when_demo_mode_disabled(client: AsyncClient) -> None:
    """demo-login → 403 wenn KONTURA_DEMO_MODE=false."""
    app.dependency_overrides[get_settings] = _disabled_settings
    try:
        resp = await client.post("/api/v1/auth/demo-login")
        assert resp.status_code == 403
        assert "deaktiviert" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_demo_login_returns_token_when_demo_mode_enabled(client: AsyncClient) -> None:
    """demo-login → 200 mit access_token wenn demo_mode=True."""
    app.dependency_overrides[get_settings] = _demo_settings
    try:
        resp = await client.post("/api/v1/auth/demo-login")
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_demo_login_idempotent_second_call_returns_token(
    client: AsyncClient,
) -> None:
    """Zweiter Aufruf von demo-login gibt ebenfalls 200 zurueck (User already exists)."""
    app.dependency_overrides[get_settings] = _demo_settings
    try:
        resp1 = await client.post("/api/v1/auth/demo-login")
        resp2 = await client.post("/api/v1/auth/demo-login")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)


# ========================== reset-demo ==========================


@pytest.mark.asyncio
async def test_reset_demo_returns_403_when_demo_mode_disabled(client: AsyncClient) -> None:
    """reset-demo → 403 wenn KONTURA_DEMO_MODE=false."""
    app.dependency_overrides[get_settings] = _disabled_settings
    try:
        resp = await client.post("/api/v1/admin/reset-demo")
        assert resp.status_code == 403
        assert "deaktiviert" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


@pytest.mark.asyncio
async def test_reset_demo_succeeds_when_demo_mode_enabled(
    client: AsyncClient, session: AsyncSession
) -> None:
    """reset-demo → 204 und Daten werden angelegt."""
    from sqlalchemy import func, select  # noqa: PLC0415

    from kontura.infra.models.invoice import Invoice  # noqa: PLC0415

    app.dependency_overrides[get_settings] = _demo_settings
    try:
        resp = await client.post("/api/v1/admin/reset-demo")
        assert resp.status_code == 204

        # Pruefen ob Daten angelegt wurden
        count = (
            await session.execute(
                select(func.count(Invoice.id)).where(Invoice.tenant_id == "demo-tenant")
            )
        ).scalar_one()
        assert count == 50
    finally:
        app.dependency_overrides.pop(get_settings, None)
