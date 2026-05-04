"""Rate-Limiting via slowapi (Token-Bucket).

Senior-Konzept: Smart Key-Function
==================================
Authentifizierte Endpoints sollen PRO TENANT limitiert werden, nicht pro IP -
sonst wuerde ein NAT (z.B. Buerogateway) alle Mitarbeiter desselben Kunden
gegenseitig ausbremsen.

Loesung: Key-Function liest den JWT direkt aus dem Authorization-Header,
ohne FastAPI's Dependency-Injection zu nutzen (die laeuft erst NACH dem
Limiter). Bei ungueltigem/fehlendem JWT -> Fallback auf IP.

In-Memory vs Redis
==================
slowapi nutzt per Default In-Memory-Storage. Das reicht fuer Single-Instance.
Wenn wir spaeter auf 2+ App-Replicas skalieren, wechseln wir auf Redis -
1 Config-Aenderung (RATELIMIT_STORAGE_URI=redis://...), keine Code-Aenderung.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from kontura.api.middleware import REQUEST_ID_HEADER
from kontura.core.config import settings
from kontura.core.jwt import TokenError, decode_token

logger = structlog.get_logger(__name__)


# ---------- Key-Functions ----------


def ip_key(request: Request) -> str:
    """Limit pro IP - fuer login/register."""
    return f"ip:{get_remote_address(request)}"


def tenant_key(request: Request) -> str:
    """Limit pro Tenant (aus JWT). Fallback: IP, wenn JWT fehlt/ungueltig.

    KEIN crash bei kaputtem Token - der eigentliche Auth-Check passiert
    spaeter im Dependency-Tree und wirft dort sauber 401.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            payload = decode_token(token)
            return f"tenant:{payload.tenant_id}"
        except TokenError:
            pass  # ungueltig - faellt unten auf IP zurueck
    return f"ip:{get_remote_address(request)}"


# ---------- Limiter-Instanz ----------

# default_limits leer lassen - wir setzen Limits explizit pro Endpoint via Decorator.
# Das vermeidet versehentliche globale Drosselung von /health o.ae.
limiter = Limiter(
    key_func=tenant_key,
    enabled=settings.rate_limit_enabled,
    default_limits=[],
    headers_enabled=True,  # X-RateLimit-* Header in Response
)


# ---------- 429-Handler (RFC9457-konform) ----------


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """Konvertiert slowapi's RateLimitExceeded in unser RFC9457-Schema.

    Liefert 'Retry-After' Header (Sekunden) - HTTP-Standard, jeder Client
    kann automatisch backoffen.
    """
    if not isinstance(exc, RateLimitExceeded):
        # Sollte nie passieren - slowapi ruft Handler nur fuer RateLimitExceeded.
        raise exc

    detail = f"Rate-Limit ueberschritten: {exc.detail}"
    request_id = getattr(request.state, "request_id", None) or request.headers.get(
        REQUEST_ID_HEADER
    )
    logger.warning(
        "rate_limit_exceeded",
        path=request.url.path,
        limit=str(exc.detail),
    )

    body = {
        "type": "about:blank",
        "title": "Too Many Requests",
        "status": 429,
        "detail": detail,
        "instance": str(request.url.path),
    }
    if request_id:
        body["request_id"] = request_id

    headers = {
        "Content-Type": "application/problem+json",
        "Retry-After": "60",  # konservativ: 1 Minute
    }
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id

    return JSONResponse(status_code=429, content=body, headers=headers)


# ---------- App-Wiring ----------


def install_rate_limiter(app: FastAPI) -> None:
    """Haengt den Limiter + Middleware + 429-Handler an die App.

    Wird einmalig in main.create_app() gerufen.
    """
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
