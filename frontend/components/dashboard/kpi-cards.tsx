import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency } from "@/lib/format";
import type { DashboardKpis } from "@/lib/api/schemas";

interface KpiCardsProps {
  data: DashboardKpis;
}

export function KpiCards({ data }: KpiCardsProps): React.JSX.Element {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardContent className="space-y-1">
          <p className="text-sm text-muted-foreground">Offene Rechnungen</p>
          <p className="text-2xl font-semibold">{data.open_invoices_count}</p>
          <p className="text-sm text-muted-foreground">{formatCurrency(data.open_invoices_total_amount)}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-1">
          <p className="text-sm text-muted-foreground">Vorsteuer (aktuelles Quartal)</p>
          <p className="text-2xl font-semibold">{formatCurrency(data.vat_balance_current_quarter)}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-1">
          <p className="text-sm text-muted-foreground">Bezahlt (aktueller Monat)</p>
          <p className="text-2xl font-semibold">{formatCurrency(data.paid_this_month_total)}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-1">
          <p className="text-sm text-muted-foreground">Skonto bald fällig</p>
          <p className="text-2xl font-semibold">{data.skonto_expiring_soon_count}</p>
          <p className="text-sm text-muted-foreground">
            Potenzial: {formatCurrency(data.skonto_expiring_soon_potential_savings)}
          </p>
        </CardContent>
      </Card>
    </section>
  );
}
