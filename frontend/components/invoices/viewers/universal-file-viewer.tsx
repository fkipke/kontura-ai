"use client";

import { ImageViewer } from "@/components/invoices/viewers/image-viewer";
import { PdfViewer } from "@/components/invoices/viewers/pdf-viewer";
import { UnknownViewer } from "@/components/invoices/viewers/unknown-viewer";
import { XmlViewer } from "@/components/invoices/viewers/xml-viewer";

interface UniversalFileViewerProps {
  fileId: string;
  filename: string;
  mimeType: string;
  fileUrl: string;
}

export function UniversalFileViewer({
  fileId,
  filename,
  mimeType,
  fileUrl,
}: UniversalFileViewerProps): React.JSX.Element {
  const lower = mimeType.toLowerCase();
  let viewer: React.JSX.Element;

  if (lower === "application/pdf") {
    viewer = <PdfViewer key={fileUrl} file={fileUrl} filename={filename} />;
  } else if (lower === "application/xml" || lower === "text/xml") {
    viewer = <XmlViewer key={fileUrl} fileUrl={fileUrl} filename={filename} />;
  } else if (lower === "image/png" || lower === "image/jpeg") {
    viewer = <ImageViewer key={fileUrl} fileUrl={fileUrl} filename={filename} />;
  } else {
    viewer = <UnknownViewer key={fileUrl} fileUrl={fileUrl} filename={filename} mimeType={mimeType} />;
  }

  return (
    <div data-file-id={fileId} className="h-full">
      {viewer}
    </div>
  );
}
