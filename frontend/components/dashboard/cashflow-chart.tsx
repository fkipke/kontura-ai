"use client";

import { useMemo } from "react";

import { Card, CardContent } from "@/components/ui/card";
import type { CashflowResponse } from "@/lib/dashboard/types";
import { formatCurrency } from "@/lib/format";

interface CashflowChartProps {
  points: CashflowResponse["points"];
}

// Basislayout für 12 Monatsbalken inkl. Achsen-Label.
const CHART_MULTIPLIER_WIDTH = 42;
const CHART_MIN_WIDTH = 480;
const CHART_HEIGHT = 220;
const CHART_BASELINE = 160;
const CHART_BAR_WIDTH = 18;
// Visuelle Skalierung: Bars nutzen max. 120px Höhe im Chart-Viewport.
const CHART_BAR_MAX_HEIGHT = 120;
const ZERO_AMOUNT_BAR_HEIGHT = 2;
const MIN_BAR_HEIGHT = 6;

function monthShortLabel(month: string): string {
  const date = new Date(`${month}-01T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return month;
  }
  return new Intl.DateTimeFormat("de-DE", { month: "short" }).format(date);
}

function monthLongLabel(month: string): string {
  const date = new Date(`${month}-01T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return month;
  }
  return new Intl.DateTimeFormat("de-DE", { month: "long", year: "numeric" }).format(date);
}

export function CashflowChart({ points }: CashflowChartProps): React.JSX.Element {
  const chart = useMemo(() => {
    const width = Math.max(points.length * CHART_MULTIPLIER_WIDTH, CHART_MIN_WIDTH);
    const height = CHART_HEIGHT;
    const baseline = CHART_BASELINE;
    const barWidth = CHART_BAR_WIDTH;
    const maxValue = Math.max(...points.map((point) => Number(point.total_amount) || 0), 1);

    return { width, height, baseline, barWidth, maxValue };
  }, [points]);

  return (
    <Card className="min-h-[320px] transition-opacity duration-200">
      <CardContent className="space-y-4">
        <h2 className="text-base font-semibold">Cashflow letzte 12 Monate</h2>
        <div className="overflow-x-auto">
          <svg
            viewBox={`0 0 ${chart.width} ${chart.height}`}
            className="h-[220px] w-full min-w-[480px]"
            role="img"
            aria-label="Cashflow letzte 12 Monate"
          >
            <line x1="20" y1={chart.baseline} x2={chart.width - 12} y2={chart.baseline} className="stroke-border" />
            {points.map((point, index) => {
              const amount = Number(point.total_amount) || 0;
              const x = 30 + index * 38;
              const rawHeight = (amount / chart.maxValue) * CHART_BAR_MAX_HEIGHT;
              const barHeight = amount === 0 ? ZERO_AMOUNT_BAR_HEIGHT : Math.max(rawHeight, MIN_BAR_HEIGHT);
              const y = chart.baseline - barHeight;
              const old = index < points.length - 4;
              const fillClass = old ? "fill-primary/40" : "fill-primary";

              return (
                <g key={point.month}>
                  <rect
                    x={x}
                    y={y}
                    width={chart.barWidth}
                    height={barHeight}
                    rx="3"
                    className={amount === 0 ? "fill-transparent stroke-border" : fillClass}
                  >
                    <title>{`${monthLongLabel(point.month)}: ${formatCurrency(point.total_amount)}`}</title>
                  </rect>
                  <text
                    x={x + chart.barWidth / 2}
                    y={chart.baseline + 24}
                    transform={`rotate(45 ${x + chart.barWidth / 2} ${chart.baseline + 24})`}
                    className="fill-muted-foreground text-[10px]"
                  >
                    {monthShortLabel(point.month)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </CardContent>
    </Card>
  );
}
