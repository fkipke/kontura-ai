from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.ai.einvoice.detector import detect_einvoice_format
from kontura.ai.einvoice.extractor import extract_zugferd_profile, parse_einvoice
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
        # Repositories sind Teil der Service-API fuer konsistente Konstruktion im Upload-Flow.
        self._invoice_file_repo = invoice_file_repo
        self._invoice_repo = invoice_repo

    async def try_extract(
        self,
        tenant: TenantContext,
        invoice_file: InvoiceFile,
        content_provider: Callable[[], Awaitable[bytes]],
    ) -> EinvoiceExtractionResult | None:
        """Versucht strukturierte Extraktion. None => AI-Pfad uebernimmt."""
        content = await content_provider()
        detected_fmt = detect_einvoice_format(content, invoice_file.mime_type)
        if detected_fmt == EinvoiceFormat.NONE:
            return None

        xml_content = content
        parse_fmt: EinvoiceFormat = detected_fmt
        extraction_method = (
            "zugferd_v2" if detected_fmt == EinvoiceFormat.ZUGFERD_PDF else detected_fmt.value
        )

        if detected_fmt == EinvoiceFormat.ZUGFERD_PDF:
            embedded = extract_embedded_einvoice_xml(content)
            if embedded is None:
                return None
            xml_content, _ = embedded
            parse_fmt = detect_einvoice_format(xml_content, "application/xml")
            if parse_fmt not in {EinvoiceFormat.XRECHNUNG_UBL, EinvoiceFormat.XRECHNUNG_CII}:
                return None

        log = logger.bind(
            tenant_id=tenant.tenant_id,
            file_id=str(invoice_file.id),
            parse_format=parse_fmt.value,
            upload_mime_type=invoice_file.mime_type,
        )
        try:
            extracted_data = parse_einvoice(xml_content, parse_fmt)
            zugferd_profile = extract_zugferd_profile(xml_content, parse_fmt)
        except EinvoiceParseError as exc:
            log.warning("einvoice_parse_failed", error=str(exc))
            return None
        except Exception:  # noqa: BLE001
            await self._session.rollback()
            raise

        try:
            invoice = await self._find_or_create_invoice(tenant, invoice_file, extracted_data)
            invoice_file.extraction_status = ExtractionStatus.COMPLETED
            invoice_file.extraction_result = {
                **extracted_data.model_dump(mode="json"),
                "zugferd_profile": zugferd_profile.value if zugferd_profile is not None else None,
            }
            invoice_file.extracted_at = datetime.now(tz=UTC)
            invoice_file.extraction_attempts = (invoice_file.extraction_attempts or 0) + 1
            invoice_file.extraction_method = extraction_method
            invoice_file.extraction_error = None

            await self._session.commit()
            return EinvoiceExtractionResult(
                invoice_id=invoice.id,
                invoice_file_id=invoice_file.id,
                extraction_method=extraction_method,
                zugferd_profile=zugferd_profile,
            )
        except Exception:  # noqa: BLE001
            await self._session.rollback()
            raise

    async def _find_or_create_invoice(
        self,
        tenant: TenantContext,
        invoice_file: InvoiceFile,
        data: ExtractedInvoiceData,
    ) -> Invoice:
        stmt = select(Invoice).where(
            Invoice.tenant_id == tenant.tenant_id,
            Invoice.invoice_number == data.invoice_number,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            invoice_file.invoice_id = existing.id
            return existing

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
        await self._session.flush()
        invoice_file.invoice_id = invoice.id
        return invoice
