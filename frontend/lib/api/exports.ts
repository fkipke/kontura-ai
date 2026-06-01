"use client";

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

export async function downloadDatevExport(from: string, to: string): Promise<DatevExportResult> {
  const url = `/api/proxy/api/v1/exports/datev?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
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
