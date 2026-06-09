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

/**
 * Detail-Page fuer eine einzelne InvoiceFile.
 *
 * Wichtig: Es gibt KEIN Backend-GET-by-id. Wir suchen die Metadaten in der
 * gecachten Liste. Falls die Liste leer ist (z.B. weil sie gerade noch laedt),
 * rendern wir TROTZDEM schon die PDF-Vorschau via <PdfViewer> direkt mit der
 * ID aus der URL - der Browser-PDF-Viewer braucht keine Metadaten.
 *
 * Dadurch sehen Nutzer NIE mehr ein endloses Skeleton; die PDF rendert sofort.
 * Die extrahierten Felder rechts folgen, sobald die Liste durch ist.
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

  // Falls ID nicht in der Liste ist (frisch hochgeladen / Cache leer),
  // einmalig Refetch erzwingen.
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

  // Hard-Error: Liste fertig, Retry durch, ID nirgends gefunden.
  const isNotFound = !invoice && hasRetried && !listQuery.isFetching;

  // PDF-Vorschau: wir rendern OPTIMISTISCH sofort über die URL-ID,
  // auch wenn die Metadaten der Liste noch nicht da sind. Falls die Datei
  // tatsächlich nicht existiert, gibt das iframe einen 404 zurück und der
  // "Diese Rechnung konnte nicht geladen werden"-State unten fängt es ab,
  // sobald die Liste fertig durchgelaufen ist.
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
          ) : invoice ? (
            // Volle Metadaten verfügbar — nutze den Universal-Viewer
            // (kann PDF / XML / PNG / JPEG je nach mime_type).
            <UniversalFileViewer
              fileId={invoice.id}
              filename={invoice.filename}
              mimeType={invoice.mime_type}
              fileUrl={fileUrl}
            />
          ) : (
            // Liste laedt noch — wir nehmen an es ist ein PDF (häufigster Fall)
            // und zeigen die Vorschau bereits an. Sobald Metadaten kommen,
            // wechselt der View ggf. zum korrekten Viewer.
            <PdfViewer file={fileUrl} />
          )}
        </section>
        <aside className="space-y-3 lg:col-span-2">
          {isListInitialLoading && !invoice ? (
            <>
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-48 w-full" />
            </>
          ) : (
            <>
              <ExtractionMethodBadge
                method={invoice?.extraction_method ?? null}
                zugferdProfile={extractionQuery.data?.result?.zugferd_profile ?? null}
              />
              <ExtractedFieldsPanel
                invoice={invoice}
                extraction={extractionQuery.data ?? null}
                isInvoiceLoading={isListInitialLoading}
                isExtractionLoading={isExtractionInitialLoading}
                isInvoiceDataLoading={isInvoiceInitialLoading}
                hasRetried={hasRetried}
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
