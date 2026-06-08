import { describe, expect, it } from "vitest";

import { getStatusMeta } from "@/components/invoices/status-badge";

describe("StatusBadge", () => {
  it("mappt alle Backend-Status", () => {
    expect(getStatusMeta("pending").label).toBe("Wartend");
    expect(getStatusMeta("processing").label).toBe("Verarbeitung");
    expect(getStatusMeta("completed").label).toBe("Fertig");
    expect(getStatusMeta("failed").label).toBe("Fehler");
    expect(getStatusMeta("not_an_invoice").label).toBe("Keine Rechnung");
  });
});
