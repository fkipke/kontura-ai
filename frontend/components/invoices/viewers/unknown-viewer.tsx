"use client";

import { FileQuestion } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

interface UnknownViewerProps {
  fileUrl: string;
  filename: string;
  mimeType: string;
}

export function UnknownViewer({ fileUrl, filename, mimeType }: UnknownViewerProps): React.JSX.Element {
  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <FileQuestion className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm font-medium">Vorschau für diesen Dateityp nicht verfügbar</p>
        <p className="text-xs text-muted-foreground">MIME-Type: {mimeType}</p>
        <a
          href={fileUrl}
          download={filename}
          className="inline-flex h-9 items-center justify-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition-colors duration-150 ease-out hover:bg-accent hover:text-accent-foreground"
        >
          Herunterladen
        </a>
      </CardContent>
    </Card>
  );
}
