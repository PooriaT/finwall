import type { AnalysisCharts } from "../../api/types";
import { formatLabel } from "./format";

type LiveDataStatusProps = {
  analysis: AnalysisCharts;
};

export function LiveDataStatus({ analysis }: LiveDataStatusProps) {
  const seriesWarnings = Object.values(analysis.charts).flatMap(
    (series) => series.warnings ?? [],
  );
  const warnings = [...analysis.data_warnings, ...seriesWarnings];

  return (
    <section className="dashboard-section" aria-labelledby="live-data-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Live Data Status</p>
          <h2 id="live-data-title">Market data readiness</h2>
        </div>
      </div>
      <p className="muted">
        Default live provider status is reported by backend chart data; unavailable or
        partial values can reflect provider availability, missing prices, or manual/static
        override mode.
      </p>
      <div className="status-grid">
        <div>
          <span>Valuation status</span>
          <strong>{formatLabel(analysis.valuation_status)}</strong>
        </div>
        <div>
          <span>Price completeness</span>
          <strong>{formatLabel(analysis.price_completeness_status)}</strong>
        </div>
      </div>
      {warnings.length > 0 ? (
        <div className="warning-banner" role="status">
          <strong>Data warnings</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="muted">No data warnings returned by the backend.</p>
      )}
    </section>
  );
}
