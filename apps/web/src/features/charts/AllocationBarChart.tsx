import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSeries } from "../../api/types";
import { ChartCard } from "./ChartCard";
import { displayPercent, displayValue, type DisplayChartPoint } from "./chartDataAdapters";

type AllocationBarChartProps = {
  series: ChartSeries;
};

export function AllocationBarChart({ series }: AllocationBarChartProps) {
  return (
    <ChartCard
      series={series}
      summary="Backend-provided allocation percentages and values for each holding."
    >
      {(points) => {
        const chartData = points.map((point) => ({
          ...point,
          chartValue: point.percent ?? 0,
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
                  margin={{ top: 8, right: 72, bottom: 8, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis
                    type="number"
                    tickFormatter={(value: number) => `${value}%`}
                  />
                  <YAxis dataKey="label" type="category" width={72} />
                  <Tooltip content={<AllocationTooltip />} />
                  <Bar dataKey="chartValue" name="Allocation" radius={[0, 4, 4, 0]}>
                    {chartData.map((point) => (
                      <Cell
                        fill={point.unavailableReason ? "#8c98a3" : "#2e7d68"}
                        key={point.key}
                      />
                    ))}
                    <LabelList dataKey="percentLabel" position="right" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <AllocationTable points={points} />
          </>
        );
      }}
    </ChartCard>
  );
}

function AllocationTooltip({ active, payload }: TooltipProps) {
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
      <span>Allocation: {point.percentLabel}</span>
      <span>Value: {point.valueLabel}</span>
      <span>Status: {point.unavailableReason ?? point.statusLabel}</span>
    </div>
  );
}

function AllocationTable({ points }: { points: DisplayChartPoint[] }) {
  return (
    <div className="table-wrap chart-table">
      <table aria-label="Allocation by holding fallback table">
        <thead>
          <tr>
            <th scope="col">Holding</th>
            <th scope="col">Allocation</th>
            <th scope="col">Value</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.key}>
              <td>{point.label}</td>
              <td>{displayPercent(point)}</td>
              <td>{displayValue(point)}</td>
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
