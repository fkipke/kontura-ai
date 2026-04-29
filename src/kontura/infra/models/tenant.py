"""Tenant-Modell: Repraesentiert einen zahlenden Mandanten (Kundenfirma)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ein Kunde von Kontura AI (z.B. 'Acme GmbH', 'Mueller & Co').

    Senior-Hinweis: Wir verwenden KEINEN UUID-FK, sondern den 'slug' als
    natural key (tenant_id). Das macht JWTs lesbar (sub: 'acme' statt
    'sub: 7b2d6a56-14e8-4e5e-b536-...') und Logs angenehmer.
    """

    __tablename__ = "tenants"

    # 'slug': URL-safer, lowercase, eindeutig - wird als tenant_id verwendet.
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    # Anzeigename (frei waehlbar): "Acme GmbH"
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<Tenant slug={self.slug!r} display_name={self.display_name!r}>"
