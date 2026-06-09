import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency } from "@/lib/format";
import type { TopVendor } from "@/lib/api/schemas";

interface TopVendorsCardProps {
  vendors: TopVendor[];
}

export function TopVendorsCard({ vendors }: TopVendorsCardProps): React.JSX.Element {
  return (
    <Card>
      <CardContent className="space-y-4">
        <div>
          <h2 className="text-base font-semibold">Top-Lieferanten</h2>
          <p className="text-sm text-muted-foreground">Nach Gesamtbetrag sortiert</p>
        </div>

        {vendors.length === 0 ? (
          <p className="text-sm text-muted-foreground">Noch keine Lieferanten-Daten vorhanden.</p>
        ) : (
          <ul className="space-y-3">
            {vendors.map((vendor) => (
              <li key={vendor.vendor_name} className="flex items-start justify-between gap-4 text-sm">
                <div>
                  <p className="font-medium">{vendor.vendor_name}</p>
                  <p className="text-muted-foreground">{vendor.invoice_count} Rechnungen</p>
                </div>
                <p className="font-medium">{formatCurrency(vendor.total_amount)}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
