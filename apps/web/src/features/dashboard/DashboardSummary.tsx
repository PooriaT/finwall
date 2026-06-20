import type { AnalysisCharts, Portfolio } from "../../api/types";
import { formatDate, formatLabel, formatNumber, formatText } from "./format";

type DashboardSummaryProps = {
  portfolio: Portfolio;
  analysis?: AnalysisCharts;
};

export function DashboardSummary({ portfolio, analysis }: DashboardSummaryProps) {
  const goals = portfolio.goals ?? [];
  const primaryGoal = goals[0];
  const timeline = primaryGoal?.timeline;

  const summaryItems = [
    { label: "Holdings", value: formatNumber((portfolio.holdings ?? []).length) },
    {
      label: "Cash balances",
      value: formatNumber((portfolio.cash_balances ?? []).length),
    },
    {
      label: "Active orders",
      value: formatNumber((portfolio.active_orders ?? []).length),
    },
    {
      label: "Watchlist items",
      value: formatNumber((portfolio.watchlist ?? []).length),
    },
  ];

  return (
    <section className="dashboard-section" aria-labelledby="summary-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Portfolio Summary</p>
          <h2 id="summary-title">{portfolio.name}</h2>
        </div>
      </div>
      <div className="summary-grid">
        {summaryItems.map((item) => (
          <div className="metric-card" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
      <div className="detail-grid">
        <div>
          <span>Risk profile</span>
          <strong>{formatLabel(portfolio.risk_profile?.level)}</strong>
          {portfolio.risk_profile?.notes ? <p>{portfolio.risk_profile.notes}</p> : null}
        </div>
        <div>
          <span>Goal</span>
          <strong>{formatText(primaryGoal?.name)}</strong>
          {primaryGoal?.target_amount ? (
            <p>Target amount: {formatNumber(primaryGoal.target_amount)}</p>
          ) : null}
        </div>
        <div>
          <span>Timeline</span>
          <strong>{formatDate(timeline?.start_date)}</strong>
          {timeline?.target_date ? (
            <p>Target date: {formatDate(timeline.target_date)}</p>
          ) : null}
        </div>
        <div>
          <span>Analysis portfolio</span>
          <strong>{formatText(analysis?.portfolio_name)}</strong>
        </div>
      </div>
    </section>
  );
}
