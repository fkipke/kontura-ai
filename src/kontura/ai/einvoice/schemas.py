from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class EinvoiceFormat(StrEnum):
    XRECHNUNG_UBL = "xrechnung_ubl"
    XRECHNUNG_CII = "xrechnung_cii"
    ZUGFERD_PDF = "zugferd_pdf"
    NONE = "none"


class ZugferdProfile(StrEnum):
    MINIMUM = "minimum"
    BASIC_WL = "basic_wl"
    BASIC = "basic"
    EN16931 = "en16931"
    EXTENDED = "extended"
    XRECHNUNG = "xrechnung"

    @classmethod
    def from_urn(cls, urn: str) -> ZugferdProfile | None:
        normalized = urn.strip().lower()
        mapping = {
            "urn:factur-x.eu:1p0:minimum": cls.MINIMUM,
            "urn:factur-x.eu:1p0:basicwl": cls.BASIC_WL,
            "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:basic": cls.BASIC,
            "urn:cen.eu:en16931:2017": cls.EN16931,
            "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended": cls.EXTENDED,
            "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0": cls.XRECHNUNG,
        }
        return mapping.get(normalized)


class EinvoiceParseError(Exception):
    """Hard failure beim XML-Parsing. Im Service abgefangen -> fallback auf AI."""


@dataclass(frozen=True)
class EinvoiceExtractionResult:
    invoice_id: uuid.UUID
    invoice_file_id: uuid.UUID
    extraction_method: str
    zugferd_profile: ZugferdProfile | None
