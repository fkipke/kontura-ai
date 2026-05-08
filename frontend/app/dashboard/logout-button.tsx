/**
 * <LogoutButton /> — Client Component.
 *
 * Ruft unsere /api/auth/logout-Route auf, die das Cookie loescht.
 * Anschliessend hard-redirect zu /login (kein router.push, weil wir
 * sicher sein wollen, dass der Server-State frisch geladen wird).
 */

"use client";

import { useState } from "react";

export function LogoutButton() {
  const [isLoading, setIsLoading] = useState(false);

  async function handleLogout(): Promise<void> {
    setIsLoading(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      // Auch bei Fehler: Browser zurueck zum Login schicken.
      window.location.href = "/login";
    }
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={isLoading}
      className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-300 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {isLoading ? "Abmelden …" : "Abmelden"}
    </button>
  );
}