from __future__ import annotations

_ATTACHMENT_NAMES = {"factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml"}


def extract_embedded_einvoice_xml(pdf_bytes: bytes) -> tuple[bytes, str] | None:
    """Liefert (xml_bytes, filename) fuer bekannte eingebettete e-invoice-Dateien."""
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001
        return None

    try:
        for idx in range(doc.embfile_count()):
            info = doc.embfile_info(idx)
            filename = str(info.get("filename") or info.get("name") or "")
            if filename.lower() not in _ATTACHMENT_NAMES:
                continue
            payload = doc.embfile_get(idx)
            return payload, filename
    except Exception:  # noqa: BLE001
        return None
    finally:
        doc.close()

    return None
