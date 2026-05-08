/**
 * <LoginForm /> — Client Component mit Form-State.
 *
 * "use client"-Direktive: Diese Datei wird zum Browser geschickt
 * und dort als JavaScript ausgefuehrt. Nur DEN State-tragenden Teil
 * markieren wir so — der Rest der App bleibt server-side.
 *
 * Form-Verhalten:
 *  - Submit -> POST an unsere eigene Route /api/auth/login
 *  - Bei 200: Redirect zu /dashboard
 *  - Bei Fehler: Inline-Error-Anzeige, Form behaelt eingegebene Werte
 */

"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import type { ProblemDetail } from "@/lib/types";

export function LoginForm() {
  const router = useRouter();

  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_slug: tenantSlug,
          email,
          password,
        }),
      });

      if (!response.ok) {
        const problem = (await response.json().catch(() => null)) as
          | ProblemDetail
          | null;
        setErrorMessage(
          problem?.detail ??
            problem?.title ??
            `Anmeldung fehlgeschlagen (${response.status}).`,
        );
        return;
      }

      // Erfolgreich → Cookie ist gesetzt, ab zum Dashboard.
      router.push("/dashboard");
      router.refresh(); // Server Components neu laden mit aktivem Cookie
    } catch {
      setErrorMessage(
        "Verbindung zum Server fehlgeschlagen. Bitte spaeter erneut versuchen.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      <Field
        id="tenant_slug"
        label="Mandant"
        type="text"
        autoComplete="organization"
        value={tenantSlug}
        onChange={setTenantSlug}
        placeholder="acme-corp"
        required
      />
      <Field
        id="email"
        label="E-Mail"
        type="email"
        autoComplete="email"
        value={email}
        onChange={setEmail}
        placeholder="anna@acme-corp.de"
        required
      />
      <Field
        id="password"
        label="Passwort"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
        required
      />

      {errorMessage && (
        <p
          role="alert"
          className="rounded-md bg-red-50 p-3 text-sm text-red-700 ring-1 ring-red-200"
        >
          {errorMessage}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-md bg-gray-900 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-900 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? "Anmelden …" : "Anmelden"}
      </button>
    </form>
  );
}

interface FieldProps {
  id: string;
  label: string;
  type: "text" | "email" | "password";
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
}

function Field({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
  required,
}: FieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-gray-900"
      >
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        className="mt-1 block w-full rounded-md border-0 px-3 py-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-gray-900 sm:text-sm"
      />
    </div>
  );
}