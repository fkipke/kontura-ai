"use client";

import { useRouter } from "next/navigation";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardRecentActivity } from "@/lib/api/dashboard";
import { formatCurrency, formatGermanDate } from "@/lib/format";

export function RecentActivityCard(): React.JSX.Element {
  const router = useRouter();
  const { data, isLoading, isError } = useDashboardRecentActivity(8);

  // Hinweis: Der /recent-activity-Endpoint liefert Invoice-IDs (DB-Eintrag),
  // die Detail-Page nutzt aber InvoiceFile-IDs (hochgeladene Datei). Diese
  // beiden IDs sind unterschiedlich und es gibt keine zuverlaessige Rück-
  // Verkettung im Frontend (linked_invoice_id liegt nur am ExtractionStatus
  // jeder Datei). Wir routen daher zur Rechnungsliste, wo der Nutzer den
  // gewünschten Beleg per Klick öffnet. Für's Demo-Video sind das
  // 2 Klicks statt 1 - aber kein Sackgassen-Klick.
  const handleRowClick = (): void => {
    router.push("/invoices");
  };

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Zuletzt bearbeitet</h2>
          <p className="text-xs text-muted-foreground">
            Aktuelle Rechnungsbewegungen
          </p>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-3">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-20" />
              </div>
            ))}
          </div>
        ) : isError || !data || data.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Noch keine Aktivität.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data.map((inv) => (
              <li key={inv.id}>
                <button
                  type="button"
                  onClick={handleRowClick}
                  className="flex w-full items-center justify-between gap-3 py-2.5 text-left text-sm transition-colors hover:bg-muted/50 focus:bg-muted/50 focus:outline-none -mx-2 px-2 rounded"
                >
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <p className="truncate font-medium">{inv.vendor_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {inv.invoice_number} · {formatGermanDate(inv.invoice_date)}
                    </p>
                  </div>
                  <span className="shrink-0 font-tnum">
                    {formatCurrency(inv.total_amount)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
