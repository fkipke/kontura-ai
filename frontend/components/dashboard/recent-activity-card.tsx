import { StatusBadge } from "@/components/invoices/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency, formatGermanDate } from "@/lib/format";
import type { InvoiceListItem } from "@/lib/api/schemas";

interface RecentActivityCardProps {
  items: InvoiceListItem[];
}

export function RecentActivityCard({ items }: RecentActivityCardProps): React.JSX.Element {
  return (
    <Card>
      <CardContent className="space-y-4">
        <div>
          <h2 className="text-base font-semibold">Letzte Aktivitäten</h2>
          <p className="text-sm text-muted-foreground">Zuletzt aktualisierte Rechnungen</p>
        </div>

        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Noch keine Aktivitäten vorhanden.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((invoice) => (
              <li key={invoice.id} className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-sm font-medium">{invoice.invoice_number}</p>
                  <p className="text-xs text-muted-foreground">
                    {invoice.vendor_name} · {formatGermanDate(invoice.invoice_date)}
                  </p>
                </div>
                <div className="space-y-1 text-right">
                  <StatusBadge status={invoice.status} />
                  <p className="text-xs text-muted-foreground">{formatCurrency(invoice.total_amount)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
