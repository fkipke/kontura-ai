import { useMutation, useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api/client";
import {
  loginPayloadSchema,
  meResponseSchema,
  registerPayloadSchema,
  type LoginPayload,
  type MeResponse,
  type RegisterPayload,
} from "@/lib/api/schemas";

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
    mutationFn: async (payload: RegisterPayload) => {
      const body = registerPayloadSchema.parse(payload);
      return apiRequest(
        "/api/auth/register",
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
