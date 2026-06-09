import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DemoBanner } from "@/components/layout/demo-banner";

vi.mock("@/lib/config", () => ({
  config: {
    demoMode: true,
  },
}));

describe("DemoBanner", () => {
  it("zeigt Hinweistext bei aktivem Demo-Modus", () => {
    render(<DemoBanner />);

    expect(screen.getByText(/Demo-Modus aktiv/i)).toBeInTheDocument();
  });
});
