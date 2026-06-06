import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UploadDropzone } from "@/components/invoices/upload-dropzone";

const { mutateAsync, toastError, toastInfo, routerPush } = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
  routerPush: vi.fn(),
}));

vi.mock("@/lib/api/invoiceFiles", () => ({
  useUploadInvoice: () => ({
    mutateAsync,
    isPending: false,
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: toastError,
    info: toastInfo,
    success: vi.fn(),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPush,
  }),
}));

describe("UploadDropzone", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    toastError.mockReset();
    toastInfo.mockReset();
    routerPush.mockReset();
    mutateAsync.mockResolvedValue({
      deduplicatedHeader: false,
      item: { id: "invoice-1", deduplicated: false },
    });
  });

  it("accepts XML uploads", async () => {
    const { container } = render(<UploadDropzone />);

    expect(screen.getByText("PDF, PNG, JPEG oder XML hier ablegen")).toBeInTheDocument();

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();
    expect(input?.getAttribute("accept")).toContain("application/xml");
    expect(input?.getAttribute("accept")).toContain("text/xml");
    expect(input?.getAttribute("accept")).toContain(".xml");

    const file = new File(["<?xml version='1.0'?><Invoice />"], "invoice.xml", {
      type: "application/xml",
    });

    Object.defineProperty(input, "files", {
      configurable: true,
      value: {
        0: file,
        length: 1,
        item: (index: number) => (index === 0 ? file : null),
      },
    });

    fireEvent.change(input as HTMLInputElement);

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(file);
    });
    expect(toastError).not.toHaveBeenCalled();
  });

  it("navigates to existing invoice on deduplicated response", async () => {
    mutateAsync.mockResolvedValue({
      deduplicatedHeader: true,
      item: { id: "invoice-existing", deduplicated: true },
    });

    const { container } = render(<UploadDropzone />);
    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    const file = new File(["%PDF-1.4"], "invoice.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(input, "files", {
      configurable: true,
      value: {
        0: file,
        length: 1,
        item: (index: number) => (index === 0 ? file : null),
      },
    });

    fireEvent.change(input as HTMLInputElement);

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith("/invoices/invoice-existing");
    });
    expect(toastInfo).toHaveBeenCalled();
  });
});
