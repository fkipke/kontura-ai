"""HTTP-Middleware: Request-Id, Logging, Latency, Catch-All-Errors.

Senior-Detail: Warum die Middleware den Exception-Catch-All macht
=================================================================
Starlette's BaseHTTPMiddleware und FastAPI's @app.exception_handler(Exception)
spielen nicht zusammen - bei einer unhandled Exception laeuft der Handler NICHT,
die Exception propagiert aus dem ASGI-Stack heraus.

Loesung: Wir bauen den Catch-All hier in der Middleware ein. KonturaError,
HTTPException, RequestValidationError werden weiter vom zentralen
Error-Handler in api/error_handlers.py behandelt - das funktioniert, weil
FastAPI sie INNERHALB des Routers abfaengt, bevor sie unsere Middleware
erreichen.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bindet Request-Id + Logging-Context an jeden Request.

    Plus: faengt unerwartete Exceptions ab und liefert eine RFC9457-konforme
    500-Response (Stacktrace bleibt im Log, geht NICHT nach aussen).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # noqa: BLE001 - bewusst breit, Catch-All
            logger.exception(
                "unhandled_exception",
                error_class=type(exc).__name__,
            )
            response = _build_500_problem(request, request_id)
            status_code = 500

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "request_completed",
            status=status_code,
            duration_ms=duration_ms,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _build_500_problem(request: Request, request_id: str) -> JSONResponse:
    """Generische 500-Response (Problem Details, ohne Stacktrace-Leak)."""
    body = {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": (
            "Ein interner Fehler ist aufgetreten. Bitte kontaktiere Support mit der request_id."
        ),
        "instance": str(request.url.path),
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=500,
        content=body,
        headers={
            "Content-Type": "application/problem+json",
            REQUEST_ID_HEADER: request_id,
        },
    )
