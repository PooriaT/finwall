import type { PortfolioAudit } from "../../api/types";
import { formatDateTime, formatLabel, formatText } from "./format";

type AuditPreviewProps = {
  audit: PortfolioAudit;
};

export function AuditPreview({ audit }: AuditPreviewProps) {
  return (
    <section className="dashboard-section" aria-labelledby="audit-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Latest Audit</p>
          <h2 id="audit-title">Recent portfolio changes</h2>
        </div>
      </div>
      {audit.events.length === 0 ? (
        <p className="table-empty">No audit events available.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Changed time</th>
                <th scope="col">Action</th>
                <th scope="col">Entity type</th>
                <th scope="col">Entity ID</th>
                <th scope="col">Status</th>
                <th scope="col">Summary</th>
              </tr>
            </thead>
            <tbody>
              {audit.events.map((event) => (
                <tr key={event.id}>
                  <th scope="row">{formatDateTime(event.changed_at)}</th>
                  <td>{formatLabel(event.action)}</td>
                  <td>{formatLabel(event.entity_type)}</td>
                  <td>{formatText(event.entity_id)}</td>
                  <td>
                    <span className={`badge badge-${event.status}`}>
                      {formatLabel(event.status)}
                    </span>
                  </td>
                  <td>{event.safe_error_message ?? event.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
