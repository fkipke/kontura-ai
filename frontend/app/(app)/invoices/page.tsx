"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RefreshCcw } from "lucide-react";

import { InvoiceTable } from "@/components/invoices/invoice-table";
import { UploadDropzone } from "@/components/invoices/upload-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiClientError } from "@/lib/api/client";
import { useInvoiceFiles } from "@/lib/api/invoiceFiles";

export default function InvoicesPage(): React.JSX.Element {
  const router = useRouter();
  const queryClient = useQueryClient();
  const invoiceFiles = useInvoiceFiles();

  // Beim Mount Next.js RSC-Prefetch-Cache invalidieren + react-query Cache
  // forciert neu holen. Behebt das "Liste leer nach Navigation"-Problem.
  useEffect(() => {
    router.refresh();
    void queryClient.invalidateQueries({ queryKey: ["invoice-files"] });
  }, [router, queryClient]);

  const handleManualRefresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["invoice-files"] });
    void invoiceFiles.refetch();
  };

  const errorMessage =
    invoiceFiles.error instanceof ApiClientError
      ? `${invoiceFiles.error.status} · ${invoiceFiles.error.detail}`
      : invoiceFiles.error instanceof Error
        ? invoiceFiles.error.message
        : null;

  const items = invoiceFiles.data?.items ?? [];
  const totalCount = invoiceFiles.data?.totalCount ?? 0;

  // Aggregate Counter im Header (rein clientseitig, kein extra API-Call).
  const counters = useMemo(() => {
    let completed = 0;
    let processing = 0;
    let failed = 0;
    for (const it of items) {
      if (it.extraction_status === "completed") completed += 1;
      else if (it.extraction_status === "pending" || it.extraction_status === "processing")
        processing += 1;
      else if (it.extraction_status === "failed") failed += 1;
    }
    return { completed, processing, failed };
  }, [items]);

  const showCountMismatch = items.length === 0 && totalCount > 0;

  return (
    <main className="space-y-6">
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight">Rechnungen</h1>
          <p className="text-sm text-muted-foreground">
            Übersicht aller hochgeladenen Belege
          </p>
          {items.length > 0 && (
            <p className="pt-1 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{items.length}</span>{" "}
              {items.length === 1 ? "Beleg" : "Belege"}
              <span className="mx-1.5">·</span>
              <span className="font-medium text-emerald-600 dark:text-emerald-400">
                {counters.completed}
              </span>{" "}
              verarbeitet
              {counters.processing > 0 && (
                <>
                  <span className="mx-1.5">·</span>
                  <span className="font-medium text-amber-600 dark:text-amber-400">
                    {counters.processing}
                  </span>{" "}
                  in Bearbeitung
                </>
              )}
              {counters.failed > 0 && (
                <>
                  <span className="mx-1.5">·</span>
                  <span className="font-medium text-rose-600 dark:text-rose-400">
                    {counters.failed}
                  </span>{" "}
                  fehlgeschlagen
                </>
              )}
            </p>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleManualRefresh}
          disabled={invoiceFiles.isFetching}
        >
          <RefreshCcw
            className={`mr-1 h-4 w-4 ${invoiceFiles.isFetching ? "animate-spin" : ""}`}
            aria-hidden
          />
          Aktualisieren
        </Button>
      </header>

      <UploadDropzone />

      {invoiceFiles.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : invoiceFiles.isError ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="space-y-3 py-6">
            <div className="flex items-start gap-2 text-sm">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
              <div className="space-y-1">
                <p className="font-medium">Liste konnte nicht geladen werden.</p>
                {errorMessage && (
                  <p className="text-xs text-muted-foreground">{errorMessage}</p>
                )}
              </div>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={handleManualRefresh}>
              Erneut versuchen
            </Button>
          </CardContent>
        </Card>
      ) : showCountMismatch ? (
        <Card className="border-yellow-400/40 bg-yellow-50 dark:bg-yellow-950/30">
          <CardContent className="space-y-3 py-6">
            <div className="flex items-start gap-2 text-sm">
              <AlertCircle
                className="mt-0.5 h-4 w-4 shrink-0 text-yellow-600 dark:text-yellow-400"
                aria-hidden
              />
              <div className="space-y-1">
                <p className="font-medium">
                  Datenproblem: Server meldet {totalCount} Rechnungen, der Client konnte aber
                  keine davon lesen.
                </p>
                <p className="text-xs text-muted-foreground">
                  Wahrscheinlich Schema-Mismatch. Öffne F12 → Konsole → schau nach
                  „[invoice-files] Skipping malformed item“.
                </p>
              </div>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={handleManualRefresh}>
              Erneut versuchen
            </Button>
          </CardContent>
        </Card>
      ) : (
        <InvoiceTable rows={items} />
      )}
    </main>
  );
}
