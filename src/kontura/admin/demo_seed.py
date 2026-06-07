"""Idempotentes Seed-Skript fuer den Demo-Tenant.

Wird aufgerufen von:
- scripts/seed_demo_tenant.py (CLI)
- POST /api/v1/admin/reset-demo (HTTP)
"""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.core.config import Settings
from kontura.core.security import hash_password
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_edit import InvoiceEdit
from kontura.infra.models.invoice_file import ExtractionMethod, ExtractionStatus, InvoiceFile
from kontura.infra.models.user import User

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded German vendor list (no faker dependency)
# ---------------------------------------------------------------------------
DEMO_VENDORS: list[dict[str, str]] = [
    {"name": "Telekom Deutschland GmbH", "category": "Telekommunikation"},
    {"name": "OBI Bau- und Heimwerkermärkte", "category": "Werkzeug/Material"},
    {"name": "Amazon Web Services EMEA SARL", "category": "Cloud-Infrastruktur"},
    {"name": "Steuerberater Dr. Schmidt & Partner", "category": "Beratung"},
    {"name": "Bauer Consulting GmbH", "category": "Beratung"},
    {"name": "DHL Express Germany", "category": "Logistik"},
    {"name": "Strato AG", "category": "Hosting"},
    {"name": "Vodafone GmbH", "category": "Telekommunikation"},
    {"name": "WeWork Deutschland GmbH", "category": "Büro-Miete"},
    {"name": "Conrad Electronic SE", "category": "Elektronik"},
    {"name": "Lexware GmbH & Co. KG", "category": "Software"},
    {"name": "Notariat Dr. Weber", "category": "Beratung"},
]

# Line-item descriptions per category
_CATEGORY_ITEMS: dict[str, list[str]] = {
    "Telekommunikation": [
        "Mobilfunk-Grundgebühr",
        "Datenvolumen-Paket",
        "Roaming-Gebühren",
        "Festnetz-Anschluss",
    ],
    "Werkzeug/Material": [
        "Bohrmaschine Professional",
        "Schraubenset 500-teilig",
        "Montagematerial",
        "Arbeitshandschuhe",
    ],
    "Cloud-Infrastruktur": [
        "EC2-Instanzen",
        "S3-Speicher",
        "RDS-Datenbankdienst",
        "CloudFront CDN",
    ],
    "Beratung": [
        "Strategieberatung (Stunden)",
        "Steuerliche Jahresabschlussbearbeitung",
        "Rechtsberatung",
        "Projektmanagement",
    ],
    "Logistik": [
        "Paketversand Express",
        "Lagergebühren",
        "Zollabfertigung",
        "Kurierdienst",
    ],
    "Hosting": [
        "Webhosting-Jahrespaket",
        "Domain-Registrierung",
        "SSL-Zertifikat",
        "Managed Server",
    ],
    "Büro-Miete": [
        "Büroflächenmiete",
        "Betriebskosten",
        "Parkplatz-Stellplatz",
        "Konferenzraumnutzung",
    ],
    "Elektronik": [
        "Monitor 27 Zoll",
        "Tastatur und Maus",
        "USB-Hub",
        "Netzwerkswitch",
    ],
    "Software": [
        "Lizenz Buchhaltungssoftware",
        "Support-Vertrag",
        "Cloud-Abo Professional",
        "Schulungseinheit",
    ],
}

# Extraction method distribution weights
_METHOD_WEIGHTS = [
    (ExtractionMethod.AI_VISION, 60),
    (ExtractionMethod.XRECHNUNG_UBL, 25),
    (ExtractionMethod.XRECHNUNG_CII, 10),
    (ExtractionMethod.ZUGFERD_V2, 5),
]

# Extraction status distribution weights
_STATUS_WEIGHTS = [
    (ExtractionStatus.COMPLETED, 70),
    (ExtractionStatus.PROCESSING, 20),
    (ExtractionStatus.FAILED, 5),
    (ExtractionStatus.NOT_AN_INVOICE, 5),
]

# VAT rate distribution
_VAT_RATES = [(Decimal("0.19"), 80), (Decimal("0.07"), 15), (Decimal("0"), 5)]


def _weighted_choice(rng: random.Random, choices: list[tuple[Any, int]]) -> Any:
    items, weights = zip(*choices, strict=False)
    return rng.choices(list(items), weights=list(weights), k=1)[0]


def _random_date_in_last_n_months(rng: random.Random, months: int) -> date:
    today = date.today()
    start = today - timedelta(days=months * 30)
    delta = (today - start).days
    return start + timedelta(days=rng.randint(0, delta))


def _lognormal_amount(rng: random.Random) -> Decimal:
    """Gibt einen log-normalen Betrag zwischen 50 und 15000 EUR zurueck."""
    import math  # noqa: PLC0415

    # mu=6.0 (exp(6) ~ 403), sigma=1.2 gives a nice spread
    raw = math.exp(rng.gauss(6.0, 1.2))
    clamped = max(50.0, min(15000.0, raw))
    # Round to 2 decimal places
    return Decimal(f"{clamped:.2f}")


def _generate_line_items(
    rng: random.Random, category: str, total_net: Decimal, n_items: int
) -> list[dict[str, Any]]:
    descriptions = _CATEGORY_ITEMS.get(category, ["Dienstleistung"])
    items = []
    remaining = total_net
    for i in range(n_items):
        if i == n_items - 1:
            amount = remaining
        else:
            frac = Decimal(str(round(rng.uniform(0.1, 0.6), 2)))
            amount = (remaining * frac).quantize(Decimal("0.01"))
            remaining -= amount
        desc = rng.choice(descriptions)
        qty = Decimal(str(rng.randint(1, 5)))
        unit_price = (amount / qty).quantize(Decimal("0.01"))
        items.append(
            {
                "description": desc,
                "quantity": str(qty),
                "unit_price": str(unit_price),
                "total_price": str(amount),
            }
        )
    return items


def _make_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _make_minimal_pdf_bytes(
    vendor_name: str, invoice_number: str, inv_date: date, total: Decimal
) -> bytes:
    """Generiert ein minimales PDF mit PyMuPDF (fitz) - kein neues Dependency."""
    try:
        import fitz  # noqa: PLC0415

        doc = fitz.open()
        page = doc.new_page()
        text = (
            f"RECHNUNG\n\n"
            f"Lieferant: {vendor_name}\n"
            f"Rechnungsnummer: {invoice_number}\n"
            f"Rechnungsdatum: {inv_date.isoformat()}\n"
            f"Gesamtbetrag: {total:.2f} EUR\n"
        )
        page.insert_text((72, 72), text, fontsize=12)
        pdf_bytes: bytes = doc.tobytes()
        doc.close()
        return pdf_bytes
    except Exception:  # noqa: BLE001
        # Fallback: gib ein minimales valides PDF-ähnliches Byte-Array zurueck
        return (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\ntrailer<</Size 4/Root 1 0 R>>\n"
            b"startxref\n0\n%%EOF\n"
        )


async def _wipe_demo_tenant(session: AsyncSession, tenant_id: str) -> None:
    """Loescht alle Daten des Demo-Tenants in FK-sicherer Reihenfolge."""
    await session.execute(delete(InvoiceEdit).where(InvoiceEdit.tenant_id == tenant_id))
    await session.execute(delete(InvoiceFile).where(InvoiceFile.tenant_id == tenant_id))
    await session.execute(delete(Invoice).where(Invoice.tenant_id == tenant_id))
    await session.flush()
    logger.info("demo_seed.wipe_complete", tenant_id=tenant_id)


async def _ensure_demo_user(session: AsyncSession, settings: Settings) -> User:
    """Stellt sicher dass der Demo-User existiert; legt ihn an wenn noetig."""
    stmt = select(User).where(
        User.tenant_id == settings.demo_tenant_id,
        User.email == settings.demo_user_email,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    user = User(
        tenant_id=settings.demo_tenant_id,
        email=settings.demo_user_email,
        password_hash=hash_password(settings.demo_user_password),
        full_name="Demo User",
        email_verified_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    logger.info("demo_seed.user_created", email=settings.demo_user_email)
    return user


async def seed_demo_tenant(
    session: AsyncSession,
    *,
    tenant_id: str,
    settings: Settings,
) -> None:
    """Idempotentes Seeding des Demo-Tenants.

    1. Loescht bestehende Daten des Tenants (FK-Reihenfolge beachten)
    2. Stellt sicher dass der Demo-User existiert
    3. Erstellt 50 Rechnungen mit 12 deutschen Lieferanten
    4. Erstellt passende InvoiceFiles mit Mock-Inhalt
    5. Markiert ~30% als reviewed
    """
    rng = random.Random(42)  # Reproducibility

    # 1. Wipe
    await _wipe_demo_tenant(session, tenant_id)

    # 2. Ensure demo user
    demo_user = await _ensure_demo_user(session, settings)

    # 3. Create 50 invoices
    invoices: list[Invoice] = []
    vendor_counters: dict[str, int] = {}

    for i in range(50):
        vendor = rng.choice(DEMO_VENDORS)
        vendor_name = vendor["name"]
        category = vendor["category"]

        vendor_counters[vendor_name] = vendor_counters.get(vendor_name, 0) + 1

        inv_date = _random_date_in_last_n_months(rng, 6)
        year = inv_date.year
        invoice_number = f"RE-{year}-{i + 1:04d}"

        total_amount = _lognormal_amount(rng)
        vat_rate = _weighted_choice(rng, _VAT_RATES)
        if vat_rate > 0:
            net_amount = (total_amount / (1 + vat_rate)).quantize(Decimal("0.01"))
            tax_amount = (total_amount - net_amount).quantize(Decimal("0.01"))
        else:
            net_amount = total_amount
            tax_amount = Decimal("0.00")

        n_items = rng.randint(1, 5)
        line_items = _generate_line_items(rng, category, net_amount, n_items)

        inv = Invoice(
            tenant_id=tenant_id,
            invoice_number=invoice_number,
            vendor_name=vendor_name,
            invoice_date=inv_date,
            total_amount=total_amount,
            currency="EUR",
            net_amount=net_amount,
            tax_amount=tax_amount,
            status=InvoiceStatus.RECEIVED,
            line_items=line_items,
        )
        session.add(inv)
        invoices.append(inv)

    await session.flush()

    # 4. Mark ~30% as reviewed
    n_reviewed = int(len(invoices) * 0.30)
    reviewed_invoices = rng.sample(invoices, n_reviewed)
    for inv in reviewed_invoices:
        inv.is_reviewed = True
        inv.reviewed_at = datetime.combine(
            inv.invoice_date + timedelta(days=rng.randint(1, 10)),
            datetime.min.time(),
            tzinfo=UTC,
        )
        inv.reviewed_by_user_id = demo_user.id

    await session.flush()

    # 5. Create InvoiceFiles with mock content
    for inv in invoices:
        ext_status = _weighted_choice(rng, _STATUS_WEIGHTS)
        ext_method = _weighted_choice(rng, _METHOD_WEIGHTS)

        pdf_bytes = _make_minimal_pdf_bytes(
            inv.vendor_name, inv.invoice_number, inv.invoice_date, inv.total_amount
        )
        sha256 = _make_sha256(pdf_bytes)
        storage_path = f"{tenant_id}/{sha256[:2]}/{sha256}"

        invoice_file = InvoiceFile(
            tenant_id=tenant_id,
            uploaded_by_user_id=demo_user.id,
            invoice_id=inv.id,
            filename=f"{inv.invoice_number.replace('/', '-')}.pdf",
            mime_type="application/pdf",
            size_bytes=len(pdf_bytes),
            sha256=sha256,
            storage_path=storage_path,
            extraction_status=ext_status,
            extraction_method=ext_method if ext_status == ExtractionStatus.COMPLETED else None,
            extraction_error=(
                "Simulated extraction failure" if ext_status == ExtractionStatus.FAILED else None
            ),
            extracted_at=(
                datetime.combine(
                    inv.invoice_date + timedelta(days=1),
                    datetime.min.time(),
                    tzinfo=UTC,
                )
                if ext_status == ExtractionStatus.COMPLETED
                else None
            ),
            extraction_attempts=1 if ext_status != ExtractionStatus.PENDING else 0,
        )
        session.add(invoice_file)

    await session.flush()
    logger.info(
        "demo_seed.complete",
        tenant_id=tenant_id,
        invoices=len(invoices),
        reviewed=n_reviewed,
    )
