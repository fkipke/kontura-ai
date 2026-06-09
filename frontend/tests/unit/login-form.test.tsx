import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/auth/login-form";

const { loginMutateAsync, demoMutateAsync, resendMutateAsync, routerReplace, routerRefresh } = vi.hoisted(() => ({
  loginMutateAsync: vi.fn(),
  demoMutateAsync: vi.fn(),
  resendMutateAsync: vi.fn(),
  routerReplace: vi.fn(),
  routerRefresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: routerReplace,
    refresh: routerRefresh,
  }),
}));

vi.mock("@/lib/config", () => ({
  config: {
    demoMode: true,
  },
}));

vi.mock("@/lib/api/auth", () => ({
  useLogin: () => ({
    mutateAsync: loginMutateAsync,
    isPending: false,
    error: null,
  }),
  useDemoLogin: () => ({
    mutateAsync: demoMutateAsync,
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

describe("LoginForm", () => {
  beforeEach(() => {
    loginMutateAsync.mockReset();
    demoMutateAsync.mockReset();
    resendMutateAsync.mockReset();
    routerReplace.mockReset();
    routerRefresh.mockReset();

    loginMutateAsync.mockResolvedValue({ ok: true });
    demoMutateAsync.mockResolvedValue({ ok: true });
  });

  it("zeigt im Demo-Modus einen Demo-Start-Button", () => {
    render(<LoginForm />);

    expect(screen.getByRole("button", { name: "Demo starten" })).toBeInTheDocument();
  });

  it("führt Demo-Login aus und navigiert zur Übersicht", async () => {
    render(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: "Demo starten" }));

    await waitFor(() => {
      expect(demoMutateAsync).toHaveBeenCalledTimes(1);
      expect(routerReplace).toHaveBeenCalledWith("/");
      expect(routerRefresh).toHaveBeenCalled();
    });
  });
});
