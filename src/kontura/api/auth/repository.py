"""Repositories fuer Tenant + User.

Ohne 'tenant aware'-Filter, weil Tenants gerade ERST erstellt werden -
der Auth-Layer ist die einzige Stelle, an der wir tenant-uebergreifend lesen.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models import Tenant, User


class TenantRepository:
    """DB-Zugriffe fuer Tenants."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, slug: str, display_name: str) -> Tenant:
        tenant = Tenant(slug=slug, display_name=display_name)
        self._session.add(tenant)
        await self._session.flush()
        return tenant


class UserRepository:
    """DB-Zugriffe fuer Users."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_tenant_and_email(self, tenant_id: str, email: str) -> User | None:
        stmt = select(User).where(
            User.tenant_id == tenant_id,
            User.email == email,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        tenant_id: str,
        email: str,
        password_hash: str,
        full_name: str | None,
        email_verification_token_hash: str | None = None,
        email_verification_expires_at: datetime | None = None,
        email_verification_sent_at: datetime | None = None,
        email_verified_at: datetime | None = None,
    ) -> User:
        user = User(
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            email_verification_token_hash=email_verification_token_hash,
            email_verification_expires_at=email_verification_expires_at,
            email_verification_sent_at=email_verification_sent_at,
            email_verified_at=email_verified_at,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_verification_token_hash(self, token_hash: str) -> User | None:
        stmt = select(User).where(User.email_verification_token_hash == token_hash)
        return (await self._session.execute(stmt)).scalar_one_or_none()
