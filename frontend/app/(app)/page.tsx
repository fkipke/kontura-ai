"use client";

import { AlertsCard } from "@/components/dashboard/alerts-card";
import { CashflowChart } from "@/components/dashboard/cashflow-chart";
import { KpiTiles } from "@/components/dashboard/kpi-tiles";
import { RecentActivityCard } from "@/components/dashboard/recent-activity-card";
import { TopVendorsCard } from "@/components/dashboard/top-vendors-card";

export default function DashboardPage(): React.JSX.Element {
  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Übersicht</h1>
        <p className="text-sm text-muted-foreground">
          Alle wichtigen Kennzahlen auf einen Blick
        </p>
      </header>

      <KpiTiles />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <CashflowChart />
          <RecentActivityCard />
        </div>
        <div className="space-y-6">
          <TopVendorsCard />
          <AlertsCard />
        </div>
      </div>
    </main>
  );
}
