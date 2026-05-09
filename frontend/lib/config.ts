/**
 * Zentrale Konfiguration — alle Env-Vars hier typed eingelesen.
 *
 * Senior-Pattern: KEINE direkten `process.env.X`-Zugriffe quer durch den Code.
 * Stattdessen: hier zentral validieren, dann den `config`-Export importieren.
 * Vorteile:
 *  - Tippfehler in Env-Var-Namen werden hier sofort gefangen
 *  - Klar dokumentiert, welche Vars das System braucht
 *  - Bei Wechsel der Quelle (z.B. Vault statt .env) nur diese Datei anpassen
 *
 * WICHTIG: NEXT_PUBLIC_*-Vars werden im Browser sichtbar!
 * Alles ohne Praefix bleibt server-side (sicherer Default).
 */

function requireEnv(name: string, value: string | undefined): string {
  if (!value || value.trim() === "") {
    throw new Error(
      `Environment variable ${name} ist nicht gesetzt. ` +
        `Pruefe deine .env.local Datei.`,
    );
  }
  return value;
}

export const config = {
  // Browser-seitig: wird in den Build kompiliert (sichtbar im JS-Bundle).
  publicApiBaseUrl: requireEnv(
    "NEXT_PUBLIC_API_BASE_URL",
    process.env.NEXT_PUBLIC_API_BASE_URL,
  ),

  // Server-seitig: nur in Server Components / Route Handlers verfuegbar.
  // In Production typischerweise interner Hostname (z.B. http://backend:8000).
  apiBaseUrl: requireEnv("API_BASE_URL", process.env.API_BASE_URL),

  // Cookie-Settings fuer JWT-Storage.
  authCookieName: "access_token",

  // Cookie laeuft synchron mit JWT-TTL ab (60 Min im Backend default).
  // Wir setzen 55 Min, damit das Cookie LEICHT vor dem Token ablaeuft —
  // verhindert "Token gueltig, aber Cookie schon weg"-Race-Conditions.
  authCookieMaxAgeSeconds: 55 * 60,
} as const;

export type AppConfig = typeof config;