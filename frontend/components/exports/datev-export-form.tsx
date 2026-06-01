"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Download } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { downloadDatevExport, DatevExportError } from "@/lib/api/exports";

const MAX_EXPORT_RANGE_DAYS = 366;
const AUTH_REDIRECT_DELAY_MS = 1500;

function getTodayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function getFirstDayOfMonthIso(): string {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

function daysBetween(from: string, to: string): number {
  return (new Date(to).getTime() - new Date(from).getTime()) / (1000 * 60 * 60 * 24);
}

export function DatevExportForm(): React.JSX.Element {
  const today = getTodayIso();
  const firstOfMonth = getFirstDayOfMonthIso();

  const [from, setFrom] = useState(firstOfMonth);
  const [to, setTo] = useState(today);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const fromAfterTo = Boolean(from && to && from > to);
  const rangeTooLarge = Boolean(from && to && !fromAfterTo && daysBetween(from, to) > MAX_EXPORT_RANGE_DAYS);
  const incomplete = !from || !to;
  const disabled = loading || incomplete || fromAfterTo || rangeTooLarge;

  let inlineError: string | null = null;
  if (fromAfterTo) inlineError = "Das Bis-Datum muss nach dem Von-Datum liegen.";
  else if (rangeTooLarge) inlineError = "Maximaler Zeitraum ist 1 Jahr.";

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (disabled) return;
    setLoading(true);
    try {
      const result = await downloadDatevExport(from, to);
      const invoiceLabel =
        result.invoiceCount === 1
          ? `1 Rechnung im Buchungsstapel`
          : `${result.invoiceCount} Rechnungen im Buchungsstapel`;
      if (result.skippedCount > 0) {
        const skippedLabel =
          result.skippedCount === 1
            ? `1 Rechnung wegen Wirtschaftsjahr übersprungen`
            : `${result.skippedCount} Rechnungen wegen Wirtschaftsjahr übersprungen`;
        toast.success(`Export erstellt: ${invoiceLabel}`, { description: skippedLabel });
      } else {
        toast.success(`Export erstellt: ${invoiceLabel}`);
      }
    } catch (err) {
      if (err instanceof DatevExportError) {
        if (err.status === 422) {
          toast.error("Ungültiger Zeitraum", { description: err.message });
        } else if (err.status === 401) {
          toast.error("Sitzung abgelaufen", { description: "Bitte erneut anmelden." });
          setTimeout(() => {
            router.push("/login");
          }, AUTH_REDIRECT_DELAY_MS);
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
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="export-from">Von</Label>
          <input
            id="export-from"
            type="date"
            value={from}
            max={today}
            onChange={(e) => setFrom(e.target.value)}
            aria-describedby="export-hint"
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
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
            aria-describedby="export-hint"
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          />
        </div>
      </div>

      {inlineError && (
        <p className="text-sm text-destructive" role="alert">
          {inlineError}
        </p>
      )}

      <div className="space-y-1">
        <Button type="submit" disabled={disabled} aria-busy={loading}>
          <Download className="mr-2 h-4 w-4" aria-hidden />
          {loading ? "Wird vorbereitet …" : "EXTF-Datei herunterladen"}
        </Button>
        <p id="export-hint" className="text-xs text-muted-foreground">
          Maximaler Zeitraum: 1 Jahr
        </p>
      </div>
    </form>
  );
}
