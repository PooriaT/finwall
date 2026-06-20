import type { AnalysisCharts } from "../../api/types";
import { AllocationBarChart } from "./AllocationBarChart";
import { CashVsInvestedChart } from "./CashVsInvestedChart";
import { RiskWarningsChart } from "./RiskWarningsChart";
import { UnrealizedGainLossChart } from "./UnrealizedGainLossChart";

type DashboardChartsProps = {
  analysis: AnalysisCharts;
};

export function DashboardCharts({ analysis }: DashboardChartsProps) {
  const charts = analysis.charts;

  return (
    <div className="chart-grid" aria-label="Portfolio charts">
      <AllocationBarChart series={charts.allocation_by_holding} />
      <CashVsInvestedChart
        series={charts.cash_vs_invested}
        valuationStatus={analysis.valuation_status}
        priceCompletenessStatus={analysis.price_completeness_status}
      />
      <UnrealizedGainLossChart series={charts.unrealized_gain_loss_by_holding} />
      <RiskWarningsChart series={charts.risk_warnings_by_severity} />
    </div>
  );
}
