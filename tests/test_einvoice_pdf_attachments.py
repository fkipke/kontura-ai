from __future__ import annotations

from io import BytesIO

import fitz

from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml


def _make_pdf_with_attachments(attachments: list[tuple[str, bytes]] | None = None) -> bytes:
    doc = fitz.open()
    doc.new_page()
    for filename, content in attachments or []:
        doc.embfile_add(filename, content)
    buffer = BytesIO()
    try:
        doc.save(buffer)
    finally:
        doc.close()
    return buffer.getvalue()


def test_extracts_factur_x_xml_from_zugferd_pdf() -> None:
    xml = b"<Invoice />"
    pdf = _make_pdf_with_attachments([("factur-x.xml", xml)])
    extracted = extract_embedded_einvoice_xml(pdf)
    assert extracted is not None
    assert extracted[0] == xml
    assert extracted[1] == "factur-x.xml"


def test_returns_none_when_pdf_has_no_attachments() -> None:
    pdf = _make_pdf_with_attachments()
    assert extract_embedded_einvoice_xml(pdf) is None


def test_returns_none_when_pdf_has_attachments_but_none_match_einvoice_names() -> None:
    pdf = _make_pdf_with_attachments([("readme.txt", b"hello")])
    assert extract_embedded_einvoice_xml(pdf) is None


def test_case_insensitive_filename_match() -> None:
    xml = b"<Invoice />"
    pdf = _make_pdf_with_attachments([("Factur-X.XML", xml)])
    extracted = extract_embedded_einvoice_xml(pdf)
    assert extracted is not None
    assert extracted[0] == xml
