import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExtractedFieldsPanel } from "@/components/invoices/extracted-fields-panel";
import type { ExtractionStatus, InvoiceFile, InvoiceResponse } from "@/lib/api/schemas";
import type { MappingSuggestion } from "@/lib/api/vendorMappings";

// Mock-Abhängigkeiten
const mutateAsyncMock = vi.fn();
const useVendorMappingSuggestionMock = vi.fn(
  (vendorName: string | null): { data: MappingSuggestion | null } => {
    void vendorName;
    return { data: null };
  },
);

vi.mock("@/lib/api/invoices", () => ({
  useUpdateInvoice: () => ({
    mutateAsync: mutateAsyncMock,
    isPending: false,
  }),
  InvoiceConflictError: class InvoiceConflictError extends Error {
    constructor(public conflict: unknown) {
      super("Konflikt");
    }
  },
}));

vi.mock("@/lib/api/invoiceFiles", () => ({
  useTriggerExtraction: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/lib/api/vendorMappings", () => ({
  useVendorMappingSuggestion: (vendorName: string | null) =>
    useVendorMappingSuggestionMock(vendorName),
}));

// Sonner-Toast mocken
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

// Basis-Testdaten
const baseInvoiceFile: InvoiceFile = {
  id: "file-123",
  filename: "rechnung.pdf",
  mime_type: "application/pdf",
  size_bytes: 12345,
  sha256: "abc123",
  created_at: "2025-01-15T10:00:00Z",
  extraction_status: "completed",
};

const baseExtraction: ExtractionStatus = {
  file_id: "file-123",
  status: "completed",
  attempts: 1,
  extracted_at: "2025-01-15T10:05:00Z",
  error: null,
  result: {
    invoice_number: "RE-2025-001",
    invoice_date: "2025-01-10",
    due_date: null,
    vendor_name: "Test GmbH",
    vendor_address: null,
    net_amount: 100,
    tax_amount: 19,
    total_amount: 119,
    currency: "EUR",
    line_items: [],
    confidence_notes: null,
  },
  linked_invoice_id: "invoice-456",
};

const baseInvoiceData: InvoiceResponse = {
  id: "invoice-456",
  tenant_id: "acme-corp",
  version: 1,
  is_reviewed: false,
  reviewed_at: null,
  reviewed_by_user_id: null,
  vendor_name: "Test GmbH",
  invoice_number: "RE-2025-001",
  invoice_date: "2025-01-10",
  net_amount: "100.00",
  tax_amount: "19.00",
  total_amount: "119.00",
  currency: "EUR",
  line_items: null,
  status: "received",
  created_at: "2025-01-15T10:00:00Z",
  updated_at: "2025-01-15T10:00:00Z",
  validation_warnings: [],
};

describe("ExtractedFieldsPanel", () => {
  beforeEach(() => {
    mutateAsyncMock.mockReset();
    useVendorMappingSuggestionMock.mockReset();
    useVendorMappingSuggestionMock.mockReturnValue({ data: null });
  });

  it("rendert Ladeanimation wenn loading=true", () => {
    render(
      <ExtractedFieldsPanel
        invoice={null}
        extraction={null}
        loading={true}
        invoiceData={null}
        invoiceId={null}
      />,
    );
    // Skeleton-Elemente vorhanden
    expect(document.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("rendert Fehlermeldung wenn kein Invoice vorhanden", () => {
    render(
      <ExtractedFieldsPanel
        invoice={null}
        extraction={null}
        loading={false}
        invoiceData={null}
        invoiceId={null}
      />,
    );
    expect(screen.getByText(/Rechnung konnte nicht geladen werden/i)).toBeInTheDocument();
  });

  it("zeigt skeleton statt fehlermeldung solange retry noch offen ist", () => {
    render(
      <ExtractedFieldsPanel
        invoice={null}
        extraction={null}
        loading={false}
        hasRetried={false}
        invoiceData={null}
        invoiceId={null}
      />,
    );

    expect(screen.queryByText(/Rechnung konnte nicht geladen werden/i)).not.toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("rendert Felder aus Extraction-Daten", () => {
    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );
    expect(screen.getByText("rechnung.pdf")).toBeInTheDocument();
    expect(screen.getByText("Test GmbH")).toBeInTheDocument();
  });

  it("renders Kontierung block", () => {
    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    expect(screen.getByText("Kontierung")).toBeInTheDocument();
    expect(screen.getByLabelText("Kreditorkonto")).toBeInTheDocument();
  });

  it("prefills creditor account when suggestion is auto-apply", async () => {
    useVendorMappingSuggestionMock.mockReturnValue({
      data: {
        creditor_account_number: 70042,
        vendor_name_raw: "Test GmbH",
        usage_count: 5,
        last_used_at: "2026-06-03T00:00:00Z",
        confidence: 1,
        match_type: "exact",
        auto_apply: true,
      },
    });

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Kreditorkonto")).toHaveValue(70042);
    });
    expect(screen.getByText("automatisch (5×)")).toBeInTheDocument();
  });

  it("shows suggestion box for low-confidence match", () => {
    useVendorMappingSuggestionMock.mockReturnValue({
      data: {
        creditor_account_number: 70042,
        vendor_name_raw: "Test GmbH",
        usage_count: 2,
        last_used_at: "2026-06-03T00:00:00Z",
        confidence: 0.4,
        match_type: "exact",
        auto_apply: false,
      },
    });

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    expect(screen.getByText(/Vorschlag:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Übernehmen" })).toBeInTheDocument();
  });

  it("applies suggestion when Übernehmen clicked", () => {
    useVendorMappingSuggestionMock.mockReturnValue({
      data: {
        creditor_account_number: 70042,
        vendor_name_raw: "Test GmbH",
        usage_count: 2,
        last_used_at: "2026-06-03T00:00:00Z",
        confidence: 0.4,
        match_type: "exact",
        auto_apply: false,
      },
    });

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }));

    expect(screen.getByLabelText("Kreditorkonto")).toHaveValue(70042);
  });

  it("sends creditor_account_number in PATCH payload", async () => {
    mutateAsyncMock.mockResolvedValue({
      data: { ...baseInvoiceData, version: 2, validation_warnings: [] },
      warnings: [],
    });

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    fireEvent.change(screen.getByLabelText("Kreditorkonto"), {
      target: { value: "70042" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith(
        expect.objectContaining({
          expected_version: 1,
          creditor_account_number: 70042,
        }),
      );
    });
  });

  it("shows no suggestion when API returns null", () => {
    useVendorMappingSuggestionMock.mockReturnValue({ data: null });

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    expect(screen.queryByText(/Vorschlag:/)).toBeNull();
  });

  it("zeigt USt-Mismatch-Banner wenn validation_warnings ust_total_mismatch enthält", () => {
    const invoiceWithWarning: InvoiceResponse = {
      ...baseInvoiceData,
      net_amount: "100.00",
      tax_amount: "10.00",
      total_amount: "130.00",
      validation_warnings: [
        {
          code: "ust_total_mismatch",
          message: "Netto + Steuer weicht vom Gesamtbetrag ab.",
          field: "total_amount",
        },
      ],
    };

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={invoiceWithWarning}
        invoiceId="invoice-456"
      />,
    );

    // Gelbes Banner mit USt-Hinweis
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Netto \+ Steuer weicht vom Gesamtbetrag ab/i)).toBeInTheDocument();
  });

  it("zeigt keinen USt-Banner wenn keine Warnings vorhanden", () => {
    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );
    // Kein Alert-Banner
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("zeigt 'Als geprüft markieren'-Button wenn is_reviewed=false", () => {
    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={{ ...baseInvoiceData, is_reviewed: false }}
        invoiceId="invoice-456"
      />,
    );
    expect(
      screen.getByRole("button", { name: /als geprüft markieren/i }),
    ).toBeInTheDocument();
  });

  it("zeigt 'Geprüft'-Badge wenn is_reviewed=true", () => {
    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={{ ...baseInvoiceData, is_reviewed: true }}
        invoiceId="invoice-456"
      />,
    );
    expect(screen.getByText("Geprüft")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /als geprüft markieren/i })).toBeNull();
  });

  it("klickt 'Als geprüft markieren' → ruft Mutation mit is_reviewed=true auf", async () => {
    mutateAsyncMock.mockResolvedValue({
      data: { ...baseInvoiceData, is_reviewed: true, version: 2, validation_warnings: [] },
      warnings: [],
    });

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={baseInvoiceData}
        invoiceId="invoice-456"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /als geprüft markieren/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith(
        expect.objectContaining({ is_reviewed: true }),
      );
    });
  });

  it("'Als geprüft markieren' funktioniert auch mit USt-Warning (KRITISCH)", async () => {
    mutateAsyncMock.mockResolvedValue({
      data: {
        ...baseInvoiceData,
        is_reviewed: true,
        version: 2,
        validation_warnings: [
          {
            code: "ust_total_mismatch",
            message: "Netto + Steuer weicht vom Gesamtbetrag ab.",
            field: "total_amount",
          },
        ],
      },
    });

    const invoiceWithWarning: InvoiceResponse = {
      ...baseInvoiceData,
      net_amount: "100.00",
      tax_amount: "10.00",
      total_amount: "130.00",
      validation_warnings: [
        {
          code: "ust_total_mismatch",
          message: "Netto + Steuer weicht vom Gesamtbetrag ab.",
          field: "total_amount",
        },
      ],
    };

    render(
      <ExtractedFieldsPanel
        invoice={baseInvoiceFile}
        extraction={baseExtraction}
        loading={false}
        invoiceData={invoiceWithWarning}
        invoiceId="invoice-456"
      />,
    );

    // USt-Warning sichtbar
    expect(screen.getByRole("alert")).toBeInTheDocument();

    // Button ist trotzdem klickbar und Mutation wird aufgerufen
    fireEvent.click(screen.getByRole("button", { name: /als geprüft markieren/i }));

    await waitFor(() => {
      expect(mutateAsyncMock).toHaveBeenCalledWith(
        expect.objectContaining({ is_reviewed: true }),
      );
    });
  });
});
