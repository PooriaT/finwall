import type { ReactNode } from "react";
import type { ChartSeries } from "../../api/types";
import {
  adaptChartSeries,
  hasUnavailablePoints,
  seriesWarnings,
  type DisplayChartPoint,
} from "./chartDataAdapters";

type ChartCardProps = {
  series: ChartSeries;
  summary: string;
  children: (points: DisplayChartPoint[]) => ReactNode;
  extraWarnings?: string[];
};

export function ChartCard({
  series,
  summary,
  children,
  extraWarnings = [],
}: ChartCardProps) {
  const points = adaptChartSeries(series);
  const warnings = [...seriesWarnings(series), ...extraWarnings].filter(
    (warning, index, all) => warning && all.indexOf(warning) === index,
  );
  const hasPartialData = hasUnavailablePoints(points);

  return (
    <section className="dashboard-section chart-card" aria-labelledby={`${series.key}-title`}>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Chart</p>
          <h2 id={`${series.key}-title`}>{series.title}</h2>
          <p className="chart-summary">{summary}</p>
        </div>
      </div>

      {warnings.length > 0 || hasPartialData ? (
        <div className="warning-banner chart-warning" role="status">
          <strong>Partial data visible</strong>
          <ul>
            {hasPartialData ? (
              <li>One or more chart points are unavailable and remain listed below.</li>
            ) : null}
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {points.length === 0 ? (
        <p className="table-empty">No chart data available.</p>
      ) : (
        children(points)
      )}
    </section>
  );
}
