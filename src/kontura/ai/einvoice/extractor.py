from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final

from defusedxml import ElementTree as DefusedET

from kontura.ai.einvoice.schemas import EinvoiceFormat, EinvoiceParseError, ZugferdProfile
from kontura.ai.extraction.schemas import ExtractedInvoiceData, ExtractedLineItem

_NS_UBL: Final[dict[str, str]] = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}

_NS_CII: Final[dict[str, str]] = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


def _find_text(root: DefusedET.Element, path: str, ns: dict[str, str]) -> str | None:
    found = root.find(path, ns)
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def _require_text(root: DefusedET.Element, path: str, ns: dict[str, str], field: str) -> str:
    value = _find_text(root, path, ns)
    if value is None:
        raise EinvoiceParseError(f"Pflichtfeld fehlt: {field}")
    return value


def _to_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise EinvoiceParseError(f"Ungueltige Decimal fuer {field}: {value!r}") from exc


def _to_date(value: str, field: str) -> date:
    try:
        if len(value) == 8 and value.isdigit():
            return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")
        return date.fromisoformat(value)
    except ValueError as exc:
        raise EinvoiceParseError(f"Ungueltiges Datum fuer {field}: {value!r}") from exc


def _parse_ubl_line_items(root: DefusedET.Element) -> list[ExtractedLineItem]:
    items: list[ExtractedLineItem] = []
    for line in root.findall("cac:InvoiceLine", _NS_UBL):
        description = _find_text(line, "cac:Item/cbc:Name", _NS_UBL) or ""
        quantity = _find_text(line, "cbc:InvoicedQuantity", _NS_UBL)
        unit_price = _find_text(line, "cac:Price/cbc:PriceAmount", _NS_UBL)
        total_price = _find_text(line, "cbc:LineExtensionAmount", _NS_UBL)
        try:
            items.append(
                ExtractedLineItem(
                    description=description,
                    quantity=Decimal(quantity) if quantity is not None else None,
                    unit_price=Decimal(unit_price) if unit_price is not None else None,
                    total_price=Decimal(total_price) if total_price is not None else None,
                )
            )
        except (InvalidOperation, ValueError):
            continue
    return items


def _parse_cii_line_items(root: DefusedET.Element) -> list[ExtractedLineItem]:
    items: list[ExtractedLineItem] = []
    for line in root.findall(".//ram:IncludedSupplyChainTradeLineItem", _NS_CII):
        description = _find_text(line, "ram:AssociatedDocumentLineDocument/ram:Name", _NS_CII) or ""
        quantity = _find_text(line, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", _NS_CII)
        unit_price = _find_text(
            line,
            "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount",
            _NS_CII,
        )
        total_price = _find_text(
            line,
            (
                "ram:SpecifiedLineTradeSettlement/"
                "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount"
            ),
            _NS_CII,
        )
        try:
            items.append(
                ExtractedLineItem(
                    description=description,
                    quantity=Decimal(quantity) if quantity is not None else None,
                    unit_price=Decimal(unit_price) if unit_price is not None else None,
                    total_price=Decimal(total_price) if total_price is not None else None,
                )
            )
        except (InvalidOperation, ValueError):
            continue
    return items


def _parse_ubl(root: DefusedET.Element) -> tuple[ExtractedInvoiceData, ZugferdProfile | None]:
    invoice_number = _require_text(root, "cbc:ID", _NS_UBL, "invoice_number")
    vendor_name = _require_text(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name",
        _NS_UBL,
        "vendor_name",
    )
    invoice_date = _to_date(
        _require_text(root, "cbc:IssueDate", _NS_UBL, "invoice_date"),
        "invoice_date",
    )
    total_amount = _to_decimal(
        _require_text(root, "cac:LegalMonetaryTotal/cbc:PayableAmount", _NS_UBL, "total_amount"),
        "total_amount",
    )

    net_value = _find_text(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount", _NS_UBL)
    if net_value is None:
        net_value = _find_text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", _NS_UBL)
    if net_value is None:
        raise EinvoiceParseError("Pflichtfeld fehlt: net_amount")

    tax_value = _find_text(root, "cac:TaxTotal/cbc:TaxAmount", _NS_UBL)
    if tax_value is None:
        raise EinvoiceParseError("Pflichtfeld fehlt: tax_amount")

    currency = _require_text(root, "cbc:DocumentCurrencyCode", _NS_UBL, "currency")
    profile_urn = _find_text(root, "cbc:CustomizationID", _NS_UBL)

    data = ExtractedInvoiceData(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        vendor_address=None,
        invoice_date=invoice_date,
        due_date=None,
        currency=currency,
        net_amount=_to_decimal(net_value, "net_amount"),
        tax_amount=_to_decimal(tax_value, "tax_amount"),
        total_amount=total_amount,
        line_items=_parse_ubl_line_items(root),
        confidence_notes=None,
    )
    return data, (ZugferdProfile.from_urn(profile_urn) if profile_urn else None)


def _parse_cii(root: DefusedET.Element) -> tuple[ExtractedInvoiceData, ZugferdProfile | None]:
    invoice_number = _require_text(root, "rsm:ExchangedDocument/ram:ID", _NS_CII, "invoice_number")
    vendor_name = _require_text(
        root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:Name",
        _NS_CII,
        "vendor_name",
    )
    invoice_date_raw = _require_text(
        root,
        "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString",
        _NS_CII,
        "invoice_date",
    )
    total_value = _require_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount"
        ),
        _NS_CII,
        "total_amount",
    )
    net_value = _require_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxBasisTotalAmount"
        ),
        _NS_CII,
        "net_amount",
    )
    tax_value = _require_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/"
            "ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount"
        ),
        _NS_CII,
        "tax_amount",
    )
    currency = _require_text(
        root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
        _NS_CII,
        "currency",
    )
    profile_urn = _find_text(
        root,
        "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID",
        _NS_CII,
    )

    data = ExtractedInvoiceData(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        vendor_address=None,
        invoice_date=_to_date(invoice_date_raw, "invoice_date"),
        due_date=None,
        currency=currency,
        net_amount=_to_decimal(net_value, "net_amount"),
        tax_amount=_to_decimal(tax_value, "tax_amount"),
        total_amount=_to_decimal(total_value, "total_amount"),
        line_items=_parse_cii_line_items(root),
        confidence_notes=None,
    )
    return data, (ZugferdProfile.from_urn(profile_urn) if profile_urn else None)


def parse_einvoice(
    content: bytes,
    fmt: EinvoiceFormat,
) -> tuple[ExtractedInvoiceData, ZugferdProfile | None]:
    """Parst XML -> ExtractedInvoiceData + optional erkanntes Profil."""
    try:
        root = DefusedET.fromstring(content)
    except Exception as exc:  # noqa: BLE001
        raise EinvoiceParseError("XML konnte nicht geparst werden") from exc

    if fmt == EinvoiceFormat.XRECHNUNG_UBL:
        return _parse_ubl(root)
    if fmt == EinvoiceFormat.XRECHNUNG_CII:
        return _parse_cii(root)

    raise EinvoiceParseError(f"Nicht unterstuetztes E-Invoice-Format: {fmt.value}")
