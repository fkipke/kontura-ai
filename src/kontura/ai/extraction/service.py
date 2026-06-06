"""Extraction-Service: KI-gesteuerte Rechnungsdaten-Extraktion aus hochgeladenen Dateien.

Workflow (fuer jede Extraktion):
  pending|failed -> processing -> completed|failed

Idempotenz: completed + force=False = No-op (direkt zurueck).
Auto-Link: bei Erfolg wird Invoice gefunden oder angelegt, InvoiceFile.invoice_id gesetzt.
Fehler-Toleranz: Exception crasht NIE den Caller, Status wird auf 'failed' gesetzt.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.base import AIProvider
from kontura.ai.extraction.pdf import render_pdf_to_png_pages
from kontura.ai.extraction.schemas import ExtractedInvoiceData
from kontura.core.config import settings
from kontura.core.exceptions import NotFoundError
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_file import ExtractionMethod, ExtractionStatus, InvoiceFile
from kontura.infra.storage import FileStorage

logger = structlog.get_logger(__name__)

# System-Prompt fuer deutsche Rechnungsformate.
# Praezise Anweisung verbessert die Extraction-Qualitaet deutlich.
_SYSTEM_PROMPT = """Du bist ein Spezialist fuer die Verarbeitung deutscher Eingangsrechnungen.

Deine Aufgabe: Extrahiere alle Rechnungsdaten strukturiert und vollstaendig.

Wichtige Hinweise:
- Rechnungsnummer: Genau wie auf der Rechnung angegeben (z.B. "RE-2024-001", "2024/0042")
- Datum: Immer im Format YYYY-MM-DD (z.B. "2024-01-15")
- Betraege: Nettobetrag + USt. = Bruttobetrag. Deutsche USt. ist typisch 19% oder 7%.
- Waehrung: Standard EUR, ausser anders angegeben (ISO 4217)
- Fehlende Felder: null setzen, nicht raten
- Confidence-Notes: Hinweise wenn Felder unklar oder nur teilweise lesbar sind

Lese den Text und die Bilder der Rechnung sorgfaeltig und extrahiere alle verfuegbaren Daten.
"""


def _build_extraction_schema() -> dict[str, Any]:
    """Erstellt das JSON-Schema fuer OpenAI structured outputs."""
    return ExtractedInvoiceData.model_json_schema()


class ExtractionService:
    """Orchestriert die KI-Extraktion aus hochgeladenen Rechnungsdateien.

    Einmalige Instanz pro Extraktion (nicht als Singleton verwenden).
    Session wird vom Caller uebergeben; der Service committet selbst.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        storage: FileStorage,
        session: AsyncSession,
    ) -> None:
        self._ai_provider = ai_provider
        self._storage = storage
        self._session = session

    async def extract(
        self,
        tenant: TenantContext,
        file_id: uuid.UUID,
        *,
        force: bool = False,
    ) -> InvoiceFile:
        """Laedt Datei, rendert (PDF->PNG), ruft LLM, validiert, persistiert, linkt Invoice.

        Status-Machine: pending|failed -> processing -> completed|failed
        Idempotenz: completed + force=False = no-op (returnt direkt).
        Auto-Link: findet/erstellt Invoice (tenant_id, invoice_number) und setzt invoice_id.
        Audit: LLM-Call wird via AuditedAIProvider automatisch geloggt.
        Fehler werden gefangen, Status auf failed gesetzt, Exception NICHT propagiert.
        """
        log = logger.bind(tenant_id=tenant.tenant_id, file_id=str(file_id))

        # Schritt 1: Datei laden (NotFoundError propagiert bewusst - kein Retry sinnvoll)
        # Lazy-Import um Circular-Import-Kette zu vermeiden
        # (service.py <- repository <- __init__ <- router <- service.py)
        from kontura.api.invoice_files.repository import InvoiceFileRepository  # noqa: PLC0415

        repo = InvoiceFileRepository(self._session)
        invoice_file = await repo.get_by_id(tenant, file_id)
        if invoice_file is None:
            raise NotFoundError(
                f"InvoiceFile {file_id} nicht gefunden (Tenant: {tenant.tenant_id})"
            )

        # Schritt 2: Idempotenz-Check
        if invoice_file.extraction_status == ExtractionStatus.COMPLETED and not force:
            log.info("extraction_skipped_already_completed")
            return invoice_file

        # Schritt 3: Status auf 'processing' setzen (atomarer Statuswechsel)
        invoice_file.extraction_status = ExtractionStatus.PROCESSING
        invoice_file.extraction_attempts = (invoice_file.extraction_attempts or 0) + 1
        await self._session.commit()
        log.info(
            "extraction_started",
            attempt=invoice_file.extraction_attempts,
            mime_type=invoice_file.mime_type,
        )

        try:
            # Schritt 4: Datei-Bytes laden
            file_bytes = await self._storage.load(invoice_file.storage_path)

            # Schritt 5: PDF -> PNG-Seiten oder direktes Bild
            if invoice_file.mime_type == "application/pdf":
                image_list: list[bytes] = await asyncio.get_event_loop().run_in_executor(
                    None,
                    render_pdf_to_png_pages,
                    file_bytes,
                    settings.extraction_max_pdf_pages,
                    settings.extraction_pdf_dpi,
                )
            else:
                # PNG/JPEG: direkt weitergeben (OpenAI akzeptiert beides)
                image_list = [file_bytes]

            # Schritt 6+7: LLM aufrufen (Audit erfolgt im AuditedAIProvider automatisch)
            schema = _build_extraction_schema()
            (
                result_dict,
                prompt_tokens,
                completion_tokens,
            ) = await self._ai_provider.extract_structured(
                system_prompt=_SYSTEM_PROMPT,
                user_text="Extrahiere alle Rechnungsdaten aus der beigefuegten Datei.",
                image_bytes_list=image_list,
                json_schema=schema,
            )
            log.info(
                "extraction_llm_completed",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            # Schritt 9: Pydantic-Validierung (Hard-Fail bei ungueltigem Schema)
            extracted_data = ExtractedInvoiceData.model_validate(result_dict)

            # Schritt 10: Invoice finden oder neu anlegen
            invoice = await self._find_or_create_invoice(tenant, extracted_data)

            # Schritt 11: InvoiceFile aktualisieren
            invoice_file.invoice_id = invoice.id
            invoice_file.extraction_status = ExtractionStatus.COMPLETED
            invoice_file.extraction_result = extracted_data.model_dump(mode="json")
            invoice_file.extracted_at = datetime.now(tz=timezone.utc)  # noqa: UP017
            invoice_file.extraction_error = None
            invoice_file.extraction_method = ExtractionMethod.AI_VISION
            await self._session.commit()

            log.info(
                "extraction_completed",
                invoice_id=str(invoice.id),
                invoice_number=extracted_data.invoice_number,
            )

        except (NotFoundError, ValidationError, ValueError, RuntimeError, Exception) as exc:
            # Schritt 12: Fehler-Handling - crasht NICHT nach aussen
            error_msg = repr(exc)[:1000]
            log.warning("extraction_failed", error=error_msg)
            try:
                invoice_file.extraction_status = ExtractionStatus.FAILED
                invoice_file.extraction_error = error_msg
                await self._session.commit()
            except Exception as commit_exc:  # noqa: BLE001
                log.error("extraction_failed_commit_failed", error=repr(commit_exc))

        return invoice_file

    async def _find_or_create_invoice(
        self,
        tenant: TenantContext,
        data: ExtractedInvoiceData,
    ) -> Invoice:
        """Findet eine existierende Invoice oder legt eine neue an.

        Idempotenz via (tenant_id, invoice_number) UniqueConstraint.
        Existierende Invoice wird NICHT ueberschrieben - Original bleibt Source of Truth.
        """
        stmt = select(Invoice).where(
            Invoice.tenant_id == tenant.tenant_id,
            Invoice.invoice_number == data.invoice_number,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        # Neue Invoice anlegen
        invoice = Invoice(
            tenant_id=tenant.tenant_id,
            invoice_number=data.invoice_number,
            vendor_name=data.vendor_name,
            invoice_date=data.invoice_date,
            total_amount=data.total_amount,
            currency=data.currency,
            net_amount=data.net_amount,
            tax_amount=data.tax_amount,
            status=InvoiceStatus.PROCESSING,
        )
        self._session.add(invoice)
        try:
            await self._session.flush()
        except IntegrityError:
            # Race-Condition: anderer Worker hat gleichzeitig angelegt -> refetch
            await self._session.rollback()
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                raise  # Echter Fehler, nicht Race-Condition
            return existing

        return invoice
