"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { InvoiceFilters } from "@/lib/invoices/url-state";

const decimalSchema = z.union([z.string(), z.number()]).nullable().optional();

const invoiceListItemSchema = z.object({
  id: z.string().uuid(),
  invoice_number: z.string().nullable().optional(),
  vendor_name: z.string().nullable().optional(),
  invoice_date: z.string().nullable().optional(),
  total_amount: decimalSchema,
  currency: z.string().nullable().optional(),
  status: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  is_reviewed: z.boolean().optional(),
  reviewed_at: z.string().nullable().optional(),
  extraction_method: z
    .enum(["ai_vision", "xrechnung_ubl", "xrechnung_cii", "zugferd_v2", "not_an_invoice"])
    .nullable()
    .optional(),
});

const vendorListSchema = z.union([
  z.array(z.string()),
  z.object({
    vendors: z.array(z.string()),
  }),
]);

export type InvoiceListItem = z.infer<typeof invoiceListItemSchema>;
export type ExtractionMethodFilter = "ai_vision" | "xrechnung_ubl" | "xrechnung_cii" | "zugferd_v2" | "not_an_invoice";
export type InvoiceSortKey =
  | "date_desc"
  | "date_asc"
  | "number_asc"
  | "number_desc"
  | "amount_desc"
  | "amount_asc";

interface InvoiceListResult {
  items: InvoiceListItem[];
  total: number;
  totalPages: number;
}

const sortMap: Record<InvoiceSortKey, { sortBy: string; sortOrder: "asc" | "desc" }> = {
  date_desc: { sortBy: "invoice_date", sortOrder: "desc" },
  date_asc: { sortBy: "invoice_date", sortOrder: "asc" },
  number_asc: { sortBy: "invoice_number", sortOrder: "asc" },
  number_desc: { sortBy: "invoice_number", sortOrder: "desc" },
  amount_desc: { sortBy: "total_amount", sortOrder: "desc" },
  amount_asc: { sortBy: "total_amount", sortOrder: "asc" },
};

async function fetchInvoices(filters: InvoiceFilters): Promise<InvoiceListResult> {
  const params = new URLSearchParams();
  const q = filters.q.trim();
  if (q) {
    // Backend contracts currently vary between `q` (spec) and `search` (existing router).
    params.set("q", q);
    params.set("search", q);
  }
  filters.status.forEach((status) => {
    params.append("status", status);
  });
  if (filters.reviewed) {
    params.set("reviewed", "false");
  }
  if (filters.vendor) {
    params.set("vendor", filters.vendor);
  }
  if (filters.extractionMethod) {
    // Backend contracts currently vary between `extraction_method` (spec) and `method` (existing router).
    params.set("extraction_method", filters.extractionMethod);
    params.set("method", filters.extractionMethod);
  }
  if (filters.dateFrom) {
    params.set("date_from", filters.dateFrom);
  }
  if (filters.dateTo) {
    params.set("date_to", filters.dateTo);
  }
  if (filters.amountMin) {
    params.set("amount_min", filters.amountMin);
  }
  if (filters.amountMax) {
    params.set("amount_max", filters.amountMax);
  }

  const sort = sortMap[filters.sort] ?? sortMap.date_desc;
  // `sort` keeps URL/UI state stable, while `sort_by` + `sort_order` are used by the backend router.
  params.set("sort", filters.sort);
  params.set("sort_by", sort.sortBy);
  params.set("sort_order", sort.sortOrder);

  // `page` + `page_size` are URL-state params; `limit` + `offset` are consumed by the backend router.
  params.set("page", String(filters.page));
  params.set("page_size", String(filters.pageSize));
  params.set("limit", String(filters.pageSize));
  params.set("offset", String((filters.page - 1) * filters.pageSize));

  const response = await fetch(`/api/proxy/api/v1/invoices?${params.toString()}`, {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Konnte Rechnungen nicht laden.");
  }

  const rawItems = (await response.json()) as unknown;
  const items = invoiceListItemSchema.array().parse(rawItems);
  const total = Number.parseInt(response.headers.get("x-total-count") ?? String(items.length), 10);
  const totalPages = Math.max(1, Math.ceil(total / filters.pageSize));

  return { items, total, totalPages };
}

async function fetchVendors(): Promise<string[]> {
  const response = await fetch("/api/proxy/invoices/vendors", { method: "GET", cache: "no-store" });
  if (!response.ok) {
    throw new Error("Lieferanten konnten nicht geladen werden.");
  }

  const parsed = vendorListSchema.parse((await response.json()) as unknown);
  return Array.isArray(parsed) ? parsed : parsed.vendors;
}

export function useInvoices(filters: InvoiceFilters) {
  return useQuery({
    queryKey: ["invoices", filters],
    queryFn: () => fetchInvoices(filters),
    placeholderData: (previousData) => previousData,
  });
}

export function useInvoiceVendors() {
  return useQuery({
    queryKey: ["invoices", "vendors"],
    queryFn: fetchVendors,
    staleTime: 5 * 60 * 1000,
  });
}
