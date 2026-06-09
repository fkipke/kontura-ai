"use client";

import Link from "next/link";
import { AlertTriangle, Info, ShieldAlert } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardAlerts, type DashboardAlert } from "@/lib/api/dashboard";

type SeverityConfig = {
  box: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  iconClass: string;
  label: string;
};

const SEVERITY_STYLES: Record<DashboardAlert["severity"], SeverityConfig> = {
  info: {
    box: "border-l-blue-500/60 bg-blue-500/5",
    icon: Info,
    iconClass: "text-blue-600 dark:text-blue-400",
    label: "Hinweis",
  },
  warning: {
    box: "border-l-amber-500/60 bg-amber-500/5",
    icon: AlertTriangle,
    iconClass: "text-amber-600 dark:text-amber-400",
    label: "Warnung",
  },
  danger: {
    box: "border-l-red-500/60 bg-red-500/5",
    icon: ShieldAlert,
    iconClass: "text-red-600 dark:text-red-400",
    label: "Kritisch",
  },
};

export function AlertsCard(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardAlerts();

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Hinweise &amp; Warnungen</h2>
          <p className="text-xs text-muted-foreground">
            Auffälligkeiten in den letzten Rechnungen
          </p>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : isError ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Hinweise konnten nicht geladen werden.
          </p>
        ) : !data || data.alerts.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Alles unauffällig. ✓
          </p>
        ) : (
          <ul className="space-y-2">
            {data.alerts.map((alert) => {
              const cfg = SEVERITY_STYLES[alert.severity];
              const Icon = cfg.icon;
              return (
                <li key={`${alert.invoice_id}-${alert.type}`}>
                  <Link
                    href={`/invoices/${alert.invoice_id}`}
                    className={`flex items-start gap-3 rounded-r-md border-l-4 px-3 py-2.5 transition-colors hover:bg-muted/50 ${cfg.box}`}
                  >
                    <Icon
                      className={`mt-0.5 h-4 w-4 shrink-0 ${cfg.iconClass}`}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {cfg.label}
                      </p>
                      <p className="text-sm">{alert.message}</p>
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
