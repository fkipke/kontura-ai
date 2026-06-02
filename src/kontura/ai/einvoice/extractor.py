from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree

from kontura.ai.einvoice.schemas import EinvoiceFormat, EinvoiceParseError, ZugferdProfile
from kontura.ai.extraction.schemas import ExtractedInvoiceData, ExtractedLineItem

UBL_INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
UBL_CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
UBL_CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CII_RSM_NS = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
CII_RAM_NS = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
CII_UDT_NS = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

_UBL_NS = {"cbc": UBL_CBC_NS, "cac": UBL_CAC_NS}
_CII_NS = {"rsm": CII_RSM_NS, "ram": CII_RAM_NS, "udt": CII_UDT_NS}


def _parse_xml(content: bytes) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(content)
    except Exception as exc:  # noqa: BLE001
        raise EinvoiceParseError("ungueltiges XML") from exc


def _text(root: ElementTree.Element, path: str, namespaces: dict[str, str]) -> str | None:
    node = root.find(path, namespaces)
    if node is None or node.text is None:
        return None
    stripped = node.text.strip()
    return stripped if stripped else None


def _required_text(
    root: ElementTree.Element,
    path: str,
    namespaces: dict[str, str],
    field: str,
) -> str:
    value = _text(root, path, namespaces)
    if value is None:
        raise EinvoiceParseError(f"Pflichtfeld fehlt: {field}")
    return value


def _to_money(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise EinvoiceParseError(f"ungueltiger Betrag fuer {field}") from exc


def _to_quantity(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _parse_date(raw: str, field: str) -> date:
    value = raw.strip()
    try:
        if len(value) == 8 and value.isdigit():
            return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
        return date.fromisoformat(value)
    except ValueError as exc:
        raise EinvoiceParseError(f"ungueltiges Datum fuer {field}") from exc


def _parse_ubl(root: ElementTree.Element) -> ExtractedInvoiceData:
    invoice_number = _required_text(root, "cbc:ID", _UBL_NS, "invoice_number")
    vendor_name = _required_text(
        root,
        "cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name",
        _UBL_NS,
        "vendor_name",
    )
    invoice_date = _parse_date(
        _required_text(root, "cbc:IssueDate", _UBL_NS, "invoice_date"), "invoice_date"
    )
    currency = _required_text(root, "cbc:DocumentCurrencyCode", _UBL_NS, "currency")

    total_amount = _to_money(
        _required_text(
            root,
            "cac:LegalMonetaryTotal/cbc:PayableAmount",
            _UBL_NS,
            "total_amount",
        ),
        "total_amount",
    )
    net_amount_text = _text(
        root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount", _UBL_NS
    ) or _text(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount", _UBL_NS)
    if net_amount_text is None:
        raise EinvoiceParseError("Pflichtfeld fehlt: net_amount")
    net_amount = _to_money(net_amount_text, "net_amount")
    tax_amount = _to_money(
        _required_text(root, "cac:TaxTotal/cbc:TaxAmount", _UBL_NS, "tax_amount"),
        "tax_amount",
    )

    line_items: list[ExtractedLineItem] = []
    for item in root.findall("cac:InvoiceLine", _UBL_NS):
        description = _text(item, "cac:Item/cbc:Name", _UBL_NS)
        if description is None:
            continue
        line_items.append(
            ExtractedLineItem(
                description=description,
                quantity=_to_quantity(_text(item, "cbc:InvoicedQuantity", _UBL_NS) or ""),
                unit_price=_to_quantity(_text(item, "cac:Price/cbc:PriceAmount", _UBL_NS) or ""),
                total_price=_to_quantity(_text(item, "cbc:LineExtensionAmount", _UBL_NS) or ""),
            )
        )

    return ExtractedInvoiceData(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=invoice_date,
        currency=currency,
        net_amount=net_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        line_items=line_items,
    )


def _parse_cii(root: ElementTree.Element) -> ExtractedInvoiceData:
    invoice_number = _required_text(
        root,
        "rsm:ExchangedDocument/ram:ID",
        _CII_NS,
        "invoice_number",
    )
    vendor_name = _required_text(
        root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement/ram:SellerTradeParty/ram:Name",
        _CII_NS,
        "vendor_name",
    )
    invoice_date = _parse_date(
        _required_text(
            root,
            "rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString",
            _CII_NS,
            "invoice_date",
        ),
        "invoice_date",
    )
    currency = _required_text(
        root,
        "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
        _CII_NS,
        "currency",
    )
    total_amount = _to_money(
        _required_text(
            root,
            (
                "rsm:SupplyChainTradeTransaction/"
                "ram:ApplicableHeaderTradeSettlement/"
                "ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
                "ram:GrandTotalAmount"
            ),
            _CII_NS,
            "total_amount",
        ),
        "total_amount",
    )
    net_amount = _to_money(
        _required_text(
            root,
            (
                "rsm:SupplyChainTradeTransaction/"
                "ram:ApplicableHeaderTradeSettlement/"
                "ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
                "ram:TaxBasisTotalAmount"
            ),
            _CII_NS,
            "net_amount",
        ),
        "net_amount",
    )
    tax_amount = _to_money(
        _required_text(
            root,
            (
                "rsm:SupplyChainTradeTransaction/"
                "ram:ApplicableHeaderTradeSettlement/"
                "ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
                "ram:TaxTotalAmount"
            ),
            _CII_NS,
            "tax_amount",
        ),
        "tax_amount",
    )

    line_items: list[ExtractedLineItem] = []
    for item in root.findall(
        "rsm:SupplyChainTradeTransaction/ram:IncludedSupplyChainTradeLineItem",
        _CII_NS,
    ):
        description = _text(item, "ram:SpecifiedTradeProduct/ram:Name", _CII_NS)
        if description is None:
            continue
        line_items.append(
            ExtractedLineItem(
                description=description,
                quantity=_to_quantity(
                    _text(item, "ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", _CII_NS) or ""
                ),
                unit_price=_to_quantity(
                    _text(
                        item,
                        "ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice/ram:ChargeAmount",
                        _CII_NS,
                    )
                    or ""
                ),
                total_price=_to_quantity(
                    _text(
                        item,
                        (
                            "ram:SpecifiedLineTradeSettlement/"
                            "ram:SpecifiedTradeSettlementLineMonetarySummation/"
                            "ram:LineTotalAmount"
                        ),
                        _CII_NS,
                    )
                    or ""
                ),
            )
        )

    return ExtractedInvoiceData(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date=invoice_date,
        currency=currency,
        net_amount=net_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        line_items=line_items,
    )


def parse_einvoice(content: bytes, fmt: EinvoiceFormat) -> ExtractedInvoiceData:
    """Parst E-Rechnungs-XML zu ExtractedInvoiceData."""
    root = _parse_xml(content)
    if fmt == EinvoiceFormat.XRECHNUNG_UBL:
        return _parse_ubl(root)
    if fmt == EinvoiceFormat.XRECHNUNG_CII:
        return _parse_cii(root)
    raise EinvoiceParseError(f"Format nicht parsebar: {fmt.value}")


def extract_zugferd_profile(content: bytes, fmt: EinvoiceFormat) -> ZugferdProfile | None:
    """Ermittelt das ZUGFeRD-Profil aus der XML-URN."""
    root = _parse_xml(content)
    urn: str | None
    if fmt == EinvoiceFormat.XRECHNUNG_UBL:
        urn = _text(root, "cbc:CustomizationID", _UBL_NS)
    elif fmt == EinvoiceFormat.XRECHNUNG_CII:
        urn = _text(
            root,
            "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID",
            _CII_NS,
        )
    else:
        return None
    if urn is None:
        return None
    return ZugferdProfile.from_urn(urn)
