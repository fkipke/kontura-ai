from __future__ import annotations

from typing import cast

import fitz

from kontura.ai.einvoice.detector import detect_einvoice_format
from kontura.ai.einvoice.schemas import EinvoiceFormat

_UBL_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Invoice xmlns=\"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2\"
         xmlns:cac=\"urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2\"
         xmlns:cbc=\"urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2\">
  <cbc:ID>RE-1</cbc:ID>
</Invoice>
"""

_CII_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<CrossIndustryInvoice xmlns=\"urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100\"/>
"""


def _make_pdf(*, attachment_name: str | None = None, payload: bytes | None = None) -> bytes:
    doc = fitz.open()
    try:
        doc.new_page()
        if attachment_name and payload is not None:
            doc.embfile_add(attachment_name, payload, filename=attachment_name)
        return cast(bytes, doc.tobytes())
    finally:
        doc.close()


def test_detects_xrechnung_ubl_from_xml_root() -> None:
    detected = detect_einvoice_format(_UBL_XML.encode("utf-8"), "application/xml")
    assert detected == EinvoiceFormat.XRECHNUNG_UBL


def test_detects_xrechnung_cii_from_xml_root() -> None:
    detected = detect_einvoice_format(_CII_XML.encode("utf-8"), "text/xml")
    assert detected == EinvoiceFormat.XRECHNUNG_CII


def test_detects_zugferd_pdf_with_factur_x_embedded() -> None:
    pdf = _make_pdf(attachment_name="factur-x.xml", payload=_UBL_XML.encode("utf-8"))
    detected = detect_einvoice_format(pdf, "application/pdf")
    assert detected == EinvoiceFormat.ZUGFERD_PDF


def test_returns_none_for_plain_pdf_without_attachments() -> None:
    pdf = _make_pdf()
    detected = detect_einvoice_format(pdf, "application/pdf")
    assert detected == EinvoiceFormat.NONE


def test_returns_none_for_png_image() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 24
    detected = detect_einvoice_format(png, "image/png")
    assert detected == EinvoiceFormat.NONE


def test_returns_none_for_malformed_xml() -> None:
    malformed = b"<Invoice><broken></Invoice>"
    detected = detect_einvoice_format(malformed, "application/xml")
    assert detected == EinvoiceFormat.NONE


def test_xxe_attack_is_safe() -> None:
    payload = b"""<?xml version='1.0'?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>
<Invoice>&xxe;</Invoice>
"""
    detected = detect_einvoice_format(payload, "application/xml")
    assert detected == EinvoiceFormat.NONE
