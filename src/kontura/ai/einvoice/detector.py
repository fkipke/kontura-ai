from __future__ import annotations

from defusedxml import ElementTree as DefusedET

from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml
from kontura.ai.einvoice.schemas import EinvoiceFormat

_XML_MIME_TYPES = frozenset({"application/xml", "text/xml"})
_UBL_INVOICE_TAG = "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"
_CII_INVOICE_TAG = (
    "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice"
)


def _detect_xml_root(content: bytes) -> EinvoiceFormat:
    try:
        root = DefusedET.fromstring(content)
    except Exception:  # noqa: BLE001
        return EinvoiceFormat.NONE

    if root.tag == _UBL_INVOICE_TAG:
        return EinvoiceFormat.XRECHNUNG_UBL
    if root.tag == _CII_INVOICE_TAG:
        return EinvoiceFormat.XRECHNUNG_CII
    return EinvoiceFormat.NONE


def detect_einvoice_format(content: bytes, mime_type: str) -> EinvoiceFormat:
    """Deterministische Format-Erkennung. Niemals raise."""
    normalized_mime = mime_type.strip().lower()

    if normalized_mime in _XML_MIME_TYPES:
        return _detect_xml_root(content)

    if normalized_mime == "application/pdf":
        if extract_embedded_einvoice_xml(content) is not None:
            return EinvoiceFormat.ZUGFERD_PDF

    return EinvoiceFormat.NONE
