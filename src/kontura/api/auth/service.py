"""AuthService: Use-Cases fuer Register/Login.

Senior-Pattern: Service kapselt Business-Regeln, Repository nur DB-Zugriff.
- Service entscheidet: 'darf User registriert werden?'
- Repository macht nur: 'speichere User'.
"""

from __future__ import annotations

from kontura.api.auth.repository import TenantRepository, UserRepository
from kontura.api.auth.schemas import LoginRequest, RegisterRequest
from kontura.core.security import hash_password, verify_password
from kontura.infra.models import User


class AuthError(Exception):
    """Wird bei Auth-Fehlern geworfen (Login fehlschlaegt, Tenant existiert)."""


class AuthService:
    """Business-Logik fuer Registrierung und Login."""

    def __init__(self, tenant_repo: TenantRepository, user_repo: UserRepository) -> None:
        self._tenants = tenant_repo
        self._users = user_repo

    async def register(self, payload: RegisterRequest) -> User:
        """Legt Tenant + ersten Admin-User an.

        - Tenant-Slug muss frei sein.
        - Email darf im neuen Tenant noch nicht existieren (trivialerweise).
        """
        existing_tenant = await self._tenants.get_by_slug(payload.tenant_slug)
        if existing_tenant is not None:
            raise AuthError(f"Tenant-Slug '{payload.tenant_slug}' existiert bereits.")

        await self._tenants.create(
            slug=payload.tenant_slug,
            display_name=payload.tenant_display_name,
        )

        user = await self._users.create(
            tenant_id=payload.tenant_slug,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
        )
        return user

    async def login(self, payload: LoginRequest) -> User:
        """Verifiziert Credentials und gibt den User zurueck.

        Senior-Detail: Selbe Fehlermeldung fuer 'unbekannte email' und
        'falsches passwort' - verhindert User-Enumeration.
        """
        user = await self._users.get_by_tenant_and_email(
            tenant_id=payload.tenant_slug,
            email=payload.email,
        )
        if user is None or not verify_password(payload.password, user.password_hash):
            raise AuthError("Email oder Passwort ungueltig.")
        return user
