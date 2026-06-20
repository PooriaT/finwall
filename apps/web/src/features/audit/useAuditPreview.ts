import { useQuery } from "@tanstack/react-query";
import { getPortfolioAudit } from "../../api/client";
import { queryKeys } from "../../api/queryClient";

export function useAuditPreview(limit = 5) {
  return useQuery({
    queryKey: queryKeys.auditPreview(limit),
    queryFn: () => getPortfolioAudit({ limit }),
  });
}
