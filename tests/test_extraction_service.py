"""Tests fuer ExtractionService.

Testet den Service direkt ohne HTTP-Layer.
FakeAIProvider simuliert LLM-Aufrufe.
LocalFilesystemStorage mit tmp_path als isoliertes Datei-Verzeichnis.
"""

from __future__ import annotations

import hashlib
import pathlib
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.extraction.service import ExtractionService
from kontura.api.invoice_files.repository import InvoiceFileRepository
from kontura.core.exceptions import NotFoundError
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_file import ExtractionStatus, InvoiceFile
from kontura.infra.storage import LocalFilesystemStorage
from tests.conftest import FakeAIProvider

TENANT_A = TenantContext(tenant_id="acme-corp")
TENANT_B = TenantContext(tenant_id="other-corp")

# Minimales valides PNG (1x1 Pixel)
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x11\x00\x01F\x80\xa7d\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def fake_provider() -> FakeAIProvider:
    return FakeAIProvider()


@pytest.fixture
def storage(tmp_path: pathlib.Path) -> LocalFilesystemStorage:
    return LocalFilesystemStorage(base_dir=str(tmp_path / "files"))


async def _create_invoice_file(
    session: AsyncSession,
    storage: LocalFilesystemStorage,
    tenant: TenantContext,
    content: bytes = _PNG_BYTES,
    mime_type: str = "image/png",
    user_id: str = "11111111-1111-1111-1111-111111111111",
) -> InvoiceFile:
    """Hilfsfunktion: legt InvoiceFile in DB und Storage an."""
    sha256 = hashlib.sha256(content).hexdigest()
    storage_path = await storage.save(tenant.tenant_id, sha256, content)
    repo = InvoiceFileRepository(session)
    inv_file = await repo.create(
        tenant=tenant,
        uploaded_by_user_id=uuid.UUID(user_id),
        filename="rechnung.png",
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=sha256,
        storage_path=storage_path,
    )
    await session.commit()
    await session.refresh(inv_file)
    return inv_file


@pytest.mark.asyncio
async def test_extract_png_success_creates_invoice_and_links(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """Happy-Path: PNG hochgeladen, LLM aufgerufen, Invoice angelegt und gelinkt."""
    inv_file = await _create_invoice_file(session, storage, TENANT_A)

    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)
    result = await service.extract(TENANT_A, inv_file.id)

    assert result.extraction_status == ExtractionStatus.COMPLETED
    assert result.invoice_id is not None
    assert result.extraction_result is not None
    assert result.extraction_result["invoice_number"] == "RE-2024-001"
    assert result.extracted_at is not None
    assert result.extraction_error is None
    assert result.extraction_attempts == 1
    assert fake_provider.extract_call_count == 1

    # Invoice wurde angelegt
    from sqlalchemy import select

    stmt = select(Invoice).where(
        Invoice.tenant_id == TENANT_A.tenant_id,
        Invoice.invoice_number == "RE-2024-001",
    )
    res = await session.execute(stmt)
    invoice = res.scalar_one_or_none()
    assert invoice is not None
    assert invoice.vendor_name == "Test GmbH"
    assert invoice.total_amount == Decimal("119.00")
    assert invoice.status == InvoiceStatus.PROCESSING


@pytest.mark.asyncio
async def test_extract_existing_invoice_number_links_no_duplicate(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """Existierende Invoice mit gleicher invoice_number: link statt Duplikat anlegen."""
    # Invoice vorab anlegen
    existing_invoice = Invoice(
        tenant_id=TENANT_A.tenant_id,
        invoice_number="RE-2024-001",
        vendor_name="Alt GmbH",
        invoice_date=date(2020, 1, 1),
        total_amount=Decimal("500.00"),
        currency="EUR",
        status=InvoiceStatus.RECEIVED,
    )
    session.add(existing_invoice)
    await session.commit()
    await session.refresh(existing_invoice)

    inv_file = await _create_invoice_file(session, storage, TENANT_A)
    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)
    result = await service.extract(TENANT_A, inv_file.id)

    assert result.extraction_status == ExtractionStatus.COMPLETED
    assert result.invoice_id == existing_invoice.id  # gelinkt, nicht neu

    # Kein Duplikat: nur eine Invoice mit dieser Nummer
    from sqlalchemy import func, select

    count_stmt = (
        select(func.count())
        .select_from(Invoice)
        .where(
            Invoice.tenant_id == TENANT_A.tenant_id,
            Invoice.invoice_number == "RE-2024-001",
        )
    )
    count = (await session.execute(count_stmt)).scalar_one()
    assert count == 1

    # Original nicht ueberschrieben
    await session.refresh(existing_invoice)
    assert existing_invoice.vendor_name == "Alt GmbH"


@pytest.mark.asyncio
async def test_extract_idempotent_no_force(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """Zweiter Extract-Call auf 'completed' ohne force: No-op (kein LLM-Aufruf)."""
    inv_file = await _create_invoice_file(session, storage, TENANT_A)
    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)

    # Erster Aufruf
    await service.extract(TENANT_A, inv_file.id)
    assert fake_provider.extract_call_count == 1

    # Zweiter Aufruf ohne force
    result = await service.extract(TENANT_A, inv_file.id, force=False)
    assert result.extraction_status == ExtractionStatus.COMPLETED
    assert fake_provider.extract_call_count == 1  # NICHT erneut aufgerufen


@pytest.mark.asyncio
async def test_extract_force_reruns_and_overwrites_result(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """force=True erzwingt Re-Extraktion, auch wenn Status bereits 'completed'."""
    inv_file = await _create_invoice_file(session, storage, TENANT_A)
    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)

    # Erster Aufruf
    await service.extract(TENANT_A, inv_file.id)
    assert fake_provider.extract_call_count == 1

    # Zweiter Aufruf mit force
    result = await service.extract(TENANT_A, inv_file.id, force=True)
    assert result.extraction_status == ExtractionStatus.COMPLETED
    assert fake_provider.extract_call_count == 2  # erneut aufgerufen


@pytest.mark.asyncio
async def test_extract_llm_error_sets_failed_status(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """LLM-Fehler: Status wird auf 'failed' gesetzt, Exception geht NICHT nach aussen."""
    fake_provider.extraction_return_value = RuntimeError("OpenAI API nicht erreichbar")

    inv_file = await _create_invoice_file(session, storage, TENANT_A)
    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)

    # Kein Exception nach aussen
    result = await service.extract(TENANT_A, inv_file.id)

    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.extraction_error is not None
    assert "OpenAI API nicht erreichbar" in result.extraction_error


@pytest.mark.asyncio
async def test_extract_invalid_schema_response_sets_failed(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """Fehlende Pflichtfelder im LLM-Output: ValidationError -> Status 'failed'."""
    # Pflichtfeld 'invoice_number' fehlt
    fake_provider.extraction_return_value = {
        "vendor_name": "Broken GmbH",
        "invoice_date": "2024-01-15",
        "total_amount": "100.00",
        # invoice_number fehlt!
    }

    inv_file = await _create_invoice_file(session, storage, TENANT_A)
    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)

    result = await service.extract(TENANT_A, inv_file.id)

    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.extraction_error is not None


@pytest.mark.asyncio
async def test_extract_tenant_isolation(
    session: AsyncSession,
    fake_provider: FakeAIProvider,
    storage: LocalFilesystemStorage,
    test_user: None,  # noqa: ARG001
) -> None:
    """Service mit Tenant B auf Datei von Tenant A: NotFoundError."""
    inv_file = await _create_invoice_file(session, storage, TENANT_A)
    service = ExtractionService(ai_provider=fake_provider, storage=storage, session=session)

    with pytest.raises(NotFoundError):
        await service.extract(TENANT_B, inv_file.id)

    # LLM wurde nicht aufgerufen
    assert fake_provider.extract_call_count == 0
