from __future__ import annotations

import fitz

from kontura.ai.einvoice.detector import detect_einvoice_format
from kontura.ai.einvoice.schemas import EinvoiceFormat

UBL_MINIMAL = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
  <cbc:ID>RE-2026-001</cbc:ID>
</Invoice>"""

CII_MINIMAL = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument><ram:ID>RE-2026-001</ram:ID></rsm:ExchangedDocument>
</rsm:CrossIndustryInvoice>"""


def _build_pdf_with_attachment(filename: str, payload: bytes) -> bytes:
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    doc.embfile_add(filename, payload, filename=filename)
    try:
        return bytes(doc.tobytes())
    finally:
        doc.close()


def test_detects_xrechnung_ubl_from_xml_root() -> None:
    assert detect_einvoice_format(UBL_MINIMAL, "application/xml") == EinvoiceFormat.XRECHNUNG_UBL


def test_detects_xrechnung_cii_from_xml_root() -> None:
    assert detect_einvoice_format(CII_MINIMAL, "text/xml") == EinvoiceFormat.XRECHNUNG_CII


def test_detects_zugferd_pdf_with_factur_x_embedded() -> None:
    pdf_bytes = _build_pdf_with_attachment("factur-x.xml", CII_MINIMAL)
    assert detect_einvoice_format(pdf_bytes, "application/pdf") == EinvoiceFormat.ZUGFERD_PDF


def test_returns_none_for_plain_pdf_without_attachments() -> None:
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    try:
        pdf_bytes = bytes(doc.tobytes())
    finally:
        doc.close()
    assert detect_einvoice_format(pdf_bytes, "application/pdf") == EinvoiceFormat.NONE


def test_returns_none_for_png_image() -> None:
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x11\x00\x01F\x80\xa7d"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    assert detect_einvoice_format(png, "image/png") == EinvoiceFormat.NONE


def test_returns_none_for_malformed_xml() -> None:
    malformed = b"<Invoice><cbc:ID>broken</Invoice>"
    assert detect_einvoice_format(malformed, "application/xml") == EinvoiceFormat.NONE


def test_xxe_attack_is_safe() -> None:
    xxe = b"""<?xml version="1.0"?>
<!DOCTYPE data [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">&xxe;</Invoice>"""
    assert detect_einvoice_format(xxe, "application/xml") == EinvoiceFormat.NONE
