import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UploadDropzone } from "@/components/invoices/upload-dropzone";

const { mutateAsync, toastError } = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  toastError: vi.fn(),
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
    info: vi.fn(),
    success: vi.fn(),
  },
}));

describe("UploadDropzone", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    toastError.mockReset();
    mutateAsync.mockResolvedValue({
      deduplicatedHeader: false,
      item: { deduplicated: false },
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
});
