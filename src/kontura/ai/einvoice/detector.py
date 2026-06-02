from __future__ import annotations

from defusedxml import ElementTree

from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml
from kontura.ai.einvoice.schemas import EinvoiceFormat

_XML_MIME_TYPES = frozenset({"application/xml", "text/xml"})

_UBL_ROOT = "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"
_CII_ROOT = "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}CrossIndustryInvoice"


def detect_einvoice_format(content: bytes, mime_type: str) -> EinvoiceFormat:
    """Deterministische Format-Erkennung. Niemals raise."""
    normalized_mime = (mime_type or "").split(";")[0].strip().lower()

    if normalized_mime in _XML_MIME_TYPES:
        try:
            root = ElementTree.fromstring(content)
        except Exception:  # noqa: BLE001
            return EinvoiceFormat.NONE

        if root.tag == _UBL_ROOT:
            return EinvoiceFormat.XRECHNUNG_UBL
        if root.tag == _CII_ROOT:
            return EinvoiceFormat.XRECHNUNG_CII
        return EinvoiceFormat.NONE

    if normalized_mime == "application/pdf":
        return (
            EinvoiceFormat.ZUGFERD_PDF
            if extract_embedded_einvoice_xml(content) is not None
            else EinvoiceFormat.NONE
        )

    return EinvoiceFormat.NONE
