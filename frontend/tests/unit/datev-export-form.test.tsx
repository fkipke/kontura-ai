import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DatevExportForm } from "@/components/exports/datev-export-form";

// Sonner-Toast mocken
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// next/navigation mocken
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// downloadDatevExport mocken
vi.mock("@/lib/api/exports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/exports")>();
  return {
    ...actual,
    downloadDatevExport: vi.fn(),
  };
});

async function getDownloadDatevExportMock() {
  const mod = await import("@/lib/api/exports");
  return mod.downloadDatevExport as ReturnType<typeof vi.fn>;
}

describe("DatevExportForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Nur Date mocken, keine Timer-Funktionen — sonst hängt waitFor
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-06-01T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("rendert mit Default-Werten: Von = erster Tag des Monats, Bis = heute", () => {
    render(<DatevExportForm />);
    const fromInput = screen.getByLabelText("Von") as HTMLInputElement;
    const toInput = screen.getByLabelText("Bis") as HTMLInputElement;
    expect(fromInput.value).toBe("2026-06-01");
    expect(toInput.value).toBe("2026-06-01");
  });

  it("deaktiviert den Button und zeigt Fehler wenn Von > Bis", () => {
    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-15" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });
    expect(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i })).toBeDisabled();
    expect(
      screen.getByText("Das Bis-Datum muss nach dem Von-Datum liegen."),
    ).toBeInTheDocument();
  });

  it("deaktiviert den Button und zeigt Fehler wenn Zeitraum > 366 Tage", () => {
    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2025-01-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });
    expect(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i })).toBeDisabled();
    expect(screen.getByText("Maximaler Zeitraum ist 1 Jahr.")).toBeInTheDocument();
  });

  it("deaktiviert den Button wenn ein Datum-Feld leer ist", () => {
    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "" } });
    expect(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i })).toBeDisabled();
  });

  it("ruft fetch mit korrekter Proxy-URL auf beim Klick", async () => {
    const downloadMock = await getDownloadDatevExportMock();
    downloadMock.mockResolvedValue({ invoiceCount: 3, skippedCount: 0, filename: "test.csv" });

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      expect(downloadMock).toHaveBeenCalledWith("2026-06-01", "2026-06-01");
    });
  });

  it("zeigt Lade-Zustand während Download läuft", async () => {
    const downloadMock = await getDownloadDatevExportMock();
    let resolveDownload!: () => void;
    downloadMock.mockImplementation(
      () =>
        new Promise<{ invoiceCount: number; skippedCount: number; filename: string }>(
          (resolve) => {
            resolveDownload = () =>
              resolve({ invoiceCount: 1, skippedCount: 0, filename: "test.csv" });
          },
        ),
    );

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /Wird vorbereitet/i });
      expect(btn).toBeDisabled();
      expect(btn).toHaveAttribute("aria-busy", "true");
    });

    // Download auflösen damit der Test sauber abschließt
    resolveDownload();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i })).toBeInTheDocument();
    });
  });

  it("löst Browser-Download aus bei Erfolg (triggerBrowserDownload)", async () => {
    const { triggerBrowserDownload } = await import("@/lib/api/exports");
    const triggerSpy = vi.spyOn({ triggerBrowserDownload }, "triggerBrowserDownload");

    const createObjectURLMock = vi.fn().mockReturnValue("blob:fake-url");
    const revokeObjectURLMock = vi.fn();
    global.URL.createObjectURL = createObjectURLMock;
    global.URL.revokeObjectURL = revokeObjectURLMock;

    const downloadMock = await getDownloadDatevExportMock();
    downloadMock.mockResolvedValue({ invoiceCount: 2, skippedCount: 0, filename: "test.csv" });

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      expect(downloadMock).toHaveBeenCalled();
    });

    triggerSpy.mockRestore();
  });

  it("zeigt Erfolgs-Toast mit Rechnungsanzahl (Singular)", async () => {
    const { toast } = await import("sonner");
    const downloadMock = await getDownloadDatevExportMock();
    downloadMock.mockResolvedValue({ invoiceCount: 1, skippedCount: 0, filename: "test.csv" });

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Export erstellt: 1 Rechnung im Buchungsstapel",
      );
    });
  });

  it("zeigt Erfolgs-Toast mit Rechnungsanzahl (Plural) und Skipped-Count", async () => {
    const { toast } = await import("sonner");
    const downloadMock = await getDownloadDatevExportMock();
    downloadMock.mockResolvedValue({ invoiceCount: 5, skippedCount: 2, filename: "test.csv" });

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Export erstellt: 5 Rechnungen im Buchungsstapel",
        { description: "2 Rechnungen wegen Wirtschaftsjahr übersprungen" },
      );
    });
  });

  it("zeigt Fehler-Toast bei 422 mit Backend-Detail-Meldung", async () => {
    const { toast } = await import("sonner");
    const { DatevExportError } = await import("@/lib/api/exports");
    const downloadMock = await getDownloadDatevExportMock();
    downloadMock.mockRejectedValue(
      new DatevExportError(422, "from darf nicht nach to liegen"),
    );

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Ungültiger Zeitraum", {
        description: "from darf nicht nach to liegen",
      });
    });
  });

  it("zeigt Fehler-Toast bei 429", async () => {
    const { toast } = await import("sonner");
    const { DatevExportError } = await import("@/lib/api/exports");
    const downloadMock = await getDownloadDatevExportMock();
    downloadMock.mockRejectedValue(new DatevExportError(429, "Rate limit exceeded"));

    render(<DatevExportForm />);
    fireEvent.change(screen.getByLabelText("Von"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("Bis"), { target: { value: "2026-06-01" } });

    fireEvent.click(screen.getByRole("button", { name: /EXTF-Datei herunterladen/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Zu viele Anfragen", {
        description: "Bitte einen Moment warten und erneut versuchen.",
      });
    });
  });
});
