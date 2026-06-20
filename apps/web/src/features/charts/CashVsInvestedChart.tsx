import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { ChartSeries } from "../../api/types";
import { ChartCard } from "./ChartCard";
import {
  displayPercent,
  displayValue,
  type DisplayChartPoint,
} from "./chartDataAdapters";
import { formatStatus } from "./chartFormatting";

const CASH_COLORS: Record<string, string> = {
  cash: "#2f6fba",
  invested: "#2e7d68",
};

type CashVsInvestedChartProps = {
  series: ChartSeries;
  valuationStatus: string;
  priceCompletenessStatus: string;
};

export function CashVsInvestedChart({
  series,
  valuationStatus,
  priceCompletenessStatus,
}: CashVsInvestedChartProps) {
  const extraWarnings = [];
  if (valuationStatus !== "available") {
    extraWarnings.push(`Valuation status: ${formatStatus(valuationStatus)}.`);
  }
  if (priceCompletenessStatus !== "complete") {
    extraWarnings.push(
      `Price completeness status: ${formatStatus(priceCompletenessStatus)}.`,
    );
  }

  return (
    <ChartCard
      series={series}
      summary="Backend-provided cash and invested values for the portfolio."
      extraWarnings={extraWarnings}
    >
      {(points) => {
        const chartData = points
          .filter((point) => point.value !== null)
          .map((point) => ({
            ...point,
            chartValue: point.value,
            percentLabel: displayPercent(point),
            valueLabel: displayValue(point),
          }));

        return (
          <>
            {chartData.length > 0 ? (
              <div className="chart-visual chart-visual-compact" aria-hidden="true">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Tooltip content={<CashTooltip />} />
                    <Pie
                      data={chartData}
                      dataKey="chartValue"
                      nameKey="label"
                      innerRadius={64}
                      outerRadius={96}
                      paddingAngle={2}
                      label={(entry: unknown) => {
                        const point = entry as {
                          label?: string;
                          name?: string;
                          percentLabel?: string;
                        };
                        return `${point.label ?? point.name ?? "Value"}: ${
                          point.percentLabel ?? "Unavailable"
                        }`;
                      }}
                      labelLine={false}
                      isAnimationActive={false}
                    >
                      {chartData.map((point) => (
                        <Cell
                          fill={CASH_COLORS[point.key] ?? "#6f7c8a"}
                          key={point.key}
                        />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="table-empty">No numeric values available for chart drawing.</p>
            )}
            <CashTable points={points} />
          </>
        );
      }}
    </ChartCard>
  );
}

function CashTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) {
    return null;
  }
  const point = payload[0].payload as DisplayChartPoint & {
    percentLabel: string;
    valueLabel: string;
  };
  return (
    <div className="chart-tooltip">
      <strong>{point.label}</strong>
      <span>Value: {point.valueLabel}</span>
      <span>Allocation: {point.percentLabel}</span>
      <span>Status: {point.statusLabel}</span>
    </div>
  );
}

function CashTable({ points }: { points: DisplayChartPoint[] }) {
  return (
    <div className="table-wrap chart-table">
      <table aria-label="Cash vs invested fallback table">
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">Value</th>
            <th scope="col">Allocation</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.key}>
              <td>{point.label}</td>
              <td>{displayValue(point)}</td>
              <td>{displayPercent(point)}</td>
              <td>{point.unavailableReason ?? point.statusLabel}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type TooltipProps = {
  active?: boolean;
  payload?: Array<{ payload: unknown }>;
};
