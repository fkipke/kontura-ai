"""DATEV-EXTF Buchungsstapel CSV Writer (pure function, ohne DB/FastAPI)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from kontura.infra.models.invoice import Invoice

_COLUMN_HEADERS = [
    "Umsatz (ohne Soll/Haben-Kz)",
    "Soll/Haben-Kennzeichen",
    "WKZ Umsatz",
    "Kurs",
    "Basisumsatz",
    "WKZ Basisumsatz",
    "Konto",
    "Gegenkonto (ohne BU-Schlüssel)",
    "BU-Schlüssel",
    "Belegdatum",
    "Belegfeld 1",
    "Belegfeld 2",
    "Skonto",
    "Buchungstext",
]


def _quote(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _format_decimal(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(normalized, "f").replace(".", ",")


def _format_ttmm(value: date) -> str:
    return value.strftime("%d%m")


def _truncate_buchungstext(value: str, max_length: int = 60) -> str:
    text = value.strip()
    if len(text) <= max_length:
        return text

    cut_at = text.rfind(" ", 0, max_length)
    if cut_at > 0:
        return text[:cut_at].rstrip()
    return text[:max_length]


def _build_header_row(
    *,
    from_date: date,
    to_date: date,
    consultant_number: int,
    client_number: int,
    fiscal_year_start: date,
    account_length: int,
    created_at: datetime,
) -> str:
    created_timestamp = (
        created_at.strftime("%Y%m%d%H%M%S") + f"{created_at.microsecond // 1000:03d}"
    )

    fields = [
        _quote("EXTF"),
        "700",
        "21",
        _quote("Buchungsstapel"),
        "13",
        created_timestamp,
        "",
        _quote("RE"),
        _quote(""),
        _quote(""),
        str(consultant_number),
        str(client_number),
        fiscal_year_start.strftime("%Y%m%d"),
        str(account_length),
        from_date.strftime("%Y%m%d"),
        to_date.strftime("%Y%m%d"),
        _quote("Buchungsstapel"),
        _quote(""),
        "1",
        "0",
        "0",
        _quote("EUR"),
        _quote(""),
        _quote(""),
        _quote(""),
        _quote(""),
        _quote(""),
        _quote(""),
        _quote(""),
        _quote(""),
    ]
    return ";".join(fields)


def _build_column_header_row() -> str:
    return ";".join(_quote(header) for header in _COLUMN_HEADERS)


def _build_data_row(
    invoice: Invoice,
    *,
    default_expense_account: int,
    default_creditor_account: int,
) -> str:
    invoice_number = invoice.invoice_number[:36]
    buchungstext = _truncate_buchungstext(f"{invoice.vendor_name} {invoice_number}".strip())

    fields = [
        _format_decimal(invoice.total_amount),
        _quote("S"),
        _quote(invoice.currency),
        _quote(""),
        _quote(""),
        _quote(""),
        str(default_expense_account),
        str(default_creditor_account),
        _quote(""),
        _format_ttmm(invoice.invoice_date),
        _quote(invoice_number),
        _quote(""),
        _quote(""),
        _quote(buchungstext),
    ]
    return ";".join(fields)


def build_extf_buchungsstapel(
    invoices: list[Invoice],
    *,
    from_date: date,
    to_date: date,
    consultant_number: int,
    client_number: int,
    fiscal_year_start: date,
    account_length: int,
    default_expense_account: int,
    default_creditor_account: int,
    created_at: datetime,
) -> bytes:
    """Liefert die fertige CP1252-encodierte CSV als bytes (mit CRLF)."""
    rows = [
        _build_header_row(
            from_date=from_date,
            to_date=to_date,
            consultant_number=consultant_number,
            client_number=client_number,
            fiscal_year_start=fiscal_year_start,
            account_length=account_length,
            created_at=created_at,
        ),
        _build_column_header_row(),
    ]

    for invoice in invoices:
        rows.append(
            _build_data_row(
                invoice,
                default_expense_account=default_expense_account,
                default_creditor_account=default_creditor_account,
            )
        )

    csv_text = "\r\n".join(rows) + "\r\n"
    return csv_text.encode("cp1252", errors="replace")
