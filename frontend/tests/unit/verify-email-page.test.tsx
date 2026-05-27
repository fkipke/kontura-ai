import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VerifyEmailPage from "@/app/(auth)/verify-email/page";

const verifyMutateAsync = vi.fn();
const resendMutateAsync = vi.fn();
const useSearchParamsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => useSearchParamsMock(),
}));

vi.mock("@/lib/api/auth", () => ({
  useVerifyEmail: () => ({
    mutateAsync: verifyMutateAsync,
    error: null,
  }),
  useResendVerification: () => ({
    mutateAsync: resendMutateAsync,
    isPending: false,
    isSuccess: false,
    error: null,
  }),
}));

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    verifyMutateAsync.mockReset();
    resendMutateAsync.mockReset();
    useSearchParamsMock.mockReset();
  });

  it("ruft useVerifyEmail mit URL-Token auf", async () => {
    verifyMutateAsync.mockResolvedValue({ verified: true });
    useSearchParamsMock.mockReturnValue(new URLSearchParams("token=abc123"));

    render(<VerifyEmailPage />);

    await waitFor(() => {
      expect(verifyMutateAsync).toHaveBeenCalledWith({ token: "abc123" });
    });
  });

  it("zeigt ohne Token direkt das Resend-Formular", () => {
    useSearchParamsMock.mockReturnValue(new URLSearchParams());

    render(<VerifyEmailPage />);

    expect(screen.getByLabelText("E-Mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Firmen-Kennung")).toBeInTheDocument();
  });
});
