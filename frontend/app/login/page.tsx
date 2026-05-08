/**
 * /login — Login-Seite (Server Component).
 *
 * Server Components sind der Default in Next.js 15 — kein "use client" hier.
 * Wir rendern nur Layout + statisches Markup. Der interaktive Form-State
 * lebt im Client-Component <LoginForm />, das wir hier einbetten.
 */

import { LoginForm } from "@/app/login/login-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            Kontura AI
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Anmeldung zum Mandanten-Portal
          </p>
        </div>
        <div className="rounded-lg bg-white p-8 shadow-sm ring-1 ring-gray-200">
          <LoginForm />
        </div>
      </div>
    </main>
  );
}