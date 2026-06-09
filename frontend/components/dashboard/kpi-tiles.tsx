"use client";

import { Calculator, CheckCircle2, Clock, Receipt } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardKpis } from "@/lib/api/dashboard";
import { formatCurrency } from "@/lib/format";

type Accent = "blue" | "emerald" | "amber" | "violet";

const ACCENT_CLASSES: Record<Accent, string> = {
  blue: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  violet: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
};

interface TileProps {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  accent: Accent;
}

function Tile({ label, value, sub, icon, accent }: TileProps): React.JSX.Element {
  return (
    <Card>
      <CardContent className="flex items-start gap-4 p-5">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${ACCENT_CLASSES[accent]}`}
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="truncate text-2xl font-semibold tracking-tight font-tnum">
            {value}
          </p>
          {sub ? (
            <p className="truncate text-xs text-muted-foreground">{sub}</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function TileSkeleton(): React.JSX.Element {
  return (
    <Card>
      <CardContent className="flex items-start gap-4 p-5">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
      </CardContent>
    </Card>
  );
}

export function KpiTiles(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardKpis();

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <TileSkeleton />
        <TileSkeleton />
        <TileSkeleton />
        <TileSkeleton />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardContent className="py-6 text-center text-sm text-muted-foreground">
          KPIs konnten nicht geladen werden.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Tile
        label="Offene Rechnungen"
        value={String(data.open_invoices_count)}
        sub={`${formatCurrency(data.open_invoices_total_amount)} gesamt`}
        icon={<Receipt className="h-5 w-5" aria-hidden />}
        accent="blue"
      />
      <Tile
        label="Bezahlt diesen Monat"
        value={formatCurrency(data.paid_this_month_total)}
        icon={<CheckCircle2 className="h-5 w-5" aria-hidden />}
        accent="emerald"
      />
      <Tile
        label="Skonto läuft bald ab"
        value={String(data.skonto_expiring_soon_count)}
        sub={`${formatCurrency(data.skonto_expiring_soon_potential_savings)} möglich`}
        icon={<Clock className="h-5 w-5" aria-hidden />}
        accent="amber"
      />
      <Tile
        label="USt-Saldo (Quartal)"
        value={formatCurrency(data.vat_balance_current_quarter)}
        icon={<Calculator className="h-5 w-5" aria-hidden />}
        accent="violet"
      />
    </div>
  );
}
