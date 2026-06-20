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
import { riskWarningSummary, type DisplayChartPoint } from "./chartDataAdapters";
import { formatChartNumber, formatStatus } from "./chartFormatting";

const SEVERITY_COLORS: Record<string, string> = {
  high: "#b04b3c",
  medium: "#b98620",
  low: "#2f6fba",
  other: "#6f7c8a",
};

type RiskWarningsChartProps = {
  series: ChartSeries;
};

export function RiskWarningsChart({ series }: RiskWarningsChartProps) {
  return (
    <ChartCard
      series={series}
      summary="Backend-provided count of risk warnings grouped by severity."
    >
      {(points) => {
        const chartData = points.map((point) => ({
          ...point,
          chartValue: point.value ?? 0,
          countLabel: formatChartNumber(point.value),
          severityLabel: formatStatus(point.label),
          summary: riskWarningSummary(point),
        }));

        return (
          <>
            <div className="chart-visual chart-visual-compact" aria-hidden="true">
              <ResponsiveContainer width="100%" height={Math.max(220, points.length * 52)}>
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ top: 8, right: 56, bottom: 8, left: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis allowDecimals={false} type="number" />
                  <YAxis dataKey="severityLabel" type="category" width={84} />
                  <Tooltip content={<RiskTooltip />} />
                  <Bar dataKey="chartValue" name="Warnings" radius={[0, 4, 4, 0]}>
                    {chartData.map((point) => (
                      <Cell
                        fill={SEVERITY_COLORS[point.key] ?? SEVERITY_COLORS.other}
                        key={point.key}
                      />
                    ))}
                    <LabelList dataKey="countLabel" position="right" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <RiskTable points={points} />
          </>
        );
      }}
    </ChartCard>
  );
}

function RiskTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) {
    return null;
  }
  const point = payload[0].payload as DisplayChartPoint & {
    countLabel: string;
    severityLabel: string;
    summary: string;
  };
  return (
    <div className="chart-tooltip">
      <strong>{point.severityLabel}</strong>
      <span>Count: {point.countLabel}</span>
      {point.summary ? <span>{point.summary}</span> : null}
    </div>
  );
}

function RiskTable({ points }: { points: DisplayChartPoint[] }) {
  return (
    <div className="table-wrap chart-table">
      <table aria-label="Risk warnings by severity fallback table">
        <thead>
          <tr>
            <th scope="col">Severity</th>
            <th scope="col">Count</th>
            <th scope="col">Warning summary</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => {
            const summary = riskWarningSummary(point);
            return (
              <tr key={point.key}>
                <td>{formatStatus(point.label)}</td>
                <td>{formatChartNumber(point.value)}</td>
                <td>{summary || "No warning details provided."}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type TooltipProps = {
  active?: boolean;
  payload?: Array<{ payload: unknown }>;
};
