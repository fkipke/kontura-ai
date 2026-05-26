import { describe, expect, it } from "vitest";

import { loginPayloadSchema, registerPayloadSchema } from "@/lib/api/schemas";

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
});
