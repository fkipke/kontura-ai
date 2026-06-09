import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency } from "@/lib/format";
import type { DashboardAlert } from "@/lib/api/schemas";

interface AlertsCardProps {
  alerts: DashboardAlert[];
}

function alertVariant(severity: DashboardAlert["severity"]): "secondary" | "warning" | "destructive" {
  if (severity === "danger") return "destructive";
  if (severity === "warning") return "warning";
  return "secondary";
}

export function AlertsCard({ alerts }: AlertsCardProps): React.JSX.Element {
  return (
    <Card>
      <CardContent className="space-y-4">
        <div>
          <h2 className="text-base font-semibold">Risiko-Hinweise</h2>
          <p className="text-sm text-muted-foreground">Automatische Auffälligkeiten aus den Rechnungsdaten</p>
        </div>

        {alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground">Keine auffälligen Vorgänge erkannt.</p>
        ) : (
          <ul className="space-y-3">
            {alerts.map((alert) => (
              <li key={`${alert.type}-${alert.invoice_id}`} className="space-y-1 rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">{alert.invoice_number ?? "Ohne Rechnungsnummer"}</p>
                  <Badge variant={alertVariant(alert.severity)}>{alert.severity}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">{alert.vendor_name ?? "Unbekannter Lieferant"}</p>
                <p className="text-sm">{alert.message}</p>
                {alert.total_amount !== null && (
                  <p className="text-xs text-muted-foreground">Betrag: {formatCurrency(alert.total_amount)}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
