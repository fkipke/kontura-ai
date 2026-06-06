"use client";

import { RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useMemo, useState } from "react";

import { ViewerToolbar } from "@/components/invoices/viewers/shared/viewer-toolbar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ImageViewerProps {
  fileUrl: string;
  filename: string;
}

const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200] as const;

export function ImageViewer({ fileUrl, filename }: ImageViewerProps): React.JSX.Element {
  const [zoomIndex, setZoomIndex] = useState(2);
  const [loaded, setLoaded] = useState(false);

  const zoomLevel = ZOOM_LEVELS[zoomIndex];
  const widthStyle = useMemo(() => ({ width: `${zoomLevel}%`, maxWidth: "none" }), [zoomLevel]);

  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-3 p-4">
        <ViewerToolbar
          filename={filename}
          controls={(
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setZoomIndex((current) => Math.max(0, current - 1))}
                disabled={zoomIndex === 0}
                aria-label="Verkleinern"
              >
                <ZoomOut className="h-4 w-4" />
              </Button>
              <span className="font-tnum text-xs">{zoomLevel}%</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setZoomIndex((current) => Math.min(ZOOM_LEVELS.length - 1, current + 1))}
                disabled={zoomIndex === ZOOM_LEVELS.length - 1}
                aria-label="Vergrößern"
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
                onClick={() => setZoomIndex(2)}
                aria-label="Zurücksetzen"
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
            </>
          )}
        />
        <p className="text-xs text-muted-foreground">Originalauflösung im Browser skalierbar.</p>
        <div className="relative flex-1 overflow-auto rounded-lg bg-muted/30 p-3">
          {!loaded ? <Skeleton className="h-[60vh] w-full" /> : null}
          <div className="flex min-h-full items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={fileUrl}
              alt={`Vorschau ${filename}`}
              style={widthStyle}
              className="h-auto object-contain"
              onLoad={() => setLoaded(true)}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
