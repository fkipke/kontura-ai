import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency } from "@/lib/format";
import type { CashflowPoint } from "@/lib/api/schemas";

interface CashflowCardProps {
  points: CashflowPoint[];
}

export function CashflowCard({ points }: CashflowCardProps): React.JSX.Element {
  const maxAmount = Math.max(...points.map((point) => Number(point.total_amount) || 0), 1);

  return (
    <Card>
      <CardContent className="space-y-4">
        <div>
          <h2 className="text-base font-semibold">Cashflow-Verlauf</h2>
          <p className="text-sm text-muted-foreground">Monatliche Summen der Rechnungsbeträge</p>
        </div>

        <div className="space-y-3">
          {points.map((point) => {
            const amount = Number(point.total_amount) || 0;
            const width = Math.max((amount / maxAmount) * 100, amount > 0 ? 4 : 0);

            return (
              <div key={point.month} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{point.month}</span>
                  <span className="text-muted-foreground">
                    {formatCurrency(point.total_amount)} · {point.invoice_count} Rechnungen
                  </span>
                </div>
                <div className="h-2 rounded bg-muted">
                  <div className="h-2 rounded bg-primary" style={{ width: `${width}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
