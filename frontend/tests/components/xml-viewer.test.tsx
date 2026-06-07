import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { XmlViewer } from "@/components/invoices/viewers/xml-viewer";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

function getRows(): HTMLElement[] {
  return Array.from(document.querySelectorAll(".group.flex.leading-6")) as HTMLElement[];
}

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

  it("inlines short single-text-child elements on one line", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () => '<?xml version="1.0"?><Invoice><cbc:ID>RE-001</cbc:ID></Invoice>',
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findByText("RE-001");
    expect(
      getRows().some((row) => row.textContent?.includes("<cbc:ID>RE-001</cbc:ID>")),
    ).toBe(true);
  });

  it("keeps long single-text-child elements split", async () => {
    const longText = "A".repeat(120);
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () => `<?xml version="1.0"?><Invoice><cbc:Note>${longText}</cbc:Note></Invoice>`,
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findByText(longText);
    expect(
      getRows().some((row) => row.textContent?.includes(`<cbc:Note>${longText}</cbc:Note>`)),
    ).toBe(false);
    expect(getRows().some((row) => row.textContent?.includes("<cbc:Note>"))).toBe(true);
  });

  it("highlights xml declaration with declaration color", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () => '<?xml version="1.0" encoding="UTF-8"?><Invoice />',
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    const declaration = await screen.findByText('<?xml version="1.0" encoding="UTF-8"?>');
    expect(declaration).toHaveClass("text-pink-700");
  });

  it("renders indent guides for nested elements", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () => "<Invoice><Level1><Level2>Wert</Level2></Level1></Invoice>",
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findByText("Wert");
    expect(screen.getAllByTestId("xml-indent-guide").length).toBeGreaterThan(0);
  });

  it("search input filters/highlights matches", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () =>
        '<?xml version="1.0"?><Invoice><cbc:ID>RE-001</cbc:ID><cbc:Note>Andere Zeile</cbc:Note></Invoice>',
    });

    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findByText("RE-001");
    fireEvent.change(screen.getAllByRole("textbox", { name: /xml durchsuchen/i })[0], {
      target: { value: "RE-001" },
    });

    expect(screen.getByText("RE-001").tagName).toBe("MARK");
    expect(screen.queryByText("Andere Zeile")).not.toBeInTheDocument();
  });

  it("copies content to clipboard on copy button", async () => {
    fetchMock.mockResolvedValue({ ok: true, text: async () => "<Invoice><A>1</A></Invoice>" });
    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findAllByText("Invoice");
    fireEvent.click(screen.getByRole("button", { name: "Kopieren" }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("<Invoice><A>1</A></Invoice>");
    });
  });

  it("download link points to fileUrl", async () => {
    fetchMock.mockResolvedValue({ ok: true, text: async () => "<Invoice><A>1</A></Invoice>" });
    render(<XmlViewer fileUrl="/xml" filename="test.xml" />);

    await screen.findAllByText("Invoice");
    expect(screen.getByRole("link", { name: /herunterladen/i })).toHaveAttribute("href", "/xml");
  });
});
