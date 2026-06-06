"""E2E-Tests fuer den synchronen E-Invoice-Pfad im Upload-Endpoint."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import fitz
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeAIProvider, auth_headers

HEADERS = auth_headers("acme-corp")

UBL_MINIMAL = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Invoice xmlns=\"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2\"
         xmlns:cac=\"urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2\"
         xmlns:cbc=\"urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2\">
  <cbc:CustomizationID>urn:factur-x.eu:1p0:minimum</cbc:CustomizationID>
  <cbc:ID>RE-2026-XML</cbc:ID>
  <cbc:IssueDate>2026-06-01</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>Müller Beratung GmbH</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:TaxTotal><cbc:TaxAmount>190.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount>1000.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount>1190.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
</Invoice>
"""


class AIProviderSpy:
    def __init__(self, extract_structured: AsyncMock) -> None:
        self.extract_structured = extract_structured


@pytest.fixture
def test_client(client: AsyncClient) -> AsyncClient:
    return client


@pytest.fixture
def test_db(session: AsyncSession) -> AsyncSession:
    return session


@pytest.fixture
def test_storage(tmp_path: Path) -> object:
    return tmp_path


@pytest.fixture
def mock_ai_provider_spy(fake_ai_provider: FakeAIProvider) -> Generator[AIProviderSpy, None, None]:
    original = fake_ai_provider.extract_structured
    mocked = AsyncMock(side_effect=original)
    object.__setattr__(fake_ai_provider, "extract_structured", mocked)
    yield AIProviderSpy(mocked)


def _make_pdf(*, attachment_name: str | None = None, payload: bytes | None = None) -> bytes:
    doc = fitz.open()
    try:
        doc.new_page()
        if attachment_name and payload is not None:
            doc.embfile_add(attachment_name, payload, filename=attachment_name)
        return cast(bytes, doc.tobytes())
    finally:
        doc.close()


@pytest.mark.asyncio
async def test_xml_upload_completes_synchronously_no_ai_call(
    test_client: AsyncClient,
    test_db: AsyncSession,  # noqa: ARG001
    test_storage: object,  # noqa: ARG001
    mock_ai_provider_spy: AIProviderSpy,
) -> None:
    xml_bytes = UBL_MINIMAL.encode("utf-8")
    response = await test_client.post(
        "/api/v1/invoice-files",
        files={"file": ("test.xml", xml_bytes, "application/xml")},
        headers=HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["extraction_status"] == "completed", (
        f"Expected synchronously completed, got {body['extraction_status']}"
    )
    assert body["extraction_method"] == "xrechnung_ubl", (
        f"Expected xrechnung_ubl, got {body.get('extraction_method')!r}"
    )
    assert mock_ai_provider_spy.extract_structured.call_count == 0, (
        "AI provider was called - the XML fast-path did NOT work!"
    )


@pytest.mark.asyncio
async def test_zugferd_pdf_upload_completes_synchronously_no_ai_call(
    test_client: AsyncClient,
    mock_ai_provider_spy: AIProviderSpy,
) -> None:
    pdf_bytes = _make_pdf(attachment_name="factur-x.xml", payload=UBL_MINIMAL.encode("utf-8"))
    response = await test_client.post(
        "/api/v1/invoice-files",
        files={"file": ("zugferd.pdf", pdf_bytes, "application/pdf")},
        headers=HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["extraction_status"] == "completed"
    assert body["extraction_method"] == "zugferd_v2"
    assert mock_ai_provider_spy.extract_structured.call_count == 0


@pytest.mark.asyncio
async def test_plain_pdf_upload_falls_back_to_ai_pipeline(
    test_client: AsyncClient,
    mock_ai_provider_spy: AIProviderSpy,
) -> None:
    pdf_bytes = _make_pdf()
    response = await test_client.post(
        "/api/v1/invoice-files",
        files={"file": ("plain.pdf", pdf_bytes, "application/pdf")},
        headers=HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["extraction_status"] == "pending"
    assert body.get("extraction_method") is None
    assert mock_ai_provider_spy.extract_structured.call_count >= 1


@pytest.mark.asyncio
async def test_zugferd_minimum_profile_stored_in_extraction_result(
    test_client: AsyncClient,
) -> None:
    pdf_bytes = _make_pdf(attachment_name="Factur-X.XML", payload=UBL_MINIMAL.encode("utf-8"))
    response = await test_client.post(
        "/api/v1/invoice-files",
        files={"file": ("zugferd-profile.pdf", pdf_bytes, "application/pdf")},
        headers=HEADERS,
    )
    assert response.status_code == 201
    file_id = response.json()["id"]

    status_response = await test_client.get(
        f"/api/v1/invoice-files/{file_id}/extraction", headers=HEADERS
    )
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["status"] == "completed"
    assert payload["result"]["zugferd_profile"] == "minimum"
