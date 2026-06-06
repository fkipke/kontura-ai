"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import { ExtractionMethodBadge } from "@/components/invoices/extraction-method-badge";
import { ExtractedFieldsPanel } from "@/components/invoices/extracted-fields-panel";
import { UniversalFileViewer } from "@/components/invoices/viewers/universal-file-viewer";
import { Card, CardContent } from "@/components/ui/card";
import { useInvoice } from "@/lib/api/invoices";
import { useExtractionStatus, useInvoiceFiles } from "@/lib/api/invoiceFiles";

export default function InvoiceDetailPage(): React.JSX.Element {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();

  const listQuery = useInvoiceFiles();
  const extractionQuery = useExtractionStatus(id);

  const invoice = listQuery.data?.items.find((item) => item.id === id) ?? null;
  const [hasRetried, setHasRetried] = useState(false);
  const hasRetriedRef = useRef(false);

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

  // G3.2: linked_invoice_id aus Extraction-Status → Invoice-Daten laden
  const linkedInvoiceId = extractionQuery.data?.linked_invoice_id ?? null;
  const invoiceQuery = useInvoice(linkedInvoiceId ?? "");
  const isListInitialLoading = listQuery.isLoading;
  const isExtractionInitialLoading = extractionQuery.isLoading;
  const isInvoiceInitialLoading = invoiceQuery.isLoading;

  const handleConflictReload = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["invoice", linkedInvoiceId] });
  }, [queryClient, linkedInvoiceId]);

  return (
    <>
      <div className="flex items-center gap-2 px-1 pb-2">
        <Link
          href="/"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Zurück zur Übersicht
        </Link>
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
