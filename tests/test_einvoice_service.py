from __future__ import annotations

from io import BytesIO
from typing import Any

import fitz
import pytest
from fastapi import BackgroundTasks
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.infra.models.invoice_file import InvoiceFile
from tests.conftest import FakeAIProvider, auth_headers

BASE_URL = "/api/v1/invoice-files"
TENANT_A_HEADERS = auth_headers("acme-corp")
TENANT_B_HEADERS = auth_headers("other-corp")

UBL_MINIMAL = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID>
  <cbc:ID>RE-2026-001</cbc:ID>
  <cbc:IssueDate>2026-05-15</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>ACME Lieferant GmbH</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount currencyID="EUR">100.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">119.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount>
  </cac:TaxTotal>
</Invoice>"""


# MINIMUM profil
UBL_MINIMUM = UBL_MINIMAL.replace(
    "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
    "urn:factur-x.eu:1p0:minimum",
)


def _make_valid_pdf_bytes() -> bytes:
    doc = fitz.open()
    doc.new_page()
    buffer = BytesIO()
    try:
        doc.save(buffer)
    finally:
        doc.close()
    return buffer.getvalue()


def _make_zugferd_pdf(xml_bytes: bytes) -> bytes:
    doc = fitz.open()
    doc.new_page()
    doc.embfile_add("factur-x.xml", xml_bytes)
    buffer = BytesIO()
    try:
        doc.save(buffer)
    finally:
        doc.close()
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_xrechnung_ubl_upload_creates_invoice_synchronously(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    fake_ai_provider: FakeAIProvider,
) -> None:
    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def _spy_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        queued.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _spy_add_task)

    response = await client.post(
        BASE_URL,
        files={"file": ("xrechnung.xml", UBL_MINIMAL.encode("utf-8"), "application/xml")},
        headers=TENANT_A_HEADERS,
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["extraction_status"] == "completed"
    assert body["extraction_method"] == "xrechnung_ubl"
    assert queued == []
    assert fake_ai_provider.extract_call_count == 0


@pytest.mark.asyncio
async def test_zugferd_pdf_upload_creates_invoice_synchronously(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def _spy_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        queued.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _spy_add_task)

    pdf = _make_zugferd_pdf(UBL_MINIMAL.encode("utf-8"))
    response = await client.post(
        BASE_URL,
        files={"file": ("zugferd.pdf", pdf, "application/pdf")},
        headers=TENANT_A_HEADERS,
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["extraction_status"] == "completed"
    assert body["extraction_method"] == "zugferd_v2"
    assert queued == []


@pytest.mark.asyncio
async def test_zugferd_minimum_profile_stored_in_extraction_result(
    client: AsyncClient,
) -> None:
    pdf = _make_zugferd_pdf(UBL_MINIMUM.encode("utf-8"))
    upload = await client.post(
        BASE_URL,
        files={"file": ("zugferd-minimum.pdf", pdf, "application/pdf")},
        headers=TENANT_A_HEADERS,
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=TENANT_A_HEADERS)
    assert status_resp.status_code == 200
    result = status_resp.json()["result"]
    assert result is not None
    assert result["zugferd_profile"] == "minimum"


@pytest.mark.asyncio
async def test_plain_pdf_upload_falls_back_to_ai_pipeline(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def _spy_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        queued.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _spy_add_task)

    response = await client.post(
        BASE_URL,
        files={"file": ("plain.pdf", _make_valid_pdf_bytes(), "application/pdf")},
        headers=TENANT_A_HEADERS,
    )
    assert response.status_code == 201
    assert response.json()["extraction_status"] == "pending"
    assert len(queued) == 1


@pytest.mark.asyncio
async def test_duplicate_invoice_number_does_not_raise_integrity_error(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def _spy_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        queued.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _spy_add_task)

    first = await client.post(
        BASE_URL,
        files={"file": ("first.xml", UBL_MINIMAL.encode("utf-8"), "application/xml")},
        headers=TENANT_A_HEADERS,
    )
    second = await client.post(
        BASE_URL,
        files={
            "file": (
                "second.xml",
                (UBL_MINIMAL + "\n<!--different bytes-->\n").encode("utf-8"),
                "application/xml",
            )
        },
        headers=TENANT_A_HEADERS,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert queued == []

    first_status = await client.get(
        f"{BASE_URL}/{first.json()['id']}/extraction", headers=TENANT_A_HEADERS
    )
    second_status = await client.get(
        f"{BASE_URL}/{second.json()['id']}/extraction", headers=TENANT_A_HEADERS
    )

    assert first_status.status_code == 200
    assert second_status.status_code == 200
    assert first_status.json()["linked_invoice_id"] == second_status.json()["linked_invoice_id"]


@pytest.mark.asyncio
async def test_einvoice_parse_failure_falls_back_to_ai(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def _spy_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        queued.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _spy_add_task)

    broken = b"<?xml version='1.0'?><Invoice><broken>"
    response = await client.post(
        BASE_URL,
        files={"file": ("broken.xml", broken, "application/xml")},
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["extraction_status"] == "pending"
    assert len(queued) == 1


@pytest.mark.asyncio
async def test_tenant_isolation_einvoice_invoice(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def _spy_add_task(self: BackgroundTasks, func: Any, *args: Any, **kwargs: Any) -> None:
        queued.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _spy_add_task)

    a = await client.post(
        BASE_URL,
        files={"file": ("a.xml", UBL_MINIMAL.encode("utf-8"), "application/xml")},
        headers=TENANT_A_HEADERS,
    )
    b = await client.post(
        BASE_URL,
        files={"file": ("b.xml", UBL_MINIMAL.encode("utf-8"), "application/xml")},
        headers=TENANT_B_HEADERS,
    )

    assert a.status_code == 201
    assert b.status_code == 201
    assert queued == []

    a_status = await client.get(f"{BASE_URL}/{a.json()['id']}/extraction", headers=TENANT_A_HEADERS)
    b_status = await client.get(f"{BASE_URL}/{b.json()['id']}/extraction", headers=TENANT_B_HEADERS)

    assert a_status.status_code == 200
    assert b_status.status_code == 200
    assert a_status.json()["linked_invoice_id"] != b_status.json()["linked_invoice_id"]

    file_rows = (
        (
            await session.execute(
                select(InvoiceFile).where(InvoiceFile.id.in_([a.json()["id"], b.json()["id"]]))
            )
        )
        .scalars()
        .all()
    )
    assert {row.tenant_id for row in file_rows} == {"acme-corp", "other-corp"}
