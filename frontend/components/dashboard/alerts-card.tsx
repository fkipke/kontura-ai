import Link from "next/link";
import { AlertCircle, AlertTriangle, Info } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { AlertsResponse } from "@/lib/dashboard/types";

interface AlertsCardProps {
  alerts: AlertsResponse["alerts"];
}

const severityMeta = {
  info: {
    icon: Info,
    className: "text-blue-500",
  },
  warning: {
    icon: AlertTriangle,
    className: "text-amber-500",
  },
  danger: {
    icon: AlertCircle,
    className: "text-rose-500",
  },
} as const;

export function AlertsCard({ alerts }: AlertsCardProps): React.JSX.Element {
  const visibleAlerts = alerts.slice(0, 5);

  return (
    <Card className="min-h-[360px] transition-opacity duration-200">
      <CardContent className="space-y-4">
        <h2 className="text-base font-semibold">Hinweise</h2>

        {visibleAlerts.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Keine Hinweise — lade die erste Rechnung hoch, um Auffälligkeiten automatisch zu sehen.
          </p>
        ) : (
          <ul className="space-y-3">
            {visibleAlerts.map((alert) => {
              const meta = severityMeta[alert.severity];
              const Icon = meta.icon;

              return (
                <li key={`${alert.type}-${alert.invoice_id}`} className="rounded-lg border border-border px-3 py-2">
                  <div className="flex items-start gap-2">
                    <Icon className={`mt-0.5 h-4 w-4 ${meta.className}`} aria-hidden />
                    <div className="space-y-1">
                      <p className="text-sm">{alert.message}</p>
                      {alert.invoice_number ? (
                        <Link href={`/invoices/${alert.invoice_id}`} className="text-xs text-primary hover:underline">
                          Rechnung {alert.invoice_number} öffnen
                        </Link>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {alerts.length > 5 ? (
          <Link href="/invoices" className="inline-flex text-sm text-primary hover:underline">
            Alle anzeigen
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}
