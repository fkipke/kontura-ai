"""Service fuer DATEV-Export (orchestriert Repository + CSV-Writer)."""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import structlog

from kontura.api.exports.csv_writer import build_extf_buchungsstapel
from kontura.api.exports.repository import ExportRepository
from kontura.api.exports.schemas import (
    DatevExportPreviewInvoice,
    DatevExportPreviewResponse,
    DatevExportResult,
)
from kontura.api.vendor_mappings.service import VendorMappingService
from kontura.core.config import settings
from kontura.core.tenant import TenantContext
from kontura.infra.models.invoice import Invoice

logger = structlog.get_logger(__name__)


class DatevExportService:
    """Kapselt DATEV-Export-Usecase ohne HTTP-spezifische Logik.

    Bietet zwei Operationen auf demselben Datensatz:
      * ``export_buchungsstapel``  -> bytes (DATEV-EXTF-CSV)
      * ``preview_buchungsstapel`` -> strukturierte JSON-Vorschau

    Beide nutzen denselben internen Selektor ``_collect``, damit Vorschau und
    Download garantiert die *gleichen* Rechnungen treffen - sonst koennten sie
    auseinanderlaufen und Nutzer*innen verwirren.
    """

    def __init__(
        self,
        repository: ExportRepository,
        *,
        vendor_mapping_service: VendorMappingService | None = None,
    ) -> None:
        self._repository = repository
        self._vendor_mapping_service = vendor_mapping_service

    async def export_buchungsstapel(
        self,
        tenant: TenantContext,
        *,
        from_date: date,
        to_date: date,
        include_all_years: bool = False,
    ) -> DatevExportResult:
        included, skipped_count = await self._collect(
            tenant,
            from_date=from_date,
            to_date=to_date,
            include_all_years=include_all_years,
        )
        creditor_overrides = await self._resolve_creditor_accounts(tenant, included)

        content = build_extf_buchungsstapel(
            included,
            from_date=from_date,
            to_date=to_date,
            consultant_number=settings.datev_consultant_number,
            client_number=settings.datev_client_number,
            fiscal_year_start=settings.datev_fiscal_year_start,
            account_length=settings.datev_account_length,
            default_expense_account=settings.datev_default_expense_account,
            default_creditor_account=settings.datev_default_creditor_account,
            created_at=datetime.now(tz=UTC),
            creditor_account_overrides=creditor_overrides,
        )

        logger.info(
            "datev_export_created",
            tenant_id=tenant.tenant_id,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            invoice_count=len(included),
            skipped_count=skipped_count,
            include_all_years=include_all_years,
        )

        return DatevExportResult(
            content=content,
            invoice_count=len(included),
            skipped_count=skipped_count,
        )

    async def preview_buchungsstapel(
        self,
        tenant: TenantContext,
        *,
        from_date: date,
        to_date: date,
        include_all_years: bool = False,
    ) -> DatevExportPreviewResponse:
        included, skipped_count = await self._collect(
            tenant,
            from_date=from_date,
            to_date=to_date,
            include_all_years=include_all_years,
        )
        creditor_overrides = await self._resolve_creditor_accounts(tenant, included)

        preview_invoices: list[DatevExportPreviewInvoice] = []
        total_gross = Decimal(0)
        total_net = Decimal(0)
        total_tax = Decimal(0)

        for invoice in included:
            creditor = (
                creditor_overrides.get(invoice.id, settings.datev_default_creditor_account)
                if creditor_overrides is not None
                else settings.datev_default_creditor_account
            )
            preview_invoices.append(
                DatevExportPreviewInvoice(
                    id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    vendor_name=invoice.vendor_name,
                    invoice_date=invoice.invoice_date,
                    total_amount=invoice.total_amount,
                    net_amount=invoice.net_amount,
                    tax_amount=invoice.tax_amount,
                    currency=invoice.currency,
                    creditor_account=creditor,
                    expense_account=settings.datev_default_expense_account,
                )
            )
            total_gross += invoice.total_amount
            if invoice.net_amount is not None:
                total_net += invoice.net_amount
            if invoice.tax_amount is not None:
                total_tax += invoice.tax_amount

        fiscal_year_end = _fiscal_year_end(settings.datev_fiscal_year_start)

        return DatevExportPreviewResponse(
            from_date=from_date,
            to_date=to_date,
            invoices=preview_invoices,
            total_count=len(preview_invoices),
            skipped_outside_fiscal_year=skipped_count,
            fiscal_year_start=settings.datev_fiscal_year_start,
            fiscal_year_end=fiscal_year_end,
            total_gross_amount=total_gross,
            total_net_amount=total_net,
            total_tax_amount=total_tax,
            consultant_number=settings.datev_consultant_number,
            client_number=settings.datev_client_number,
            default_expense_account=settings.datev_default_expense_account,
            default_creditor_account=settings.datev_default_creditor_account,
            include_all_years=include_all_years,
        )

    async def _collect(
        self,
        tenant: TenantContext,
        *,
        from_date: date,
        to_date: date,
        include_all_years: bool,
    ) -> tuple[list[Invoice], int]:
        """Holt geprueftee Rechnungen aus dem Repo und wendet ggf. den Wirtschaftsjahr-Filter an.

        Returns: (included_invoices, skipped_count)
        """
        invoices = await self._repository.list_reviewed_in_range(
            tenant, from_date=from_date, to_date=to_date
        )

        if include_all_years:
            return list(invoices), 0

        fiscal_year_end = _fiscal_year_end(settings.datev_fiscal_year_start)
        included = [
            inv
            for inv in invoices
            if settings.datev_fiscal_year_start <= inv.invoice_date <= fiscal_year_end
        ]
        return included, len(invoices) - len(included)

    async def _resolve_creditor_accounts(
        self,
        tenant: TenantContext,
        invoices: list[Invoice],
    ) -> dict[uuid.UUID, int] | None:
        if self._vendor_mapping_service is None:
            return None
        overrides: dict[uuid.UUID, int] = {}
        for inv in invoices:
            overrides[inv.id] = await self._vendor_mapping_service.resolve_for_export(
                tenant,
                inv.vendor_name,
                settings.datev_default_creditor_account,
            )
        return overrides


def _fiscal_year_end(start: date) -> date:
    """Liefert das inklusive Enddatum eines Wirtschaftsjahres (1 Jahr - 1 Tag)."""
    try:
        next_year_start = start.replace(year=start.year + 1)
    except ValueError:
        max_day = calendar.monthrange(start.year + 1, start.month)[1]
        next_year_start = date(start.year + 1, start.month, min(start.day, max_day))
    return next_year_start - timedelta(days=1)
