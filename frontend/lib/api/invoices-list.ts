import { useQuery } from "@tanstack/react-query";

import { ApiClientError } from "@/lib/api/client";
import { invoiceListItemSchema, type InvoiceListItem } from "@/lib/api/schemas";

export interface InvoicesListFilters {
  search?: string;
  status?: string;
  reviewed?: "all" | "true" | "false";
  vendor?: string;
  dateFrom?: string;
  dateTo?: string;
  amountMin?: string;
  amountMax?: string;
  sortBy?: "invoice_date" | "created_at" | "total_amount" | "vendor_name" | "invoice_number" | "status";
  sortOrder?: "asc" | "desc";
}

export interface InvoicesListResult {
  items: InvoiceListItem[];
  totalCount: number;
}

function buildQuery(filters: InvoicesListFilters): string {
  const params = new URLSearchParams();
  params.set("limit", "200");
  params.set("offset", "0");

  if (filters.search?.trim()) params.set("search", filters.search.trim());
  if (filters.status && filters.status !== "all") params.append("status", filters.status);
  if (filters.reviewed && filters.reviewed !== "all") params.set("reviewed", filters.reviewed);
  if (filters.vendor?.trim()) params.append("vendor", filters.vendor.trim());
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);
  if (filters.amountMin) params.set("amount_min", filters.amountMin);
  if (filters.amountMax) params.set("amount_max", filters.amountMax);
  if (filters.sortBy) params.set("sort_by", filters.sortBy);
  if (filters.sortOrder) params.set("sort_order", filters.sortOrder);

  return params.toString();
}

export function useInvoicesList(filters: InvoicesListFilters) {
  return useQuery({
    queryKey: ["invoices", filters],
    queryFn: async (): Promise<InvoicesListResult> => {
      const query = buildQuery(filters);
      const response = await fetch(`/api/proxy/invoices?${query}`, { method: "GET" });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
          request_id?: string;
          errors?: Array<Record<string, unknown>>;
        } | null;
        throw new ApiClientError(
          response.status,
          payload?.detail ?? "Rechnungen konnten nicht geladen werden.",
          payload?.request_id ?? null,
          payload?.errors ?? [],
          null,
        );
      }

      const body = (await response.json()) as unknown;
      const parsed = invoiceListItemSchema.array().parse(body);
      const totalRaw = response.headers.get("x-total-count");
      return {
        items: parsed,
        totalCount: totalRaw ? Number.parseInt(totalRaw, 10) : parsed.length,
      };
    },
  });
}

export function useInvoiceVendors() {
  return useQuery({
    queryKey: ["invoice-vendors"],
    queryFn: async (): Promise<string[]> => {
      const response = await fetch("/api/proxy/invoices/vendors", { method: "GET" });
      if (!response.ok) {
        throw new Error("Lieferanten konnten nicht geladen werden.");
      }
      const body = (await response.json()) as unknown;
      return Array.isArray(body) ? body.filter((v): v is string => typeof v === "string") : [];
    },
  });
}
