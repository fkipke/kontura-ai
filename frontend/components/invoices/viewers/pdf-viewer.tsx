"use client";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 2.0;

interface PdfViewerProps {
  file: string;
}

export function PdfViewer({ file }: PdfViewerProps): React.JSX.Element {
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      const tag = (document.activeElement as HTMLElement | null)?.tagName ?? "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
        return;
      }

      switch (event.key) {
        case "ArrowLeft":
          setPage((current) => Math.max(1, current - 1));
          break;
        case "ArrowRight":
          setPage((current) => Math.min(pages, current + 1));
          break;
        case "+":
        case "=":
          setZoom((current) => Math.min(ZOOM_MAX, current + ZOOM_STEP));
          break;
        case "-":
          setZoom((current) => Math.max(ZOOM_MIN, current - ZOOM_STEP));
          break;
        case "0":
          setZoom(1);
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [pages]);

  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </Button>
            <span className="px-2 text-xs text-muted-foreground">Seite {page} von {pages}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => Math.min(pages, current + 1))}
              disabled={page >= pages}
            >
              <ChevronRight className="h-4 w-4" aria-hidden />
            </Button>
          </div>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setZoom((current) => Math.max(ZOOM_MIN, current - ZOOM_STEP))}
            >
              <Minus className="h-4 w-4" aria-hidden />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setZoom(1)}
              title="Auf 100% zurücksetzen"
              aria-label="Auf 100% zurücksetzen"
            >
              {Math.round(zoom * 100)}%
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setZoom((current) => Math.min(ZOOM_MAX, current + ZOOM_STEP))}
            >
              <Plus className="h-4 w-4" aria-hidden />
            </Button>
          </div>
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
      </CardContent>
    </Card>
  );
}
