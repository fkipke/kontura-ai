"""Security-Headers-Middleware (OWASP-Basics).

Setzt auf jede Response HTTP-Header, die Browser-seitig vor gaengigen
Angriffen schuetzen:
- HSTS               -> erzwingt HTTPS
- nosniff            -> verhindert MIME-Type-Confusion
- X-Frame-Options    -> verhindert Clickjacking via iframe
- Referrer-Policy    -> begrenzt Info-Leaks via Referer-Header
- Permissions-Policy -> deaktiviert Browser-Features wie Kamera/Mikrofon

Diese Header sind Industrie-Standard - Stripe, GitHub, Banking-Apps
setzen alle die gleichen.
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Fuegt OWASP-Security-Header zu jeder Response hinzu."""

    def __init__(self, app: object, *, enable_hsts: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.enable_hsts = enable_hsts

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # MIME-Sniffing verhindern (Browser darf Content-Type nicht raten).
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Clickjacking verhindern (Seite nicht in fremde iframes einbettbar).
        response.headers["X-Frame-Options"] = "DENY"

        # Referer-Header nur an gleichen Origin schicken (Privacy).
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Browser-Features default deaktivieren (kann bei Bedarf gelockert werden).
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # HSTS nur in Production - im Dev ueber HTTP wuerde das den Browser
        # zwingen, Localhost-HTTP-Requests zu blocken.
        # max-age=63072000 = 2 Jahre, Industrie-Standard.
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response
