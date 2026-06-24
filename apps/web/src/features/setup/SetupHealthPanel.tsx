import type { SetupHealth } from "../../api/types";
import { formatLabel } from "../dashboard/format";
import { useSetupHealth } from "./useSetupHealth";

type LiveDataStatusItem = NonNullable<SetupHealth["live_data"]["statuses"]>[number];

const HEALTH_DESCRIPTIONS: Record<string, string> = {
  ok: "Reachable",
  unavailable: "Unavailable",
  authenticated: "Authenticated",
  "not available": "Not available",
};

export function SetupHealthPanel() {
  const setupHealthQuery = useSetupHealth();
  const isRefreshing = setupHealthQuery.isFetching;

  if (setupHealthQuery.isPending) {
    return (
      <section
        className="dashboard-section setup-health-panel"
        aria-labelledby="setup-health-title"
      >
        <PanelHeading
          isRefreshing={isRefreshing}
          onRefresh={() => void setupHealthQuery.refetch()}
        />
        <div className="status-grid">
          <SetupHealthCard title="Backend" status="Loading" />
          <SetupHealthCard title="Session" status="Loading" />
          <SetupHealthCard title="Database" status="Loading" />
          <SetupHealthCard title="Live data" status="Loading" />
        </div>
      </section>
    );
  }

  if (setupHealthQuery.isError) {
    return (
      <section
        className="dashboard-section setup-health-panel error-state"
        aria-labelledby="setup-health-title"
      >
        <PanelHeading
          isRefreshing={isRefreshing}
          onRefresh={() => void setupHealthQuery.refetch()}
        />
        <p>
          Setup health could not load. The backend rejected the request or returned
          an unavailable response.
        </p>
      </section>
    );
  }

  const setupHealth = setupHealthQuery.data;
  const liveDataStatuses = setupHealth.live_data.statuses ?? [];
  const warnings = setupHealth.warnings ?? [];
  const diagnosticStatus = setupHealth.diagnostics.available
    ? "available"
    : "not available";

  return (
    <section
      className="dashboard-section setup-health-panel"
      aria-labelledby="setup-health-title"
    >
      <PanelHeading
        isRefreshing={isRefreshing}
        onRefresh={() => void setupHealthQuery.refetch()}
      />
      <div className="status-grid">
        <SetupHealthCard
          title="Backend"
          status={setupHealth.backend.status}
          detail={HEALTH_DESCRIPTIONS[setupHealth.backend.status] ?? "Unknown"}
        />
        <SetupHealthCard
          title="Session"
          status={setupHealth.session.authenticated ? "authenticated" : "unavailable"}
          detail={
            setupHealth.session.authenticated
              ? "Browser session accepted"
              : "Session not accepted"
          }
        />
        <SetupHealthCard
          title="Database"
          status={setupHealth.database.status}
          detail={`Store: ${formatLabel(setupHealth.database.store)}`}
        />
        <SetupHealthCard
          title="Diagnostics"
          status={diagnosticStatus}
          detail={setupHealth.diagnostics.summary}
        />
      </div>

      <div className="setup-health-detail-grid">
        <div>
          <h3>Live data</h3>
          {liveDataStatuses.length > 0 ? (
            <ul className="setup-live-summary">
              {liveDataStatuses.map((status) => (
                <LiveDataSummaryItem key={status.domain} status={status} />
              ))}
            </ul>
          ) : (
            <p className="muted">No live-data statuses were returned.</p>
          )}
        </div>

        <div>
          <h3>Diagnostics</h3>
          <p className="muted">{setupHealth.diagnostics.summary}</p>
          {setupHealth.diagnostics.next_step ? (
            <code className="command-hint">{setupHealth.diagnostics.next_step}</code>
          ) : null}
        </div>
      </div>

      {warnings.length > 0 ? (
        <div className="warning-banner" role="status">
          <strong>Setup warnings</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function PanelHeading({
  isRefreshing,
  onRefresh,
}: {
  isRefreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">Setup Health</p>
        <h2 id="setup-health-title">Environment readiness</h2>
      </div>
      <button
        className="retry-button"
        type="button"
        onClick={onRefresh}
        disabled={isRefreshing}
      >
        {isRefreshing ? "Refreshing..." : "Refresh"}
      </button>
    </div>
  );
}

function SetupHealthCard({
  title,
  status,
  detail,
}: {
  title: string;
  status: string;
  detail?: string;
}) {
  const badgeStatus = normalizeHealthStatus(status);

  return (
    <div className="status-card">
      <span>{title}</span>
      <strong>
        <span className={`status-badge status-${badgeStatus}`}>
          {formatLabel(status)}
        </span>
      </strong>
      {detail ? <p>{detail}</p> : null}
    </div>
  );
}

function LiveDataSummaryItem({ status }: { status: LiveDataStatusItem }) {
  const availability = normalizeAvailability(status.availability);

  return (
    <li>
      <span>{formatLabel(status.domain)}</span>
      <span className={`status-badge status-${availability}`}>
        {formatLabel(availability)}
      </span>
      <small>{formatLabel(status.provider)}</small>
    </li>
  );
}

function normalizeHealthStatus(status: string) {
  const normalized = status.trim().toLowerCase();
  if (
    normalized === "ok" ||
    normalized === "authenticated" ||
    normalized === "available"
  ) {
    return "live";
  }
  if (normalized === "unavailable" || normalized === "not available") {
    return "unavailable";
  }
  return "unknown";
}

function normalizeAvailability(availability: string | null | undefined) {
  const normalized = availability?.trim().toLowerCase();
  if (
    normalized === "live" ||
    normalized === "partial" ||
    normalized === "unavailable" ||
    normalized === "static" ||
    normalized === "manual" ||
    normalized === "unknown"
  ) {
    return normalized;
  }
  return "unknown";
}
