"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

export function DemoBanner(): React.JSX.Element {
  const queryClient = useQueryClient();
  const [isResetting, setIsResetting] = useState(false);

  const handleReset = async (): Promise<void> => {
    const confirmed = window.confirm(
      "Demo-Daten wirklich zurücksetzen? Alle aktuellen Daten werden gelöscht und 50 neue Beispielrechnungen werden angelegt.",
    );
    if (!confirmed) {
      return;
    }

    setIsResetting(true);
    try {
      const response = await fetch("/api/proxy/admin/reset-demo", {
        method: "POST",
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "Demo konnte nicht zurückgesetzt werden.");
      }

      queryClient.clear();
      toast.success("Demo zurückgesetzt — 50 neue Rechnungen");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Demo konnte nicht zurückgesetzt werden.");
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="sticky top-14 z-10 border-b border-amber-200 bg-amber-100 text-amber-900">
      <div className="mx-auto flex h-10 w-full max-w-[1280px] items-center justify-between gap-2 px-4 md:px-6">
        <p className="truncate text-sm">
          🎬 Demo-Modus aktiv — alle Daten sind generiert und können jederzeit zurückgesetzt werden.
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-200"
          onClick={handleReset}
          disabled={isResetting}
        >
          {isResetting ? "Wird zurückgesetzt…" : "Demo-Daten zurücksetzen"}
        </Button>
      </div>
    </div>
  );
}
