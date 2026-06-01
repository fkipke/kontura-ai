import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EditableField } from "@/components/invoices/editable-field";

describe("EditableField", () => {
  const onSaveMock = vi.fn();

  beforeEach(() => {
    onSaveMock.mockReset();
  });

  it("zeigt Wert und Edit-Icon an (kein Input initial)", () => {
    render(<EditableField value="ACME GmbH" label="Lieferant" onSave={onSaveMock} />);
    expect(screen.getByText("ACME GmbH")).toBeInTheDocument();
    // Input ist initial nicht sichtbar
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("zeigt Platzhalter '–' wenn kein Wert vorhanden", () => {
    render(<EditableField value={null} label="Lieferant" onSave={onSaveMock} />);
    expect(screen.getByText("–")).toBeInTheDocument();
  });

  it("Klick auf Button öffnet Input und fokussiert ihn", async () => {
    render(<EditableField value="ACME GmbH" label="Lieferant" onSave={onSaveMock} />);

    fireEvent.click(screen.getByRole("button", { name: /lieferant bearbeiten/i }));

    await waitFor(() => {
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });
  });

  it("Enter ruft onSave mit neuem Wert auf", async () => {
    onSaveMock.mockResolvedValue(undefined);

    render(<EditableField value="ACME GmbH" label="Lieferant" onSave={onSaveMock} />);

    fireEvent.click(screen.getByRole("button", { name: /lieferant bearbeiten/i }));

    const input = await screen.findByRole("textbox");
    fireEvent.change(input, { target: { value: "Neuer Lieferant AG" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(onSaveMock).toHaveBeenCalledWith("Neuer Lieferant AG");
    });
  });

  it("Escape verwirft Änderungen und schließt Input", async () => {
    render(<EditableField value="ACME GmbH" label="Lieferant" onSave={onSaveMock} />);

    fireEvent.click(screen.getByRole("button", { name: /lieferant bearbeiten/i }));

    const input = await screen.findByRole("textbox");
    fireEvent.change(input, { target: { value: "Verworfener Wert" } });
    fireEvent.keyDown(input, { key: "Escape", code: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("textbox")).toBeNull();
      expect(onSaveMock).not.toHaveBeenCalled();
    });
    // Ursprünglicher Wert bleibt
    expect(screen.getByText("ACME GmbH")).toBeInTheDocument();
  });

  it("kein onSave-Aufruf wenn Wert unverändert", async () => {
    onSaveMock.mockResolvedValue(undefined);

    render(<EditableField value="ACME GmbH" label="Lieferant" onSave={onSaveMock} />);

    fireEvent.click(screen.getByRole("button", { name: /lieferant bearbeiten/i }));
    const input = await screen.findByRole("textbox");
    // Kein Änderung — direkt Enter
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(onSaveMock).not.toHaveBeenCalled();
    });
  });

  it("zeigt blauen Dot wenn isModified=true", () => {
    render(
      <EditableField
        value="Manuell"
        label="Lieferant"
        onSave={onSaveMock}
        isModified={true}
      />,
    );
    expect(screen.getByLabelText("Manuell korrigiert")).toBeInTheDocument();
  });

  it("zeigt keinen Dot wenn isModified=false", () => {
    render(
      <EditableField
        value="Original"
        label="Lieferant"
        onSave={onSaveMock}
        isModified={false}
      />,
    );
    expect(screen.queryByLabelText("Manuell korrigiert")).toBeNull();
  });
});
