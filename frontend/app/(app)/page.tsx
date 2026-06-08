"use client";

import { useQueryClient } from "@tanstack/react-query";

import { AlertsCard } from "@/components/dashboard/alerts-card";
import { CashflowChart } from "@/components/dashboard/cashflow-chart";
import { KpiTiles } from "@/components/dashboard/kpi-tiles";
import { RecentActivityCard } from "@/components/dashboard/recent-activity-card";
import { DashboardCardSkeleton, DashboardKpiSkeletons } from "@/components/dashboard/skeletons";
import { TopVendorsCard } from "@/components/dashboard/top-vendors-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  dashboardQueryKeys,
  useDashboardAlerts,
  useDashboardCashflow,
  useDashboardKpis,
  useDashboardRecentActivity,
  useDashboardTopVendors,
} from "@/lib/dashboard/queries";

function DashboardErrorCard({ onRetry }: { onRetry: () => void }): React.JSX.Element {
  return (
    <Card className="border-destructive/40 bg-destructive/5">
      <CardContent className="flex items-center justify-between gap-4 py-4">
        <p className="text-sm text-destructive">Konnte Daten nicht laden.</p>
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          Erneut versuchen
        </Button>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage(): React.JSX.Element {
  const queryClient = useQueryClient();
  const kpis = useDashboardKpis();
  const cashflow = useDashboardCashflow();
  const topVendors = useDashboardTopVendors();
  const recentActivity = useDashboardRecentActivity();
  const alerts = useDashboardAlerts();

  const hasAnyError =
    kpis.isError || cashflow.isError || topVendors.isError || recentActivity.isError || alerts.isError;

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Übersicht</h1>
        <p className="text-sm text-muted-foreground">Stand: heute</p>
      </header>

      {hasAnyError ? (
        <DashboardErrorCard
          onRetry={() => {
            queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.root });
          }}
        />
      ) : null}

      {kpis.isLoading || !kpis.data ? <DashboardKpiSkeletons /> : <KpiTiles data={kpis.data} />}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {cashflow.isLoading || !cashflow.data ? (
          <Card className="min-h-[320px]">
            <CardContent className="space-y-4">
              <h2 className="text-base font-semibold">Cashflow letzte 12 Monate</h2>
              <DashboardCardSkeleton rows={6} />
            </CardContent>
          </Card>
        ) : (
          <CashflowChart points={cashflow.data.points} />
        )}

        {topVendors.isLoading || !topVendors.data ? (
          <Card className="min-h-[320px]">
            <CardContent className="space-y-4">
              <h2 className="text-base font-semibold">Top Lieferanten</h2>
              <DashboardCardSkeleton rows={5} />
            </CardContent>
          </Card>
        ) : (
          <TopVendorsCard vendors={topVendors.data.vendors} />
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {recentActivity.isLoading || !recentActivity.data ? (
          <Card className="min-h-[360px]">
            <CardContent className="space-y-4">
              <h2 className="text-base font-semibold">Letzte Aktivität</h2>
              <DashboardCardSkeleton rows={6} />
            </CardContent>
          </Card>
        ) : (
          <RecentActivityCard items={recentActivity.data} />
        )}

        {alerts.isLoading || !alerts.data ? (
          <Card className="min-h-[360px]">
            <CardContent className="space-y-4">
              <h2 className="text-base font-semibold">Hinweise</h2>
              <DashboardCardSkeleton rows={5} />
            </CardContent>
          </Card>
        ) : (
          <AlertsCard alerts={alerts.data.alerts} />
        )}
      </div>
    </main>
  );
}
