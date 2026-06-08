import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { TopVendorsResponse } from "@/lib/dashboard/types";
import { formatCurrency } from "@/lib/format";

interface TopVendorsCardProps {
  vendors: TopVendorsResponse["vendors"];
}

export function TopVendorsCard({ vendors }: TopVendorsCardProps): React.JSX.Element {
  const maxAmount = Math.max(...vendors.map((vendor) => Number(vendor.total_amount) || 0), 1);

  return (
    <Card className="min-h-[320px] transition-opacity duration-200">
      <CardContent className="space-y-4">
        <h2 className="text-base font-semibold">Top Lieferanten</h2>

        {vendors.length === 0 ? (
          <p className="text-sm text-muted-foreground">Noch keine Rechnungen — lade die erste hoch.</p>
        ) : (
          <ul className="space-y-3">
            {vendors.map((vendor) => {
              const amount = Number(vendor.total_amount) || 0;
              const width = Math.max(6, (amount / maxAmount) * 100);
              return (
                <li key={vendor.vendor_name} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-medium">{vendor.vendor_name}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{formatCurrency(vendor.total_amount)}</span>
                      <Badge variant="secondary">{vendor.invoice_count}</Badge>
                    </div>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 rounded-full bg-primary/70" style={{ width: `${width}%` }} />
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
