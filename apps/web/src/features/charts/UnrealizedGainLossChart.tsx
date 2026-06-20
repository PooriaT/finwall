import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSeries } from "../../api/types";
import { ChartCard } from "./ChartCard";
import { displayPercent, displayValue, type DisplayChartPoint } from "./chartDataAdapters";

type UnrealizedGainLossChartProps = {
  series: ChartSeries;
};

export function UnrealizedGainLossChart({ series }: UnrealizedGainLossChartProps) {
  return (
    <ChartCard
      series={series}
      summary="Backend-provided unrealized gain or loss values by holding."
    >
      {(points) => {
        const chartData = points.map((point) => ({
          ...point,
          chartValue: point.value ?? 0,
          percentLabel: displayPercent(point),
          valueLabel: displayValue(point),
        }));

        return (
          <>
            <div className="chart-visual" aria-hidden="true">
              <ResponsiveContainer width="100%" height={Math.max(240, points.length * 48)}>
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ top: 8, right: 84, bottom: 8, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" />
                  <YAxis dataKey="label" type="category" width={72} />
                  <Tooltip content={<GainLossTooltip />} />
                  <ReferenceLine x={0} stroke="#526171" />
                  <Bar dataKey="chartValue" name="Unrealized gain/loss" radius={4}>
                    {chartData.map((point) => (
                      <Cell fill={barColor(point)} key={point.key} />
                    ))}
                    <LabelList dataKey="valueLabel" position="right" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <GainLossTable points={points} />
          </>
        );
      }}
    </ChartCard>
  );
}

function barColor(point: DisplayChartPoint): string {
  if (point.unavailableReason) {
    return "#8c98a3";
  }
  if ((point.value ?? 0) < 0) {
    return "#b04b3c";
  }
  return "#2e7d68";
}

function GainLossTooltip({ active, payload }: TooltipProps) {
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
      <span>Return: {point.percentLabel}</span>
      <span>Status: {point.unavailableReason ?? point.statusLabel}</span>
    </div>
  );
}

function GainLossTable({ points }: { points: DisplayChartPoint[] }) {
  return (
    <div className="table-wrap chart-table">
      <table aria-label="Unrealized gain/loss fallback table">
        <thead>
          <tr>
            <th scope="col">Holding</th>
            <th scope="col">Unrealized gain/loss</th>
            <th scope="col">Return</th>
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
