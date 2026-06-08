"use client";

import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api/client";
import {
  alertsResponseSchema,
  cashflowResponseSchema,
  dashboardKpisSchema,
  recentActivityItemSchema,
  topVendorsResponseSchema,
  type AlertsResponse,
  type CashflowResponse,
  type DashboardKpis,
  type RecentActivityItem,
  type TopVendorsResponse,
} from "@/lib/dashboard/types";

export const dashboardQueryKeys = {
  root: ["dashboard"] as const,
  kpis: ["dashboard", "kpis"] as const,
  cashflow: ["dashboard", "cashflow"] as const,
  topVendors: ["dashboard", "top-vendors"] as const,
  recentActivity: ["dashboard", "recent-activity"] as const,
  alerts: ["dashboard", "alerts"] as const,
};

export function useDashboardKpis() {
  return useQuery({
    queryKey: dashboardQueryKeys.kpis,
    queryFn: () =>
      apiRequest(
        "/api/proxy/dashboard/kpis",
        { method: "GET" },
        (value) => dashboardKpisSchema.parse(value),
      ) as Promise<DashboardKpis>,
  });
}

export function useDashboardCashflow() {
  return useQuery({
    queryKey: dashboardQueryKeys.cashflow,
    queryFn: () =>
      apiRequest(
        "/api/proxy/dashboard/cashflow",
        { method: "GET" },
        (value) => cashflowResponseSchema.parse(value),
      ) as Promise<CashflowResponse>,
  });
}

export function useDashboardTopVendors() {
  return useQuery({
    queryKey: dashboardQueryKeys.topVendors,
    queryFn: () =>
      apiRequest(
        "/api/proxy/dashboard/top-vendors",
        { method: "GET" },
        (value) => topVendorsResponseSchema.parse(value),
      ) as Promise<TopVendorsResponse>,
  });
}

export function useDashboardRecentActivity() {
  return useQuery({
    queryKey: dashboardQueryKeys.recentActivity,
    queryFn: () =>
      apiRequest(
        "/api/proxy/dashboard/recent-activity",
        { method: "GET" },
        (value) => recentActivityItemSchema.array().parse(value),
      ) as Promise<RecentActivityItem[]>,
  });
}

export function useDashboardAlerts() {
  return useQuery({
    queryKey: dashboardQueryKeys.alerts,
    queryFn: () =>
      apiRequest(
        "/api/proxy/dashboard/alerts",
        { method: "GET" },
        (value) => alertsResponseSchema.parse(value),
      ) as Promise<AlertsResponse>,
  });
}
