"""Dashboard-Schemas fuer KPIs, Cashflow, Top-Vendors, Recent-Activity, Alerts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    open_invoices_count: int
    open_invoices_total_amount: Decimal
    paid_this_month_total: Decimal
    skonto_expiring_soon_count: int
    skonto_expiring_soon_potential_savings: Decimal
    vat_balance_current_quarter: Decimal


class CashflowPoint(BaseModel):
    month: str  # "YYYY-MM"
    total_amount: Decimal
    invoice_count: int


class CashflowResponse(BaseModel):
    points: list[CashflowPoint]


class TopVendor(BaseModel):
    vendor_name: str
    invoice_count: int
    total_amount: Decimal


class TopVendorsResponse(BaseModel):
    vendors: list[TopVendor]


class DashboardAlert(BaseModel):
    type: Literal["unusual_amount", "first_time_high_value_vendor", "potential_duplicate"]
    invoice_id: UUID
    invoice_number: str | None
    vendor_name: str | None
    total_amount: Decimal | None
    message: str
    severity: Literal["info", "warning", "danger"]


class AlertsResponse(BaseModel):
    alerts: list[DashboardAlert]
