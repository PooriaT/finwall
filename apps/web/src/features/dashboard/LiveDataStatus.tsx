import type { AnalysisCharts } from "../../api/types";
import { formatDateTime, formatLabel } from "./format";
import {
  legacyPriceCompletenessStatus,
  normalizeAvailability,
  type LiveDataStatusItem,
} from "./liveDataStatusFallback";

type LiveDataStatusProps = {
  analysis: AnalysisCharts;
  isRetrying?: boolean;
  onRetry?: () => void;
};

const STATUS_DESCRIPTIONS: Record<string, string> = {
  live: "Live: data was returned for this dashboard surface.",
  partial: "Partial: some requested items were available and some are missing.",
  unavailable: "Unavailable: the provider could not return usable data.",
  static: "Static: configured source is static, test, or fixture data.",
  manual: "Manual: user-supplied values were used.",
  unknown: "Unknown: provider configured, but this surface has not been evaluated yet.",
};

const ACTIONABLE_STATUSES = new Set([
  "partial",
  "unavailable",
  "static",
  "manual",
  "unknown",
]);

export function LiveDataStatus({
  analysis,
  isRetrying = false,
  onRetry,
}: LiveDataStatusProps) {
  const statuses =
    analysis.live_data_status && analysis.live_data_status.length > 0
      ? analysis.live_data_status
      : [legacyPriceCompletenessStatus(analysis.price_completeness_status)];
  const seriesWarnings = Object.values(analysis.charts).flatMap(
    (series) => series.warnings ?? [],
  );
  const statusWarnings = statuses.flatMap((status) => status.warnings ?? []);
  const warnings = [
    ...analysis.data_warnings,
    ...seriesWarnings,
    ...statusWarnings,
  ].filter((warning, index, all) => warning && all.indexOf(warning) === index);
  const safeErrorMessages = statuses
    .flatMap((status) => status.safe_error_messages ?? [])
    .filter((message, index, all) => message && all.indexOf(message) === index);
  const hasActionableStatus = statuses.some((status) =>
    ACTIONABLE_STATUSES.has(normalizeAvailability(status.availability)),
  );
  const showRetry = Boolean(
    onRetry && (warnings.length > 0 || safeErrorMessages.length > 0 || hasActionableStatus),
  );

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
        {statuses.map((status) => <StatusCard key={status.domain} status={status} />)}
      </div>
      {warnings.length > 0 || safeErrorMessages.length > 0 ? (
        <div className="warning-banner" role="status">
          <strong>Data warnings</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
            {safeErrorMessages.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
          {showRetry ? (
            <button
              className="retry-button"
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
            >
              {isRetrying ? "Refreshing..." : "Retry status check"}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="status-footer">
          <p className="muted">No data warnings returned by the backend.</p>
          {showRetry ? (
            <button
              className="retry-button"
              type="button"
              onClick={onRetry}
              disabled={isRetrying}
            >
              {isRetrying ? "Refreshing..." : "Retry status check"}
            </button>
          ) : null}
        </div>
      )}
    </section>
  );
}

function StatusCard({ status }: { status: LiveDataStatusItem }) {
  const availability = normalizeAvailability(status.availability);

  return (
    <div className="status-card">
      <span>{formatLabel(status.domain)}</span>
      <strong>
        <span className={`status-badge status-${availability}`}>
          {formatLabel(availability)}
        </span>
      </strong>
      <p>{STATUS_DESCRIPTIONS[availability] ?? STATUS_DESCRIPTIONS.unknown}</p>
      <dl className="status-details">
        <div>
          <dt>Provider</dt>
          <dd>{configuredValue(status.provider)}</dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{configuredValue(status.source)}</dd>
        </div>
        <div>
          <dt>Fallback</dt>
          <dd>
            {status.fallback_used
              ? `Fallback provider: ${configuredValue(status.fallback_provider)}`
              : "Not used"}
          </dd>
        </div>
        <div>
          <dt>Last attempted</dt>
          <dd>
            {status.last_attempted_at
              ? formatDateTime(status.last_attempted_at)
              : "Not attempted"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function configuredValue(value: string | null | undefined) {
  return value?.trim() || "Not configured";
}
