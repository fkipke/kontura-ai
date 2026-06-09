"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RefreshCcw } from "lucide-react";

import { ExtractionMethodBadge } from "@/components/invoices/extraction-method-badge";
import { ExtractedFieldsPanel } from "@/components/invoices/extracted-fields-panel";
import { UniversalFileViewer } from "@/components/invoices/viewers/universal-file-viewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvoice } from "@/lib/api/invoices";
import { useExtractionStatus, useInvoiceFiles } from "@/lib/api/invoiceFiles";

/**
 * Detail-Page fuer eine einzelne InvoiceFile.
 *
 * Architektur-Hinweis: Es existiert kein Backend-GET fuer EINE InvoiceFile - der
 * vorhandene `/api/v1/invoice-files`-Endpoint listet IMMER alles. Wir ziehen uns
 * die Metadaten daher aus der gecachten Liste. Falls die ID nicht in der Liste
 * gefunden wird (z.B. weil der Cache leer ist oder die Datei eben erst angelegt
 * wurde), forcen wir einen Refetch. Schlaegt auch der fehl, blenden wir einen
 * "Erneut laden"-Button + klaren Fehlerzustand ein - statt ewig "Vorschau wird
 * geladen..." stehen zu lassen.
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

  // Falls die ID nicht in der Liste ist (frisch hochgeladen oder Cache leer),
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

  // Loading-State: erster Listen-Fetch laeuft noch ODER wir haben gerade den
  // Retry getriggert.
  const isInitialLoading = isListInitialLoading || (!invoice && !hasRetried);

  // Hard-Error-State: Liste fertig, Retry durch, immer noch nichts gefunden.
  const isNotFound = !invoice && hasRetried && !listQuery.isFetching;

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
          {invoice ? (
            <UniversalFileViewer
              fileId={invoice.id}
              filename={invoice.filename}
              mimeType={invoice.mime_type}
              fileUrl={`/api/proxy/api/v1/invoice-files/${invoice.id}`}
            />
          ) : isInitialLoading ? (
            <Card className="h-full">
              <CardContent className="flex h-full flex-col gap-3 p-4">
                <div className="flex items-center justify-between gap-2">
                  <Skeleton className="h-8 w-40" />
                  <Skeleton className="h-8 w-32" />
                </div>
                <Skeleton className="h-[60vh] w-full" />
              </CardContent>
            </Card>
          ) : isNotFound ? (
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
          ) : (
            <Card>
              <CardContent className="py-8 text-sm text-muted-foreground">
                Vorschau wird geladen…
              </CardContent>
            </Card>
          )}
        </section>
        <aside className="space-y-3 lg:col-span-2">
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
        </aside>
      </main>
    </>
  );
}
