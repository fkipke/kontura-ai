"use client";

import { useId, useMemo } from "react";

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

// Chart-Geometrie (viewBox-Koordinaten)
const VIEW_W = 600;
const VIEW_H = 220;
const PAD_L = 16;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 36;
const PLOT_W = VIEW_W - PAD_L - PAD_R;
const PLOT_H = VIEW_H - PAD_T - PAD_B;

export function CashflowChart(): React.JSX.Element {
  const { data, isLoading, isError } = useDashboardCashflow(12);
  const gradientId = useId();

  const chart = useMemo(() => {
    if (!data || data.points.length === 0) return null;

    const amounts = data.points.map((p) => Number(p.total_amount) || 0);
    const maxAmount = Math.max(...amounts, 1);
    const total = amounts.reduce((acc, n) => acc + n, 0);

    const stepX = data.points.length > 1 ? PLOT_W / (data.points.length - 1) : 0;
    const baseY = PAD_T + PLOT_H;

    const coords = data.points.map((p, i) => {
      const amount = Number(p.total_amount) || 0;
      const x = PAD_L + i * stepX;
      const y = baseY - (amount / maxAmount) * PLOT_H;
      return { x, y, amount, month: p.month };
    });

    const linePath = coords
      .map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(2)} ${c.y.toFixed(2)}`)
      .join(" ");

    const first = coords[0];
    const last = coords[coords.length - 1];
    const areaPath = `${linePath} L ${last.x.toFixed(2)} ${baseY} L ${first.x.toFixed(2)} ${baseY} Z`;

    // Y-Gridlines (3 horizontale Hilfslinien bei 25/50/75%)
    const gridLines = [0.25, 0.5, 0.75].map((frac) => baseY - frac * PLOT_H);

    return { coords, linePath, areaPath, gridLines, baseY, total, maxAmount };
  }, [data]);

  return (
    <Card>
      <CardContent className="space-y-4 p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-base font-semibold">Cashflow letzte 12 Monate</h2>
            <p className="text-xs text-muted-foreground">
              Summe Rechnungsbeträge pro Monat
            </p>
          </div>
          {chart ? (
            <div className="text-right">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Gesamt
              </p>
              <p className="text-lg font-semibold font-tnum">
                {formatCurrency(chart.total)}
              </p>
            </div>
          ) : null}
        </div>

        {isLoading ? (
          <Skeleton className="h-[220px] w-full" />
        ) : isError || !chart ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            Keine Cashflow-Daten verfügbar.
          </p>
        ) : (
          <div className="-mx-2 overflow-x-auto">
            <svg
              viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
              preserveAspectRatio="none"
              className="block h-[220px] w-full min-w-[480px]"
              role="img"
              aria-label="Cashflow-Verlauf der letzten 12 Monate"
            >
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" className="[stop-color:var(--color-primary,#6366f1)]" stopOpacity="0.35" />
                  <stop offset="100%" className="[stop-color:var(--color-primary,#6366f1)]" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Gridlines */}
              {chart.gridLines.map((y, i) => (
                <line
                  key={i}
                  x1={PAD_L}
                  y1={y}
                  x2={PAD_L + PLOT_W}
                  y2={y}
                  className="stroke-border"
                  strokeWidth="1"
                  strokeDasharray="2 4"
                />
              ))}

              {/* Baseline */}
              <line
                x1={PAD_L}
                y1={chart.baseY}
                x2={PAD_L + PLOT_W}
                y2={chart.baseY}
                className="stroke-border"
                strokeWidth="1"
              />

              {/* Area-Fill */}
              <path d={chart.areaPath} fill={`url(#${gradientId})`} />

              {/* Linie */}
              <path
                d={chart.linePath}
                fill="none"
                className="stroke-primary"
                strokeWidth="2.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />

              {/* Datenpunkte */}
              {chart.coords.map((c, i) => {
                const isCurrent = i === chart.coords.length - 1;
                return (
                  <g key={c.month}>
                    {isCurrent ? (
                      <circle
                        cx={c.x}
                        cy={c.y}
                        r="8"
                        className="fill-primary/20"
                      >
                        <animate
                          attributeName="r"
                          values="6;10;6"
                          dur="2s"
                          repeatCount="indefinite"
                        />
                      </circle>
                    ) : null}
                    <circle
                      cx={c.x}
                      cy={c.y}
                      r={isCurrent ? 4 : 3}
                      className={isCurrent ? "fill-primary" : "fill-background stroke-primary"}
                      strokeWidth="2"
                    >
                      <title>{`${shortMonthLabel(c.month)}: ${formatCurrency(c.amount)}`}</title>
                    </circle>
                    <text
                      x={c.x}
                      y={chart.baseY + 18}
                      textAnchor="middle"
                      className="fill-muted-foreground text-[10px]"
                    >
                      {shortMonthLabel(c.month)}
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
