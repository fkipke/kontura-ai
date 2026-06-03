from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.einvoice.detector import detect_einvoice_format
from kontura.ai.einvoice.extractor import parse_einvoice
from kontura.ai.einvoice.pdf_attachments import extract_embedded_einvoice_xml
from kontura.ai.einvoice.schemas import EinvoiceFormat, EinvoiceParseError, ZugferdProfile
from kontura.ai.extraction.schemas import ExtractedInvoiceData
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice, InvoiceStatus
from kontura.infra.models.invoice_file import ExtractionStatus, InvoiceFile

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EinvoiceExtractionResult:
    invoice_id: uuid.UUID
    invoice_file_id: uuid.UUID
    extraction_method: str
    zugferd_profile: ZugferdProfile | None


class EinvoiceExtractionService:
    def __init__(
        self,
        session: AsyncSession,
        invoice_file_repo: object,
        invoice_repo: object,
    ) -> None:
        self._session = session
        self._invoice_file_repo = invoice_file_repo
        self._invoice_repo = invoice_repo

    async def _find_or_create_invoice(
        self, tenant: TenantContext, extracted: ExtractedInvoiceData
    ) -> Invoice:
        stmt = select(Invoice).where(
            Invoice.tenant_id == tenant.tenant_id,
            Invoice.invoice_number == extracted.invoice_number,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        invoice = Invoice(
            tenant_id=tenant.tenant_id,
            invoice_number=extracted.invoice_number,
            vendor_name=extracted.vendor_name,
            invoice_date=extracted.invoice_date,
            total_amount=extracted.total_amount,
            currency=extracted.currency,
            net_amount=extracted.net_amount,
            tax_amount=extracted.tax_amount,
            status=InvoiceStatus.PROCESSING,
        )
        self._session.add(invoice)
        await self._session.flush()
        return invoice

    async def try_extract(
        self,
        tenant: TenantContext,
        invoice_file: InvoiceFile,
        content_provider: Callable[[], Awaitable[bytes]],
    ) -> EinvoiceExtractionResult | None:
        """None = AI-Pfad muss uebernehmen. Result = synchron extrahiert + persistiert."""
        content = await content_provider()
        fmt = detect_einvoice_format(content, invoice_file.mime_type)
        if fmt == EinvoiceFormat.NONE:
            return None

        xml_content = content
        effective_fmt: EinvoiceFormat = fmt
        extraction_method = fmt.value

        if fmt == EinvoiceFormat.ZUGFERD_PDF:
            attachment = extract_embedded_einvoice_xml(content)
            if attachment is None:
                return None
            xml_content = attachment[0]
            effective_fmt = detect_einvoice_format(xml_content, "application/xml")
            if effective_fmt == EinvoiceFormat.NONE:
                return None
            extraction_method = "zugferd_v2"

        if effective_fmt == EinvoiceFormat.XRECHNUNG_UBL and fmt != EinvoiceFormat.ZUGFERD_PDF:
            extraction_method = "xrechnung_ubl"
        elif effective_fmt == EinvoiceFormat.XRECHNUNG_CII and fmt != EinvoiceFormat.ZUGFERD_PDF:
            extraction_method = "xrechnung_cii"

        try:
            extracted, profile = parse_einvoice(xml_content, effective_fmt)
        except EinvoiceParseError as exc:
            logger.warning(
                "einvoice_parse_failed",
                tenant_id=tenant.tenant_id,
                file_id=str(invoice_file.id),
                error=str(exc),
            )
            return None

        try:
            invoice = await self._find_or_create_invoice(tenant, extracted)

            invoice_file.invoice_id = invoice.id
            invoice_file.extraction_status = ExtractionStatus.COMPLETED
            invoice_file.extraction_result = {
                **extracted.model_dump(mode="json"),
                "zugferd_profile": profile.value if profile is not None else None,
            }
            invoice_file.extracted_at = datetime.now(tz=UTC)
            invoice_file.extraction_error = None
            invoice_file.extraction_attempts = invoice_file.extraction_attempts + 1
            invoice_file.extraction_method = extraction_method

            await self._session.commit()

            return EinvoiceExtractionResult(
                invoice_id=invoice.id,
                invoice_file_id=invoice_file.id,
                extraction_method=extraction_method,
                zugferd_profile=profile,
            )
        except Exception:  # noqa: BLE001
            await self._session.rollback()
            raise
