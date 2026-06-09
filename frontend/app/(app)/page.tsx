"use client";

import { AlertsCard } from "@/components/dashboard/alerts-card";
import { CashflowCard } from "@/components/dashboard/cashflow-card";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { RecentActivityCard } from "@/components/dashboard/recent-activity-card";
import { TopVendorsCard } from "@/components/dashboard/top-vendors-card";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDashboardAlerts,
  useDashboardCashflow,
  useDashboardKpis,
  useDashboardRecentActivity,
  useDashboardTopVendors,
} from "@/lib/api/dashboard";

export default function DashboardPage(): React.JSX.Element {
  const kpis = useDashboardKpis();
  const cashflow = useDashboardCashflow(12);
  const topVendors = useDashboardTopVendors(5);
  const recentActivity = useDashboardRecentActivity(8);
  const alerts = useDashboardAlerts();

  const isLoading =
    kpis.isLoading ||
    cashflow.isLoading ||
    topVendors.isLoading ||
    recentActivity.isLoading ||
    alerts.isLoading;

  if (isLoading) {
    return (
      <main className="space-y-6">
        <Skeleton className="h-8 w-56" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
        <Skeleton className="h-72" />
      </main>
    );
  }

  if (kpis.isError || cashflow.isError || topVendors.isError || recentActivity.isError || alerts.isError) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Dashboard-Daten konnten nicht geladen werden. Bitte Seite neu laden.
        </CardContent>
      </Card>
    );
  }

  const kpiData = kpis.data;
  const cashflowPoints = cashflow.data?.points ?? [];
  const topVendorItems = topVendors.data?.vendors ?? [];
  const recentItems = recentActivity.data ?? [];
  const alertItems = alerts.data?.alerts ?? [];

  if (!kpiData) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Dashboard-Daten konnten nicht geladen werden. Bitte Seite neu laden.
        </CardContent>
      </Card>
    );
  }

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Übersicht</h1>
        <p className="text-sm text-muted-foreground">Finanzstatus, Cashflow und Risiko-Hinweise auf einen Blick</p>
      </header>

      <KpiCards data={kpiData} />

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <CashflowCard points={cashflowPoints} />
        </div>
        <TopVendorsCard vendors={topVendorItems} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <RecentActivityCard items={recentItems} />
        <AlertsCard alerts={alertItems} />
      </div>
    </main>
  );
}
