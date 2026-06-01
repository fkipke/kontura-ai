"""Schemas fuer DATEV-Export-Service."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatevExportResult:
    """Ergebnis eines DATEV-Exports inkl. Header-Metadaten."""

    content: bytes
    invoice_count: int
    skipped_count: int
