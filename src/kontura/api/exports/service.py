"""Service fuer DATEV-Export (orchestriert Repository + CSV-Writer)."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta

import structlog

from kontura.api.exports.csv_writer import build_extf_buchungsstapel
from kontura.api.exports.repository import ExportRepository
from kontura.api.exports.schemas import DatevExportResult
from kontura.core.config import settings
from kontura.core.tenant import TenantContext

logger = structlog.get_logger(__name__)


class DatevExportService:
    """Kapselt DATEV-Export-Usecase ohne HTTP-spezifische Logik."""

    def __init__(self, repository: ExportRepository) -> None:
        self._repository = repository

    async def export_buchungsstapel(
        self,
        tenant: TenantContext,
        *,
        from_date: date,
        to_date: date,
    ) -> DatevExportResult:
        invoices = await self._repository.list_reviewed_in_range(
            tenant,
            from_date=from_date,
            to_date=to_date,
        )

        fiscal_year_end = _fiscal_year_end(settings.datev_fiscal_year_start)
        included = [
            invoice
            for invoice in invoices
            if settings.datev_fiscal_year_start <= invoice.invoice_date <= fiscal_year_end
        ]
        skipped_count = len(invoices) - len(included)

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
        )

        logger.info(
            "datev_export_created",
            tenant_id=tenant.tenant_id,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            invoice_count=len(included),
            skipped_count=skipped_count,
        )

        return DatevExportResult(
            content=content,
            invoice_count=len(included),
            skipped_count=skipped_count,
        )


def _fiscal_year_end(start: date) -> date:
    """Liefert das inklusive Enddatum eines Wirtschaftsjahres (1 Jahr - 1 Tag)."""
    try:
        next_year_start = start.replace(year=start.year + 1)
    except ValueError:
        max_day = calendar.monthrange(start.year + 1, start.month)[1]
        next_year_start = date(start.year + 1, start.month, min(start.day, max_day))
    return next_year_start - timedelta(days=1)
