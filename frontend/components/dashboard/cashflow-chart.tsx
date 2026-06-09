"use client";

import { useMemo } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardCashflow } from "@/lib/api/dashboard";
import { formatCurrency } from "@/lib/format";

const SHORT_MONTHS = [
  "Jan",
  "Feb",
  "Mär",
  "Apr",
  "Mai",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Okt",
  "Nov",
  "Dez",
];

function shortMonthLabel(yyyymm: string): string {
  const parts = yyyymm.split("-");
  if (parts.length !== 2) return yyyymm;
  const idx = Number.parseInt(parts[1], 10) - 1;
  if (Number.isNaN(idx) || idx < 0 || idx > 11) return yyyymm;
  return SHORT_MONTHS[idx];
}

export function CashflowChart(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardCashflow(12);

  const chart = useMemo(() => {
    if (!data || data.points.length === 0) return null;
    const amounts = data.points.map((p) => Number(p.total_amount) || 0);
    const maxAmount = Math.max(...amounts, 1);
    return { points: data.points, maxAmount };
  }, [data]);

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Cashflow letzte 12 Monate</h2>
          <p className="text-xs text-muted-foreground">
            Summe Rechnungsbeträge pro Monat
          </p>
        </div>

        {isLoading ? (
          <Skeleton className="h-[200px] w-full" />
        ) : isError || !chart ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            Keine Cashflow-Daten verfügbar.
          </p>
        ) : (
          <div className="-mx-2 overflow-x-auto">
            <svg
              viewBox="0 0 560 220"
              preserveAspectRatio="none"
              className="block h-[200px] w-full min-w-[480px]"
              role="img"
              aria-label="Cashflow-Verlauf der letzten 12 Monate"
            >
              <line
                x1="20"
                y1="180"
                x2="540"
                y2="180"
                className="stroke-border"
                strokeWidth="1"
              />

              {chart.points.map((p, i) => {
                const x = 28 + i * 44;
                const amount = Number(p.total_amount) || 0;
                const rawHeight =
                  chart.maxAmount === 0 ? 0 : (amount / chart.maxAmount) * 140;
                const barHeight = amount === 0 ? 2 : Math.max(rawHeight, 6);
                const y = 180 - barHeight;
                const isCurrent = i >= chart.points.length - 1;
                return (
                  <g key={p.month}>
                    <rect
                      x={x}
                      y={y}
                      width="22"
                      height={barHeight}
                      rx="3"
                      className={isCurrent ? "fill-primary" : "fill-primary/40"}
                    >
                      <title>{`${shortMonthLabel(p.month)}: ${formatCurrency(p.total_amount)}`}</title>
                    </rect>
                    <text
                      x={x + 11}
                      y="200"
                      textAnchor="middle"
                      className="fill-muted-foreground text-[10px]"
                    >
                      {shortMonthLabel(p.month)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
