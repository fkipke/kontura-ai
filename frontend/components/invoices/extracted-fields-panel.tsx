"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/invoices/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiClientError } from "@/lib/api/client";
import { useTriggerExtraction } from "@/lib/api/invoiceFiles";
import type { ExtractionStatus, InvoiceFile } from "@/lib/api/schemas";
import { formatCurrency, formatGermanDate, formatGermanDateTime } from "@/lib/format";

interface ExtractedFieldsPanelProps {
  invoice: InvoiceFile | null;
  extraction: ExtractionStatus | null;
  loading: boolean;
}

function renderValue(value: string | null | undefined): React.JSX.Element {
  return <span className={value ? "text-foreground" : "text-muted-foreground"}>{value || "–"}</span>;
}

export function ExtractedFieldsPanel({
  invoice,
  extraction,
  loading,
}: ExtractedFieldsPanelProps): React.JSX.Element {
  const retryMutation = useTriggerExtraction(invoice?.id ?? "");

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!invoice || !extraction) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">Rechnung konnte nicht geladen werden.</CardContent>
      </Card>
    );
  }

  const result = extraction.result;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Zurück
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">{invoice.filename}</h1>
      </div>

      <Card>
        <CardContent className="space-y-2 p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Status</span>
            <StatusBadge status={extraction.status} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Extrahiert am</span>
            <span>{formatGermanDateTime(extraction.extracted_at)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Versuche</span>
            <span className="font-tnum">{extraction.attempts}</span>
          </div>
        </CardContent>
      </Card>

      {extraction.status === "failed" && (
        <Card className="border-destructive/30 bg-destructive/10">
          <CardContent className="space-y-3 p-4 text-sm">
            <p className="font-medium text-destructive">Extraktion fehlgeschlagen</p>
            <p>{extraction.error || "Bitte erneut versuchen."}</p>
            <Button
              type="button"
              variant="destructive"
              onClick={async () => {
                try {
                  await retryMutation.mutateAsync();
                  toast.success("Extraktion wurde erneut gestartet.");
                } catch (error) {
                  if (error instanceof ApiClientError) {
                    toast.error(error.detail);
                    return;
                  }
                  toast.error("Extraktion konnte nicht gestartet werden.");
                }
              }}
              disabled={retryMutation.isPending}
            >
              Erneut extrahieren
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="space-y-4 p-4 text-sm">
          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-tight">Beleg</h2>
            <Field label="Rechnungsnummer" value={result?.invoice_number} />
            <Field label="Rechnungsdatum" value={formatGermanDate(result?.invoice_date ?? null)} />
            <Field label="Fälligkeitsdatum" value={formatGermanDate(result?.due_date ?? null)} />
            <Field label="Lieferant" value={result?.vendor_name} />
            <Field label="Adresse" value={result?.vendor_address} />
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-tight">Beträge</h2>
            <Field label="Netto" value={formatCurrency(result?.net_amount ?? null)} align="right" />
            <Field label="Steuer" value={formatCurrency(result?.tax_amount ?? null)} align="right" />
            <Field label="Gesamt" value={formatCurrency(result?.total_amount ?? null)} align="right" />
            <Field label="Währung" value={result?.currency} align="right" />
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-tight">Positionen</h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Beschreibung</TableHead>
                  <TableHead>Menge</TableHead>
                  <TableHead>Einzelpreis</TableHead>
                  <TableHead>Gesamt</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(result?.line_items?.length ?? 0) === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-muted-foreground">
                      –
                    </TableCell>
                  </TableRow>
                ) : (
                  result?.line_items?.map((item, index) => (
                    <TableRow key={`${item.description ?? "item"}-${index}`}>
                      <TableCell>{item.description || "–"}</TableCell>
                      <TableCell className="font-tnum">{item.quantity ?? "–"}</TableCell>
                      <TableCell className="font-tnum">{formatCurrency(item.unit_price ?? null)}</TableCell>
                      <TableCell className="font-tnum">{formatCurrency(item.total_price ?? null)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-tight">Notizen</h2>
            <p className="text-sm text-muted-foreground">{result?.confidence_notes || "–"}</p>
          </section>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  align,
}: {
  label: string;
  value: string | null | undefined;
  align?: "right";
}): React.JSX.Element {
  return (
    <div className="grid grid-cols-2 gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className={`${align === "right" ? "text-right font-tnum" : ""}`}>
        {renderValue(value)}
      </span>
    </div>
  );
}
