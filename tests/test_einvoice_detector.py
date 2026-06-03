from __future__ import annotations

from io import BytesIO

import fitz

from kontura.ai.einvoice.detector import detect_einvoice_format
from kontura.ai.einvoice.schemas import EinvoiceFormat


def _make_simple_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    buffer = BytesIO()
    try:
        doc.save(buffer)
    finally:
        doc.close()
    return buffer.getvalue()


def _make_zugferd_pdf(xml_bytes: bytes, filename: str = "factur-x.xml") -> bytes:
    doc = fitz.open()
    doc.new_page()
    doc.embfile_add(filename, xml_bytes)
    buffer = BytesIO()
    try:
        doc.save(buffer)
    finally:
        doc.close()
    return buffer.getvalue()


def test_detects_xrechnung_ubl_from_xml_root() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"/>'
    )
    assert detect_einvoice_format(xml, "application/xml") == EinvoiceFormat.XRECHNUNG_UBL


def test_detects_xrechnung_cii_from_xml_root() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<CrossIndustryInvoice "
        b'xmlns="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"/>'
    )
    assert detect_einvoice_format(xml, "text/xml") == EinvoiceFormat.XRECHNUNG_CII


def test_detects_zugferd_pdf_with_factur_x_embedded() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"/>'
    )
    pdf = _make_zugferd_pdf(xml)
    assert detect_einvoice_format(pdf, "application/pdf") == EinvoiceFormat.ZUGFERD_PDF


def test_returns_none_for_plain_pdf_without_attachments() -> None:
    assert detect_einvoice_format(_make_simple_pdf(), "application/pdf") == EinvoiceFormat.NONE


def test_returns_none_for_png_image() -> None:
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert detect_einvoice_format(png, "image/png") == EinvoiceFormat.NONE


def test_returns_none_for_malformed_xml() -> None:
    malformed = b"<Invoice><broken>"
    assert detect_einvoice_format(malformed, "application/xml") == EinvoiceFormat.NONE


def test_xxe_attack_is_safe() -> None:
    payload = b"""<?xml version='1.0'?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>
<Invoice xmlns='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'>&xxe;</Invoice>
"""
    assert detect_einvoice_format(payload, "application/xml") == EinvoiceFormat.NONE
