from __future__ import annotations

import fitz
import structlog

_EINVOICE_ATTACHMENT_NAMES = frozenset(
    {
        "factur-x.xml",
        "zugferd-invoice.xml",
        "xrechnung.xml",
    }
)

logger = structlog.get_logger(__name__)


def extract_embedded_einvoice_xml(pdf_bytes: bytes) -> tuple[bytes, str] | None:
    """Liefert eingebettetes E-Rechnungs-XML aus einem PDF, falls vorhanden."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001
        logger.warning("einvoice_pdf_open_failed")
        return None

    try:
        for index in range(doc.embfile_count()):
            info = doc.embfile_info(index)
            name = str(info.get("filename", ""))
            if name.lower() in _EINVOICE_ATTACHMENT_NAMES:
                xml_bytes = bytes(doc.embfile_get(index))
                return (xml_bytes, name)
        return None
    finally:
        doc.close()
