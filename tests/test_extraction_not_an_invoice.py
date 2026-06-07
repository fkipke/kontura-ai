"""Tests fuer Cluster 1.2: NOT_AN_INVOICE Extraktion-Status-Heuristik."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.extraction.service import ExtractionService, _format_validation_error_de
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice_file import ExtractionStatus, InvoiceFile
from tests.conftest import FakeAIProvider


def _make_invoice_file(tenant_id: str) -> InvoiceFile:
    f = InvoiceFile(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        filename="test.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256="a" * 64,
        storage_path=f"{tenant_id}/aa/{'a' * 64}",
    )
    f.extraction_attempts = 0
    return f


@pytest.mark.asyncio
async def test_all_null_payload_sets_not_an_invoice(session: AsyncSession, tmp_path: Any) -> None:
    """Wenn LLM alle kritischen Felder None zurueckgibt -> NOT_AN_INVOICE."""
    from kontura.infra.storage import LocalFilesystemStorage  # noqa: PLC0415

    storage = LocalFilesystemStorage(base_dir=str(tmp_path))
    tenant = TenantContext(tenant_id="acme-corp")

    # Datei anlegen
    inv_file = _make_invoice_file("acme-corp")
    session.add(inv_file)
    await session.commit()
    await session.refresh(inv_file)

    # Storage befuellen
    await storage.save("acme-corp", "a" * 64, b"%PDF-1.4 fake content")

    fake_ai = FakeAIProvider()
    fake_ai.extraction_return_value = {
        "invoice_number": None,
        "vendor_name": None,
        "total_amount": None,
        "invoice_date": None,
        "currency": "EUR",
        "net_amount": None,
        "tax_amount": None,
        "line_items": [],
        "vendor_address": None,
        "due_date": None,
        "confidence_notes": None,
    }

    service = ExtractionService(ai_provider=fake_ai, storage=storage, session=session)
    result = await service.extract(tenant, inv_file.id)

    assert result.extraction_status == ExtractionStatus.NOT_AN_INVOICE
    assert result.extraction_error is not None
    assert "Rechnung" in result.extraction_error
    assert "Rechnungsfelder" in result.extraction_error


@pytest.mark.asyncio
async def test_partial_missing_sets_failed(session: AsyncSession, tmp_path: Any) -> None:
    """Wenn nur invoice_date fehlt (nicht alle kritischen Felder) -> FAILED mit kurzem Text."""
    from kontura.infra.storage import LocalFilesystemStorage  # noqa: PLC0415

    storage = LocalFilesystemStorage(base_dir=str(tmp_path))
    tenant = TenantContext(tenant_id="acme-corp")

    inv_file = _make_invoice_file("acme-corp")
    session.add(inv_file)
    await session.commit()
    await session.refresh(inv_file)

    await storage.save("acme-corp", "a" * 64, b"%PDF-1.4 fake content")

    fake_ai = FakeAIProvider()
    # invoice_number and vendor_name and total_amount present, but invoice_date is invalid
    fake_ai.extraction_return_value = {
        "invoice_number": "RE-2024-001",
        "vendor_name": "Test GmbH",
        "total_amount": "119.00",
        "invoice_date": "not-a-date",  # This will cause ValidationError
        "currency": "EUR",
        "net_amount": "100.00",
        "tax_amount": "19.00",
        "line_items": [],
        "vendor_address": None,
        "due_date": None,
        "confidence_notes": None,
    }

    service = ExtractionService(ai_provider=fake_ai, storage=storage, session=session)
    result = await service.extract(tenant, inv_file.id)

    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.extraction_error is not None
    # Should have short German summary, NOT a raw Pydantic dump
    assert "Extraktion fehlgeschlagen" in result.extraction_error
    assert "Folgende Felder" in result.extraction_error
    # Must NOT expose raw Pydantic internals
    assert "ValidationError" not in result.extraction_error
    assert "validation_error" not in result.extraction_error


def test_format_validation_error_de_returns_field_list() -> None:
    """_format_validation_error_de liefert deutsche Feldliste ohne Pydantic-Dump."""
    from pydantic import ValidationError  # noqa: PLC0415

    from kontura.ai.extraction.schemas import ExtractedInvoiceData  # noqa: PLC0415

    try:
        ExtractedInvoiceData.model_validate(
            {"invoice_number": "X", "vendor_name": "Y", "invoice_date": "bad", "total_amount": "Z"}
        )
    except ValidationError as exc:
        msg = _format_validation_error_de(exc)
        assert "Folgende Felder" in msg
        # Field names must be present, not Pydantic internals
        assert "ValidationError" not in msg


@pytest.mark.asyncio
async def test_cross_tenant_not_an_invoice_invisible(
    client: Any, session: AsyncSession, tmp_path: Any
) -> None:
    """NOT_AN_INVOICE-Datei von Tenant A ist fuer Tenant B nicht sichtbar (404)."""

    from tests.conftest import auth_headers  # noqa: PLC0415

    inv_file = _make_invoice_file("acme-corp")
    inv_file.extraction_status = ExtractionStatus.NOT_AN_INVOICE
    session.add(inv_file)
    await session.commit()
    await session.refresh(inv_file)

    # Tenant B tries to get tenant A's file
    resp = await client.get(
        f"/api/v1/invoice-files/{inv_file.id}",
        headers=auth_headers("other-corp"),
    )
    assert resp.status_code == 404
