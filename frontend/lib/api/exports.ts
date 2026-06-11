"use client";

import { z } from "zod";

export interface DatevExportResult {
  invoiceCount: number;
  skippedCount: number;
  filename: string;
}

export class DatevExportError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "DatevExportError";
  }
}

export function parseFilename(header: string | null): string | null {
  if (!header) return null;
  const match = /filename="?([^"]+)"?/i.exec(header);
  return match?.[1] ?? null;
}

export function defaultFilename(from: string, to: string): string {
  const fromClean = from.replace(/-/g, "");
  const toClean = to.replace(/-/g, "");
  return `EXTF_Buchungsstapel_${fromClean}_${toClean}.csv`;
}

export function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }, 0);
}

export async function downloadDatevExport(
  from: string,
  to: string,
  includeAllYears: boolean = false,
): Promise<DatevExportResult> {
  const params = new URLSearchParams({
    from,
    to,
    include_all_years: includeAllYears ? "true" : "false",
  });
  const url = `/api/proxy/api/v1/exports/datev?${params.toString()}`;
  const response = await fetch(url, { method: "GET" });

  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new DatevExportError(
      response.status,
      problem?.detail ?? `Fehler (${response.status})`,
    );
  }

  const blob = await response.blob();
  const filename =
    parseFilename(response.headers.get("content-disposition")) ?? defaultFilename(from, to);
  const invoiceCount = Number.parseInt(
    response.headers.get("x-datev-invoice-count") ?? "0",
    10,
  );
  const skippedCount = Number.parseInt(
    response.headers.get("x-datev-skipped-count") ?? "0",
    10,
  );

  triggerBrowserDownload(blob, filename);
  return { invoiceCount, skippedCount, filename };
}

// ============================================================================
// Preview (matches GET /api/v1/exports/datev/preview)
// ============================================================================

export const datevPreviewInvoiceSchema = z.object({
  id: z.string().uuid(),
  invoice_number: z.string(),
  vendor_name: z.string(),
  invoice_date: z.string(),
  total_amount: z.union([z.string(), z.number()]),
  net_amount: z.union([z.string(), z.number()]).nullable(),
  tax_amount: z.union([z.string(), z.number()]).nullable(),
  currency: z.string(),
  creditor_account: z.number().int(),
  expense_account: z.number().int(),
});

export const datevPreviewResponseSchema = z.object({
  from_date: z.string(),
  to_date: z.string(),
  invoices: z.array(datevPreviewInvoiceSchema),
  total_count: z.number().int(),
  skipped_outside_fiscal_year: z.number().int(),
  fiscal_year_start: z.string(),
  fiscal_year_end: z.string(),
  total_gross_amount: z.union([z.string(), z.number()]),
  total_net_amount: z.union([z.string(), z.number()]),
  total_tax_amount: z.union([z.string(), z.number()]),
  consultant_number: z.number().int(),
  client_number: z.number().int(),
  default_expense_account: z.number().int(),
  default_creditor_account: z.number().int(),
  include_all_years: z.boolean(),
});

export type DatevPreviewInvoice = z.infer<typeof datevPreviewInvoiceSchema>;
export type DatevPreviewResponse = z.infer<typeof datevPreviewResponseSchema>;

export async function fetchDatevPreview(
  from: string,
  to: string,
  includeAllYears: boolean = false,
): Promise<DatevPreviewResponse> {
  const params = new URLSearchParams({
    from,
    to,
    include_all_years: includeAllYears ? "true" : "false",
  });
  const url = `/api/proxy/api/v1/exports/datev/preview?${params.toString()}`;
  const response = await fetch(url, { method: "GET" });

  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new DatevExportError(
      response.status,
      problem?.detail ?? `Fehler (${response.status})`,
    );
  }

  const body = (await response.json()) as unknown;
  return datevPreviewResponseSchema.parse(body);
}
