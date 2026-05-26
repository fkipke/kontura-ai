import { describe, expect, it } from "vitest";

import { formatCurrency, formatGermanDate } from "@/lib/format";

describe("Formatter", () => {
  it("formatiert Eurobeträge im deutschen Format", () => {
    expect(formatCurrency(11.99)).toBe("11,99 €");
    expect(formatCurrency(0)).toBe("0,00 €");
  });

  it("behandelt null sicher", () => {
    expect(formatCurrency(null)).toBe("–");
  });

  it("formatiert Datum", () => {
    expect(formatGermanDate("2026-05-25T09:00:00Z")).toMatch(/25\.05\.2026/);
  });

  it("behandelt ungültige Datumswerte", () => {
    expect(formatGermanDate("invalid")).toBe("–");
    expect(formatGermanDate(null)).toBe("–");
  });
});
