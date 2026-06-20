import { useAnalysisCharts } from "../analysis/useAnalysisCharts";
import { useAuditPreview } from "../audit/useAuditPreview";
import { usePortfolio } from "../portfolio/usePortfolio";

export function useDashboardData() {
  const portfolioQuery = usePortfolio();
  const analysisChartsQuery = useAnalysisCharts();
  const auditPreviewQuery = useAuditPreview(5);

  return {
    portfolioQuery,
    analysisChartsQuery,
    auditPreviewQuery,
  };
}
