"""Integration-Tests fuer DATEV-EXTF-Export (G4.0)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.rate_limit import limiter
from kontura.core.config import settings
from kontura.infra.models.invoice import Invoice
from tests.conftest import auth_headers

TENANT_A_HEADERS = auth_headers("acme-corp")
TENANT_B_HEADERS = auth_headers("other-corp")


@pytest.fixture(autouse=True)
def _datev_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "datev_consultant_number", 12345)
    monkeypatch.setattr(settings, "datev_client_number", 67890)
    monkeypatch.setattr(settings, "datev_fiscal_year_start", date(2026, 1, 1))
    monkeypatch.setattr(settings, "datev_account_length", 4)
    monkeypatch.setattr(settings, "datev_default_expense_account", 3400)
    monkeypatch.setattr(settings, "datev_default_creditor_account", 70000)


async def _make_invoice(
    session: AsyncSession,
    *,
    tenant_id: str = "acme-corp",
    invoice_number: str = "RE-2026-001",
    vendor_name: str = "Musterlieferant GmbH",
    invoice_date: date = date(2026, 3, 15),
    total_amount: Decimal = Decimal("1190.00"),
    currency: str = "EUR",
    is_reviewed: bool = True,
) -> Invoice:
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=invoice_date,
        total_amount=total_amount,
        currency=currency,
        is_reviewed=is_reviewed,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


def _rows_from_response(response_body: bytes) -> list[list[str]]:
    decoded = response_body.decode("cp1252")
    reader = csv.reader(io.StringIO(decoded), delimiter=";", quotechar='"')
    return list(reader)


@pytest.mark.asyncio
async def test_export_happy_path_one_invoice(client: AsyncClient, session: AsyncSession) -> None:
    await _make_invoice(session)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=windows-1252"
    assert response.headers["x-datev-invoice-count"] == "1"
    rows = _rows_from_response(response.content)
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_export_header_fields_match_datev_spec(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    header_row = response.content.decode("cp1252").split("\r\n")[0].split(";")
    assert header_row[0] == '"EXTF"'
    assert header_row[1] == "700"
    assert header_row[2] == "21"
    assert header_row[3] == '"Buchungsstapel"'
    assert header_row[4] == "13"
    assert header_row[10] == "12345"
    assert header_row[11] == "67890"
    assert header_row[12] == "20260101"
    assert header_row[14] == "20260101"
    assert header_row[15] == "20260331"


@pytest.mark.asyncio
async def test_export_column_header_row_exact(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    second_line = response.content.decode("cp1252").split("\r\n")[1]
    assert (
        second_line == '"Umsatz (ohne Soll/Haben-Kz)";"Soll/Haben-Kennzeichen";"WKZ Umsatz";"Kurs";'
        '"Basisumsatz";"WKZ Basisumsatz";"Konto";"Gegenkonto (ohne BU-Schlüssel)";'
        '"BU-Schlüssel";"Belegdatum";"Belegfeld 1";"Belegfeld 2";"Skonto";"Buchungstext"'
    )


@pytest.mark.asyncio
async def test_export_data_row_field_mapping(client: AsyncClient, session: AsyncSession) -> None:
    await _make_invoice(
        session,
        invoice_number="RE-2026-777",
        vendor_name="Alpha GmbH",
        invoice_date=date(2026, 3, 15),
        total_amount=Decimal("1190.00"),
        currency="EUR",
    )

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    data_row = _rows_from_response(response.content)[2]
    assert data_row == [
        "1190,00",
        "S",
        "EUR",
        "",
        "",
        "",
        "3400",
        "70000",
        "",
        "1503",
        "RE-2026-777",
        "",
        "",
        "Alpha GmbH RE-2026-777",
    ]


@pytest.mark.asyncio
async def test_export_decimal_format_uses_comma_not_dot(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, total_amount=Decimal("1234.56"))

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    data_row = _rows_from_response(response.content)[2]
    assert data_row[0] == "1234,56"


@pytest.mark.asyncio
async def test_export_belegdatum_is_ttmm_format(client: AsyncClient, session: AsyncSession) -> None:
    await _make_invoice(session, invoice_date=date(2026, 3, 15))

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    data_row = _rows_from_response(response.content)[2]
    assert data_row[9] == "1503"


@pytest.mark.asyncio
async def test_export_charset_cp1252_with_umlauts(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, vendor_name="Müller & Söhne GmbH")

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    assert b"M\xfcller & S\xf6hne GmbH" in response.content
    assert response.content.decode("cp1252")


@pytest.mark.asyncio
async def test_export_quotes_in_strings_are_doubled(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, vendor_name='Restaurant "Zur Krone"', invoice_number="RE-42")

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    decoded = response.content.decode("cp1252")
    assert '"Restaurant ""Zur Krone"" RE-42"' in decoded


@pytest.mark.asyncio
async def test_export_crlf_line_endings(client: AsyncClient, session: AsyncSession) -> None:
    await _make_invoice(session)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    assert b"\r\n" in response.content
    assert b"\n" not in response.content.replace(b"\r\n", b"")


@pytest.mark.asyncio
async def test_export_excludes_unreviewed_invoices(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, invoice_number="RE-OK", is_reviewed=True)
    await _make_invoice(session, invoice_number="RE-NOK", is_reviewed=False)

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    rows = _rows_from_response(response.content)
    assert response.headers["x-datev-invoice-count"] == "1"
    assert rows[2][10] == "RE-OK"


@pytest.mark.asyncio
async def test_export_tenant_isolation(client: AsyncClient, session: AsyncSession) -> None:
    await _make_invoice(session, tenant_id="acme-corp", invoice_number="RE-A")
    await _make_invoice(session, tenant_id="other-corp", invoice_number="RE-B")

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    rows = _rows_from_response(response.content)
    assert response.headers["x-datev-invoice-count"] == "1"
    assert rows[2][10] == "RE-A"


@pytest.mark.asyncio
async def test_export_date_range_filter_inclusive(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, invoice_number="RE-START", invoice_date=date(2026, 1, 1))
    await _make_invoice(session, invoice_number="RE-END", invoice_date=date(2026, 3, 31))
    await _make_invoice(session, invoice_number="RE-OUT", invoice_date=date(2026, 4, 1))

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    rows = _rows_from_response(response.content)
    belegfelder = [row[10] for row in rows[2:]]
    assert belegfelder == ["RE-START", "RE-END"]


@pytest.mark.asyncio
async def test_export_empty_result_returns_200_with_header_only(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 200
    assert response.headers["x-datev-invoice-count"] == "0"
    lines = response.content.decode("cp1252").split("\r\n")
    non_empty = [line for line in lines if line != ""]
    assert len(non_empty) == 2


@pytest.mark.asyncio
async def test_export_from_greater_than_to_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/exports/datev?from=2026-03-01&to=2026-01-01",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_range_over_one_year_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/exports/datev?from=2025-01-01&to=2026-06-01",
        headers=TENANT_A_HEADERS,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_export_no_auth_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/exports/datev?from=2026-01-01&to=2026-03-31")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_content_disposition_filename(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
        headers=TENANT_A_HEADERS,
    )

    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="EXTF_Buchungsstapel_20260101_20260331.csv"'
    )


@pytest.mark.asyncio
async def test_export_invoice_outside_fiscal_year_is_skipped(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(session, invoice_number="RE-IN", invoice_date=date(2026, 5, 1))
    await _make_invoice(session, invoice_number="RE-OUT", invoice_date=date(2027, 1, 1))

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2027-01-01",
        headers=TENANT_A_HEADERS,
    )

    rows = _rows_from_response(response.content)
    belegfelder = [row[10] for row in rows[2:]]
    assert response.headers["x-datev-invoice-count"] == "1"
    assert response.headers["x-datev-skipped-count"] == "1"
    assert belegfelder == ["RE-IN"]


@pytest.mark.asyncio
async def test_export_buchungstext_truncated_to_60_chars(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _make_invoice(
        session,
        vendor_name=(
            "Sehr sehr langer Lieferantenname mit vielen Woertern fuer den Exporttext GmbH"
        ),
        invoice_number="RE-LONG-TEXT-2026",
    )

    response = await client.get(
        "/api/v1/exports/datev?from=2026-01-01&to=2026-12-31",
        headers=TENANT_A_HEADERS,
    )

    data_row = _rows_from_response(response.content)[2]
    assert len(data_row[13]) <= 60


@pytest.mark.asyncio
async def test_export_rate_limited_after_n_calls(client: AsyncClient) -> None:
    limiter.enabled = True
    try:
        last_status = 200
        for _ in range(75):
            response = await client.get(
                "/api/v1/exports/datev?from=2026-01-01&to=2026-03-31",
                headers=TENANT_A_HEADERS,
            )
            last_status = response.status_code
            if response.status_code == 429:
                break

        assert last_status == 429
    finally:
        limiter.enabled = False
