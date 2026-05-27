import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { apiRequest } from "@/lib/api/client";
import {
  loginPayloadSchema,
  meResponseSchema,
  registerPayloadSchema,
  registerResponseSchema,
  resendVerificationResponseSchema,
  verifyEmailResponseSchema,
  type LoginPayload,
  type MeResponse,
  type RegisterPayload,
  type RegisterResponse,
  type ResendVerificationResponse,
  type VerifyEmailResponse,
} from "@/lib/api/schemas";

const verifyEmailPayloadSchema = z.object({ token: z.string().min(1) });
const resendVerificationPayloadSchema = z.object({
  email: z.string().email(),
  tenant_slug: z.string().min(2),
});

function parseOk(value: unknown): { ok: true } {
  if (typeof value === "object" && value !== null && "ok" in value) {
    return { ok: true };
  }
  return { ok: true };
}

export function useLogin() {
  return useMutation({
    mutationFn: async (payload: LoginPayload) => {
      const body = loginPayloadSchema.parse(payload);
      return apiRequest(
        "/api/auth/login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        parseOk,
      );
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (payload: RegisterPayload): Promise<RegisterResponse> => {
      const body = registerPayloadSchema.parse(payload);
      return apiRequest(
        "/api/auth/register",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        (value) => registerResponseSchema.parse(value),
      );
    },
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: async (payload: { token: string }): Promise<VerifyEmailResponse> => {
      const body = verifyEmailPayloadSchema.parse(payload);
      return apiRequest(
        "/api/proxy/api/v1/auth/verify-email",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        (value) => verifyEmailResponseSchema.parse(value),
      );
    },
  });
}

export function useResendVerification() {
  return useMutation({
    mutationFn: async (payload: {
      email: string;
      tenant_slug: string;
    }): Promise<ResendVerificationResponse> => {
      const body = resendVerificationPayloadSchema.parse(payload);
      return apiRequest(
        "/api/proxy/api/v1/auth/resend-verification",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        (value) => resendVerificationResponseSchema.parse(value),
      );
    },
  });
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<MeResponse> => {
      return apiRequest(
        "/api/proxy/api/v1/auth/me",
        {
          method: "GET",
        },
        (value) => meResponseSchema.parse(value),
      );
    },
    retry: false,
  });
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
  });
}
