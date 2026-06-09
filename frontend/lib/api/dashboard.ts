import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api/client";
import {
  alertsResponseSchema,
  cashflowResponseSchema,
  dashboardKpisSchema,
  invoiceListItemSchema,
  topVendorsResponseSchema,
  type AlertsResponse,
  type CashflowResponse,
  type DashboardKpis,
  type InvoiceListItem,
  type TopVendorsResponse,
} from "@/lib/api/schemas";

export function useDashboardKpis() {
  return useQuery({
    queryKey: ["dashboard", "kpis"],
    queryFn: async (): Promise<DashboardKpis> =>
      apiRequest(
        "/api/proxy/api/v1/dashboard/kpis",
        { method: "GET" },
        (value) => dashboardKpisSchema.parse(value),
      ),
  });
}

export function useDashboardCashflow(months = 12) {
  return useQuery({
    queryKey: ["dashboard", "cashflow", months],
    queryFn: async (): Promise<CashflowResponse> =>
      apiRequest(
        `/api/proxy/api/v1/dashboard/cashflow?months=${months}`,
        { method: "GET" },
        (value) => cashflowResponseSchema.parse(value),
      ),
  });
}

export function useDashboardTopVendors(limit = 5) {
  return useQuery({
    queryKey: ["dashboard", "top-vendors", limit],
    queryFn: async (): Promise<TopVendorsResponse> =>
      apiRequest(
        `/api/proxy/api/v1/dashboard/top-vendors?limit=${limit}`,
        { method: "GET" },
        (value) => topVendorsResponseSchema.parse(value),
      ),
  });
}

export function useDashboardRecentActivity(limit = 8) {
  return useQuery({
    queryKey: ["dashboard", "recent-activity", limit],
    queryFn: async (): Promise<InvoiceListItem[]> =>
      apiRequest(
        `/api/proxy/api/v1/dashboard/recent-activity?limit=${limit}`,
        { method: "GET" },
        (value) => invoiceListItemSchema.array().parse(value),
      ),
  });
}

export function useDashboardAlerts() {
  return useQuery({
    queryKey: ["dashboard", "alerts"],
    queryFn: async (): Promise<AlertsResponse> =>
      apiRequest(
        "/api/proxy/api/v1/dashboard/alerts",
        { method: "GET" },
        (value) => alertsResponseSchema.parse(value),
      ),
  });
}
