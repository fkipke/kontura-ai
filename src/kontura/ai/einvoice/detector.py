from __future__ import annotations

from defusedxml import ElementTree as DefusedET

from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml
from kontura.ai.einvoice.schemas import EinvoiceFormat

_UBL_INVOICE_ROOT = "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"
_CII_INVOICE_ROOT = (
    "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice"
)
_XML_MIME_TYPES = {"application/xml", "text/xml"}


def detect_einvoice_format(content: bytes, mime_type: str) -> EinvoiceFormat:
    """Deterministische Format-Erkennung. Niemals raise."""
    normalized_mime = mime_type.split(";", 1)[0].strip().lower()

    if normalized_mime in _XML_MIME_TYPES:
        try:
            root = DefusedET.fromstring(content)
        except Exception:  # noqa: BLE001
            return EinvoiceFormat.NONE

        if root.tag == _UBL_INVOICE_ROOT:
            return EinvoiceFormat.XRECHNUNG_UBL
        if root.tag == _CII_INVOICE_ROOT:
            return EinvoiceFormat.XRECHNUNG_CII
        return EinvoiceFormat.NONE

    if normalized_mime == "application/pdf":
        embedded = extract_embedded_einvoice_xml(content)
        if embedded is not None:
            return EinvoiceFormat.ZUGFERD_PDF

    return EinvoiceFormat.NONE
