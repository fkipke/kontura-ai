import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExtractionMethodBadge } from "@/components/invoices/extraction-method-badge";

describe("ExtractionMethodBadge", () => {
  it("renders nothing when method is null", () => {
    const { container } = render(<ExtractionMethodBadge method={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders XRechnung badge for xrechnung_ubl with green styling", () => {
    render(<ExtractionMethodBadge method="xrechnung_ubl" />);

    const badge = screen.getByLabelText("Extrahiert aus XRechnung-XML (UBL-Format), 100% Genauigkeit");
    expect(badge).toBeInTheDocument();
    expect(screen.getByText("XRechnung")).toBeInTheDocument();
    expect(badge).toHaveClass("bg-emerald-100");
  });

  it("renders XRechnung badge for xrechnung_cii with dedicated aria-label", () => {
    render(<ExtractionMethodBadge method="xrechnung_cii" />);

    expect(screen.getByText("XRechnung")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Extrahiert aus XRechnung-XML (CII-Format), 100% Genauigkeit"),
    ).toBeInTheDocument();
  });

  it("renders ZUGFeRD badge for zugferd_v2", () => {
    render(<ExtractionMethodBadge method="zugferd_v2" />);

    expect(screen.getByText("ZUGFeRD")).toBeInTheDocument();
  });

  it("renders KI-extrahiert badge for ai_vision", () => {
    render(<ExtractionMethodBadge method="ai_vision" />);

    const badge = screen.getByText("KI-extrahiert");
    expect(badge).toBeInTheDocument();
  });

  it("renders MINIMUM warning when zugferdProfile is minimum", () => {
    render(<ExtractionMethodBadge method="zugferd_v2" zugferdProfile="minimum" />);

    expect(screen.getByText("MINIMUM-Profil — Positionen ggf. ergänzen")).toBeInTheDocument();
  });

  it("does not render MINIMUM warning for zugferdProfile basic", () => {
    render(<ExtractionMethodBadge method="zugferd_v2" zugferdProfile="basic" />);

    expect(screen.queryByText("MINIMUM-Profil — Positionen ggf. ergänzen")).not.toBeInTheDocument();
  });

  it("does not render MINIMUM warning when method is ai_vision", () => {
    render(<ExtractionMethodBadge method="ai_vision" zugferdProfile="minimum" />);

    expect(screen.queryByText("MINIMUM-Profil — Positionen ggf. ergänzen")).not.toBeInTheDocument();
  });

  it("uses descriptive aria-label text for screen readers", () => {
    render(<ExtractionMethodBadge method="ai_vision" />);

    const badge = screen.getByLabelText("Extrahiert per KI-Vision (GPT-4o), bitte Felder prüfen");
    expect(badge).toBeInTheDocument();
  });
});
