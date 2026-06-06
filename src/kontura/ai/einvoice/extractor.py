from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as DefusedET

from kontura.ai.einvoice.schemas import EinvoiceFormat, EinvoiceParseError, ZugferdProfile
from kontura.ai.extraction.schemas import ExtractedInvoiceData, ExtractedLineItem

_UBL_NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}
_CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


def _text(root: DefusedET.Element, path: str, ns: dict[str, str]) -> str | None:
    node = root.find(path, ns)
    if node is None or node.text is None:
        return None
    stripped = node.text.strip()
    return stripped if stripped else None


def _required_text(root: DefusedET.Element, path: str, ns: dict[str, str], field: str) -> str:
    value = _text(root, path, ns)
    if value is None:
        raise EinvoiceParseError(f"Missing required field: {field}")
    return value


def _to_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise EinvoiceParseError(f"Invalid decimal for {field}: {value!r}") from exc


def _optional_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _to_date(value: str, field: str) -> date:
    normalized = value.strip()
    try:
        if len(normalized) == 8 and normalized.isdigit():
            return date.fromisoformat(f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}")
        if "T" in normalized:
            normalized = normalized.split("T", 1)[0]
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise EinvoiceParseError(f"Invalid date for {field}: {value!r}") from exc


def _parse_ubl(root: DefusedET.Element) -> tuple[ExtractedInvoiceData, ZugferdProfile | None]:
    invoice_number = _required_text(root, "cbc:ID", _UBL_NS, "invoice_number")
    vendor_name = _required_text(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name",
        _UBL_NS,
        "vendor_name",
    )
    invoice_date_raw = _required_text(root, "cbc:IssueDate", _UBL_NS, "invoice_date")
    total_amount_raw = _required_text(
        root,
        "cac:LegalMonetaryTotal/cbc:PayableAmount",
        _UBL_NS,
        "total_amount",
    )
    net_amount_raw = _text(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount", _UBL_NS) or _text(
        root,
        "cac:LegalMonetaryTotal/cbc:LineExtensionAmount",
        _UBL_NS,
    )
    if net_amount_raw is None:
        raise EinvoiceParseError("Missing required field: net_amount")
    tax_amount_raw = _required_text(root, "cac:TaxTotal/cbc:TaxAmount", _UBL_NS, "tax_amount")
    currency = _required_text(root, "cbc:DocumentCurrencyCode", _UBL_NS, "currency")

    line_items: list[ExtractedLineItem] = []
    for line in root.findall("cac:InvoiceLine", _UBL_NS):
        description = _text(line, "cac:Item/cbc:Name", _UBL_NS)
        if not description:
            continue
        quantity_raw = _text(line, "cbc:InvoicedQuantity", _UBL_NS)
        unit_price_raw = _text(line, "cac:Price/cbc:PriceAmount", _UBL_NS)
        total_price_raw = _text(line, "cbc:LineExtensionAmount", _UBL_NS)
        line_items.append(
            ExtractedLineItem(
                description=description,
                quantity=_optional_decimal(quantity_raw),
                unit_price=_optional_decimal(unit_price_raw),
                total_price=_optional_decimal(total_price_raw),
            )
        )

    profile = ZugferdProfile.from_urn(_text(root, "cbc:CustomizationID", _UBL_NS) or "")
    data = ExtractedInvoiceData(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=_to_date(invoice_date_raw, "invoice_date"),
        total_amount=_to_decimal(total_amount_raw, "total_amount"),
        net_amount=_to_decimal(net_amount_raw, "net_amount"),
        tax_amount=_to_decimal(tax_amount_raw, "tax_amount"),
        currency=currency,
        line_items=line_items,
    )
    return data, profile


def _parse_cii(root: DefusedET.Element) -> tuple[ExtractedInvoiceData, ZugferdProfile | None]:
    invoice_number = _required_text(root, "rsm:ExchangedDocument/ram:ID", _CII_NS, "invoice_number")
    vendor_name = _required_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/"
            "ram:SellerTradeParty/ram:Name"
        ),
        _CII_NS,
        "vendor_name",
    )
    invoice_date_raw = _required_text(
        root,
        "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString",
        _CII_NS,
        "invoice_date",
    )
    total_amount_raw = _required_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount"
        ),
        _CII_NS,
        "total_amount",
    )
    net_amount_raw = _required_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxBasisTotalAmount"
        ),
        _CII_NS,
        "net_amount",
    )
    tax_amount_raw = _required_text(
        root,
        (
            "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/"
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount"
        ),
        _CII_NS,
        "tax_amount",
    )
    currency = _required_text(
        root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
        _CII_NS,
        "currency",
    )

    line_items: list[ExtractedLineItem] = []
    for line in root.findall(
        "rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem",
        _CII_NS,
    ):
        description = _text(line, "ram:SpecifiedTradeProduct/ram:Name", _CII_NS)
        if not description:
            continue
        quantity_raw = _text(line, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", _CII_NS)
        unit_price_raw = _text(
            line,
            "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount",
            _CII_NS,
        )
        total_price_raw = _text(
            line,
            (
                "ram:SpecifiedLineTradeSettlement/"
                "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount"
            ),
            _CII_NS,
        )
        line_items.append(
            ExtractedLineItem(
                description=description,
                quantity=_optional_decimal(quantity_raw),
                unit_price=_optional_decimal(unit_price_raw),
                total_price=_optional_decimal(total_price_raw),
            )
        )

    profile = ZugferdProfile.from_urn(
        _text(
            root,
            ("rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID"),
            _CII_NS,
        )
        or ""
    )

    data = ExtractedInvoiceData(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=_to_date(invoice_date_raw, "invoice_date"),
        total_amount=_to_decimal(total_amount_raw, "total_amount"),
        net_amount=_to_decimal(net_amount_raw, "net_amount"),
        tax_amount=_to_decimal(tax_amount_raw, "tax_amount"),
        currency=currency,
        line_items=line_items,
    )
    return data, profile


def parse_einvoice(
    content: bytes,
    fmt: EinvoiceFormat,
) -> tuple[ExtractedInvoiceData, ZugferdProfile | None]:
    """Parst XML -> ExtractedInvoiceData + optional erkanntes Profil."""
    try:
        root = DefusedET.fromstring(content)
    except Exception as exc:  # noqa: BLE001
        raise EinvoiceParseError("XML parsing failed") from exc

    if fmt == EinvoiceFormat.XRECHNUNG_UBL:
        return _parse_ubl(root)
    if fmt == EinvoiceFormat.XRECHNUNG_CII:
        return _parse_cii(root)

    raise EinvoiceParseError(f"Unsupported e-invoice format: {fmt.value}")
