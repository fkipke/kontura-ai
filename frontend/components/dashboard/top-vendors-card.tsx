"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardTopVendors } from "@/lib/api/dashboard";
import { formatCurrency } from "@/lib/format";

// Kleine Werte bleiben mindestens 6% breit, damit sie im Demo-Video sichtbar sind.
const MIN_BAR_PERCENT = 6;

export function TopVendorsCard(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardTopVendors(5);

  const max =
    data?.vendors.reduce((acc, v) => {
      const num = Number(v.total_amount) || 0;
      return num > acc ? num : acc;
    }, 0) ?? 0;

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Top-Lieferanten</h2>
          <p className="text-xs text-muted-foreground">
            Nach Gesamtbetrag aller Rechnungen
          </p>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-2 w-full" />
              </div>
            ))}
          </div>
        ) : isError || !data || data.vendors.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Noch keine Lieferanten-Daten.
          </p>
        ) : (
          <ul className="space-y-3">
            {data.vendors.map((v) => {
              const num = Number(v.total_amount) || 0;
              const rawPercent = max === 0 ? 0 : (num / max) * 100;
              const percent = Math.max(rawPercent, MIN_BAR_PERCENT);
              return (
                <li key={v.vendor_name} className="space-y-1.5">
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="truncate font-medium">{v.vendor_name}</span>
                    <span className="shrink-0 font-tnum text-muted-foreground">
                      {formatCurrency(v.total_amount)} · {v.invoice_count} Re.
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
