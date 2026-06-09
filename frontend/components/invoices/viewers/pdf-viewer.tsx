"use client";

import { Download, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface PdfViewerProps {
  file: string;
  filename?: string;
}

/**
 * Native PDF-Viewer via <iframe>.
 *
 * Wir nutzen bewusst KEIN react-pdf / pdf.js mehr:
 *  - Chrome, Firefox, Edge, Safari haben alle einen eingebauten PDF-Renderer.
 *  - Kein zerbrechlicher worker.js-Pfad, kein Loading-Skeleton-Loop.
 *
 * Toolbar ist bewusst AUS (`#toolbar=0`) damit kein schwarzer Chrome-Balken
 * über der Vorschau hängt - der Look soll hochprofessionell sein.
 * Download &amp; "in neuem Tab" bieten wir über eigene Buttons oben rechts an.
 */
export function PdfViewer({ file, filename }: PdfViewerProps): React.JSX.Element {
  // toolbar=0  -> keine schwarze Chrome-PDF-Toolbar (kein Frame mehr)
  // navpanes=0 -> keine Seitenleiste mit Thumbnails
  // view=FitH  -> PDF passt sich an die Breite des iframes an
  const src = `${file}#toolbar=0&navpanes=0&view=FitH`;

  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">
              {filename ?? "Rechnungsbeleg"}
            </p>
            <p className="text-xs text-muted-foreground">
              Browser-Vorschau
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <a
              href={file}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex"
            >
              <Button type="button" variant="outline" size="sm">
                <ExternalLink className="mr-1 h-4 w-4" aria-hidden />
                In neuem Tab
              </Button>
            </a>
            <a href={file} download={filename ?? "rechnung.pdf"} className="inline-flex">
              <Button type="button" variant="outline" size="sm">
                <Download className="mr-1 h-4 w-4" aria-hidden />
                Download
              </Button>
            </a>
          </div>
        </div>
        <div className="flex-1 overflow-hidden rounded-lg border bg-white">
          <iframe
            src={src}
            title={filename ?? "PDF-Vorschau"}
            className="h-full w-full"
            style={{ minHeight: "60vh", border: "none" }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
