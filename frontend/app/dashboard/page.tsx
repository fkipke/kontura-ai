/**
 * /dashboard — geschuetzte Startseite nach Login.
 *
 * Server Component:
 *   - Liest Cookie via @/lib/auth (server-side)
 *   - Ruft Backend /api/v1/auth/me mit Bearer-Token
 *   - Rendert HTML mit den User-Daten
 *
 * Auth-Failure-Handling:
 *   - Cookie fehlt → eigentlich verhindert die Middleware das.
 *     Falls der Cookie aber AUSGELAUFEN ist (Token expired), antwortet
 *     das Backend mit 401. Dann redirecten wir zum Login.
 */

import { redirect } from "next/navigation";

import { LogoutButton } from "@/app/dashboard/logout-button";
import { ApiError, apiFetch } from "@/lib/api";
import { readAuthToken } from "@/lib/auth";
import type { MeResponse } from "@/lib/types";

async function loadMe(): Promise<MeResponse | null> {
  const token = await readAuthToken();
  if (!token) return null;

  try {
    return await apiFetch<MeResponse>("/api/v1/auth/me", {
      bearerToken: token,
    });
  } catch (error) {
    if (error instanceof ApiError && error.isUnauthorized) {
      return null;
    }
    throw error;
  }
}

export default async function DashboardPage() {
  const me = await loadMe();
  if (!me) {
    // Cookie weg / Token abgelaufen / Backend sagt 401 → zurueck zum Login.
    redirect("/login");
  }

  const expiresAt = new Date(me.token_expires_at * 1000);

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold text-gray-900">Kontura AI</h1>
          <LogoutButton />
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-6 py-10">
        <h2 className="text-2xl font-bold tracking-tight text-gray-900">
          Willkommen
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Sie sind angemeldet als <strong>{me.email}</strong>.
        </p>

        <dl className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InfoCard label="Mandant" value={me.tenant_id} />
          <InfoCard label="User-ID" value={me.user_id} mono />
          <InfoCard label="E-Mail" value={me.email} />
          <InfoCard
            label="Sitzung gueltig bis"
            value={expiresAt.toLocaleString("de-DE")}
          />
        </dl>
      </section>
    </main>
  );
}

interface InfoCardProps {
  label: string;
  value: string;
  mono?: boolean;
}

function InfoCard({ label, value, mono }: InfoCardProps) {
  return (
    <div className="rounded-lg bg-white p-5 shadow-sm ring-1 ring-gray-200">
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </dt>
      <dd
        className={`mt-1 text-sm text-gray-900 ${mono ? "font-mono" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}