"""Einmaliges Reparatur-/Vorbereitungs-Skript fuer das Demo-Video.

Problem im Demo-Setup:
  Die UI markiert eine ``InvoiceFile`` als "geprueft" - faktisch wird aber das
  ``is_reviewed``-Flag auf der verknuepften ``Invoice`` gesetzt. Wenn fuer
  eine Datei keine ``Invoice`` existiert (z.B. weil die KI-Extraktion das
  Auto-Anlegen uebersprungen hat, oder weil die Verknuepfung verlorengegangen
  ist), kann das Frontend ein gruenes "Geprueft"-Badge zeigen, der
  DATEV-Export sieht die Rechnung aber trotzdem nicht.

Dieses Skript stellt fuer eine Liste von Dateinamen-Mustern sicher:
  1. Die InvoiceFile existiert (sonst Warnung).
  2. Es gibt eine verknuepfte Invoice mit sinnvollen Feldwerten
     (aus ``extraction_result`` rekonstruiert oder mit Demo-Defaults befuellt).
  3. ``Invoice.is_reviewed = True`` ist gesetzt.
  4. ``reviewed_at`` und ``reviewed_by_user_id`` sind gesetzt.
  5. ``invoice_files.invoice_id`` zeigt auf die richtige Invoice.

Idempotent - mehrfache Ausfuehrung ist sicher.

Usage:
    uv run python scripts/force_review_for_demo.py

Die Suche nach Dateinamen ist case-insensitive und benutzt ILIKE-Wildcards:
z.B. ``getrankebob`` matcht ``GetraenkeBoB - Test.pdf``,
``GetränkeBob.pdf`` etc.

Der Ziel-Tenant kommt aus ``settings.demo_tenant_id``. Sollten mehrere
Dateien matchen, werden ALLE behandelt.
"""

from __future__ import annotations

import asyncio
import unicodedata
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kontura.core.config import get_settings
from kontura.infra.db import engine
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_file import InvoiceFile
from kontura.infra.models.user import User

logger = structlog.get_logger(__name__)

# Substrings, nach denen im filename gesucht wird. Case-insensitive,
# umlautfrei - Postgres ILIKE und unsere unaccent-aehnliche Normalisierung
# matchen beide Varianten (GetraenkeBoB, GetränkeBob, ...).
TARGET_NAME_PATTERNS: list[str] = [
    "getrankebob",
    "getraenkebob",
    "getr%bob",  # ILIKE-Wildcard fuer den Umlaut-Fall
    "re-test",
    "re_test",
    "retest",
]

# Fallback-Werte falls die Extraction-Result nichts brauchbares liefert.
# Wir setzen ein realistisches deutsches Demo-Datum + sinnvolle Betraege,
# damit die Vorschau nicht leer aussieht.
FALLBACK_INVOICE_DATE = date(2026, 1, 15)
FALLBACK_TOTAL = Decimal("119.00")
FALLBACK_NET = Decimal("100.00")
FALLBACK_TAX = Decimal("19.00")
FALLBACK_CURRENCY = "EUR"


def _strip_accents(value: str) -> str:
    """Entfernt deutsche Umlaute fuer den Pattern-Vergleich."""
    nfkd = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _extract_vendor_from_filename(filename: str) -> str:
    """Rekonstruiert einen lesbaren Default-Vendor aus dem Dateinamen."""
    stem = filename.rsplit(".", 1)[0]
    lower = _strip_accents(stem).lower()
    if "getr" in lower and "bob" in lower:
        return "Getr\u00e4nke Bob D\u00fcsseldorf"
    if "re-test" in lower or "retest" in lower or "re_test" in lower:
        return "Ernst Mustermann"
    return stem


async def _find_target_files(
    session: AsyncSession, tenant_id: str
) -> list[InvoiceFile]:
    """Sucht alle InvoiceFiles des Tenants, deren Dateiname zu den Patterns passt."""
    clauses = [InvoiceFile.filename.ilike(f"%{p}%") for p in TARGET_NAME_PATTERNS]
    stmt = (
        select(InvoiceFile)
        .where(InvoiceFile.tenant_id == tenant_id)
        .where(or_(*clauses))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _pick_reviewer(session: AsyncSession, tenant_id: str) -> uuid.UUID | None:
    """Liefert eine User-Id fuer reviewed_by_user_id. Bevorzugt den Demo-User.

    Falls niemand gefunden wird: None (Spalte ist nullable).
    """
    settings = get_settings()
    stmt = (
        select(User)
        .where(User.tenant_id == tenant_id)
        .where(User.email == settings.demo_user_email)
        .limit(1)
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user.id
    stmt_any = select(User).where(User.tenant_id == tenant_id).limit(1)
    fallback_user = (await session.execute(stmt_any)).scalar_one_or_none()
    return fallback_user.id if fallback_user is not None else None


async def _ensure_unique_invoice_number(
    session: AsyncSession, tenant_id: str, candidate: str
) -> str:
    """Findet eine freie invoice_number (Tenant-eindeutig) durch ggf. Suffix-Anbau."""
    base = candidate or f"DEMO-{uuid.uuid4().hex[:8].upper()}"
    base = base[:90]  # 100 ist die DB-Grenze; Platz fuer Suffix lassen
    suffix = 0
    while True:
        check = base if suffix == 0 else f"{base}-{suffix}"
        stmt = (
            select(Invoice.id)
            .where(Invoice.tenant_id == tenant_id)
            .where(Invoice.invoice_number == check)
            .limit(1)
        )
        existing = (await session.execute(stmt)).first()
        if existing is None:
            return check
        suffix += 1


async def _ensure_invoice(
    session: AsyncSession,
    inv_file: InvoiceFile,
    reviewer_id: uuid.UUID | None,
) -> Invoice:
    """Stellt sicher dass es eine Invoice fuer die Datei gibt, gibt sie zurueck."""
    if inv_file.invoice_id is not None:
        existing = await session.get(Invoice, inv_file.invoice_id)
        if existing is not None:
            return existing
        # Hint: invoice_id zeigt ins Leere - wir legen unten neu an und
        # ueberschreiben die Verknuepfung.

    raw_result: dict[str, Any] = (
        inv_file.extraction_result if isinstance(inv_file.extraction_result, dict) else {}
    )

    vendor_name = (
        str(raw_result.get("vendor_name") or "").strip()
        or _extract_vendor_from_filename(inv_file.filename)
    )[:255]

    invoice_number_candidate = str(
        raw_result.get("invoice_number") or inv_file.filename.rsplit(".", 1)[0]
    ).strip()
    invoice_number = await _ensure_unique_invoice_number(
        session, inv_file.tenant_id, invoice_number_candidate
    )

    invoice_date_val = _coerce_date(raw_result.get("invoice_date")) or FALLBACK_INVOICE_DATE
    total = _coerce_decimal(raw_result.get("total_amount")) or FALLBACK_TOTAL
    net = _coerce_decimal(raw_result.get("net_amount")) or FALLBACK_NET
    tax = _coerce_decimal(raw_result.get("tax_amount")) or FALLBACK_TAX
    currency = str(raw_result.get("currency") or FALLBACK_CURRENCY)[:3].upper()

    new_invoice = Invoice(
        tenant_id=inv_file.tenant_id,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=invoice_date_val,
        total_amount=total,
        currency=currency,
        net_amount=net,
        tax_amount=tax,
        status=InvoiceStatus.RECEIVED,
        is_reviewed=True,
        reviewed_at=datetime.now(tz=UTC),
        reviewed_by_user_id=reviewer_id,
    )
    session.add(new_invoice)
    await session.flush()

    inv_file.invoice_id = new_invoice.id
    await session.flush()

    logger.info(
        "force_review.invoice_created",
        filename=inv_file.filename,
        invoice_id=str(new_invoice.id),
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        total_amount=str(total),
    )
    return new_invoice


async def _force_review_for_file(
    session: AsyncSession,
    inv_file: InvoiceFile,
    reviewer_id: uuid.UUID | None,
) -> None:
    invoice = await _ensure_invoice(session, inv_file, reviewer_id)

    already_reviewed = invoice.is_reviewed is True
    invoice.is_reviewed = True
    if invoice.reviewed_at is None:
        invoice.reviewed_at = datetime.now(tz=UTC)
    if invoice.reviewed_by_user_id is None and reviewer_id is not None:
        invoice.reviewed_by_user_id = reviewer_id

    if not invoice.vendor_name:
        invoice.vendor_name = _extract_vendor_from_filename(inv_file.filename)
    if invoice.invoice_date is None:
        invoice.invoice_date = FALLBACK_INVOICE_DATE
    if invoice.total_amount is None or Decimal(invoice.total_amount) <= 0:
        invoice.total_amount = FALLBACK_TOTAL
    if invoice.net_amount is None:
        invoice.net_amount = FALLBACK_NET
    if invoice.tax_amount is None:
        invoice.tax_amount = FALLBACK_TAX
    if not invoice.currency:
        invoice.currency = FALLBACK_CURRENCY

    await session.flush()

    logger.info(
        "force_review.applied",
        filename=inv_file.filename,
        invoice_id=str(invoice.id),
        already_reviewed=already_reviewed,
        vendor_name=invoice.vendor_name,
        invoice_date=invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        total_amount=str(invoice.total_amount),
    )


async def main() -> None:
    settings = get_settings()
    tenant_id = settings.demo_tenant_id

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as session:
        async with session.begin():
            reviewer_id = await _pick_reviewer(session, tenant_id)
            files = await _find_target_files(session, tenant_id)

            if not files:
                logger.warning(
                    "force_review.no_files_found",
                    tenant_id=tenant_id,
                    patterns=TARGET_NAME_PATTERNS,
                )
                print(
                    "Keine Dateien passend zu den Mustern "
                    f"{TARGET_NAME_PATTERNS} im Tenant '{tenant_id}' gefunden."
                )
                return

            print(
                f"{len(files)} Datei(en) im Tenant '{tenant_id}' gefunden:"
            )
            for inv_file in files:
                print(f"  - {inv_file.filename}  (id={inv_file.id})")
                await _force_review_for_file(session, inv_file, reviewer_id)

            print("Alle Ziel-Dateien wurden auf 'gepr\u00fcft' gesetzt und sind nun exportierbar.")


if __name__ == "__main__":
    asyncio.run(main())
