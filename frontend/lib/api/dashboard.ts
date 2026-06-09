"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { apiRequest } from "@/lib/api/client";

// ============================================================
// Zod-Schemas (mirror src/kontura/api/dashboard/schemas.py)
// ============================================================

export const dashboardKpisSchema = z.object({
  open_invoices_count: z.number().int(),
  open_invoices_total_amount: z.union([z.string(), z.number()]),
  paid_this_month_total: z.union([z.string(), z.number()]),
  skonto_expiring_soon_count: z.number().int(),
  skonto_expiring_soon_potential_savings: z.union([z.string(), z.number()]),
  vat_balance_current_quarter: z.union([z.string(), z.number()]),
});

export const cashflowPointSchema = z.object({
  month: z.string(), // "YYYY-MM"
  total_amount: z.union([z.string(), z.number()]),
  invoice_count: z.number().int(),
});

export const cashflowResponseSchema = z.object({
  points: z.array(cashflowPointSchema),
});

export const topVendorSchema = z.object({
  vendor_name: z.string(),
  invoice_count: z.number().int(),
  total_amount: z.union([z.string(), z.number()]),
});

export const topVendorsResponseSchema = z.object({
  vendors: z.array(topVendorSchema),
});

// Backend returns list[InvoiceRead] for /recent-activity
export const recentInvoiceSchema = z.object({
  id: z.string().uuid(),
  invoice_number: z.string(),
  vendor_name: z.string(),
  invoice_date: z.string(),
  total_amount: z.union([z.string(), z.number()]),
  currency: z.string(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const dashboardAlertSchema = z.object({
  type: z.enum([
    "unusual_amount",
    "first_time_high_value_vendor",
    "potential_duplicate",
  ]),
  invoice_id: z.string().uuid(),
  invoice_number: z.string().nullable(),
  vendor_name: z.string().nullable(),
  total_amount: z.union([z.string(), z.number()]).nullable(),
  message: z.string(),
  severity: z.enum(["info", "warning", "danger"]),
});

export const alertsResponseSchema = z.object({
  alerts: z.array(dashboardAlertSchema),
});

export type DashboardKpis = z.infer<typeof dashboardKpisSchema>;
export type CashflowPoint = z.infer<typeof cashflowPointSchema>;
export type CashflowResponse = z.infer<typeof cashflowResponseSchema>;
export type TopVendor = z.infer<typeof topVendorSchema>;
export type TopVendorsResponse = z.infer<typeof topVendorsResponseSchema>;
export type RecentInvoice = z.infer<typeof recentInvoiceSchema>;
export type DashboardAlert = z.infer<typeof dashboardAlertSchema>;
export type AlertsResponse = z.infer<typeof alertsResponseSchema>;

// ============================================================
// react-query hooks
// ============================================================

const STALE_TIME_MS = 30_000;

export function useDashboardKpis() {
  return useQuery({
    queryKey: ["dashboard", "kpis"],
    queryFn: () =>
      apiRequest(
        "/api/proxy/api/v1/dashboard/kpis",
        { method: "GET" },
        (value) => dashboardKpisSchema.parse(value),
      ),
    staleTime: STALE_TIME_MS,
  });
}

export function useDashboardCashflow(months: number = 12) {
  return useQuery({
    queryKey: ["dashboard", "cashflow", months],
    queryFn: () =>
      apiRequest(
        `/api/proxy/api/v1/dashboard/cashflow?months=${months}`,
        { method: "GET" },
        (value) => cashflowResponseSchema.parse(value),
      ),
    staleTime: STALE_TIME_MS,
  });
}

export function useDashboardTopVendors(limit: number = 5) {
  return useQuery({
    queryKey: ["dashboard", "top-vendors", limit],
    queryFn: () =>
      apiRequest(
        `/api/proxy/api/v1/dashboard/top-vendors?limit=${limit}`,
        { method: "GET" },
        (value) => topVendorsResponseSchema.parse(value),
      ),
    staleTime: STALE_TIME_MS,
  });
}

export function useDashboardRecentActivity(limit: number = 10) {
  return useQuery({
    queryKey: ["dashboard", "recent-activity", limit],
    queryFn: () =>
      apiRequest(
        `/api/proxy/api/v1/dashboard/recent-activity?limit=${limit}`,
        { method: "GET" },
        (value) => z.array(recentInvoiceSchema).parse(value),
      ),
    staleTime: STALE_TIME_MS,
  });
}

export function useDashboardAlerts() {
  return useQuery({
    queryKey: ["dashboard", "alerts"],
    queryFn: () =>
      apiRequest(
        "/api/proxy/api/v1/dashboard/alerts",
        { method: "GET" },
        (value) => alertsResponseSchema.parse(value),
      ),
    staleTime: STALE_TIME_MS,
  });
}
