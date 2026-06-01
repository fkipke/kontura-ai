"""Integration-Tests fuer PATCH /invoices/{id} (G3.2).

Prueft:
1.  Happy Path: gueltige Werte → 200, Felder geupdated, version=2, Audit-Eintraege
2.  Optimistic Lock Konflikt: veraltete version → 409 mit current_version + current_state
3.  Optimistic Lock Erfolg: korrekte version → 200
4.  USt-Mismatch + is_reviewed=true → 200 OK, is_reviewed=true gespeichert, Warning NICHT 422
5.  USt-Mismatch ohne is_reviewed → 200 mit Warning
6.  Zukunftsdatum → 422
7.  Tenant-Isolation: Tenant B sieht Tenant-A-Invoice nicht → 404
8.  Audit-Trail: jedes Feld erzeugt genau einen invoice_edits-Eintrag
9.  line_items-Snapshot: ganzes Array als old_value/new_value
10. line_items ungeaendert → kein Audit-Eintrag
11. Unsupported Currency → 422
12. Auth fehlt → 401
13. Rate-Limit-Header vorhanden (slowapi-Smoketest)
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_USER_IDS_BY_TENANT, auth_headers

TENANT_A_HEADERS = auth_headers("acme-corp")
TENANT_B_HEADERS = auth_headers("other-corp")

BASE_INVOICE = {
    "invoice_number": "RE-G32-001",
    "vendor_name": "Testlieferant GmbH",
    "invoice_date": "2025-01-15",
    "total_amount": "119.00",
    "currency": "EUR",
}


async def _create_invoice(client: AsyncClient) -> dict:  # type: ignore[type-arg]
    """Hilfsfunktion: legt eine Testrechnung an und gibt den Response-Body zurueck."""
    resp = await client.post("/invoices", json=BASE_INVOICE, headers=TENANT_A_HEADERS)
    assert resp.status_code == 201, f"Setup-Fehler beim Anlegen der Rechnung: {resp.text}"
    return resp.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Test 1: Happy Path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_invoice_happy_path(client: AsyncClient, session: AsyncSession) -> None:
    """PATCH mit gueltigen Werten → 200, Felder geupdated, version=2, Audit-Eintraege."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    payload = {
        "expected_version": 1,
        "vendor_name": "Neuer Lieferant AG",
        "net_amount": "100.00",
        "tax_amount": "19.00",
    }
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["vendor_name"] == "Neuer Lieferant AG"
    assert body["version"] == 2
    assert body["net_amount"] == "100.00"
    assert body["tax_amount"] == "19.00"
    assert "validation_warnings" in body

    # Audit-Eintraege pruefen
    result = await session.execute(
        text("SELECT field FROM invoice_edits WHERE invoice_id = :inv_id ORDER BY field"),
        {"inv_id": invoice_id},
    )
    rows = result.fetchall()
    fields = [r[0] for r in rows]
    assert "vendor_name" in fields
    assert "net_amount" in fields
    assert "tax_amount" in fields


# ---------------------------------------------------------------------------
# Test 2: Optimistic Lock Konflikt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_optimistic_lock_conflict(client: AsyncClient, session: AsyncSession) -> None:
    """Version stimmt nicht ueberein → 409 mit current_version und current_state."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    # Version in DB direkt erhoehen (simuliert parallelen Edit)
    await session.execute(
        text("UPDATE invoices SET version = 2 WHERE id = :inv_id"),
        {"inv_id": invoice_id},
    )
    await session.commit()

    payload = {"expected_version": 1, "vendor_name": "Verspaetet"}
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 409, resp.text

    body = resp.json()
    assert body["current_version"] == 2
    assert "current_state" in body
    assert body["current_state"]["id"] == invoice_id


# ---------------------------------------------------------------------------
# Test 3: Optimistic Lock Erfolg
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_optimistic_lock_success(client: AsyncClient) -> None:
    """Korrekte expected_version → 200."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    payload = {"expected_version": 1, "vendor_name": "Richtig aktualisiert"}
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["vendor_name"] == "Richtig aktualisiert"


# ---------------------------------------------------------------------------
# Test 4: USt-Mismatch + is_reviewed=true → 200 (KRITISCH: NIEMALS 422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ust_mismatch_with_is_reviewed_returns_200(
    client: AsyncClient, session: AsyncSession
) -> None:
    """USt-Mismatch blockiert NICHT. is_reviewed=true wird gespeichert. Warning vorhanden."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    payload = {
        "expected_version": 1,
        "net_amount": "100.00",
        "tax_amount": "10.00",
        "total_amount": "130.00",  # Mismatch: 100+10=110 ≠ 130
        "is_reviewed": True,
    }
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)

    # KRITISCHES Akzeptanzkriterium: MUSS 200 sein, NIEMALS 422
    assert resp.status_code == 200, (
        f"USt-Mismatch darf NICHT 422 ergeben! Response: {resp.status_code} - {resp.text}"
    )

    body = resp.json()
    assert body["is_reviewed"] is True, "is_reviewed muss trotz USt-Mismatch gespeichert werden"
    assert body["reviewed_at"] is not None

    warnings = body["validation_warnings"]
    assert len(warnings) > 0, "USt-Mismatch-Warning fehlt"
    codes = [w["code"] for w in warnings]
    assert "ust_total_mismatch" in codes

    # In DB pruefen
    result = await session.execute(
        text("SELECT is_reviewed FROM invoices WHERE id = :inv_id"),
        {"inv_id": invoice_id},
    )
    row = result.fetchone()
    assert row is not None and row[0] is True, "is_reviewed muss in DB gespeichert sein"


# ---------------------------------------------------------------------------
# Test 5: USt-Mismatch ohne is_reviewed → 200 mit Warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ust_mismatch_without_reviewed_returns_200_with_warning(
    client: AsyncClient,
) -> None:
    """USt-Mismatch ohne is_reviewed → 200, Warning im Array."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    payload = {
        "expected_version": 1,
        "net_amount": "100.00",
        "tax_amount": "10.00",
        "total_amount": "130.00",
    }
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    warnings = body["validation_warnings"]
    assert any(w["code"] == "ust_total_mismatch" for w in warnings)
    assert body["is_reviewed"] is False  # Kein is_reviewed gesetzt


# ---------------------------------------------------------------------------
# Test 6: Zukunftsdatum → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_future_invoice_date_returns_422(client: AsyncClient) -> None:
    """invoice_date in der Zukunft → 422 Hard-Validation."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    future_date = (date.today() + timedelta(days=7)).isoformat()
    payload = {"expected_version": 1, "invoice_date": future_date}
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Test 7: Tenant-Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_other_tenant_returns_404(client: AsyncClient) -> None:
    """Tenant B versucht Tenant-A-Invoice zu aendern → 404 (kein Info-Leak)."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    payload = {"expected_version": 1, "vendor_name": "Hacker AG"}
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_B_HEADERS)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Test 8: Audit-Trail-Invarianten
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_trail_per_field(client: AsyncClient, session: AsyncSession) -> None:
    """Jedes geaenderte Feld → genau ein invoice_edits-Eintrag mit korrekten Werten."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]
    expected_user_id = TEST_USER_IDS_BY_TENANT["acme-corp"]

    payload = {
        "expected_version": 1,
        "vendor_name": "Audit Lieferant GmbH",
        "total_amount": "200.00",
    }
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 200, resp.text

    result = await session.execute(
        text(
            "SELECT field, old_value, new_value, user_id, created_at "
            "FROM invoice_edits WHERE invoice_id = :inv_id ORDER BY field"
        ),
        {"inv_id": invoice_id},
    )
    rows = result.fetchall()
    assert len(rows) == 2, f"Erwartet 2 Audit-Eintraege, gefunden: {len(rows)}"

    fields_found = {r[0] for r in rows}
    assert fields_found == {"vendor_name", "total_amount"}

    for row in rows:
        field, old_val, new_val, user_id_str, created_at = row
        assert user_id_str is not None
        assert str(user_id_str) == expected_user_id, f"user_id falsch fuer {field}"
        assert created_at is not None
        assert old_val is not None
        assert new_val is not None

        if field == "vendor_name":
            assert old_val["value"] == BASE_INVOICE["vendor_name"]
            assert new_val["value"] == "Audit Lieferant GmbH"
        elif field == "total_amount":
            assert old_val["value"] == BASE_INVOICE["total_amount"]
            assert new_val["value"] == "200.00"


# ---------------------------------------------------------------------------
# Test 9: line_items-Snapshot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_line_items_snapshot_audit(client: AsyncClient, session: AsyncSession) -> None:
    """line_items-Aenderung → ganzes Array in old_value/new_value als JSONB."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    items_v1 = [
        {"description": "Pos 1", "quantity": "1", "unit_price": "100.00", "total_price": "100.00"},
        {"description": "Pos 2", "quantity": "2", "unit_price": "50.00", "total_price": "100.00"},
    ]
    # Erst line_items setzen
    resp = await client.patch(
        f"/invoices/{invoice_id}",
        json={"expected_version": 1, "line_items": items_v1},
        headers=TENANT_A_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 2

    # Jetzt Pos 2 aendern
    items_v2 = [
        {"description": "Pos 1", "quantity": "1", "unit_price": "100.00", "total_price": "100.00"},
        {
            "description": "Pos 2 NEU",
            "quantity": "3",
            "unit_price": "50.00",
            "total_price": "150.00",
        },
    ]
    resp2 = await client.patch(
        f"/invoices/{invoice_id}",
        json={"expected_version": 2, "line_items": items_v2},
        headers=TENANT_A_HEADERS,
    )
    assert resp2.status_code == 200, resp2.text

    # Audit-Eintrag fuer line_items pruefen
    result = await session.execute(
        text(
            "SELECT old_value, new_value FROM invoice_edits "
            "WHERE invoice_id = :inv_id AND field = 'line_items' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"inv_id": invoice_id},
    )
    row = result.fetchone()
    assert row is not None, "Kein Audit-Eintrag fuer line_items"

    old_val, new_val = row
    # Ganzes Array (nicht nur ein Item) muss im Snapshot sein
    assert "value" in old_val
    assert isinstance(old_val["value"], list)
    assert len(old_val["value"]) == 2  # Beide Items des alten Stands

    assert "value" in new_val
    assert isinstance(new_val["value"], list)
    assert len(new_val["value"]) == 2  # Beide Items des neuen Stands


# ---------------------------------------------------------------------------
# Test 10: line_items ungeaendert → kein Audit-Eintrag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_line_items_unchanged_no_audit(client: AsyncClient, session: AsyncSession) -> None:
    """Gleiche line_items erneut senden → kein Audit-Eintrag."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    items = [
        {"description": "Pos 1", "quantity": "1", "unit_price": "50.00", "total_price": "50.00"}
    ]

    # Erst setzen
    await client.patch(
        f"/invoices/{invoice_id}",
        json={"expected_version": 1, "line_items": items},
        headers=TENANT_A_HEADERS,
    )

    # Gleiche Daten nochmal senden
    resp = await client.patch(
        f"/invoices/{invoice_id}",
        json={"expected_version": 2, "line_items": items},
        headers=TENANT_A_HEADERS,
    )
    assert resp.status_code == 200, resp.text

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM invoice_edits WHERE invoice_id = :inv_id AND field = 'line_items'"
        ),
        {"inv_id": invoice_id},
    )
    count = result.scalar()
    # Nur der erste Edit soll einen Eintrag haben (None → items), nicht der zweite (items → items)
    assert count == 1, f"Erwartet 1 Audit-Eintrag fuer line_items, gefunden: {count}"


# ---------------------------------------------------------------------------
# Test 11: Unsupported Currency → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsupported_currency_returns_422(client: AsyncClient) -> None:
    """GBP ist nicht in der Whitelist → 422."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    payload = {"expected_version": 1, "currency": "GBP"}
    resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Test 12: Auth fehlt → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_without_auth_returns_401(client: AsyncClient) -> None:
    """Kein JWT → 401."""
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/invoices/{fake_id}",
        json={"expected_version": 1, "vendor_name": "Test"},
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Test 13: Rate-Limit-Header vorhanden (slowapi-Smoketest)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_has_rate_limit_headers(client: AsyncClient) -> None:
    """200-Response enthaelt X-RateLimit-*-Header (beweist response: Response-Parameter)."""
    from kontura.api.rate_limit import limiter

    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    # Rate-Limiting fuer diesen Test aktivieren
    limiter.enabled = True
    try:
        payload = {"expected_version": 1, "vendor_name": "Rate-Limit-Test"}
        resp = await client.patch(f"/invoices/{invoice_id}", json=payload, headers=TENANT_A_HEADERS)
        assert resp.status_code == 200, resp.text
        # slowapi setzt diese Header wenn rate limiting aktiv ist
        rl_headers = {k: v for k, v in resp.headers.items() if "ratelimit" in k.lower()}
        assert len(rl_headers) > 0, (
            f"Keine X-RateLimit-Header gefunden. Response-Headers: {dict(resp.headers)}"
        )
    finally:
        limiter.enabled = False


# ---------------------------------------------------------------------------
# Test: Bestehendes GET /{id} liefert jetzt InvoiceResponse mit version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_invoice_returns_version_field(client: AsyncClient) -> None:
    """GET /invoices/{id} liefert version und is_reviewed (InvoiceResponse)."""
    inv = await _create_invoice(client)
    invoice_id = inv["id"]

    resp = await client.get(f"/invoices/{invoice_id}", headers=TENANT_A_HEADERS)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "version" in body, "GET muss version-Feld enthalten (fuer optimistic locking im FE)"
    assert body["version"] == 1
    assert "is_reviewed" in body
    assert body["is_reviewed"] is False
    assert "validation_warnings" in body
