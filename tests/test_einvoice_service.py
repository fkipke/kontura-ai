from __future__ import annotations

import io
from decimal import Decimal

import fitz
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice import Invoice
from tests.conftest import FakeAIProvider, auth_headers

BASE_URL = "/api/v1/invoice-files"
HEADERS_A = auth_headers("acme-corp")
HEADERS_B = auth_headers("other-corp")

MINIMAL_PDF = b"%PDF-1.4\n%%EOF\n"

UBL_MINIMAL = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID>
  <cbc:ID>RE-2026-001</cbc:ID>
  <cbc:IssueDate>2026-05-15</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party><cac:PartyName><cbc:Name>ACME Lieferant GmbH</cbc:Name></cac:PartyName></cac:Party>
  </cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount>100.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount>119.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:TaxTotal><cbc:TaxAmount>19.00</cbc:TaxAmount></cac:TaxTotal>
</Invoice>"""

UBL_MINIMUM_PROFILE = UBL_MINIMAL.replace(
    b"urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
    b"urn:factur-x.eu:1p0:minimum",
)


def _build_zugferd_pdf(xml_bytes: bytes) -> bytes:
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.embfile_add("factur-x.xml", xml_bytes, filename="factur-x.xml")
    try:
        return bytes(doc.tobytes())
    finally:
        doc.close()


def _xml_file(payload: bytes, name: str = "invoice.xml") -> dict[str, tuple[str, io.BytesIO, str]]:
    return {"file": (name, io.BytesIO(payload), "application/xml")}


def _pdf_file(payload: bytes, name: str = "invoice.pdf") -> dict[str, tuple[str, io.BytesIO, str]]:
    return {"file": (name, io.BytesIO(payload), "application/pdf")}


@pytest.mark.asyncio
async def test_xrechnung_ubl_upload_creates_invoice_synchronously(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
    session: AsyncSession,
) -> None:
    resp = await client.post(BASE_URL, files=_xml_file(UBL_MINIMAL), headers=HEADERS_A)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["extraction_status"] == "completed"
    assert body["extraction_method"] == "xrechnung_ubl"
    assert fake_ai_provider.extract_call_count == 0

    invoice = (
        await session.execute(
            select(Invoice).where(
                Invoice.tenant_id == "acme-corp",
                Invoice.invoice_number == "RE-2026-001",
            )
        )
    ).scalar_one_or_none()
    assert invoice is not None
    assert invoice.total_amount == Decimal("119.00")


@pytest.mark.asyncio
async def test_zugferd_pdf_upload_creates_invoice_synchronously(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    pdf_bytes = _build_zugferd_pdf(UBL_MINIMAL)
    resp = await client.post(BASE_URL, files=_pdf_file(pdf_bytes), headers=HEADERS_A)
    assert resp.status_code == 201
    body = resp.json()
    assert body["extraction_status"] == "completed"
    assert body["extraction_method"] == "zugferd_v2"
    assert fake_ai_provider.extract_call_count == 0


@pytest.mark.asyncio
async def test_zugferd_minimum_profile_stored_in_extraction_result(client: AsyncClient) -> None:
    pdf_bytes = _build_zugferd_pdf(UBL_MINIMUM_PROFILE)
    upload = await client.post(
        BASE_URL, files=_pdf_file(pdf_bytes, "minimum.pdf"), headers=HEADERS_A
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_A)
    assert status_resp.status_code == 200
    assert status_resp.json()["result"]["zugferd_profile"] == "minimum"


@pytest.mark.asyncio
async def test_plain_pdf_upload_falls_back_to_ai_pipeline(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    resp = await client.post(BASE_URL, files=_pdf_file(MINIMAL_PDF, "plain.pdf"), headers=HEADERS_A)
    assert resp.status_code == 201
    assert resp.json()["extraction_status"] == "pending"
    assert fake_ai_provider.extract_call_count >= 1


@pytest.mark.asyncio
async def test_duplicate_invoice_number_links_existing_invoice_no_overwrite(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    first = await client.post(
        BASE_URL, files=_xml_file(UBL_MINIMAL, "first.xml"), headers=HEADERS_A
    )
    assert first.status_code == 201

    second_payload = UBL_MINIMAL.replace(
        b"ACME Lieferant GmbH",
        b"Anderer Lieferant GmbH",
    )
    second = await client.post(
        BASE_URL, files=_xml_file(second_payload, "second.xml"), headers=HEADERS_A
    )
    assert second.status_code == 201

    invoices_count = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.tenant_id == "acme-corp", Invoice.invoice_number == "RE-2026-001")
        )
    ).scalar_one()
    assert invoices_count == 1

    invoice = (
        await session.execute(
            select(Invoice).where(
                Invoice.tenant_id == "acme-corp",
                Invoice.invoice_number == "RE-2026-001",
            )
        )
    ).scalar_one()
    assert invoice.vendor_name == "ACME Lieferant GmbH"


@pytest.mark.asyncio
async def test_einvoice_parse_failure_falls_back_to_ai(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    broken_xml = b"<Invoice><broken></Invoice>"
    resp = await client.post(BASE_URL, files=_xml_file(broken_xml, "broken.xml"), headers=HEADERS_A)
    assert resp.status_code == 201
    assert resp.json()["extraction_status"] == "pending"
    assert fake_ai_provider.extract_call_count >= 1


@pytest.mark.asyncio
async def test_tenant_isolation_einvoice_invoice(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    upload_a = await client.post(BASE_URL, files=_xml_file(UBL_MINIMAL, "a.xml"), headers=HEADERS_A)
    assert upload_a.status_code == 201

    invoice_a = (
        await session.execute(
            select(Invoice).where(
                Invoice.tenant_id == "acme-corp",
                Invoice.invoice_number == "RE-2026-001",
            )
        )
    ).scalar_one_or_none()
    assert invoice_a is not None

    invoice_b = (
        await session.execute(
            select(Invoice).where(
                Invoice.tenant_id == "other-corp",
                Invoice.invoice_number == "RE-2026-001",
            )
        )
    ).scalar_one_or_none()
    assert invoice_b is None

    upload_b = await client.post(BASE_URL, files=_xml_file(UBL_MINIMAL, "b.xml"), headers=HEADERS_B)
    assert upload_b.status_code == 201
