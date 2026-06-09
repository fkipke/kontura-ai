import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/(app)/page";

vi.mock("@/lib/api/dashboard", () => ({
  useDashboardKpis: () => ({
    isLoading: false,
    isError: false,
    data: {
      open_invoices_count: 12,
      open_invoices_total_amount: "1200.00",
      paid_this_month_total: "500.00",
      skonto_expiring_soon_count: 2,
      skonto_expiring_soon_potential_savings: "40.00",
      vat_balance_current_quarter: "190.00",
    },
  }),
  useDashboardCashflow: () => ({
    isLoading: false,
    isError: false,
    data: {
      points: [{ month: "2026-06", total_amount: "1200.00", invoice_count: 12 }],
    },
  }),
  useDashboardTopVendors: () => ({
    isLoading: false,
    isError: false,
    data: {
      vendors: [{ vendor_name: "Telekom GmbH", invoice_count: 4, total_amount: "400.00" }],
    },
  }),
  useDashboardRecentActivity: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        id: "9e84b5b7-d688-4f2e-bd40-2664c85f20f3",
        invoice_number: "RE-1001",
        vendor_name: "Telekom GmbH",
        invoice_date: "2026-06-01",
        total_amount: "120.00",
        currency: "EUR",
        status: "received",
        created_at: "2026-06-01T10:00:00Z",
        updated_at: "2026-06-01T10:00:00Z",
      },
    ],
  }),
  useDashboardAlerts: () => ({
    isLoading: false,
    isError: false,
    data: {
      alerts: [
        {
          type: "potential_duplicate",
          invoice_id: "9e84b5b7-d688-4f2e-bd40-2664c85f20f3",
          invoice_number: "RE-1001",
          vendor_name: "Telekom GmbH",
          total_amount: "120.00",
          message: "Mögliche Doppelbuchung",
          severity: "danger",
        },
      ],
    },
  }),
}));

describe("DashboardPage", () => {
  it("rendert KPI- und Dashboard-Bereiche", () => {
    render(<DashboardPage />);

    expect(screen.getByRole("heading", { name: "Übersicht" })).toBeInTheDocument();
    expect(screen.getByText("Offene Rechnungen")).toBeInTheDocument();
    expect(screen.getByText("Top-Lieferanten")).toBeInTheDocument();
    expect(screen.getByText("Risiko-Hinweise")).toBeInTheDocument();
  });
});
