from __future__ import annotations

from decimal import Decimal

import pytest

from kontura.ai.einvoice.extractor import parse_einvoice
from kontura.ai.einvoice.schemas import EinvoiceFormat, EinvoiceParseError

UBL_MINIMAL = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Invoice xmlns=\"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2\"
         xmlns:cac=\"urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2\"
         xmlns:cbc=\"urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2\">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID>
  <cbc:ID>RE-2026-001</cbc:ID>
  <cbc:IssueDate>2026-06-01</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>Müller Beratung GmbH</cbc:Name></cac:PartyName>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:TaxTotal><cbc:TaxAmount>190.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount>1000.00</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount>1000.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount>1190.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>2</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>1000.00</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>Beratungsleistung</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount>500.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>
"""

CII_MINIMAL = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<CrossIndustryInvoice
  xmlns=\"urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100\"
  xmlns:rsm=\"urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100\"
  xmlns:ram=\"urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100\"
  xmlns:udt=\"urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100\">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:factur-x.eu:1p0:minimum</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>CII-2026-001</ram:ID>
    <ram:IssueDateTime><udt:DateTimeString>20260601</udt:DateTimeString></ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty><ram:Name>ACME GmbH</ram:Name></ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>1000.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount>190.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>1190.00</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:SpecifiedTradeProduct><ram:Name>Service</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity>1</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice><ram:ChargeAmount>1000.00</ram:ChargeAmount></ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeSettlement>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>1000.00</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>
  </rsm:SupplyChainTradeTransaction>
</CrossIndustryInvoice>
"""


def test_parses_minimal_ubl_invoice_all_required_fields() -> None:
    data, _profile = parse_einvoice(UBL_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)
    assert data.invoice_number == "RE-2026-001"
    assert data.vendor_name == "Müller Beratung GmbH"
    assert data.currency == "EUR"


def test_parses_minimal_cii_invoice_all_required_fields() -> None:
    data, _profile = parse_einvoice(CII_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_CII)
    assert data.invoice_number == "CII-2026-001"
    assert data.vendor_name == "ACME GmbH"
    assert data.currency == "EUR"


def test_decimals_are_decimal_not_float() -> None:
    data, _profile = parse_einvoice(UBL_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)
    assert isinstance(data.total_amount, Decimal)
    assert isinstance(data.net_amount, Decimal)
    assert isinstance(data.tax_amount, Decimal)


def test_amount_precision_preserved() -> None:
    data, _profile = parse_einvoice(UBL_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)
    assert data.total_amount == Decimal("1190.00")


def test_line_items_extracted_when_present() -> None:
    data, _profile = parse_einvoice(UBL_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)
    assert len(data.line_items) == 1
    assert data.line_items[0].description == "Beratungsleistung"


def test_line_items_empty_when_missing_no_raise() -> None:
    ubl_without_lines = UBL_MINIMAL.replace("<cac:InvoiceLine>", "<cac:Ignored>").replace(
        "</cac:InvoiceLine>", "</cac:Ignored>"
    )
    data, _profile = parse_einvoice(ubl_without_lines.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)
    assert data.line_items == []


def test_raises_einvoice_parse_error_on_missing_required_field() -> None:
    broken = UBL_MINIMAL.replace("<cbc:ID>RE-2026-001</cbc:ID>", "")
    with pytest.raises(EinvoiceParseError):
        parse_einvoice(broken.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)


def test_zugferd_profile_xrechnung_detected_from_customization_id() -> None:
    _data, profile = parse_einvoice(UBL_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_UBL)
    assert profile is not None
    assert profile.value == "xrechnung"


def test_zugferd_profile_minimum_detected_from_urn() -> None:
    _data, profile = parse_einvoice(CII_MINIMAL.encode("utf-8"), EinvoiceFormat.XRECHNUNG_CII)
    assert profile is not None
    assert profile.value == "minimum"


def test_zugferd_profile_unknown_urn_returns_none_no_raise() -> None:
    unknown_profile = CII_MINIMAL.replace("urn:factur-x.eu:1p0:minimum", "urn:unknown")
    _data, profile = parse_einvoice(unknown_profile.encode("utf-8"), EinvoiceFormat.XRECHNUNG_CII)
    assert profile is None
