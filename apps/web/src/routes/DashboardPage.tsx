type DashboardPageProps = {
  onLogout?: () => void | Promise<void>;
};

export default function DashboardPage({ onLogout }: DashboardPageProps) {
  return (
    <section className="panel" aria-labelledby="dashboard-title">
      <p className="eyebrow">Dashboard</p>
      <div className="panel-heading">
        <h1 id="dashboard-title">Portfolio overview placeholder</h1>
        {onLogout ? (
          <button className="secondary-button" type="button" onClick={() => void onLogout()}>
            Log out
          </button>
        ) : null}
      </div>
      <p>
        This page will present backend-provided portfolio summaries, risk signals, and
        chart-ready analysis in later issues.
      </p>
      <div className="placeholder-grid" aria-label="Planned dashboard sections">
        <div>
          <h2>Allocation</h2>
          <p>Charts are intentionally deferred until backend API integration is added.</p>
        </div>
        <div>
          <h2>Risk signals</h2>
          <p>Risk rules remain owned by the Finwall backend.</p>
        </div>
        <div>
          <h2>Recommendations</h2>
          <p>Decision-support output will be rendered from backend responses only.</p>
        </div>
      </div>
    </section>
  );
}
