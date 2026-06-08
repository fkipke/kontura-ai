import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { DashboardInvoiceStatus, RecentActivityItem } from "@/lib/dashboard/types";
import { formatCurrency, formatRelativeTime } from "@/lib/format";

const statusMeta: Record<
  DashboardInvoiceStatus,
  { label: string; variant: "secondary" | "warning" | "success" }
> = {
  received: { label: "Eingegangen", variant: "secondary" },
  processing: { label: "In Prüfung", variant: "warning" },
  extracted: { label: "Extrahiert", variant: "warning" },
  reviewed: { label: "Geprüft", variant: "success" },
  booked: { label: "Verbucht", variant: "success" },
};

export function RecentActivityCard({ items }: { items: RecentActivityItem[] }): React.JSX.Element {
  return (
    <Card className="min-h-[360px] transition-opacity duration-200">
      <CardContent className="space-y-4">
        <h2 className="text-base font-semibold">Letzte Aktivität</h2>

        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Noch keine Rechnungen — lade die erste hoch.</p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => {
              const status = statusMeta[item.status];

              return (
                <li key={item.id}>
                  <Link
                    href={`/invoices/${item.id}`}
                    className="block rounded-lg border border-border px-3 py-2 transition-colors hover:bg-muted/40"
                  >
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-medium">{item.invoice_number}</p>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                      <span className="truncate">{item.vendor_name}</span>
                      <span>·</span>
                      <span>{formatCurrency(item.total_amount)}</span>
                      <span>·</span>
                      <span>{formatRelativeTime(item.updated_at)}</span>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
