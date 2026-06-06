import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { XmlViewer } from "@/components/invoices/viewers/xml-viewer";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

describe("XmlViewer", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  it("pretty prints UBL invoice with indentation", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () =>
        '<?xml version="1.0"?><Invoice><cbc:ID xmlns:cbc="x">RE-1</cbc:ID></Invoice>',
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    expect((await screen.findAllByText("Invoice")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("cbc:ID").length).toBeGreaterThan(0);
    expect(screen.getByText("RE-1")).toBeInTheDocument();
  });

  it("shows line numbers", async () => {
    fetchMock.mockResolvedValue({ ok: true, text: async () => "<Invoice><A>1</A></Invoice>" });
    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findAllByText("Invoice");
    const lineNumbers = Array.from(document.querySelectorAll("span.select-none")).map(
      (node) => node.textContent?.trim() ?? "",
    );
    expect(lineNumbers).toContain("1");
  });

  it("shows error state when fetch fails", async () => {
    fetchMock.mockRejectedValue(new Error("boom"));
    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    expect(await screen.findByText(/XML konnte nicht geladen werden/i)).toBeInTheDocument();
  });

  it("copies content to clipboard on copy button", async () => {
    fetchMock.mockResolvedValue({ ok: true, text: async () => "<Invoice><A>1</A></Invoice>" });
    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findAllByText("Invoice");
    fireEvent.click(screen.getByRole("button", { name: "Kopieren" }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });
  });

  it("font-size changes when zoom buttons clicked", async () => {
    fetchMock.mockResolvedValue({ ok: true, text: async () => "<Invoice><A>1</A></Invoice>" });
    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findAllByText("Invoice");
    expect(screen.getByText("14px")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Vergrößern" }));
    expect(screen.getByText("16px")).toBeInTheDocument();
  });

  it("escapes XML content (no innerHTML/dangerouslySetInnerHTML in DOM)", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () => '<Invoice><Note>&lt;script&gt;alert(1)&lt;/script&gt;</Note></Invoice>',
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findAllByText("Invoice");
    expect(document.querySelector("script")).toBeNull();
    expect(document.body.textContent).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });
});
