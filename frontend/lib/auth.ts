/**
 * Server-side Auth-Helpers — Cookie-Handling.
 *
 * Senior-Pattern: Cookies werden NUR server-side gelesen/geschrieben.
 * Der Browser kann den HttpOnly-Cookie nicht via JavaScript anfassen.
 *
 * Cookie-Properties (Senior-Best-Practice):
 *  - HttpOnly: true   → kein JS-Zugriff (XSS-Schutz)
 *  - Secure: true     → nur ueber HTTPS senden (in Production)
 *  - SameSite: "lax"  → CSRF-Schutz, aber Standard-Navigation funktioniert
 *  - Path: "/"        → fuer alle Routes verfuegbar
 *  - MaxAge           → automatisches Ablaufen
 */

import "server-only";

import { cookies } from "next/headers";

import { config } from "@/lib/config";

/**
 * Liest den JWT aus dem HttpOnly-Cookie.
 * Returned `null`, falls kein Cookie gesetzt ist.
 */
export async function readAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const cookie = cookieStore.get(config.authCookieName);
  return cookie?.value ?? null;
}

/**
 * Setzt das Auth-Cookie nach erfolgreichem Login.
 *
 * @param token — der JWT, den das Backend zurueckgegeben hat
 */
export async function writeAuthToken(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set({
    name: config.authCookieName,
    value: token,
    httpOnly: true,
    // In Dev (HTTP) muss Secure=false sein, sonst sendet der Browser das Cookie nicht.
    // In Production (HTTPS) immer Secure=true.
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: config.authCookieMaxAgeSeconds,
  });
}

/**
 * Loescht das Auth-Cookie (Logout).
 */
export async function clearAuthToken(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(config.authCookieName);
}