from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.einvoice.detector import detect_einvoice_format
from kontura.ai.einvoice.extractor import parse_einvoice
from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml
from kontura.ai.einvoice.schemas import (
    EinvoiceExtractionResult,
    EinvoiceFormat,
    EinvoiceParseError,
)
from kontura.api.invoice_files.repository import InvoiceFileRepository
from kontura.api.invoices.repository import InvoiceRepository
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_file import ExtractionMethod, ExtractionStatus, InvoiceFile

logger = structlog.get_logger(__name__)


class EinvoiceExtractionService:
    def __init__(
        self,
        session: AsyncSession,
        invoice_file_repo: InvoiceFileRepository,
        invoice_repo: InvoiceRepository,
    ) -> None:
        self._session = session
        self._invoice_file_repo = invoice_file_repo
        self._invoice_repo = invoice_repo

    def _apply_invoice_fields(
        self,
        invoice: Invoice,
        extracted_data: object,
    ) -> None:
        """Apply extracted data onto an Invoice ORM row (no invoice_number).

        invoice_number is handled separately because changing it can violate
        the (tenant_id, invoice_number) unique constraint.
        """
        invoice.vendor_name = extracted_data.vendor_name  # type: ignore[attr-defined]
        invoice.invoice_date = extracted_data.invoice_date  # type: ignore[attr-defined]
        invoice.total_amount = extracted_data.total_amount  # type: ignore[attr-defined]
        invoice.currency = extracted_data.currency  # type: ignore[attr-defined]
        invoice.net_amount = extracted_data.net_amount  # type: ignore[attr-defined]
        invoice.tax_amount = extracted_data.tax_amount  # type: ignore[attr-defined]
        invoice.line_items = [
            item.model_dump(mode="json")
            for item in (extracted_data.line_items or [])  # type: ignore[attr-defined]
        ]

    async def try_extract(
        self,
        tenant: TenantContext,
        invoice_file: InvoiceFile,
        content_provider: Callable[[], Awaitable[bytes]],
    ) -> EinvoiceExtractionResult | None:
        content = await content_provider()
        fmt = detect_einvoice_format(content, invoice_file.mime_type)
        if fmt == EinvoiceFormat.NONE:
            return None

        xml_bytes = content
        real_fmt: EinvoiceFormat = fmt
        extraction_method: ExtractionMethod

        if fmt == EinvoiceFormat.ZUGFERD_PDF:
            embedded = extract_embedded_einvoice_xml(content)
            if embedded is None:
                return None
            xml_bytes, _filename = embedded
            real_fmt = detect_einvoice_format(xml_bytes, "application/xml")
            if real_fmt not in (EinvoiceFormat.XRECHNUNG_UBL, EinvoiceFormat.XRECHNUNG_CII):
                return None
            extraction_method = ExtractionMethod.ZUGFERD_V2
        elif fmt == EinvoiceFormat.XRECHNUNG_UBL:
            extraction_method = ExtractionMethod.XRECHNUNG_UBL
        elif fmt == EinvoiceFormat.XRECHNUNG_CII:
            extraction_method = ExtractionMethod.XRECHNUNG_CII
        else:
            return None

        try:
            extracted_data, profile = parse_einvoice(xml_bytes, real_fmt)
        except EinvoiceParseError as exc:
            logger.warning(
                "einvoice_parse_failed",
                file_id=str(invoice_file.id),
                tenant_id=tenant.tenant_id,
                error=repr(exc),
            )
            return None

        try:
            # Step 1: find any invoice we might want to link / update.
            # Priority order:
            #   a) the invoice currently linked via invoice_file.invoice_id
            #   b) any invoice with the same (tenant_id, invoice_number)
            currently_linked: Invoice | None = None
            if invoice_file.invoice_id is not None:
                currently_linked = await self._session.get(Invoice, invoice_file.invoice_id)

            same_number_stmt = select(Invoice).where(
                Invoice.tenant_id == tenant.tenant_id,
                Invoice.invoice_number == extracted_data.invoice_number,
            )
            same_number_invoice = (
                await self._session.execute(same_number_stmt)
            ).scalar_one_or_none()

            # Step 2: pick the target invoice without ever causing a
            # (tenant_id, invoice_number) unique-constraint violation.
            if same_number_invoice is not None:
                # There is already an invoice with the new invoice_number.
                # Re-link to it (no INSERT, no UPDATE of invoice_number elsewhere).
                # If currently_linked is a DIFFERENT row, we leave it untouched —
                # changing its invoice_number would violate the unique constraint.
                invoice = same_number_invoice
                self._apply_invoice_fields(invoice, extracted_data)
            elif currently_linked is not None:
                # No other invoice has the new invoice_number, so it's safe to
                # rename currently_linked to the new invoice_number (idempotent
                # when it's already the same).
                invoice = currently_linked
                invoice.invoice_number = extracted_data.invoice_number
                self._apply_invoice_fields(invoice, extracted_data)
            else:
                # Nothing to update → insert a new invoice.
                invoice = Invoice(
                    tenant_id=tenant.tenant_id,
                    invoice_number=extracted_data.invoice_number,
                    vendor_name=extracted_data.vendor_name,
                    invoice_date=extracted_data.invoice_date,
                    total_amount=extracted_data.total_amount,
                    currency=extracted_data.currency,
                    net_amount=extracted_data.net_amount,
                    tax_amount=extracted_data.tax_amount,
                    line_items=[
                        item.model_dump(mode="json") for item in (extracted_data.line_items or [])
                    ],
                    status=InvoiceStatus.PROCESSING,
                )
                self._session.add(invoice)
                await self._session.flush()

            invoice_file.invoice_id = invoice.id
            invoice_file.extraction_status = ExtractionStatus.COMPLETED
            invoice_file.extraction_result = {
                **extracted_data.model_dump(mode="json"),
                "zugferd_profile": profile.value if profile else None,
            }
            invoice_file.extracted_at = datetime.now(tz=timezone.utc)  # noqa: UP017
            invoice_file.extraction_attempts = (invoice_file.extraction_attempts or 0) + 1
            invoice_file.extraction_error = None
            invoice_file.extraction_method = extraction_method

            await self._session.commit()

            return EinvoiceExtractionResult(
                invoice_id=invoice.id,
                invoice_file_id=invoice_file.id,
                extraction_method=extraction_method.value,
                zugferd_profile=profile,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "einvoice_extraction_unexpected_error",
                file_id=str(invoice_file.id),
                tenant_id=tenant.tenant_id,
            )
            await self._session.rollback()
            raise
