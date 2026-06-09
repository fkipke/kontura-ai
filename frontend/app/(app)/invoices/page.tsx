"use client";

import { InvoiceTable } from "@/components/invoices/invoice-table";
import { UploadDropzone } from "@/components/invoices/upload-dropzone";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvoiceFiles } from "@/lib/api/invoiceFiles";

export default function InvoicesPage(): React.JSX.Element {
  const invoiceFiles = useInvoiceFiles();

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Rechnungen</h1>
        <p className="text-sm text-muted-foreground">Übersicht aller hochgeladenen Belege</p>
      </header>

      <UploadDropzone />

      {invoiceFiles.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      ) : (
        <InvoiceTable rows={invoiceFiles.data?.items ?? []} />
      )}
    </main>
  );
}
