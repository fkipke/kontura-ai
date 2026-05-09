/**
 * Typed fetch-Wrapper fuer das Backend.
 *
 * Senior-Pattern: ALLE Backend-Calls gehen ueber diese Funktionen.
 * Vorteile:
 *  - Eine Stelle fuer Auth-Header, Error-Handling, Logging
 *  - Type-Safety: Compiler weiss, was zurueckkommt
 *  - Bei Backend-URL-Change: nur diese Datei aendern
 *
 * Architektur:
 *  - apiFetch() ist server-side (Server Components, Route Handlers).
 *  - Browser-Code ruft NIE direkt das Backend auf — er ruft Next.js-Routes,
 *    die intern apiFetch() nutzen.
 *
 * Dieses File ist server-only:
 *  - Es liest Env-Vars, die im Browser nicht da sind (API_BASE_URL ohne Prefix).
 *  - Wir kennzeichnen das mit "import 'server-only'", damit ein versehentlicher
 *    Import in einem Client-Component beim Build SOFORT scheitert (nicht erst zur Laufzeit).
 */

import "server-only";

import { config } from "@/lib/config";
import type { ProblemDetail } from "@/lib/types";

// =====================================================
// Fehler-Typ
// =====================================================

/**
 * Wird geworfen, wenn das Backend nicht-2xx antwortet.
 * Enthaelt das geparste Problem-Detail (RFC 9457) — falls vorhanden.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ProblemDetail | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

// =====================================================
// Core fetch-Wrapper
// =====================================================

interface ApiFetchOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** JSON-Body — wird automatisch stringified. */
  body?: unknown;
  /** JWT fuer "Authorization: Bearer ...". Optional. */
  bearerToken?: string;
  /** Zusaetzliche Headers (z.B. Request-ID-Forwarding). */
  headers?: Record<string, string>;
}

/**
 * Wrappt fetch mit:
 *  - JSON-Serialisierung
 *  - Authorization-Header (falls Token gesetzt)
 *  - 2xx-Check + ApiError bei Fehlern
 *  - Generic-Type fuer Type-Safety auf den Antwort-Body
 */
export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { method = "GET", body, bearerToken, headers = {} } = options;

  const url = `${config.apiBaseUrl}${path}`;
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }
  if (bearerToken) {
    finalHeaders["Authorization"] = `Bearer ${bearerToken}`;
  }

  const response = await fetch(url, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    // Wir cachen NIE Backend-Responses (Auth-relevant, kann sich aendern).
    cache: "no-store",
  });

  if (!response.ok) {
    let problem: ProblemDetail | null = null;
    try {
      problem = (await response.json()) as ProblemDetail;
    } catch {
      // Backend hat kein JSON zurueckgeschickt — kein Problem-Detail verfuegbar.
    }
    throw new ApiError(
      response.status,
      problem,
      problem?.detail ??
        problem?.title ??
        `Backend antwortete mit ${response.status}`,
    );
  }

  // 204 No Content → kein Body zu parsen.
  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}