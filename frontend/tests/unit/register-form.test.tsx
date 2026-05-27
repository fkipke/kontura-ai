import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterForm } from "@/components/auth/register-form";

const registerMutateAsync = vi.fn();
const resendMutateAsync = vi.fn();

vi.mock("@/lib/api/auth", () => ({
  useRegister: () => ({
    mutateAsync: registerMutateAsync,
    isPending: false,
    error: null,
  }),
  useResendVerification: () => ({
    mutateAsync: resendMutateAsync,
    isPending: false,
    isSuccess: false,
    error: null,
  }),
}));

describe("RegisterForm", () => {
  beforeEach(() => {
    registerMutateAsync.mockReset();
    resendMutateAsync.mockReset();
  });

  it("zeigt nach erfolgreichem Submit die Success-Card", async () => {
    registerMutateAsync.mockResolvedValue({ email_verification_required: true });

    render(<RegisterForm />);

    fireEvent.change(screen.getByLabelText("E-Mail"), { target: { value: "max@example.com" } });
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "sehrsicherespasswort" } });
    fireEvent.change(screen.getByLabelText("Firmen-Kennung"), { target: { value: "demo-firma" } });
    fireEvent.change(screen.getByLabelText("Firmenname"), { target: { value: "Demo Firma GmbH" } });

    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));

    await waitFor(() => {
      expect(screen.getByText(/Wir haben dir eine E-Mail an/i)).toBeInTheDocument();
      expect(screen.getByText("max@example.com")).toBeInTheDocument();
    });
  });
});
