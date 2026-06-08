"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { InvoiceSortKey } from "@/lib/invoices/queries";

export interface InvoiceFilters {
  q: string;
  status: string[];
  reviewed: boolean;
  vendor: string;
  extractionMethod: string;
  dateFrom: string;
  dateTo: string;
  amountMin: string;
  amountMax: string;
  sort: InvoiceSortKey;
  page: number;
  pageSize: number;
}

const DEFAULT_SORT: InvoiceSortKey = "date_desc";
const DEFAULT_PAGE_SIZE = 25;

function parseNumber(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(value ?? "", 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

function parseFilters(searchParams: URLSearchParams): InvoiceFilters {
  const statusRaw = searchParams.get("status");
  const status =
    statusRaw
      ?.split(",")
      .map((entry) => entry.trim())
      .filter(Boolean) ?? [];

  return {
    q: searchParams.get("q") ?? "",
    status,
    reviewed: searchParams.get("reviewed") === "false",
    vendor: searchParams.get("vendor") ?? "",
    extractionMethod: searchParams.get("extraction_method") ?? "",
    dateFrom: searchParams.get("date_from") ?? "",
    dateTo: searchParams.get("date_to") ?? "",
    amountMin: searchParams.get("amount_min") ?? "",
    amountMax: searchParams.get("amount_max") ?? "",
    sort: (searchParams.get("sort") as InvoiceSortKey | null) ?? DEFAULT_SORT,
    page: parseNumber(searchParams.get("page"), 1),
    pageSize: parseNumber(searchParams.get("page_size"), DEFAULT_PAGE_SIZE),
  };
}

export function useInvoiceUrlState() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const filters = useMemo(() => parseFilters(new URLSearchParams(searchParams.toString())), [searchParams]);

  const updateSearchParams = useCallback((updater: (params: URLSearchParams) => void): void => {
    const next = new URLSearchParams(searchParams.toString());
    updater(next);
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  const setFilter = useCallback(<K extends keyof InvoiceFilters>(key: K, value: InvoiceFilters[K] | null): void => {
    updateSearchParams((next) => {
      const paramKeyMap: Record<keyof InvoiceFilters, string> = {
        q: "q",
        status: "status",
        reviewed: "reviewed",
        vendor: "vendor",
        extractionMethod: "extraction_method",
        dateFrom: "date_from",
        dateTo: "date_to",
        amountMin: "amount_min",
        amountMax: "amount_max",
        sort: "sort",
        page: "page",
        pageSize: "page_size",
      };

      const targetKey = paramKeyMap[key];

      if (value === null) {
        next.delete(targetKey);
      } else if (Array.isArray(value)) {
        if (value.length === 0) {
          next.delete(targetKey);
        } else {
          next.set(targetKey, value.join(","));
        }
      } else if (typeof value === "boolean") {
        next.set(targetKey, String(value));
      } else if (typeof value === "number") {
        next.set(targetKey, String(value));
      } else if (value.length === 0) {
        next.delete(targetKey);
      } else {
        next.set(targetKey, value);
      }

      if (key !== "page" && key !== "pageSize") {
        next.set("page", "1");
      }
    });
  }, [updateSearchParams]);

  const setPage = useCallback((page: number): void => setFilter("page", page), [setFilter]);
  const setPageSize = useCallback((pageSize: number): void => {
    updateSearchParams((next) => {
      next.set("page_size", String(pageSize));
      next.set("page", "1");
    });
  }, [updateSearchParams]);

  const resetFilters = useCallback((): void => {
    updateSearchParams((next) => {
      const currentPage = next.get("page") ?? "1";
      const currentPageSize = next.get("page_size") ?? String(DEFAULT_PAGE_SIZE);
      const keys = Array.from(next.keys());
      keys.forEach((key) => next.delete(key));
      next.set("page", currentPage);
      next.set("page_size", currentPageSize);
    });
  }, [updateSearchParams]);

  return {
    filters,
    getFilters: () => filters,
    setFilter,
    setPage,
    setPageSize,
    resetFilters,
  };
}
