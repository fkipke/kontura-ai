"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardRecentActivity } from "@/lib/api/dashboard";
import { formatCurrency, formatGermanDate } from "@/lib/format";

export function RecentActivityCard(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardRecentActivity(8);

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
              <li key={inv.id} className="py-2.5">
                <Link
                  href={`/invoices/${inv.id}`}
                  className="flex items-center justify-between gap-3 text-sm transition-colors hover:text-primary"
                >
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <p className="truncate font-medium">{inv.vendor_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {inv.invoice_number} · {formatGermanDate(inv.invoice_date)}
                    </p>
                  </div>
                  <span className="shrink-0 font-tnum text-sm">
                    {formatCurrency(inv.total_amount)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
