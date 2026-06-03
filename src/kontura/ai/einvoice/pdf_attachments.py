from __future__ import annotations

from typing import Final

_EINVOICE_ATTACHMENT_NAMES: Final[frozenset[str]] = frozenset(
    {
        "factur-x.xml",
        "zugferd-invoice.xml",
        "xrechnung.xml",
    }
)


def extract_embedded_einvoice_xml(pdf_bytes: bytes) -> tuple[bytes, str] | None:
    """Liefert (xml_bytes, filename) wenn bekannte E-Invoice-XML eingebettet ist."""
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001
        return None

    try:
        for idx in range(doc.embfile_count()):
            info = doc.embfile_info(idx)
            filename = str(info.get("filename") or info.get("name") or "")
            if filename.lower() not in _EINVOICE_ATTACHMENT_NAMES:
                continue
            content = doc.embfile_get(idx)
            if isinstance(content, bytes):
                return content, filename
    except Exception:  # noqa: BLE001
        return None
    finally:
        doc.close()

    return None
