"""Zentrale FastAPI-Exception-Handler.

RFC 9457 Problem Details fuer alle bekannten Fehlerklassen.

Hinweis: Der Catch-All fuer unerwartete Exceptions sitzt in der
RequestContextMiddleware (Starlette/BaseHTTPMiddleware-Quirk:
@app.exception_handler(Exception) wird bei BaseHTTPMiddleware nicht
aufgerufen). Dadurch ist der globale Stacktrace-Schutz garantiert.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from kontura.api.middleware import REQUEST_ID_HEADER
from kontura.core.exceptions import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    KonturaError,
    NotFoundError,
    UnauthorizedError,
)

logger = structlog.get_logger(__name__)

_DOMAIN_TO_HTTP: dict[type[KonturaError], tuple[int, str]] = {
    ConflictError: (status.HTTP_409_CONFLICT, "Conflict"),
    NotFoundError: (status.HTTP_404_NOT_FOUND, "Not Found"),
    ForbiddenError: (status.HTTP_403_FORBIDDEN, "Forbidden"),
    UnauthorizedError: (status.HTTP_401_UNAUTHORIZED, "Unauthorized"),
    DomainValidationError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Unprocessable Entity"),
}


def _resolve_request_id(request: Request) -> str | None:
    state_id = getattr(request.state, "request_id", None)
    if state_id:
        return str(state_id)
    return request.headers.get(REQUEST_ID_HEADER)


def _build_problem(
    *,
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
    }
    request_id = _resolve_request_id(request)
    if request_id:
        body["request_id"] = request_id
    headers = {"Content-Type": "application/problem+json"}
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Registriert Handler fuer KonturaError, HTTPException, ValidationError."""

    @app.exception_handler(KonturaError)
    async def handle_domain_error(request: Request, exc: KonturaError) -> JSONResponse:
        for cls, (status_code, title) in _DOMAIN_TO_HTTP.items():
            if isinstance(exc, cls):
                logger.warning(
                    "domain_error",
                    error_class=type(exc).__name__,
                    status=status_code,
                    detail=str(exc),
                )
                return _build_problem(
                    request=request,
                    status_code=status_code,
                    title=title,
                    detail=str(exc),
                )
        # Unbekannte KonturaError-Subklasse - sollte nie passieren, aber sicher ist sicher.
        logger.exception("unmapped_domain_error", error_class=type(exc).__name__)
        return _build_problem(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="Ein interner Fehler ist aufgetreten.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = _http_status_title(exc.status_code)
        if exc.status_code >= 500:
            logger.exception("http_exception_5xx", status=exc.status_code)
        else:
            logger.warning("http_exception_4xx", status=exc.status_code, detail=str(exc.detail))
        return _build_problem(
            request=request,
            status_code=exc.status_code,
            title=title,
            detail=str(exc.detail) if exc.detail else title,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(p) for p in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        logger.warning(
            "validation_error",
            error_count=len(errors),
            first_error=errors[0] if errors else None,
        )
        return _build_problem(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Unprocessable Entity",
            detail="Eingabe-Validierung fehlgeschlagen.",
            extra={"errors": errors},
        )


_STATUS_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    410: "Gone",
    415: "Unsupported Media Type",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def _http_status_title(code: int) -> str:
    return _STATUS_TITLES.get(code, "Error")
