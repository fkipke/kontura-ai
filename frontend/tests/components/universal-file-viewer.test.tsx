import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UniversalFileViewer } from "@/components/invoices/viewers/universal-file-viewer";

vi.mock("@/components/invoices/viewers/pdf-viewer", () => ({
  PdfViewer: ({ file }: { file: string }) => <div>PDF:{file}</div>,
}));

vi.mock("@/components/invoices/viewers/xml-viewer", () => ({
  XmlViewer: ({ filename }: { fileUrl: string; filename: string }) => <div>XML:{filename}</div>,
}));

vi.mock("@/components/invoices/viewers/image-viewer", () => ({
  ImageViewer: ({ filename }: { fileUrl: string; filename: string }) => <div>IMG:{filename}</div>,
}));

vi.mock("@/components/invoices/viewers/unknown-viewer", () => ({
  UnknownViewer: ({ mimeType }: { fileUrl: string; filename: string; mimeType: string }) => (
    <div>UNKNOWN:{mimeType}</div>
  ),
}));

describe("UniversalFileViewer", () => {
  const baseProps = {
    fileId: "f1",
    filename: "test.file",
    fileUrl: "/api/proxy/api/v1/invoice-files/f1",
  };

  it("renders PdfViewer for application/pdf", () => {
    render(<UniversalFileViewer {...baseProps} mimeType="application/pdf" />);
    expect(screen.getByText("PDF:/api/proxy/api/v1/invoice-files/f1")).toBeInTheDocument();
  });

  it("renders XmlViewer for application/xml", () => {
    render(<UniversalFileViewer {...baseProps} mimeType="application/xml" />);
    expect(screen.getByText("XML:test.file")).toBeInTheDocument();
  });

  it("renders XmlViewer for text/xml", () => {
    render(<UniversalFileViewer {...baseProps} mimeType="text/xml" />);
    expect(screen.getByText("XML:test.file")).toBeInTheDocument();
  });

  it("renders ImageViewer for image/png", () => {
    render(<UniversalFileViewer {...baseProps} mimeType="image/png" />);
    expect(screen.getByText("IMG:test.file")).toBeInTheDocument();
  });

  it("renders ImageViewer for image/jpeg", () => {
    render(<UniversalFileViewer {...baseProps} mimeType="image/jpeg" />);
    expect(screen.getByText("IMG:test.file")).toBeInTheDocument();
  });

  it("renders UnknownViewer for application/zip", () => {
    render(<UniversalFileViewer {...baseProps} mimeType="application/zip" />);
    expect(screen.getByText("UNKNOWN:application/zip")).toBeInTheDocument();
  });
});
