"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { ExtractedFieldsPanel } from "@/components/invoices/extracted-fields-panel";
import { useExtractionStatus, useInvoiceFiles, fetchInvoiceFileBlob } from "@/lib/api/invoiceFiles";

const PdfViewer = dynamic(
  () => import("@/components/invoices/pdf-viewer").then((module) => module.PdfViewer),
  { ssr: false },
);

export default function InvoiceDetailPage(): React.JSX.Element {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const listQuery = useInvoiceFiles();
  const extractionQuery = useExtractionStatus(id);
  const blobQuery = useQuery({
    queryKey: ["invoice-blob", id],
    queryFn: () => fetchInvoiceFileBlob(id),
  });

  const invoice = listQuery.data?.items.find((item) => item.id === id) ?? null;

  return (
    <main className="grid min-h-[calc(100vh-8rem)] grid-cols-1 gap-4 lg:grid-cols-5">
      <section className="lg:col-span-3">
        <PdfViewer blob={blobQuery.data ?? null} isLoading={blobQuery.isLoading} />
      </section>
      <aside className="lg:col-span-2">
        <ExtractedFieldsPanel
          invoice={invoice}
          extraction={extractionQuery.data ?? null}
          loading={listQuery.isLoading || extractionQuery.isLoading}
        />
      </aside>
    </main>
  );
}
