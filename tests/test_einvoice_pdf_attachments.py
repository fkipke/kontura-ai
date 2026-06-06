from __future__ import annotations

from typing import cast

import fitz

from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml

UBL_XML = (
    b"<?xml version='1.0'?><Invoice "
    b"xmlns='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'/>"
)


def _make_pdf_with_attachments(attachments: list[tuple[str, bytes]] | None = None) -> bytes:
    doc = fitz.open()
    try:
        doc.new_page()
        for name, payload in attachments or []:
            doc.embfile_add(name, payload, filename=name)
        return cast(bytes, doc.tobytes())
    finally:
        doc.close()


def test_extracts_factur_x_xml_from_zugferd_pdf() -> None:
    pdf = _make_pdf_with_attachments([("factur-x.xml", UBL_XML)])
    extracted = extract_embedded_einvoice_xml(pdf)
    assert extracted is not None
    xml_bytes, filename = extracted
    assert filename == "factur-x.xml"
    assert xml_bytes == UBL_XML


def test_returns_none_when_pdf_has_no_attachments() -> None:
    pdf = _make_pdf_with_attachments()
    assert extract_embedded_einvoice_xml(pdf) is None


def test_returns_none_when_pdf_has_attachments_but_none_match_einvoice_names() -> None:
    pdf = _make_pdf_with_attachments([("not-invoice.xml", UBL_XML)])
    assert extract_embedded_einvoice_xml(pdf) is None


def test_case_insensitive_filename_match() -> None:
    pdf = _make_pdf_with_attachments([("Factur-X.XML", UBL_XML)])
    extracted = extract_embedded_einvoice_xml(pdf)
    assert extracted is not None
    xml_bytes, filename = extracted
    assert filename == "Factur-X.XML"
    assert xml_bytes == UBL_XML
