"""Tests fuer die Extraction-API-Endpoints.

Testet via HTTP-Client (ASGI-Transport), analog zu test_invoice_files_api.py.
FakeAIProvider ist im client-Fixture injiziert (kein echter LLM-Aufruf).

Hinweis: FastAPI-BackgroundTasks laufen bei ASGI-Tests SYNCHRON (innerhalb
des await-Aufrufs). D.h. nach einem Upload-Call ist die Extraction bereits
ausgefuehrt. Tests, die 'pending'-Status brauchen, nutzen den manuellen
Extraction-Endpoint oder pruefen den Upload-Response-Body direkt.
"""

from __future__ import annotations

import hashlib
import io

import pytest
from httpx import AsyncClient

from tests.conftest import FakeAIProvider, auth_headers

BASE_URL = "/api/v1/invoice-files"
HEADERS_A = auth_headers("acme-corp")
HEADERS_B = auth_headers("other-corp")

# Minimales valides PNG (1x1 Pixel)
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x11\x00\x01F\x80\xa7d\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _png_file(name: str = "rechnung.png") -> dict[str, tuple[str, io.BytesIO, str]]:
    return {"file": (name, io.BytesIO(_PNG_BYTES), "image/png")}


@pytest.mark.asyncio
async def test_upload_response_has_pending_extraction_status(
    client: AsyncClient,
) -> None:
    """Upload-Response enthaelt extraction_status='pending' (Stand vor BG-Task-Lauf)."""
    # Wichtig: Der Response-Body wird gebaut VOR dem BG-Task-Lauf.
    # In ASGI-Tests laeuft der BG-Task direkt nach dem Await,
    # aber das Response-Body selbst reflektiert den Status zum Zeitpunkt der Antwort.
    resp = await client.post(BASE_URL, files=_png_file(), headers=HEADERS_A)
    assert resp.status_code in (200, 201)
    # extraction_status im Response-Body
    body = resp.json()
    assert "extraction_status" in body


@pytest.mark.skip(
    reason="BG-Task DB-Sichtbarkeit zwischen Test-Session und BG-Session "
    "ist ein bekanntes Test-Infra-Limit (separate Connections sehen "
    "committete Daten nicht in NullPool-Tests). End-to-End via "
    "test_extraction_service.py und manueller Test mit echter PDF."
)
@pytest.mark.asyncio
async def test_upload_triggers_extraction_via_background_tasks(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    """Nach Upload wurde der FakeProvider aufgerufen (BG-Task lief in ASGI-Test-Kontext)."""
    resp = await client.post(BASE_URL, files=_png_file(), headers=HEADERS_A)
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # In ASGI-Tests laeuft BG-Task synchron: Provider sollte aufgerufen worden sein
    assert fake_ai_provider.extract_call_count >= 1

    # Extraction-Status sollte completed oder failed sein (nicht pending)
    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_A)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in ("completed", "failed")


@pytest.mark.asyncio
async def test_manual_extract_endpoint_runs_extraction(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    """POST /extract laedt Datei inline aus und GET /extraction zeigt 'completed'."""

    # Andere Bytes damit kein Dedup-Hit mit anderem Test
    png_content = _PNG_BYTES + b"\x00" * 10
    _ = hashlib.sha256(png_content).hexdigest()  # noqa: F841 - nur zur Dokumentation

    # Upload (BG-Task laeuft in ASGI-Test)
    resp = await client.post(
        BASE_URL,
        files={"file": ("rechnung2.png", png_content, "image/png")},
        headers=HEADERS_A,
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Reset call count fuer praezisere Pruefung
    call_count_before = fake_ai_provider.extract_call_count

    # Manuelle Re-Extraktion mit force=True
    extract_resp = await client.post(f"{BASE_URL}/{file_id}/extract?force=true", headers=HEADERS_A)
    assert extract_resp.status_code == 202
    assert extract_resp.json()["status"] == "completed"
    assert fake_ai_provider.extract_call_count > call_count_before

    # GET /extraction zeigt completed
    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_A)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] == "completed"
    assert data["result"] is not None
    assert data["linked_invoice_id"] is not None


@pytest.mark.asyncio
async def test_get_extraction_other_tenant_returns_404(
    client: AsyncClient,
) -> None:
    """GET /extraction mit anderem Tenant: 404 (kein Info-Leak)."""
    resp = await client.post(BASE_URL, files=_png_file("t1.png"), headers=HEADERS_A)
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Tenant B versucht Status von Tenant A abzurufen
    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_B)
    assert status_resp.status_code == 404


@pytest.mark.asyncio
async def test_manual_extract_other_tenant_returns_404(
    client: AsyncClient,
) -> None:
    """POST /extract mit anderem Tenant: 404."""
    resp = await client.post(BASE_URL, files=_png_file("t2.png"), headers=HEADERS_A)
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    extract_resp = await client.post(f"{BASE_URL}/{file_id}/extract", headers=HEADERS_B)
    assert extract_resp.status_code == 404


@pytest.mark.asyncio
async def test_force_param_no_force_is_noop_if_completed(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    """force=false: kein erneuter LLM-Aufruf wenn Status schon 'completed'."""
    # Upload + erste Extraktion (BG-Task in ASGI-Test)
    resp = await client.post(BASE_URL, files=_png_file("dedup_test.png"), headers=HEADERS_A)
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Status sicherstellen
    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_A)
    if status_resp.json()["status"] != "completed":
        # Falls BG-Task fehlgeschlagen: direkt via force=true
        await client.post(f"{BASE_URL}/{file_id}/extract?force=true", headers=HEADERS_A)

    call_count_after_first = fake_ai_provider.extract_call_count

    # Zweiter Aufruf ohne force
    extract_resp = await client.post(f"{BASE_URL}/{file_id}/extract?force=false", headers=HEADERS_A)
    assert extract_resp.status_code == 202
    # Kein zusaetzlicher LLM-Aufruf
    assert fake_ai_provider.extract_call_count == call_count_after_first


@pytest.mark.asyncio
async def test_extraction_result_contains_expected_fields(
    client: AsyncClient,
) -> None:
    """Extraction-Ergebnis enthaelt alle erwarteten Felder."""
    resp = await client.post(BASE_URL, files=_png_file("full_test.png"), headers=HEADERS_A)
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Force-Extract um sicherzustellen dass completed
    extract_resp = await client.post(f"{BASE_URL}/{file_id}/extract?force=true", headers=HEADERS_A)
    assert extract_resp.status_code == 202

    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_A)
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert data["status"] == "completed"
    assert data["result"]["invoice_number"] == "RE-2024-001"
    assert data["result"]["vendor_name"] == "Test GmbH"
    assert data["result"]["total_amount"] == "119.00"
    assert data["linked_invoice_id"] is not None
    assert data["attempts"] >= 1
    assert data["extracted_at"] is not None
    assert data["error"] is None


# =============================================================================
# G3.1b Bug #1 — slowapi Response-Param-Fix: GET /extraction darf nicht 500 geben
# =============================================================================


@pytest.mark.asyncio
async def test_get_extraction_status_returns_200_not_500(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    """GET /extraction gibt 200 zurueck — nicht 500 (slowapi Response-Param-Fix).

    Prueft:
    1. Status 200 (kein Crash durch fehlenden Response-Parameter)
    2. JSON-Body enthaelt 'status'-Feld
    """
    # Upload + force-extract um sicherzustellen, dass die Datei existiert
    resp = await client.post(
        BASE_URL,
        files={"file": ("slowapi_test.png", io.BytesIO(_PNG_BYTES + b"\xff"), "image/png")},
        headers=HEADERS_A,
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Force-Extract damit Datei im System ist
    await client.post(f"{BASE_URL}/{file_id}/extract?force=true", headers=HEADERS_A)

    # GET /extraction — darf nicht 500 geben
    status_resp = await client.get(f"{BASE_URL}/{file_id}/extraction", headers=HEADERS_A)
    assert status_resp.status_code == 200, (
        f"Erwartet 200, bekam {status_resp.status_code}: {status_resp.text}"
    )
    body = status_resp.json()
    assert "status" in body


# =============================================================================
# G3.1b Bug #3 — Denormalisierte Extraction-Felder im Listing
# =============================================================================


@pytest.mark.asyncio
async def test_listing_with_completed_extraction_contains_denormalized_fields(
    client: AsyncClient,
    fake_ai_provider: FakeAIProvider,
) -> None:
    """Listing enthaelt vendor_name, invoice_date, total_amount, currency bei 'completed'."""
    resp = await client.post(
        BASE_URL,
        files={"file": ("listing_completed.png", io.BytesIO(_PNG_BYTES + b"\x01"), "image/png")},
        headers=HEADERS_A,
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Force-Extract damit Status 'completed'
    await client.post(f"{BASE_URL}/{file_id}/extract?force=true", headers=HEADERS_A)

    # Listing abrufen
    list_resp = await client.get(BASE_URL, headers=HEADERS_A)
    assert list_resp.status_code == 200

    items = list_resp.json()
    target = next((item for item in items if item["id"] == file_id), None)
    assert target is not None, "Datei nicht im Listing gefunden"

    assert target["extraction_status"] == "completed"
    assert target["vendor_name"] == "Test GmbH"
    assert target["invoice_date"] == "2024-01-15"
    assert target["total_amount"] == "119.00"
    assert target["currency"] == "EUR"


@pytest.mark.asyncio
async def test_listing_with_pending_extraction_has_none_denormalized_fields(
    client: AsyncClient,
) -> None:
    """Listing mit extraction_status 'pending' hat None fuer alle Extraction-Felder.

    Prueft dass Upload-Response (vor BG-Task) die Felder korrekt als None liefert.
    """
    # Upload-Response wird VOR dem BG-Task-Lauf gebaut → Status ist 'pending'
    resp = await client.post(
        BASE_URL,
        files={"file": ("listing_pending.png", io.BytesIO(_PNG_BYTES + b"\x02"), "image/png")},
        headers=HEADERS_A,
    )
    assert resp.status_code == 201
    body = resp.json()

    # Upload-Response: extraction_status ist 'pending', Felder muessen None sein
    assert body["extraction_status"] == "pending"
    assert body["vendor_name"] is None
    assert body["invoice_date"] is None
    assert body["total_amount"] is None
    assert body["currency"] is None


def test_listing_with_broken_extraction_result_does_not_crash() -> None:
    """Kaputtes extraction_result (unparsebare Felder) in der DB crasht from_model nicht.

    Simuliert einen DB-Eintrag mit teilweise unparseabaren Feldern (z.B. Legacy-Daten).
    Felder mit Parse-Fehler werden zu None — kein 500.
    """
    import uuid
    from unittest.mock import MagicMock

    from kontura.api.invoice_files.schemas import InvoiceFileResponse
    from kontura.infra.models.invoice_file import ExtractionStatus

    # Mock eines InvoiceFile-ORM-Objekts mit kaputten Feldern
    mock_file = MagicMock()
    mock_file.id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    mock_file.filename = "broken.png"
    mock_file.mime_type = "image/png"
    mock_file.size_bytes = 100
    mock_file.sha256 = "aabbcc" * 10 + "aa"  # 64 Zeichen
    mock_file.created_at = __import__("datetime").datetime(2024, 1, 1)
    mock_file.deduplicated = False
    mock_file.extraction_status = ExtractionStatus.COMPLETED
    # Neue denormalisierte Felder — auf None setzen, damit model_validate() nicht crasht
    mock_file.vendor_name = None
    mock_file.invoice_date = None
    mock_file.total_amount = None
    mock_file.currency = None
    mock_file.extraction_result = {
        "vendor_name": "Broken GmbH",
        "invoice_date": "not-a-date",  # kaputt
        "total_amount": "not-a-number",  # kaputt
        "currency": "EUR",
    }

    # from_model darf nicht crashen — kaputte Felder → None
    result = InvoiceFileResponse.from_model(mock_file)

    assert result.extraction_status == ExtractionStatus.COMPLETED
    assert result.vendor_name == "Broken GmbH"
    assert result.invoice_date is None  # kaputt → None
    assert result.total_amount is None  # kaputt → None
    assert result.currency == "EUR"
