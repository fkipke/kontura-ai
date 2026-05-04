"""Tests fuer den zentralen Error-Handler.

Wir testen:
- Domain-Exceptions werden auf richtige Statuscodes gemappt.
- Response-Body folgt RFC9457 Problem Details.
- Request-Id wandert in den Response-Body.
- Pydantic-Validation-Errors haben 'errors'-Liste.
- Unerwartete Exceptions fuehren NICHT zu Stacktrace-Leak nach aussen.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from kontura.api.error_handlers import register_exception_handlers
from kontura.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from kontura.core.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)


def _build_test_app() -> FastAPI:
    """Mini-App nur fuer Error-Handler-Tests, ohne DB/Auth-Dependencies."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/raise/conflict")
    async def _conflict() -> None:
        raise ConflictError("Slug 'acme' existiert bereits.")

    @app.get("/raise/not-found")
    async def _not_found() -> None:
        raise NotFoundError("Invoice 123 nicht gefunden.")

    @app.get("/raise/forbidden")
    async def _forbidden() -> None:
        raise ForbiddenError("Du darfst diese Rechnung nicht sehen.")

    @app.get("/raise/unauthorized")
    async def _unauthorized() -> None:
        raise UnauthorizedError("Token abgelaufen.")

    @app.get("/raise/domain-validation")
    async def _domain_validation() -> None:
        raise DomainValidationError("Rechnungsdatum darf nicht in der Zukunft liegen.")

    @app.get("/raise/unexpected")
    async def _unexpected() -> None:
        raise RuntimeError("Datenbank ist abgebrannt. SQL: SELECT secrets FROM ...")

    return app


@pytest.mark.asyncio
async def test_conflict_error_returns_409_with_problem_details() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/raise/conflict")
    assert response.status_code == 409
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "Conflict"
    assert body["status"] == 409
    assert "existiert bereits" in body["detail"]
    assert body["instance"] == "/raise/conflict"
    assert "request_id" in body
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.asyncio
async def test_not_found_error_returns_404() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/raise/not-found")
    assert response.status_code == 404
    assert response.json()["title"] == "Not Found"


@pytest.mark.asyncio
async def test_forbidden_error_returns_403() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/raise/forbidden")
    assert response.status_code == 403
    assert response.json()["title"] == "Forbidden"


@pytest.mark.asyncio
async def test_unauthorized_error_returns_401() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/raise/unauthorized")
    assert response.status_code == 401
    assert response.json()["title"] == "Unauthorized"


@pytest.mark.asyncio
async def test_domain_validation_returns_422() -> None:
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/raise/domain-validation")
    assert response.status_code == 422
    assert response.json()["title"] == "Unprocessable Entity"


@pytest.mark.asyncio
async def test_unexpected_exception_returns_500_without_stacktrace_leak() -> None:
    """KRITISCH: Stacktrace darf NIEMALS nach aussen leaken (DB-Pfade etc)."""
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/raise/unexpected")
    assert response.status_code == 500
    body = response.json()
    assert body["title"] == "Internal Server Error"
    # Originale Fehlermeldung darf NICHT durchsickern.
    assert "Datenbank ist abgebrannt" not in body["detail"]
    assert "SELECT" not in body["detail"]
    assert "secrets" not in body["detail"]
    # Request-Id muss da sein, damit User Support kontaktieren kann.
    assert "request_id" in body


@pytest.mark.asyncio
async def test_request_id_from_client_appears_in_error_body() -> None:
    """Trace-Propagation: Client-Id taucht im Body auf."""
    app = _build_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/raise/conflict", headers={REQUEST_ID_HEADER: "client-trace-42"}
        )
    assert response.status_code == 409
    assert response.json()["request_id"] == "client-trace-42"
    assert response.headers[REQUEST_ID_HEADER] == "client-trace-42"


@pytest.mark.asyncio
async def test_validation_error_returns_422_with_errors_list() -> None:
    """Pydantic-Validation laeuft durch unseren Handler -> 'errors'-Array."""
    from pydantic import BaseModel, Field

    app = _build_test_app()

    class _Body(BaseModel):
        name: str = Field(..., min_length=3)

    @app.post("/raise/pydantic")
    async def _pydantic(body: _Body) -> dict[str, str]:
        return {"name": body.name}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/raise/pydantic", json={"name": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["title"] == "Unprocessable Entity"
    assert "errors" in body
    assert len(body["errors"]) >= 1
    assert "field" in body["errors"][0]
    assert "message" in body["errors"][0]
