import { CheckCircle2, Clock, Inbox, Receipt } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { DashboardKpis } from "@/lib/dashboard/types";
import { formatCurrency } from "@/lib/format";

interface KpiTilesProps {
  data: DashboardKpis;
}

function isZero(value: string | number): boolean {
  return Number(value) === 0;
}

export function KpiTiles({ data }: KpiTilesProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card className="transition-opacity duration-200">
        <CardContent className="space-y-2 p-5">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Offene Rechnungen</span>
            <Inbox className="h-4 w-4" aria-hidden />
          </div>
          <p className="text-3xl font-semibold">{data.open_invoices_count}</p>
          <p className="text-sm text-muted-foreground">{formatCurrency(data.open_invoices_total_amount)}</p>
        </CardContent>
      </Card>

      <Card className="transition-opacity duration-200">
        <CardContent className="space-y-2 p-5">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Bezahlt diesen Monat</span>
            <CheckCircle2 className="h-4 w-4" aria-hidden />
          </div>
          <p className="text-3xl font-semibold">
            {isZero(data.paid_this_month_total) ? "—" : formatCurrency(data.paid_this_month_total)}
          </p>
          <p className="text-sm text-muted-foreground">Monatsstand</p>
        </CardContent>
      </Card>

      <Card className="transition-opacity duration-200">
        <CardContent className="space-y-2 p-5">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Skonto bald ablaufend</span>
            <Clock className="h-4 w-4" aria-hidden />
          </div>
          <p className="text-3xl font-semibold">{data.skonto_expiring_soon_count}</p>
          <p className="text-sm text-muted-foreground">
            {isZero(data.skonto_expiring_soon_potential_savings)
              ? "—"
              : formatCurrency(data.skonto_expiring_soon_potential_savings)}
          </p>
        </CardContent>
      </Card>

      <Card className="transition-opacity duration-200">
        <CardContent className="space-y-2 p-5">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>USt aktuelles Quartal</span>
            <Receipt className="h-4 w-4" aria-hidden />
          </div>
          <p className="text-3xl font-semibold">{formatCurrency(data.vat_balance_current_quarter)}</p>
          <p className="text-sm text-muted-foreground">Saldo</p>
        </CardContent>
      </Card>
    </div>
  );
}
