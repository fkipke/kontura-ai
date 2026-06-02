from __future__ import annotations

import fitz

from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml

XML_BYTES = b"<root/>"


def _build_pdf(*attachments: tuple[str, bytes]) -> bytes:
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    for name, payload in attachments:
        doc.embfile_add(name, payload, filename=name)
    try:
        return bytes(doc.tobytes())
    finally:
        doc.close()


def test_extracts_factur_x_xml_from_zugferd_pdf() -> None:
    pdf = _build_pdf(("factur-x.xml", XML_BYTES))
    result = extract_embedded_einvoice_xml(pdf)
    assert result is not None
    assert result[0] == XML_BYTES
    assert result[1] == "factur-x.xml"


def test_returns_none_when_pdf_has_no_attachments() -> None:
    pdf = _build_pdf()
    assert extract_embedded_einvoice_xml(pdf) is None


def test_returns_none_when_pdf_has_attachments_but_none_match_einvoice_names() -> None:
    pdf = _build_pdf(("readme.txt", b"nope"))
    assert extract_embedded_einvoice_xml(pdf) is None


def test_case_insensitive_filename_match() -> None:
    pdf = _build_pdf(("Factur-X.XML", XML_BYTES))
    result = extract_embedded_einvoice_xml(pdf)
    assert result is not None
    assert result[0] == XML_BYTES
    assert result[1] == "Factur-X.XML"
