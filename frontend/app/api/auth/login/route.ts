/**
 * Next.js Route Handler: POST /api/auth/login
 *
 * Architektur (BFF-Pattern):
 *   Browser (Form) ──► dieser Handler ──► FastAPI ──► JWT
 *                            │
 *                            └─► setzt HttpOnly-Cookie
 *
 * Der Browser bekommt den JWT NIE direkt. Maximale Sicherheit gegen XSS.
 *
 * Validierung:
 *   - Wir validieren das Body-Schema HIER NICHT erneut, weil das Backend
 *     das per Pydantic ohnehin macht. Bei einem Fehler im Backend (z.B.
 *     400 wegen falscher Email) reichen wir das Problem-Detail durch.
 */

import { NextResponse } from "next/server";

import { ApiError, apiFetch } from "@/lib/api";
import { writeAuthToken } from "@/lib/auth";
import type { LoginRequest, TokenResponse } from "@/lib/types";

export async function POST(request: Request): Promise<NextResponse> {
  let body: LoginRequest;
  try {
    body = (await request.json()) as LoginRequest;
  } catch {
    return NextResponse.json(
      { title: "Bad Request", status: 400, detail: "Invalid JSON body" },
      { status: 400 },
    );
  }

  try {
    const tokenResponse = await apiFetch<TokenResponse>(
      "/api/v1/auth/login",
      {
        method: "POST",
        body,
      },
    );

    // Cookie setzen (HttpOnly, Secure in Production, SameSite=Lax)
    await writeAuthToken(tokenResponse.access_token);

    // Wir geben dem Browser KEIN Token zurueck — nur "ok".
    return NextResponse.json({ ok: true }, { status: 200 });
  } catch (error) {
    if (error instanceof ApiError) {
      // Backend-Fehler 1:1 weiterreichen (Status + Problem-Detail).
      return NextResponse.json(
        error.problem ?? { title: error.message, status: error.status },
        { status: error.status },
      );
    }
    // Unbekannter Fehler (Netzwerk, Backend down, ...).
    console.error("Login route handler error:", error);
    return NextResponse.json(
      {
        title: "Service Unavailable",
        status: 503,
        detail: "Backend nicht erreichbar.",
      },
      { status: 503 },
    );
  }
}