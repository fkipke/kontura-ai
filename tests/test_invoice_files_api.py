"""Integration-Tests fuer die Invoice-Files-API (G2.0).

Prueft:
- Upload-Validierung (Groesse, MIME-Type, Magic-Bytes, Filename-Sanitisierung)
- Deduplication (gleiche Datei zweimal hochladen -> 200 + selbe ID)
- Tenant-Isolation (Tenant A sieht NIEMALS Dateien von Tenant B)
- Round-trip: Upload -> Download (Bytes gleich, Content-Type korrekt)
- List-Endpoint mit Tenant-Isolation

Alle Tests sind async und verwenden die bestehenden conftest.py-Fixtures.
"""

import pytest
from httpx import AsyncClient

from kontura.api.invoice_files.router import _ALLOWED_MIME_TYPES, _check_magic_bytes
from tests.conftest import auth_headers

# --- Test-Fixtures: Header fuer zwei Tenants ---

TENANT_A_HEADERS = auth_headers("acme-corp")
TENANT_B_HEADERS = auth_headers("other-corp")

# --- Minimale valide Testdaten fuer verschiedene Formate ---

# Minimal gueltiger PDF-Header (Magic-Bytes genuegen fuer den Test)
MINIMAL_PDF = b"%PDF-1.4\n%%EOF\n"
# Minimal gueltiger PNG-Header (8 Magic-Bytes + IHDR-Chunk-Anfang)
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
# Minimal gueltiger JPEG-Header (SOI + App0 Marker)
MINIMAL_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 12
MINIMAL_XML = b'<?xml version="1.0" encoding="UTF-8"?><Invoice></Invoice>'

UPLOAD_URL = "/api/v1/invoice-files"


def _pdf_file(filename: str = "test.pdf") -> dict[str, tuple[str, bytes, str]]:
    """Erstellt ein multipart/form-data-Feld fuer den Upload."""
    return {"file": (filename, MINIMAL_PDF, "application/pdf")}


def _png_file(filename: str = "test.png") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (filename, MINIMAL_PNG, "image/png")}


def _jpeg_file(filename: str = "test.jpg") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (filename, MINIMAL_JPEG, "image/jpeg")}


def _xml_file(
    filename: str = "test.xml",
    content: bytes = MINIMAL_XML,
    mime_type: str = "application/xml",
) -> dict[str, tuple[str, bytes, str]]:
    return {"file": (filename, content, mime_type)}


# =============================================================================
# 1. Happy Path - Verschiedene Formate
# =============================================================================


@pytest.mark.asyncio
async def test_upload_pdf_returns_201_and_persists(client: AsyncClient) -> None:
    """PDF-Upload gibt 201 zurueck und persistiert den Eintrag in der DB."""
    response = await client.post(UPLOAD_URL, files=_pdf_file(), headers=TENANT_A_HEADERS)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["filename"] == "test.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(MINIMAL_PDF)
    assert len(body["sha256"]) == 64
    assert "id" in body
    assert body["deduplicated"] is False


@pytest.mark.asyncio
async def test_upload_png_returns_201(client: AsyncClient) -> None:
    """PNG-Upload gibt 201 zurueck."""
    response = await client.post(UPLOAD_URL, files=_png_file(), headers=TENANT_A_HEADERS)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mime_type"] == "image/png"
    assert body["deduplicated"] is False


@pytest.mark.asyncio
async def test_upload_jpeg_returns_201(client: AsyncClient) -> None:
    """JPEG-Upload gibt 201 zurueck."""
    response = await client.post(UPLOAD_URL, files=_jpeg_file(), headers=TENANT_A_HEADERS)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mime_type"] == "image/jpeg"
    assert body["deduplicated"] is False


@pytest.mark.asyncio
async def test_upload_xml_returns_201(client: AsyncClient) -> None:
    """XML-Upload gibt 201 zurueck."""
    response = await client.post(UPLOAD_URL, files=_xml_file(), headers=TENANT_A_HEADERS)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mime_type"] == "application/xml"
    assert body["deduplicated"] is False


# =============================================================================
# 2. Validierung - Groesse, MIME-Type, Magic-Bytes
# =============================================================================


@pytest.mark.asyncio
async def test_upload_oversized_returns_413(client: AsyncClient) -> None:
    """Datei groesser als INVOICE_FILE_MAX_BYTES wird mit 413 abgelehnt."""
    # 11 MB - deutlich ueber dem 10-MB-Limit
    oversized_content = b"%PDF-" + b"x" * (11 * 1024 * 1024)
    big_file = {"file": ("big.pdf", oversized_content, "application/pdf")}
    response = await client.post(UPLOAD_URL, files=big_file, headers=TENANT_A_HEADERS)
    assert response.status_code == 413, response.text


@pytest.mark.asyncio
async def test_upload_wrong_mime_returns_415(client: AsyncClient) -> None:
    """Nicht erlaubter MIME-Type (text/plain) wird mit 415 abgelehnt."""
    txt_file = {"file": ("note.txt", b"Some plain text content", "text/plain")}
    response = await client.post(UPLOAD_URL, files=txt_file, headers=TENANT_A_HEADERS)
    assert response.status_code == 415, response.text


@pytest.mark.asyncio
async def test_upload_extension_spoof_returns_415(client: AsyncClient) -> None:
    """Magic-Byte-Pruefung: Textinhalt mit Content-Type application/pdf -> 415.

    Extension-Spoofing: Jemand gibt an, es sei ein PDF, aber der Inhalt
    beginnt nicht mit '%PDF-'. Der Magic-Byte-Check schlaegt an.
    """
    spoofed_file = {"file": ("malicious.pdf", b"This is not a PDF, just text", "application/pdf")}
    response = await client.post(UPLOAD_URL, files=spoofed_file, headers=TENANT_A_HEADERS)
    assert response.status_code == 415, response.text


def test_xml_mime_types_are_allowed() -> None:
    """XML-MIME-Types stehen auf der Upload-Whitelist."""
    assert {"application/xml", "text/xml"} <= _ALLOWED_MIME_TYPES


@pytest.mark.parametrize(
    ("content", "mime_type"),
    [
        (MINIMAL_XML, "application/xml"),
        (b"\xef\xbb\xbf<?xml version='1.0'?><Invoice />", "application/xml"),
        (b"\n  <Invoice></Invoice>", "application/xml"),
        (b"<rsm:CrossIndustryInvoice></rsm:CrossIndustryInvoice>", "text/xml"),
        (
            b"\xff\xfe<\x00?\x00x\x00m\x00l\x00 \x00v\x00e\x00r\x00s\x00i\x00o\x00n\x00=\x00"
            b'"\x001\x00.\x000\x00"\x00?\x00>\x00<\x00I\x00n\x00v\x00o\x00i\x00c\x00e\x00/\x00>\x00',
            "application/xml",
        ),
    ],
)
def test_check_magic_bytes_accepts_xml_variants(content: bytes, mime_type: str) -> None:
    """XML-Validierung akzeptiert gaengige Header-, BOM- und Root-Element-Varianten."""
    assert _check_magic_bytes(content, mime_type) is True


@pytest.mark.parametrize("mime_type", ["application/xml", "text/xml"])
def test_check_magic_bytes_rejects_non_xml_for_xml_mime(mime_type: str) -> None:
    """Nicht-XML-Inhalt wird trotz XML-MIME-Type abgelehnt."""
    assert _check_magic_bytes(b"This is definitely not XML", mime_type) is False


# =============================================================================
# 3. Deduplication
# =============================================================================


@pytest.mark.asyncio
async def test_upload_same_file_twice_is_deduplicated(client: AsyncClient) -> None:
    """Gleiche Datei zweimal hochladen: zweiter Upload gibt 200 + selbe ID zurueck.

    Nur 1 Zeile in der DB (Deduplication via UniqueConstraint tenant_id + sha256).
    """
    first = await client.post(UPLOAD_URL, files=_pdf_file(), headers=TENANT_A_HEADERS)
    assert first.status_code == 201

    second = await client.post(UPLOAD_URL, files=_pdf_file(), headers=TENANT_A_HEADERS)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["deduplicated"] is True
    assert second.headers.get("X-Deduplicated") == "true"

    # Verifizieren: List zeigt nur 1 Eintrag (kein Duplikat in DB)
    list_resp = await client.get(UPLOAD_URL, headers=TENANT_A_HEADERS)
    assert len(list_resp.json()) == 1


# =============================================================================
# 4. Tenant-Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_list_returns_only_own_tenant_files(client: AsyncClient) -> None:
    """KRITISCH: Tenant A sieht NIEMALS Dateien von Tenant B in der Liste."""
    # Tenant A laedt eine PDF hoch
    r_a = await client.post(UPLOAD_URL, files=_pdf_file("a.pdf"), headers=TENANT_A_HEADERS)
    assert r_a.status_code == 201

    # Tenant B laedt eine andere Datei hoch (anderer Inhalt, keine Dedup zwischen Tenants)
    b_content = b"%PDF-1.4\n%% Tenant B Dokument\n%%EOF\n"
    r_b = await client.post(
        UPLOAD_URL,
        files={"file": ("b.pdf", b_content, "application/pdf")},
        headers=TENANT_B_HEADERS,
    )
    assert r_b.status_code == 201

    # Tenant A listet: nur eigene Datei
    list_a = await client.get(UPLOAD_URL, headers=TENANT_A_HEADERS)
    assert list_a.status_code == 200
    ids_a = [item["id"] for item in list_a.json()]
    assert r_a.json()["id"] in ids_a
    assert r_b.json()["id"] not in ids_a

    # Tenant B listet: nur eigene Datei
    list_b = await client.get(UPLOAD_URL, headers=TENANT_B_HEADERS)
    assert list_b.status_code == 200
    ids_b = [item["id"] for item in list_b.json()]
    assert r_b.json()["id"] in ids_b
    assert r_a.json()["id"] not in ids_b


# =============================================================================
# 5. Download (GET /invoice-files/{file_id})
# =============================================================================


@pytest.mark.asyncio
async def test_get_by_id_returns_bytes_with_correct_mime(
    client: AsyncClient,
) -> None:
    """Round-trip: Upload -> Download -> Bytes und Content-Type stimmen ueberein."""
    upload = await client.post(UPLOAD_URL, files=_pdf_file(), headers=TENANT_A_HEADERS)
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    download = await client.get(f"{UPLOAD_URL}/{file_id}", headers=TENANT_A_HEADERS)
    assert download.status_code == 200, download.text
    assert download.content == MINIMAL_PDF
    assert download.headers["content-type"] == "application/pdf"
    assert "test.pdf" in download.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_get_by_id_other_tenant_returns_404(client: AsyncClient) -> None:
    """KRITISCH: Tenant B darf nicht via UUID auf Dateien von Tenant A zugreifen.

    Kein Info-Leak: Wir geben 404 zurueck, nicht 403 - so weiss Tenant B nicht,
    ob die Datei existiert oder nicht.
    """
    upload = await client.post(UPLOAD_URL, files=_pdf_file(), headers=TENANT_A_HEADERS)
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    # Tenant B versucht, Datei von Tenant A abzurufen -> 404 (kein Info-Leak)
    response = await client.get(f"{UPLOAD_URL}/{file_id}", headers=TENANT_B_HEADERS)
    assert response.status_code == 404
