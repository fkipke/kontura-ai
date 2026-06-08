"""Dashboard-Router: KPIs, Cashflow, Top-Vendors, Recent-Activity, Alerts."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

import sqlalchemy as sa
import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kontura.api.dashboard.schemas import (
    AlertsResponse,
    CashflowPoint,
    CashflowResponse,
    DashboardAlert,
    DashboardKpis,
    TopVendor,
    TopVendorsResponse,
)
from kontura.api.dependencies import TenantDep
from kontura.api.invoices.schemas import InvoiceRead
from kontura.api.rate_limit import limiter
from kontura.core.config import settings
from kontura.core.tenant import TenantContext
from kontura.infra.db import get_session
from kontura.infra.models.invoice import Invoice, InvoiceStatus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _current_quarter_bounds(today: date) -> tuple[date, date]:
    """Gibt (erster Tag, letzter Tag) des aktuellen Quartals zurueck."""
    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    quarter_start = date(today.year, quarter_start_month, 1)
    # Letzter Monat des Quartals
    last_month = quarter_start_month + 2
    last_day = calendar.monthrange(today.year, last_month)[1]
    quarter_end = date(today.year, last_month, last_day)
    return quarter_start, quarter_end


@router.get(
    "/kpis",
    response_model=DashboardKpis,
    summary="Dashboard-KPIs fuer den aktuellen Tenant",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_kpis(
    request: Request,  # noqa: ARG001
    tenant: TenantDep,
    session: SessionDep,
) -> DashboardKpis:
    today = date.today()

    # "Open" = not BOOKED or not reviewed
    open_stmt = select(
        func.count(Invoice.id),
        func.coalesce(func.sum(Invoice.total_amount), Decimal("0")),
    ).where(
        Invoice.tenant_id == tenant.tenant_id,
        (Invoice.status != InvoiceStatus.BOOKED) | (Invoice.is_reviewed.is_(False)),
    )
    open_result = (await session.execute(open_stmt)).one()
    open_count: int = open_result[0]
    open_total: Decimal = Decimal(str(open_result[1]))

    # "paid this month" — payment_status column does not exist yet; return 0
    paid_this_month: Decimal = Decimal("0")
    logger.info("dashboard.kpis.paid_this_month_unavailable", tenant_id=tenant.tenant_id)

    # skonto_* columns do not exist yet; return 0
    skonto_count = 0
    skonto_savings: Decimal = Decimal("0")

    # VAT balance current quarter = SUM(tax_amount) for current quarter
    q_start, q_end = _current_quarter_bounds(today)
    vat_stmt = select(func.coalesce(func.sum(Invoice.tax_amount), Decimal("0"))).where(
        Invoice.tenant_id == tenant.tenant_id,
        Invoice.invoice_date >= q_start,
        Invoice.invoice_date <= q_end,
        Invoice.tax_amount.is_not(None),
    )
    vat_result = (await session.execute(vat_stmt)).scalar_one()
    vat_balance = Decimal(str(vat_result))

    return DashboardKpis(
        open_invoices_count=open_count,
        open_invoices_total_amount=open_total,
        paid_this_month_total=paid_this_month,
        skonto_expiring_soon_count=skonto_count,
        skonto_expiring_soon_potential_savings=skonto_savings,
        vat_balance_current_quarter=vat_balance,
    )


@router.get(
    "/cashflow",
    response_model=CashflowResponse,
    summary="Cashflow-Zeitreihe (gruppiert nach Monat)",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_cashflow(
    request: Request,  # noqa: ARG001
    tenant: TenantDep,
    session: SessionDep,
    months: Annotated[int, Query(ge=1, le=60)] = 12,
) -> CashflowResponse:
    today = date.today()

    # Build the list of months we need (YYYY-MM strings, oldest first)
    month_labels: list[str] = []
    for i in range(months - 1, -1, -1):
        # Subtract i months from today
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        month_labels.append(f"{y:04d}-{m:02d}")

    # Aggregate from DB using to_char
    agg_stmt = (
        select(
            func.to_char(Invoice.invoice_date, "YYYY-MM").label("month"),
            func.sum(Invoice.total_amount).label("total_amount"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .where(Invoice.tenant_id == tenant.tenant_id)
        .group_by(text("month"))
        .order_by(text("month ASC"))
    )
    rows = (await session.execute(agg_stmt)).all()
    db_map = {row.month: (Decimal(str(row.total_amount)), row.invoice_count) for row in rows}

    # Fill gaps with zeros
    points = [
        CashflowPoint(
            month=label,
            total_amount=db_map.get(label, (Decimal("0"), 0))[0],
            invoice_count=db_map.get(label, (Decimal("0"), 0))[1],
        )
        for label in month_labels
    ]
    return CashflowResponse(points=points)


@router.get(
    "/top-vendors",
    response_model=TopVendorsResponse,
    summary="Top-Lieferanten nach Gesamtbetrag",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_top_vendors(
    request: Request,  # noqa: ARG001
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> TopVendorsResponse:
    stmt = (
        select(
            Invoice.vendor_name,
            func.count(Invoice.id).label("invoice_count"),
            func.sum(Invoice.total_amount).label("total_amount"),
        )
        .where(Invoice.tenant_id == tenant.tenant_id)
        .where(Invoice.vendor_name.is_not(None))
        .where(Invoice.vendor_name != "")
        .group_by(Invoice.vendor_name)
        .order_by(func.sum(Invoice.total_amount).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    vendors = [
        TopVendor(
            vendor_name=row.vendor_name,
            invoice_count=row.invoice_count,
            total_amount=Decimal(str(row.total_amount)),
        )
        for row in rows
    ]
    return TopVendorsResponse(vendors=vendors)


@router.get(
    "/recent-activity",
    response_model=list[InvoiceRead],
    summary="Zuletzt aktualisierte Rechnungen",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_recent_activity(
    request: Request,  # noqa: ARG001
    tenant: TenantDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[InvoiceRead]:
    stmt = (
        select(Invoice)
        .where(Invoice.tenant_id == tenant.tenant_id)
        .order_by(Invoice.updated_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [InvoiceRead.model_validate(inv) for inv in rows]


async def _build_alerts(tenant: TenantContext, session: AsyncSession) -> list[DashboardAlert]:
    """Berechnet Dashboard-Alerts nach einfachen Heuristiken (kein ML)."""
    alerts: list[DashboardAlert] = []
    today = date.today()
    ninety_days_ago = today - timedelta(days=90)

    # -- Unusual amount: total_amount > 10 * avg(last 90 days) --
    avg_stmt = select(func.avg(Invoice.total_amount)).where(
        Invoice.tenant_id == tenant.tenant_id,
        Invoice.invoice_date >= ninety_days_ago,
    )
    avg_amount_raw = (await session.execute(avg_stmt)).scalar_one()
    if avg_amount_raw is not None:
        avg_amount = Decimal(str(avg_amount_raw))
        threshold = avg_amount * 10
        unusual_stmt = (
            select(Invoice)
            .where(
                Invoice.tenant_id == tenant.tenant_id,
                Invoice.total_amount > threshold,
            )
            .order_by(Invoice.invoice_date.desc())
            .limit(10)
        )
        unusual_rows = (await session.execute(unusual_stmt)).scalars().all()
        for inv in unusual_rows:
            alerts.append(
                DashboardAlert(
                    type="unusual_amount",
                    invoice_id=inv.id,
                    invoice_number=inv.invoice_number,
                    vendor_name=inv.vendor_name,
                    total_amount=inv.total_amount,
                    message=(
                        f"Ungewöhnlich hoher Betrag: {inv.total_amount:.2f} € "
                        f"(Ø letzte 90 Tage: {avg_amount:.2f} €)."
                    ),
                    severity="warning",
                )
            )

    # -- First-time high-value vendor: first invoice ever AND total_amount > 1000 --
    high_value_stmt = (
        select(Invoice)
        .where(
            Invoice.tenant_id == tenant.tenant_id,
            Invoice.total_amount > Decimal("1000"),
            Invoice.vendor_name.is_not(None),
            Invoice.vendor_name != "",
        )
        .order_by(Invoice.invoice_date.desc())
        .limit(20)
    )
    high_value_rows = (await session.execute(high_value_stmt)).scalars().all()
    for inv in high_value_rows:
        # Check if this is the first invoice for this vendor
        count_stmt = select(func.count(Invoice.id)).where(
            Invoice.tenant_id == tenant.tenant_id,
            Invoice.vendor_name == inv.vendor_name,
        )
        vendor_count: int = (await session.execute(count_stmt)).scalar_one()
        if vendor_count == 1:
            alerts.append(
                DashboardAlert(
                    type="first_time_high_value_vendor",
                    invoice_id=inv.id,
                    invoice_number=inv.invoice_number,
                    vendor_name=inv.vendor_name,
                    total_amount=inv.total_amount,
                    message=(
                        f"Erste Rechnung von neuem Lieferant '{inv.vendor_name}' "
                        f"mit hohem Betrag ({inv.total_amount:.2f} €)."
                    ),
                    severity="info",
                )
            )

    # -- Potential duplicate: same vendor and amount across multiple invoices --
    dup_subq = (
        select(
            Invoice.vendor_name,
            Invoice.total_amount,
            func.count(Invoice.id).label("invoice_count"),
            func.min(sa.cast(Invoice.id, sa.String)).label("sample_id"),
        )
        .where(
            Invoice.tenant_id == tenant.tenant_id,
            Invoice.vendor_name.is_not(None),
            Invoice.vendor_name != "",
            Invoice.total_amount.is_not(None),
        )
        .group_by(Invoice.vendor_name, Invoice.total_amount)
        .having(func.count(Invoice.id) > 1)
        .order_by(func.count(Invoice.id).desc())
        .limit(10)
        .subquery()
    )
    dup_rows_stmt = select(
        Invoice.id,
        Invoice.invoice_number,
        Invoice.vendor_name,
        Invoice.total_amount,
    ).join(dup_subq, sa.cast(Invoice.id, sa.String) == dup_subq.c.sample_id)

    dup_rows = (await session.execute(dup_rows_stmt)).all()
    for row in dup_rows:
        alerts.append(
            DashboardAlert(
                type="potential_duplicate",
                invoice_id=row.id,
                invoice_number=row.invoice_number,
                vendor_name=row.vendor_name,
                total_amount=row.total_amount,
                message=(
                    f"Mögliche Doppelbuchung: Lieferant '{row.vendor_name}' "
                    f"hat mehrere Rechnungen mit demselben Betrag ({row.total_amount:.2f} €)."
                ),
                severity="danger",
            )
        )

    # Cap at 10, most recent invoice first
    alerts.sort(key=lambda a: str(a.invoice_id))
    return alerts[:10]


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Dashboard-Alerts (Heuristiken: ungewoehnliche Betraege, Duplikate, ...)",
)
@limiter.limit(settings.rate_limit_default_per_tenant)
async def get_alerts(
    request: Request,  # noqa: ARG001
    tenant: TenantDep,
    session: SessionDep,
) -> AlertsResponse:
    alerts = await _build_alerts(tenant, session)
    return AlertsResponse(alerts=alerts)
