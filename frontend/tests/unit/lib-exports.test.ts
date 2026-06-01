import { describe, expect, it } from "vitest";

import { parseFilename, defaultFilename } from "@/lib/api/exports";

describe("parseFilename", () => {
  it("parst Filename aus Content-Disposition-Header", () => {
    expect(
      parseFilename('attachment; filename="EXTF_Buchungsstapel_20260101_20260131.csv"'),
    ).toBe("EXTF_Buchungsstapel_20260101_20260131.csv");
  });

  it("parst Filename ohne Anführungszeichen", () => {
    expect(parseFilename("attachment; filename=EXTF_Buchungsstapel_20260101_20260131.csv")).toBe(
      "EXTF_Buchungsstapel_20260101_20260131.csv",
    );
  });

  it("gibt null zurück bei null-Header", () => {
    expect(parseFilename(null)).toBeNull();
  });

  it("gibt null zurück bei Header ohne filename", () => {
    expect(parseFilename("attachment")).toBeNull();
  });
});

describe("defaultFilename", () => {
  it("erstellt Fallback-Dateiname ohne Bindestriche", () => {
    expect(defaultFilename("2026-01-01", "2026-01-31")).toBe(
      "EXTF_Buchungsstapel_20260101_20260131.csv",
    );
  });

  it("funktioniert mit beliebigen Datum-Strings", () => {
    expect(defaultFilename("2025-06-15", "2025-12-31")).toBe(
      "EXTF_Buchungsstapel_20250615_20251231.csv",
    );
  });
});
