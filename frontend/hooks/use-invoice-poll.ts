import type { InvoiceFile } from "@/lib/api/schemas";

export function shouldPollInvoices(rows: InvoiceFile[]): boolean {
  return rows.some(
    (row) =>
      row.extraction_status === "pending" || row.extraction_status === "processing",
  );
}
