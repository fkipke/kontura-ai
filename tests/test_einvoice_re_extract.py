from __future__ import annotations

import uuid
from typing import cast

import fitz
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice_file import ExtractionMethod, ExtractionStatus, InvoiceFile
from tests.conftest import FakeAIProvider, auth_headers

BASE_URL = "/api/v1/invoice-files"
HEADERS = auth_headers("acme-corp")

UBL_MINIMAL = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>RE-2026-REEXTRACT</cbc:ID>
  <cbc:IssueDate>2026-06-01</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>Bauer Consulting GmbH</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:TaxTotal><cbc:TaxAmount>19.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount>100.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount>119.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
</Invoice>
"""


def _make_pdf(*, attachment_name: str | None = None, payload: bytes | None = None) -> bytes:
    doc = fitz.open()
    try:
        doc.new_page()
        if attachment_name and payload is not None:
            doc.embfile_add(attachment_name, payload, filename=attachment_name)
        return cast(bytes, doc.tobytes())
    finally:
        doc.close()


async def _set_legacy_failed_status(session: AsyncSession, file_id: str) -> None:
    file_uuid = uuid.UUID(file_id)
    result = await session.execute(select(InvoiceFile).where(InvoiceFile.id == file_uuid))
    invoice_file = result.scalar_one()
    invoice_file.extraction_status = ExtractionStatus.FAILED
    invoice_file.extraction_error = "invalid_image_format"
    invoice_file.extraction_result = None
    invoice_file.invoice_id = None
    invoice_file.extraction_method = ExtractionMethod.AI_VISION
    invoice_file.extraction_attempts = 1
    await session.commit()


@pytest.mark.asyncio
async def test_re_extract_heals_old_failed_xml_invoice(
    client: AsyncClient,
    session: AsyncSession,
    fake_ai_provider: FakeAIProvider,
) -> None:
    upload = await client.post(
        BASE_URL,
        files={"file": ("RE_1.xml", UBL_MINIMAL.encode("utf-8"), "application/xml")},
        headers=HEADERS,
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    await _set_legacy_failed_status(session, file_id)

    call_count_before = fake_ai_provider.extract_call_count
    response = await client.post(f"{BASE_URL}/{file_id}/extract", headers=HEADERS)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["vendor_name"] == "Bauer Consulting GmbH"
    assert body["result"]["invoice_number"] == "RE-2026-REEXTRACT"
    assert fake_ai_provider.extract_call_count == call_count_before


@pytest.mark.asyncio
async def test_re_extract_xml_with_invalid_content_returns_failed_without_ai_call(
    client: AsyncClient,
    session: AsyncSession,
    fake_ai_provider: FakeAIProvider,
) -> None:
    invalid_xml = b'<?xml version="1.0" encoding="UTF-8"?><Root><Only>Invalid</Only></Root>'
    upload = await client.post(
        BASE_URL,
        files={"file": ("broken.xml", invalid_xml, "application/xml")},
        headers=HEADERS,
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    await _set_legacy_failed_status(session, file_id)

    call_count_before = fake_ai_provider.extract_call_count
    response = await client.post(f"{BASE_URL}/{file_id}/extract", headers=HEADERS)
    assert response.status_code == 202

    body = response.json()
    assert body["status"] == "failed"
    assert "XML konnte nicht als E-Rechnung interpretiert werden" in (body["error"] or "")
    assert fake_ai_provider.extract_call_count == call_count_before


@pytest.mark.asyncio
async def test_re_extract_zugferd_pdf_falls_through_to_einvoice(
    client: AsyncClient,
    session: AsyncSession,
    fake_ai_provider: FakeAIProvider,
) -> None:
    zugferd_pdf = _make_pdf(attachment_name="factur-x.xml", payload=UBL_MINIMAL.encode("utf-8"))
    upload = await client.post(
        BASE_URL,
        files={"file": ("zugferd.pdf", zugferd_pdf, "application/pdf")},
        headers=HEADERS,
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    await _set_legacy_failed_status(session, file_id)

    call_count_before = fake_ai_provider.extract_call_count
    response = await client.post(f"{BASE_URL}/{file_id}/extract", headers=HEADERS)
    assert response.status_code == 202

    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["vendor_name"] == "Bauer Consulting GmbH"
    assert body["result"]["invoice_number"] == "RE-2026-REEXTRACT"
    assert fake_ai_provider.extract_call_count == call_count_before


@pytest.mark.asyncio
async def test_re_extract_normal_pdf_still_uses_ai(
    client: AsyncClient,
    session: AsyncSession,
    fake_ai_provider: FakeAIProvider,
) -> None:
    plain_pdf = _make_pdf()
    upload = await client.post(
        BASE_URL,
        files={"file": ("plain.pdf", plain_pdf, "application/pdf")},
        headers=HEADERS,
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    await _set_legacy_failed_status(session, file_id)

    call_count_before = fake_ai_provider.extract_call_count
    response = await client.post(f"{BASE_URL}/{file_id}/extract?force=true", headers=HEADERS)
    assert response.status_code == 202
    assert response.json()["status"] == "completed"
    assert fake_ai_provider.extract_call_count > call_count_before
