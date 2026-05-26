import "server-only";

import { cookies } from "next/headers";

import { config } from "@/lib/config";

export async function readAuthToken(): Promise<string | null> {
  return (await cookies()).get(config.authCookieName)?.value ?? null;
}

export async function writeAuthToken(
  token: string,
  maxAgeSeconds: number,
): Promise<void> {
  (await cookies()).set(config.authCookieName, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: maxAgeSeconds,
    path: "/",
  });
}

export async function clearAuthToken(): Promise<void> {
  (await cookies()).set(config.authCookieName, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 0,
    path: "/",
  });
}
