import type { AnalysisCharts } from "../../api/types";
import { ActionableEmptyState } from "./ActionableEmptyState";
import { formatDateTime, formatLabel, formatText } from "./format";

type LatestReportCardProps = {
  analysis: AnalysisCharts;
};

function metadataValue(
  metadata: Record<string, unknown>,
  key: string,
): string | null {
  const value = metadata[key];
  return typeof value === "string" ? value : null;
}

export function LatestReportCard({ analysis }: LatestReportCardProps) {
  const latestReport = analysis.charts.report_history_summary.points[0];
  const metadata = latestReport?.metadata ?? {};

  return (
    <section className="dashboard-section" aria-labelledby="latest-report-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Latest Report</p>
          <h2 id="latest-report-title">Report metadata</h2>
        </div>
      </div>
      {!latestReport ? (
        <ActionableEmptyState
          title="No saved report history yet"
          message="Saved report metadata will appear here after a report run is persisted."
          nextStep="Run a report with --save-run to populate this section."
          commandHint="poetry run finwall --database finwall.db report --save-run"
        />
      ) : (
        <dl className="report-list">
          <div>
            <dt>Created</dt>
            <dd>{formatDateTime(metadataValue(metadata, "created_at") ?? latestReport.label)}</dd>
          </div>
          <div>
            <dt>Command context</dt>
            <dd>{formatText(metadataValue(metadata, "command_context"))}</dd>
          </div>
          <div>
            <dt>Valuation status</dt>
            <dd>{formatLabel(metadataValue(metadata, "valuation_status"))}</dd>
          </div>
          <div>
            <dt>Price completeness</dt>
            <dd>{formatLabel(metadataValue(metadata, "price_completeness_status"))}</dd>
          </div>
          <div>
            <dt>Recommendation summary</dt>
            <dd>{formatText(metadataValue(metadata, "recommendation_summary"))}</dd>
          </div>
          <div>
            <dt>Report summary</dt>
            <dd>{formatText(metadataValue(metadata, "report_summary"))}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}
