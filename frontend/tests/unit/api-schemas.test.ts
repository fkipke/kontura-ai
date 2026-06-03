import { describe, expect, it } from "vitest";

import {
  extractionStatusSchema,
  invoiceFileSchema,
  loginPayloadSchema,
  registerPayloadSchema,
} from "@/lib/api/schemas";

describe("Auth-Schemas", () => {
  it("akzeptiert gültige Login-Daten", () => {
    const result = loginPayloadSchema.safeParse({
      email: "max@example.de",
      password: "Passwort123456",
      tenant_slug: "kanzlei-demo",
    });

    expect(result.success).toBe(true);
  });

  it("lehnt ungültige Login-E-Mail ab", () => {
    const result = loginPayloadSchema.safeParse({
      email: "falsch",
      password: "Passwort123456",
      tenant_slug: "kanzlei-demo",
    });

    expect(result.success).toBe(false);
  });

  it("lehnt zu kurzes Register-Passwort ab", () => {
    const result = registerPayloadSchema.safeParse({
      email: "max@example.de",
      password: "kurz",
      tenant_slug: "kanzlei-demo",
      tenant_display_name: "Kanzlei Demo",
    });

    expect(result.success).toBe(false);
  });

  it("akzeptiert fehlendes extraction_method Feld als optional", () => {
    const result = invoiceFileSchema.safeParse({
      id: "0f2f4d52-c405-4a88-b6b7-7f3e7f8d2cb0",
      filename: "rechnung.pdf",
      mime_type: "application/pdf",
      size_bytes: 1234,
      sha256: "abc",
      created_at: "2026-01-01T00:00:00Z",
      extraction_status: "completed",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.extraction_method).toBeUndefined();
    }
  });

  it("akzeptiert zugferd_profile in extraction result", () => {
    const result = extractionStatusSchema.safeParse({
      file_id: "0f2f4d52-c405-4a88-b6b7-7f3e7f8d2cb0",
      status: "completed",
      attempts: 1,
      extracted_at: null,
      error: null,
      result: {
        invoice_number: "RE-1",
        zugferd_profile: "minimum",
      },
      linked_invoice_id: null,
    });

    expect(result.success).toBe(true);
  });
});
