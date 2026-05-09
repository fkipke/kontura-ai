/**
 * TypeScript-Types — synchron zu den Pydantic-Schemas im Backend.
 *
 * Senior-Pattern: Wir spiegeln die Backend-Schemas hier manuell.
 * (Spaeter koennten wir openapi-typescript nutzen, um es auto-zu-generieren —
 * fuer den Anfang ist manuelles Spiegeln transparenter und einfacher zu lernen.)
 *
 * Konvention: Types sind im "PascalCase", entsprechen 1:1 den
 * Pydantic-Klassen im Backend (LoginRequest, MeResponse, ...).
 */

// =====================================================
// Auth
// =====================================================

export interface LoginRequest {
  tenant_slug: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
}

export interface MeResponse {
  user_id: string;
  tenant_id: string;
  email: string;
  token_expires_at: number; // Unix-Timestamp
}

// =====================================================
// Allgemein
// =====================================================

/**
 * Backend nutzt RFC 9457 Problem-Details fuer Fehler-Responses.
 * Beispiel: { "type": "...", "title": "Unauthorized", "status": 401, "detail": "..." }
 */
export interface ProblemDetail {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
}