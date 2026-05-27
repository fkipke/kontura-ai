"""User-Modell: ein User gehoert zu genau einem Tenant."""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ein Anwender innerhalb eines Tenants.

    Senior-Detail (composite Unique):
    - Email ist innerhalb eines Tenants eindeutig.
    - Theoretisch kann derselbe Mensch in 2 Tenants angemeldet sein
      (z.B. Berater fuer mehrere Kunden) - dafuer waeren 2 Datensaetze noetig.
    """

    __tablename__ = "users"

    # FK auf Tenant.slug (string-basiert, kein UUID-FK).
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)

    email: Mapped[str] = mapped_column(String(255), nullable=False)

    # bcrypt-Hash (NIEMALS Klartext-Passwort speichern!)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Anzeigename, optional
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verification_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    def __repr__(self) -> str:
        return f"<User id={self.id} tenant={self.tenant_id} email={self.email!r}>"
