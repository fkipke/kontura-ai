"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, CheckCircle2, Zap } from "lucide-react";
import { toast } from "sonner";

import { EditableField } from "@/components/invoices/editable-field";
import { StatusBadge } from "@/components/invoices/status-badge";
import { Badge } from "@/components/ui/badge";
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
import {
  InvoiceConflictError,
  useUpdateInvoice,
  type InvoiceUpdatePayload,
} from "@/lib/api/invoices";
import { useTriggerExtraction } from "@/lib/api/invoiceFiles";
import { useVendorMappingSuggestion } from "@/lib/api/vendorMappings";
import type {
  ExtractionStatus,
  InvoiceFile,
  InvoiceResponse,
  ValidationWarning,
} from "@/lib/api/schemas";
import { formatCurrency, formatGermanDate, formatGermanDateTime } from "@/lib/format";

interface ExtractedFieldsPanelProps {
  invoice: InvoiceFile | null;
  extraction: ExtractionStatus | null;
  loading: boolean;
  /** G3.2: verknüpftes Invoice-Objekt (editierbar) */
  invoiceData: InvoiceResponse | null;
  /** G3.2: invoiceId für PATCH-Mutations */
  invoiceId: string | null;
  /** G3.2: Wird aufgerufen wenn Nutzer auf „Neu laden" klickt nach 409 */
  onConflictReload?: () => void;
}

function renderValue(value: string | null | undefined): React.JSX.Element {
  return (
    <span className={value ? "text-foreground" : "text-muted-foreground"}>{value || "–"}</span>
  );
}

/** Prüft ob ein Feld sich vom KI-Original unterscheidet */
function isFieldModified(
  invoiceValue: string | number | null | undefined,
  extractionValue: string | number | null | undefined,
): boolean {
  if (invoiceValue == null && extractionValue == null) return false;
  return String(invoiceValue ?? "") !== String(extractionValue ?? "");
}

export function ExtractedFieldsPanel({
  invoice,
  extraction,
  loading,
  invoiceData,
  invoiceId,
  onConflictReload,
}: ExtractedFieldsPanelProps): React.JSX.Element {
  const retryMutation = useTriggerExtraction(invoice?.id ?? "");
  const updateMutation = useUpdateInvoice(invoiceId ?? "");
  const result = extraction?.result ?? null;
  const displayVendor = invoiceData?.vendor_name ?? result?.vendor_name ?? null;
  const suggestionQuery = useVendorMappingSuggestion(displayVendor);
  const suggestion = suggestionQuery.data ?? null;
  const creditorSuggestionKey = `${displayVendor ?? ""}:${suggestion?.creditor_account_number ?? ""}:${suggestion?.auto_apply ? "auto" : "manual"}`;
  const [creditorDraft, setCreditorDraft] = useState<{ key: string; value: string }>({
    key: "",
    value: "",
  });
  const creditorAccount =
    creditorDraft.key === creditorSuggestionKey
      ? creditorDraft.value
      : suggestion?.auto_apply
        ? String(suggestion.creditor_account_number)
        : "";

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
        <CardContent className="p-6 text-sm text-muted-foreground">
          Rechnung konnte nicht geladen werden.
        </CardContent>
      </Card>
    );
  }

  const version = invoiceData?.version ?? 1;
  const warnings: ValidationWarning[] = invoiceData?.validation_warnings ?? [];
  const ustWarning = warnings.find((w) => w.code === "ust_total_mismatch");
  const currencyWarning = warnings.find((w) => w.code === "unusual_currency");

  // USt-Live-Check (lokal während Tippens, ohne Server-Aufruf)
  const netVal = invoiceData?.net_amount;
  const taxVal = invoiceData?.tax_amount;
  const totalVal = invoiceData?.total_amount;
  const localUstMismatch =
    netVal != null &&
    taxVal != null &&
    totalVal != null &&
    Math.abs(
      parseFloat(String(netVal)) + parseFloat(String(taxVal)) - parseFloat(String(totalVal)),
    ) > 0.01;

  const handleSave = async (field: keyof InvoiceUpdatePayload, value: string) => {
    if (!invoiceId) return;
    try {
      const payload: InvoiceUpdatePayload = {
        expected_version: version,
        [field]: value || null,
      };
      const updateResult = await updateMutation.mutateAsync(payload);
      if (updateResult.warnings.some((w) => w.code === "ust_total_mismatch")) {
        toast.warning("USt-Prüfung: Netto + Steuer stimmt nicht mit Gesamtbetrag überein.");
      }
    } catch (error) {
      if (error instanceof InvoiceConflictError) {
        toast.error("Rechnung wurde zwischenzeitlich geändert. Bitte neu laden.");
        onConflictReload?.();
        return;
      }
      if (error instanceof ApiClientError) {
        toast.error(error.detail);
        return;
      }
      toast.error("Speichern fehlgeschlagen.");
    }
  };

  const handleMarkReviewed = async () => {
    if (!invoiceId) return;
    try {
      await updateMutation.mutateAsync({
        expected_version: version,
        is_reviewed: true,
      });
      toast.success("Rechnung als geprüft markiert.");
    } catch (error) {
      if (error instanceof InvoiceConflictError) {
        toast.error("Rechnung wurde zwischenzeitlich geändert. Bitte neu laden.");
        onConflictReload?.();
        return;
      }
      if (error instanceof ApiClientError) {
        toast.error(error.detail);
        return;
      }
      toast.error("Speichern fehlgeschlagen.");
    }
  };

  // Wert aus invoiceData (bearbeitbar) oder Fallback auf extraction
  const displayInvoiceNumber = invoiceData?.invoice_number ?? result?.invoice_number;
  const displayInvoiceDate = invoiceData?.invoice_date ?? result?.invoice_date;
  const displayNet = invoiceData?.net_amount != null ? String(invoiceData.net_amount) : null;
  const displayTax = invoiceData?.tax_amount != null ? String(invoiceData.tax_amount) : null;
  const displayTotal =
    invoiceData?.total_amount != null ? String(invoiceData.total_amount) : null;
  const displayCurrency = invoiceData?.currency ?? result?.currency;

  const handleCreditAccountSave = async () => {
    if (!invoiceId || !creditorAccount) return;
    try {
      await updateMutation.mutateAsync({
        expected_version: version,
        creditor_account_number: Number.parseInt(creditorAccount, 10),
      });
      toast.success("Kreditorkonto gespeichert.");
    } catch (error) {
      if (error instanceof InvoiceConflictError) {
        toast.error("Rechnung wurde zwischenzeitlich geändert. Bitte neu laden.");
        onConflictReload?.();
        return;
      }
      if (error instanceof ApiClientError) {
        toast.error(error.detail);
        return;
      }
      toast.error("Speichern fehlgeschlagen.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Zurück
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">{invoice.filename}</h1>
      </div>

      {/* G3.2: Geprüft-Badge oder Button */}
      {invoiceData && (
        <div className="flex items-center justify-between">
          {invoiceData.is_reviewed ? (
            <Badge
              variant="success"
              className="flex items-center gap-1 bg-green-600 text-white hover:bg-green-600"
            >
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
              Geprüft
            </Badge>
          ) : (
            <Button
              type="button"
              onClick={() => void handleMarkReviewed()}
              disabled={updateMutation.isPending}
              className="w-full"
            >
              Als geprüft markieren
            </Button>
          )}
        </div>
      )}

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

            {/* Rechnungsnummer: editierbar wenn invoiceData vorhanden */}
            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Rechnungsnummer</span>
              {invoiceId ? (
                <EditableField
                  value={displayInvoiceNumber}
                  label="Rechnungsnummer"
                  onSave={(v) => void handleSave("invoice_number", v)}
                  isPending={updateMutation.isPending}
                  isModified={isFieldModified(
                    invoiceData?.invoice_number,
                    result?.invoice_number,
                  )}
                />
              ) : (
                renderValue(result?.invoice_number)
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Rechnungsdatum</span>
              {invoiceId ? (
                <EditableField
                  value={displayInvoiceDate}
                  label="Rechnungsdatum"
                  onSave={(v) => void handleSave("invoice_date", v)}
                  isPending={updateMutation.isPending}
                  inputType="date"
                  isModified={isFieldModified(
                    invoiceData?.invoice_date,
                    result?.invoice_date,
                  )}
                />
              ) : (
                renderValue(formatGermanDate(result?.invoice_date ?? null))
              )}
            </div>

            <Field
              label="Fälligkeitsdatum"
              value={formatGermanDate(result?.due_date ?? null)}
            />

            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Lieferant</span>
              {invoiceId ? (
                <EditableField
                  value={displayVendor}
                  label="Lieferant"
                  onSave={(v) => void handleSave("vendor_name", v)}
                  isPending={updateMutation.isPending}
                  isModified={isFieldModified(invoiceData?.vendor_name, result?.vendor_name)}
                />
              ) : (
                renderValue(result?.vendor_name)
              )}
            </div>

            <Field label="Adresse" value={result?.vendor_address} />
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight">Kontierung</h2>

            <div className="grid gap-2">
              <label htmlFor="creditor-account" className="text-muted-foreground">
                Kreditorkonto
              </label>
              <div className="flex gap-2">
                <input
                  id="creditor-account"
                  type="number"
                  min={10000}
                  max={999999}
                  inputMode="numeric"
                  value={creditorAccount}
                  onChange={(event) =>
                    setCreditorDraft({
                      key: creditorSuggestionKey,
                      value: event.target.value,
                    })
                  }
                  className="w-full rounded border border-input bg-background px-3 py-2 text-sm"
                  placeholder="z. B. 70042"
                />
                <Button
                  type="button"
                  onClick={() => void handleCreditAccountSave()}
                  disabled={updateMutation.isPending || creditorAccount.length < 4}
                >
                  Speichern
                </Button>
              </div>

              {suggestion?.auto_apply && (
                <div className="flex items-center gap-2">
                  <Badge
                    variant="success"
                    className="flex items-center gap-1 bg-green-600 text-white hover:bg-green-600"
                  >
                    <Zap className="h-3.5 w-3.5" aria-hidden />
                    automatisch ({suggestion.usage_count}×)
                  </Badge>
                </div>
              )}

              {suggestion && !suggestion.auto_apply && (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-300">
                  <p>
                    Vorschlag: <strong>{suggestion.creditor_account_number}</strong> (zuletzt
                    verwendet {formatGermanDate(suggestion.last_used_at)}, {suggestion.usage_count}
                    × gebucht)
                  </p>
                  <Button
                    type="button"
                    variant="secondary"
                    className="mt-2"
                    onClick={() =>
                      setCreditorDraft({
                        key: creditorSuggestionKey,
                        value: String(suggestion.creditor_account_number),
                      })
                    }
                  >
                    Übernehmen
                  </Button>
                </div>
              )}
            </div>
          </section>

          {/* G3.2: USt-Mismatch-Warnung (gelbes Banner, nicht blockierend) */}
          {(ustWarning ?? localUstMismatch) && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-yellow-400 bg-yellow-50 p-3 text-xs text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-300"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>
                {ustWarning?.message ??
                  "Netto + Steuer stimmt nicht mit Gesamtbetrag überein. Bitte prüfen."}
              </span>
            </div>
          )}

          <section className="space-y-2">
            <h2 className="text-sm font-semibold tracking-tight">Beträge</h2>

            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Netto</span>
              {invoiceId ? (
                <EditableField
                  value={displayNet ?? formatCurrency(result?.net_amount ?? null)}
                  label="Nettobetrag"
                  onSave={(v) => void handleSave("net_amount", v)}
                  isPending={updateMutation.isPending}
                  inputType="number"
                  alignRight
                  isModified={isFieldModified(
                    invoiceData?.net_amount,
                    result?.net_amount,
                  )}
                />
              ) : (
                <span className="text-right font-tnum">
                  {renderValue(formatCurrency(result?.net_amount ?? null))}
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Steuer</span>
              {invoiceId ? (
                <EditableField
                  value={displayTax ?? formatCurrency(result?.tax_amount ?? null)}
                  label="Steuerbetrag"
                  onSave={(v) => void handleSave("tax_amount", v)}
                  isPending={updateMutation.isPending}
                  inputType="number"
                  alignRight
                  isModified={isFieldModified(
                    invoiceData?.tax_amount,
                    result?.tax_amount,
                  )}
                />
              ) : (
                <span className="text-right font-tnum">
                  {renderValue(formatCurrency(result?.tax_amount ?? null))}
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Gesamt</span>
              {invoiceId ? (
                <EditableField
                  value={displayTotal ?? formatCurrency(result?.total_amount ?? null)}
                  label="Gesamtbetrag"
                  onSave={(v) => void handleSave("total_amount", v)}
                  isPending={updateMutation.isPending}
                  inputType="number"
                  alignRight
                  isModified={isFieldModified(
                    invoiceData?.total_amount,
                    result?.total_amount,
                  )}
                />
              ) : (
                <span className="text-right font-tnum">
                  {renderValue(formatCurrency(result?.total_amount ?? null))}
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <span className="text-muted-foreground">Währung</span>
              {invoiceId ? (
                <EditableField
                  value={displayCurrency}
                  label="Währung"
                  onSave={(v) => void handleSave("currency", v)}
                  isPending={updateMutation.isPending}
                  alignRight
                  isModified={isFieldModified(invoiceData?.currency, result?.currency)}
                />
              ) : (
                <span className="text-right">{renderValue(result?.currency)}</span>
              )}
            </div>

            {/* G3.2: Ungewöhnliche Währung Warning */}
            {currencyWarning && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-yellow-400 bg-yellow-50 p-2 text-xs text-yellow-800 dark:border-yellow-600 dark:bg-yellow-950 dark:text-yellow-300"
              >
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                <span>{currencyWarning.message}</span>
              </div>
            )}
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
                      <TableCell className="font-tnum">
                        {formatCurrency(item.unit_price ?? null)}
                      </TableCell>
                      <TableCell className="font-tnum">
                        {formatCurrency(item.total_price ?? null)}
                      </TableCell>
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
