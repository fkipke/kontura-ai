/**
 * Next.js Route Handler: POST /api/auth/logout
 *
 * Loescht das Auth-Cookie. Optional: ruft auch das Backend-Logout auf
 * (nice-to-have fuer spaetere Token-Blocklist-Phase).
 */

import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api";
import { clearAuthToken, readAuthToken } from "@/lib/auth";

export async function POST(): Promise<NextResponse> {
  const token = await readAuthToken();

  // Best-effort Backend-Logout. Fehler ignorieren (Cookie wird trotzdem geloescht).
  if (token) {
    try {
      await apiFetch<void>("/api/v1/auth/logout", {
        method: "POST",
        bearerToken: token,
      });
    } catch (error) {
      if (!(error instanceof ApiError)) {
        console.error("Backend logout failed (best-effort):", error);
      }
      // Bei ApiError (z.B. Token bereits abgelaufen): einfach weiter.
    }
  }

  await clearAuthToken();
  return NextResponse.json({ ok: true }, { status: 200 });
}