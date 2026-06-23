import type { AnalysisCharts } from "../../api/types";
import { formatLabel } from "./format";

type LiveDataStatusProps = {
  analysis: AnalysisCharts;
};

export function LiveDataStatus({ analysis }: LiveDataStatusProps) {
  const statuses = analysis.live_data_status ?? [];
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
        Default live provider status is reported by backend chart data. The shared
        live-data contract describes whether dashboard inputs are live, partial,
        unavailable, static, manual, or unknown; it is not a guarantee of real-time
        or broker-grade data.
      </p>
      <div className="status-grid">
        {statuses.length > 0 ? (
          statuses.map((status) => (
            <div key={status.domain}>
              <span>{formatLabel(status.domain)}</span>
              <strong>{formatLabel(status.availability)}</strong>
              <small>
                {status.provider} · {status.source}
                {status.fallback_used && status.fallback_provider
                  ? ` · fallback ${status.fallback_provider}`
                  : ""}
              </small>
            </div>
          ))
        ) : (
          <div>
            <span>Market prices</span>
            <strong>{formatLabel(analysis.price_completeness_status)}</strong>
            <small>Legacy chart metadata</small>
          </div>
        )}
      </div>
      {warnings.length > 0 || statuses.some((status) => (status.safe_error_messages ?? []).length) ? (
        <div className="warning-banner" role="status">
          <strong>Data warnings</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
            {statuses.flatMap((status) => status.safe_error_messages ?? []).map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="muted">No data warnings returned by the backend.</p>
      )}
    </section>
  );
}
