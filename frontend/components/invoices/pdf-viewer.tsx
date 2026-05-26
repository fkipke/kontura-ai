"use client";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  blob: Blob | null;
  isLoading: boolean;
}

export function PdfViewer({ blob, isLoading }: PdfViewerProps): React.JSX.Element {
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [zoom, setZoom] = useState(1);

  const file = useMemo(() => {
    if (!blob) {
      return null;
    }
    return URL.createObjectURL(blob);
  }, [blob]);

  if (isLoading) {
    return <Skeleton className="h-[70vh] w-full rounded-xl" />;
  }

  if (!file) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">Vorschau wird geladen…</CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => setZoom((current) => Math.max(0.5, current - 0.1))}>
            <Minus className="h-4 w-4" aria-hidden />
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setZoom((current) => Math.min(2, current + 0.1))}>
            <Plus className="h-4 w-4" aria-hidden />
          </Button>
        </div>
        <div className="flex-1 overflow-auto rounded-lg bg-muted/30 p-3">
          <Document
            file={file}
            loading={<Skeleton className="h-[60vh] w-full" />}
            onLoadSuccess={(payload) => {
              setPages(payload.numPages);
              setPage(1);
            }}
          >
            <Page pageNumber={page} scale={zoom} renderTextLayer renderAnnotationLayer className="mx-auto" />
          </Document>
        </div>
        <div className="flex items-center justify-center gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>
            <ChevronLeft className="h-4 w-4" aria-hidden />
          </Button>
          <span className="text-xs text-muted-foreground">Seite {page} von {pages}</span>
          <Button type="button" variant="ghost" size="sm" onClick={() => setPage((current) => Math.min(pages, current + 1))} disabled={page >= pages}>
            <ChevronRight className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
