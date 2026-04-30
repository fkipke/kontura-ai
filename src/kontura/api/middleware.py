"""HTTP-Middleware: Request-Id, Logging, Latency.

Senior-Konzept: Eine Middleware, drei Aufgaben
==============================================
Fuer JEDEN Request:
1. Request-Id generieren (UUID4) - im Header zurueckgeben + im Log-Context binden.
2. Start-Zeit messen, am Ende Latenz loggen.
3. Strukturiertes Log mit Status, Methode, Path, Latency, Tenant.

Warum Request-Id wichtig ist:
- Bei Fehler schickt User Dir die Id (X-Request-Id Header).
- Du grep'st in den Logs: alle Eintraege zu DIESEM Request, ueber alle
  Komponenten (DB, AI-Provider, etc.) tauchen auf.
- In Distributed Systems (mehrere Services): wird zur Trace-Id - DER
  Goldstandard fuer Debugging.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bindet Request-Id + Logging-Context an jeden Request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Request-Id aus Header uebernehmen (Trace-Propagation aus Clients)
        # oder neu generieren.
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # ContextVars binden - ab hier in JEDEM Log automatisch dabei.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        status_code = 500  # Default falls Exception bevor Response gebaut ist

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception("request_failed_unhandled")
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "request_completed",
                status=status_code,
                duration_ms=duration_ms,
            )
            # Request-Id IMMER in Response, damit Client sie loggen kann.
            # (Bei Exception ist 'response' nicht definiert - Starlette baut
            # selbst eine 500-Response, die wir nicht modifizieren koennen.
            # Das ist akzeptabel, weil wir die Id schon ins Log geschrieben haben.)
            try:
                response.headers[REQUEST_ID_HEADER] = request_id
            except UnboundLocalError:
                pass
