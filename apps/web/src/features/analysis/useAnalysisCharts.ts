import { useQuery } from "@tanstack/react-query";
import { getAnalysisCharts } from "../../api/client";
import { queryKeys } from "../../api/queryClient";

export function useAnalysisCharts() {
  return useQuery({
    queryKey: queryKeys.analysisCharts,
    queryFn: () => getAnalysisCharts({ report_history_limit: 5 }),
  });
}
