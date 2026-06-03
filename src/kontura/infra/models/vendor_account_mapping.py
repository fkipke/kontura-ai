"""VendorAccountMapping: Lerntabelle fuer Lieferant → Kreditorkonto.

Design:
- Pro (tenant_id, vendor_name_normalized) genau ein Mapping (Unique).
- vendor_name_normalized: lowercase, gestrippt, Rechtsform-Suffix entfernt,
  Umlaute gefoldet. Erlaubt deterministisches Matching ohne LLM.
- usage_count steigt jedes Mal wenn eine neue Rechnung mit diesem Vendor
  gebucht wird und das Mapping passt. last_used_at trackt Recency.
- Confidence-Score wird im Service berechnet, nicht persistiert (jederzeit
  rekonstruierbar).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kontura.infra.db import Base
from kontura.infra.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class VendorAccountMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vendor_account_mappings"

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    vendor_name_normalized: Mapped[str] = mapped_column(String(200), nullable=False)
    vendor_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    creditor_account_number: Mapped[int] = mapped_column(Integer, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "vendor_name_normalized",
            name="uq_vendor_account_mappings_tenant_normalized",
        ),
        Index(
            "ix_vendor_account_mappings_tenant_lastused",
            "tenant_id",
            "last_used_at",
        ),
    )
