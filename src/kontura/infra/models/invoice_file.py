"""InvoiceFile-Modell: Hochgeladene Rechnungsdatei (PDF/PNG/JPG) eines Tenants.

Phase G2.0: Reine Dateispeicherung mit Tenant-Isolation und Deduplication.
Phase G2.1 wird dieses Modell mit AI-Extraktion verbinden.
"""

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InvoiceFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Eine hochgeladene Quelldatei (PDF/PNG/JPG) fuer eine Eingangsrechnung.

    Design-Entscheidungen:
    - tenant_id als String (wie Invoice, User) - kein UUID-FK, natuerlicher Key aus JWT
    - sha256 + tenant_id bilden einen UniqueConstraint fuer Deduplication
    - invoice_id ist nullable - wird erst in G2.1 gesetzt wenn AI die Rechnung erkennt
    - storage_path ist ein opaker relativer Pfad, der von FileStorage verwaltet wird
    """

    __tablename__ = "invoice_files"

    # Tenant-Isolation: wie in Invoice und User, string-basiert aus dem JWT
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Wer hat die Datei hochgeladen (FK auf users.id)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Verknuepfung zur Rechnung - wird in G2.1 gesetzt (nullable bis dahin)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Originaldateiname (vom Upload), max. 255 Zeichen, bereits sanitisiert
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # MIME-Type der Datei (application/pdf, image/png, image/jpeg)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Dateigroe in Bytes
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # SHA-256-Hash des Dateiinhalts (64 Hex-Zeichen) - fuer Deduplication
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Relativer Speicherpfad (opak, verwaltet von FileStorage)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (
        # Deduplication: Gleiche Datei (sha256) pro Tenant nur einmal speichern
        UniqueConstraint("tenant_id", "sha256", name="uq_invoice_files_tenant_sha256"),
        # Performance-Index fuer List-Queries (tenant_id, created_at DESC)
        Index("ix_invoice_files_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<InvoiceFile id={self.id} tenant={self.tenant_id} "
            f"filename={self.filename!r} mime_type={self.mime_type!r} "
            f"size_bytes={self.size_bytes} sha256={self.sha256[:8]}...>"
        )
