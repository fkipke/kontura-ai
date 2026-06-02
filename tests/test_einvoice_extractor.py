from __future__ import annotations

from decimal import Decimal

import pytest

from kontura.ai.einvoice.extractor import extract_zugferd_profile, parse_einvoice
from kontura.ai.einvoice.schemas import EinvoiceFormat, EinvoiceParseError, ZugferdProfile

UBL_MINIMAL = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID>
  <cbc:ID>RE-2026-001</cbc:ID>
  <cbc:IssueDate>2026-05-15</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party><cac:PartyName><cbc:Name>ACME Lieferant GmbH</cbc:Name></cac:PartyName></cac:Party>
  </cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount currencyID="EUR">100.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">119.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount></cac:TaxTotal>
</Invoice>"""

UBL_WITH_LINES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:ID>RE-2026-002</cbc:ID>
  <cbc:IssueDate>2026-05-15</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyName><cbc:Name>ACME</cbc:Name></cac:PartyName></cac:Party></cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount>100.00</cbc:TaxExclusiveAmount>
    <cbc:PayableAmount>119.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:TaxTotal><cbc:TaxAmount>19.00</cbc:TaxAmount></cac:TaxTotal>
  <cac:InvoiceLine>
    <cbc:InvoicedQuantity>2.0000</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>100.00</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>Beratung</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount>50.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>"""

CII_MINIMAL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:factur-x.eu:1p0:minimum</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>CII-2026-001</ram:ID>
    <ram:IssueDateTime><udt:DateTimeString>20260515</udt:DateTimeString></ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty><ram:Name>ACME CII GmbH</ram:Name></ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount>19.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""

CII_WITH_LINES = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument><ram:ID>CII-2026-002</ram:ID><ram:IssueDateTime><udt:DateTimeString>20260515</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement><ram:SellerTradeParty><ram:Name>Vendor</ram:Name></ram:SellerTradeParty></ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount>19.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:SpecifiedTradeProduct><ram:Name>Produkt A</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity>2.0000</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice><ram:ChargeAmount>50.0000</ram:ChargeAmount></ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeSettlement><ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>100.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""


def test_parses_minimal_ubl_invoice_all_required_fields() -> None:
    data = parse_einvoice(UBL_MINIMAL, EinvoiceFormat.XRECHNUNG_UBL)
    assert data.invoice_number == "RE-2026-001"
    assert data.vendor_name == "ACME Lieferant GmbH"
    assert data.currency == "EUR"
    assert data.net_amount == Decimal("100.00")
    assert data.tax_amount == Decimal("19.00")
    assert data.total_amount == Decimal("119.00")


def test_parses_minimal_cii_invoice_all_required_fields() -> None:
    data = parse_einvoice(CII_MINIMAL, EinvoiceFormat.XRECHNUNG_CII)
    assert data.invoice_number == "CII-2026-001"
    assert data.vendor_name == "ACME CII GmbH"
    assert data.currency == "EUR"
    assert data.net_amount == Decimal("100.00")
    assert data.tax_amount == Decimal("19.00")
    assert data.total_amount == Decimal("119.00")


def test_decimals_are_decimal_not_float() -> None:
    data = parse_einvoice(UBL_MINIMAL, EinvoiceFormat.XRECHNUNG_UBL)
    assert isinstance(data.total_amount, Decimal)
    assert not isinstance(data.total_amount, float)


def test_amount_precision_preserved() -> None:
    xml = UBL_MINIMAL.replace(b"119.00", b"1234.56").replace(b"100.00", b"1037.45")
    data = parse_einvoice(xml, EinvoiceFormat.XRECHNUNG_UBL)
    assert data.total_amount == Decimal("1234.56")


def test_line_items_extracted_when_present() -> None:
    ubl = parse_einvoice(UBL_WITH_LINES, EinvoiceFormat.XRECHNUNG_UBL)
    cii = parse_einvoice(CII_WITH_LINES, EinvoiceFormat.XRECHNUNG_CII)
    assert len(ubl.line_items) == 1
    assert ubl.line_items[0].description == "Beratung"
    assert len(cii.line_items) == 1
    assert cii.line_items[0].description == "Produkt A"


def test_line_items_empty_when_missing_no_raise() -> None:
    data = parse_einvoice(UBL_MINIMAL, EinvoiceFormat.XRECHNUNG_UBL)
    assert data.line_items == []


def test_raises_einvoice_parse_error_on_missing_required_field() -> None:
    broken = UBL_MINIMAL.replace(b"<cbc:ID>RE-2026-001</cbc:ID>", b"")
    with pytest.raises(EinvoiceParseError):
        parse_einvoice(broken, EinvoiceFormat.XRECHNUNG_UBL)


def test_zugferd_profile_minimum_detected_from_urn() -> None:
    profile = extract_zugferd_profile(CII_MINIMAL, EinvoiceFormat.XRECHNUNG_CII)
    assert profile == ZugferdProfile.MINIMUM


def test_zugferd_profile_xrechnung_detected_from_customization_id() -> None:
    profile = extract_zugferd_profile(UBL_MINIMAL, EinvoiceFormat.XRECHNUNG_UBL)
    assert profile == ZugferdProfile.XRECHNUNG


def test_zugferd_profile_unknown_urn_returns_none_no_raise() -> None:
    xml = UBL_MINIMAL.replace(
        b"urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
        b"urn:unknown:profile",
    )
    profile = extract_zugferd_profile(xml, EinvoiceFormat.XRECHNUNG_UBL)
    assert profile is None
