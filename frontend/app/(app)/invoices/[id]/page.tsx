"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RefreshCcw } from "lucide-react";

import { ExtractionMethodBadge } from "@/components/invoices/extraction-method-badge";
import { ExtractedFieldsPanel } from "@/components/invoices/extracted-fields-panel";
import { PdfViewer } from "@/components/invoices/viewers/pdf-viewer";
import { UniversalFileViewer } from "@/components/invoices/viewers/universal-file-viewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvoice } from "@/lib/api/invoices";
import { useExtractionStatus, useInvoiceFiles } from "@/lib/api/invoiceFiles";
import type { InvoiceFile } from "@/lib/api/schemas";

/**
 * Detail-Page fuer eine einzelne InvoiceFile.
 *
 * Wichtig: Es gibt KEIN Backend-GET-by-id fuer InvoiceFiles. Wir suchen die
 * Metadaten in der gecachten Liste. Falls die Liste leer / stale / langsam ist,
 * synthetisieren wir ein minimales Invoice-Objekt aus dem extraction-Endpoint
 * (der ist ID-basiert und immer schnell). Dadurch sehen Nutzer NIE mehr ein
 * endloses Skeleton - PDF-Vorschau UND extrahierte Felder sind sofort sichtbar,
 * solange die Extraktion durchgelaufen ist.
 */
export default function InvoiceDetailPage(): React.JSX.Element {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const queryClient = useQueryClient();

  const listQuery = useInvoiceFiles();
  const extractionQuery = useExtractionStatus(id);

  const invoice = listQuery.data?.items.find((item) => item.id === id) ?? null;
  const [hasRetried, setHasRetried] = useState(false);
  const hasRetriedRef = useRef(false);

  // Fallback: minimales Invoice aus der Extraktion synthetisieren, wenn die
  // Liste die ID (noch) nicht enthaelt. extractionQuery laeuft per ID und
  // ist deutlich robuster als der Listen-Endpoint.
  const extractionResult = extractionQuery.data?.result ?? null;
  const syntheticInvoice: InvoiceFile | null =
    !invoice && extractionResult
      ? {
          id,
          filename: "Rechnungsbeleg",
          mime_type: "application/pdf",
          size_bytes: 0,
          sha256: "",
          created_at: extractionQuery.data?.extracted_at ?? new Date().toISOString(),
          deduplicated: false,
          extraction_status: extractionQuery.data?.status ?? "completed",
          extraction_method: "ai_vision",
          vendor_name: extractionResult.vendor_name ?? null,
          invoice_date: extractionResult.invoice_date ?? null,
          total_amount:
            extractionResult.total_amount != null
              ? String(extractionResult.total_amount)
              : null,
          currency: extractionResult.currency ?? null,
        }
      : null;

  const effectiveInvoice = invoice ?? syntheticInvoice;

  // Falls ID nicht in der Liste ist, einmalig Refetch erzwingen.
  useEffect(() => {
    if (
      !invoice &&
      listQuery.isSuccess &&
      !listQuery.isFetching &&
      !hasRetriedRef.current
    ) {
      hasRetriedRef.current = true;
      void listQuery.refetch().finally(() => {
        setHasRetried(true);
      });
    }
  }, [invoice, listQuery.isSuccess, listQuery.isFetching, listQuery]);

  const linkedInvoiceId = extractionQuery.data?.linked_invoice_id ?? null;
  const invoiceQuery = useInvoice(linkedInvoiceId ?? "");
  const isListInitialLoading = listQuery.isLoading;
  const isExtractionInitialLoading = extractionQuery.isLoading;
  const isInvoiceInitialLoading = invoiceQuery.isLoading;

  const handleConflictReload = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["invoice", linkedInvoiceId] });
  }, [queryClient, linkedInvoiceId]);

  const handleForceReload = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["invoice-files"] });
    void queryClient.refetchQueries({ queryKey: ["invoice-files"] });
    void queryClient.invalidateQueries({ queryKey: ["extraction", id] });
    void queryClient.refetchQueries({ queryKey: ["extraction", id] });
  }, [queryClient, id]);

  // Hard-Error: alle drei Quellen (Liste, Retry, Extraktion) sind durch
  // und WIRKLICH nichts gefunden. Erst dann zeigen wir "konnte nicht geladen".
  const isNotFound =
    !effectiveInvoice &&
    hasRetried &&
    !listQuery.isFetching &&
    !extractionQuery.isLoading;

  const fileUrl = `/api/proxy/api/v1/invoice-files/${id}`;

  return (
    <>
      <div className="flex items-center justify-between gap-2 px-1 pb-2">
        <Link
          href="/invoices"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Zurück zu Rechnungen
        </Link>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleForceReload}
          aria-label="Aktualisieren"
        >
          <RefreshCcw className="mr-1 h-4 w-4" aria-hidden />
          Aktualisieren
        </Button>
      </div>
      <main className="grid min-h-[calc(100vh-8rem)] grid-cols-1 gap-4 lg:grid-cols-5">
        <section className="lg:col-span-3">
          {isNotFound ? (
            <Card>
              <CardContent className="space-y-4 py-10 text-center">
                <p className="text-sm font-medium">
                  Diese Rechnung konnte nicht geladen werden.
                </p>
                <p className="text-xs text-muted-foreground">
                  Versuche es mit „Aktualisieren“ oben rechts, oder kehre zur Liste zurück.
                </p>
                <div className="flex justify-center gap-2 pt-2">
                  <Button type="button" variant="outline" size="sm" onClick={handleForceReload}>
                    Neu laden
                  </Button>
                  <Button
                    type="button"
                    variant="default"
                    size="sm"
                    onClick={() => router.push("/invoices")}
                  >
                    Zurück zur Liste
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : effectiveInvoice ? (
            <UniversalFileViewer
              fileId={effectiveInvoice.id}
              filename={effectiveInvoice.filename}
              mimeType={effectiveInvoice.mime_type}
              fileUrl={fileUrl}
            />
          ) : (
            // Listen + Extraktion laden noch - wir nehmen an es ist ein PDF
            // und zeigen die Vorschau optimistisch direkt an.
            <PdfViewer file={fileUrl} />
          )}
        </section>
        <aside className="space-y-3 lg:col-span-2">
          {!effectiveInvoice && (isListInitialLoading || isExtractionInitialLoading) ? (
            <>
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-48 w-full" />
            </>
          ) : (
            <>
              <ExtractionMethodBadge
                method={effectiveInvoice?.extraction_method ?? null}
                zugferdProfile={extractionQuery.data?.result?.zugferd_profile ?? null}
              />
              <ExtractedFieldsPanel
                invoice={effectiveInvoice}
                extraction={extractionQuery.data ?? null}
                isInvoiceLoading={isListInitialLoading}
                isExtractionLoading={isExtractionInitialLoading}
                isInvoiceDataLoading={isInvoiceInitialLoading}
                hasRetried={hasRetried || Boolean(effectiveInvoice)}
                invoiceData={invoiceQuery.data ?? null}
                invoiceId={linkedInvoiceId}
                onConflictReload={handleConflictReload}
              />
            </>
          )}
        </aside>
      </main>
    </>
  );
}
