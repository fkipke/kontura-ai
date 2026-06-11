"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Calendar, Download, FileSpreadsheet, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DatevExportError,
  downloadDatevExport,
  fetchDatevPreview,
  type DatevPreviewResponse,
} from "@/lib/api/exports";
import { formatCurrency, formatGermanDate } from "@/lib/format";

const MAX_EXPORT_RANGE_DAYS = 3660;
const AUTH_REDIRECT_DELAY_MS = 1500;

function getTodayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function getFirstDayOfMonthIso(): string {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

function getFirstDayOfYearIso(): string {
  const now = new Date();
  return new Date(now.getFullYear(), 0, 1).toISOString().slice(0, 10);
}

// Weit genug zurueck, um auch alte Demo-/Testrechnungen zu erfassen.
function getEarliestIso(): string {
  return "2000-01-01";
}

function daysBetween(from: string, to: string): number {
  return (new Date(to).getTime() - new Date(from).getTime()) / (1000 * 60 * 60 * 24);
}

type QuickRange = "this-month" | "this-year" | "all-time";

/**
 * DATEV-Export mit Vorschau.
 *
 * UX-Idee: Nutzer sieht *vor* dem Download exakt welche Rechnungen mit welchen
 * Konten und welcher Summe in die EXTF-CSV einflieen. Damit ist der CSV-
 * Download nicht mehr eine Black-Box-Excel-Ausgabe, sondern das Resultat einer
 * sichtbar gemachten Buchungssicht.
 *
 * Default-Range: "Alle Zeit" + include_all_years=true. So sehen Nutzer*innen
 * sofort *alle* ihre als geprueft markierten Rechnungen, statt erst mit
 * Datumsfeldern herumprobieren zu muessen.
 */
export function DatevExportPreview(): React.JSX.Element {
  const today = getTodayIso();
  const router = useRouter();

  const [from, setFrom] = useState<string>(getEarliestIso());
  const [to, setTo] = useState<string>(today);
  const [includeAllYears, setIncludeAllYears] = useState<boolean>(true);
  const [downloading, setDownloading] = useState<boolean>(false);

  const fromAfterTo = Boolean(from && to && from > to);
  const rangeTooLarge = Boolean(
    from && to && !fromAfterTo && daysBetween(from, to) > MAX_EXPORT_RANGE_DAYS,
  );
  const incomplete = !from || !to;
  const rangeInvalid = incomplete || fromAfterTo || rangeTooLarge;

  let inlineError: string | null = null;
  if (fromAfterTo) inlineError = "Das Bis-Datum muss nach dem Von-Datum liegen.";
  else if (rangeTooLarge) inlineError = "Maximaler Zeitraum ist 10 Jahre.";

  const preview = useQuery({
    queryKey: ["datev-preview", from, to, includeAllYears],
    queryFn: () => fetchDatevPreview(from, to, includeAllYears),
    enabled: !rangeInvalid,
    staleTime: 5_000,
  });

  function applyQuickRange(range: QuickRange): void {
    if (range === "this-month") {
      setFrom(getFirstDayOfMonthIso());
      setTo(today);
    } else if (range === "this-year") {
      setFrom(getFirstDayOfYearIso());
      setTo(today);
    } else {
      setFrom(getEarliestIso());
      setTo(today);
    }
  }

  async function handleDownload(): Promise<void> {
    if (rangeInvalid || downloading) return;
    setDownloading(true);
    try {
      const result = await downloadDatevExport(from, to, includeAllYears);
      const label =
        result.invoiceCount === 1
          ? "1 Rechnung exportiert"
          : `${result.invoiceCount} Rechnungen exportiert`;
      toast.success(`DATEV-CSV bereit: ${label}`);
    } catch (err) {
      if (err instanceof DatevExportError) {
        if (err.status === 401) {
          toast.error("Sitzung abgelaufen", { description: "Bitte erneut anmelden." });
          setTimeout(() => router.push("/login"), AUTH_REDIRECT_DELAY_MS);
        } else if (err.status === 422) {
          toast.error("Ungültiger Zeitraum", { description: err.message });
        } else if (err.status === 429) {
          toast.error("Zu viele Anfragen", {
            description: "Bitte einen Moment warten und erneut versuchen.",
          });
        } else {
          toast.error("Export fehlgeschlagen", { description: err.message });
        }
      } else {
        toast.error("Export fehlgeschlagen", {
          description: "Ein unbekannter Fehler ist aufgetreten.",
        });
      }
    } finally {
      setDownloading(false);
    }
  }

  const hasNoInvoices = preview.data?.total_count === 0;
  const downloadDisabled = rangeInvalid || downloading || hasNoInvoices;

  return (
    <div className="space-y-5">
      {/* Quick-Select + Datumsfelder + Wirtschaftsjahr-Toggle */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Zeitraum
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => applyQuickRange("this-month")}
          >
            Diesen Monat
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => applyQuickRange("this-year")}
          >
            Dieses Jahr
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => applyQuickRange("all-time")}
          >
            Alle Zeit
          </Button>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="export-from">Von</Label>
            <input
              id="export-from"
              type="date"
              value={from}
              max={today}
              onChange={(e) => setFrom(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="export-to">Bis</Label>
            <input
              id="export-to"
              type="date"
              value={to}
              max={today}
              onChange={(e) => setTo(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={includeAllYears}
              onChange={(e) => setIncludeAllYears(e.target.checked)}
              className="h-4 w-4 rounded border-border accent-emerald-600"
            />
            Alle Wirtschaftsjahre einschließen
          </label>
        </div>

        {inlineError && (
          <p className="text-sm text-destructive" role="alert">
            {inlineError}
          </p>
        )}
      </div>

      {/* Preview */}
      {!rangeInvalid && (
        <PreviewContent
          isLoading={preview.isLoading}
          isError={preview.isError}
          data={preview.data ?? null}
        />
      )}

      {/* Download */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <p className="text-xs text-muted-foreground">
          Format: EXTF-Buchungsstapel (Windows-1252, Semikolon-getrennt) — direkt importierbar in
          DATEV Rechnungswesen / Unternehmen online.
        </p>
        <Button
          type="button"
          onClick={handleDownload}
          disabled={downloadDisabled}
          aria-busy={downloading}
        >
          {downloading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Download className="mr-2 h-4 w-4" aria-hidden />
          )}
          {downloading ? "Wird vorbereitet …" : "DATEV-CSV herunterladen"}
        </Button>
      </div>
    </div>
  );
}

function PreviewContent({
  isLoading,
  isError,
  data,
}: {
  isLoading: boolean;
  isError: boolean;
  data: DatevPreviewResponse | null;
}): React.JSX.Element {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="py-4 text-sm">
          Vorschau konnte nicht geladen werden.
        </CardContent>
      </Card>
    );
  }

  if (data.total_count === 0) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8 text-center">
          <FileSpreadsheet
            className="mx-auto h-8 w-8 text-muted-foreground"
            aria-hidden
          />
          <p className="text-sm font-medium">Keine geprüften Rechnungen im Zeitraum.</p>
          <p className="text-xs text-muted-foreground">
            Markiere Rechnungen in der Detail-Ansicht als „geprüft“, damit sie hier erscheinen.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {/* Summary */}
      <Card>
        <CardContent className="grid grid-cols-2 gap-4 py-4 sm:grid-cols-4">
          <SummaryStat
            label={data.total_count === 1 ? "Rechnung" : "Rechnungen"}
            value={String(data.total_count)}
          />
          <SummaryStat label="Brutto" value={formatCurrency(data.total_gross_amount)} />
          <SummaryStat label="Netto" value={formatCurrency(data.total_net_amount)} />
          <SummaryStat label="USt." value={formatCurrency(data.total_tax_amount)} />
        </CardContent>
      </Card>

      {/* Hinweise */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary" className="gap-1.5">
          <Calendar className="h-3 w-3" aria-hidden />
          Wirtschaftsjahr {data.fiscal_year_start.slice(0, 4)}
        </Badge>
        <Badge variant="secondary">
          Berater {data.consultant_number} · Mandant {data.client_number}
        </Badge>
        {data.skipped_outside_fiscal_year > 0 && (
          <Badge
            variant="secondary"
            className="border-amber-500/30 text-amber-600 dark:text-amber-400"
          >
            {data.skipped_outside_fiscal_year} außerhalb Wirtschaftsjahr übersprungen
          </Badge>
        )}
      </div>

      {/* Tabelle */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Lieferant</TableHead>
                <TableHead>Rechnungs-Nr.</TableHead>
                <TableHead>Datum</TableHead>
                <TableHead>Konten (Soll → Haben)</TableHead>
                <TableHead className="text-right">Betrag</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.invoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell className="max-w-[280px] truncate font-medium">
                    {inv.vendor_name}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{inv.invoice_number}</TableCell>
                  <TableCell>{formatGermanDate(inv.invoice_date)}</TableCell>
                  <TableCell>
                    <span className="font-mono text-xs">
                      {inv.expense_account}
                      <span className="mx-1 text-muted-foreground">→</span>
                      {inv.creditor_account}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-tnum">
                    {formatCurrency(inv.total_amount)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryStat({
  label,
  value,
}: {
  label: string;
  value: string;
}): React.JSX.Element {
  return (
    <div className="space-y-0.5">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}
