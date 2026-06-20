import { useQuery } from "@tanstack/react-query";
import { getPortfolio } from "../../api/client";
import { queryKeys } from "../../api/queryClient";

export function usePortfolio() {
  return useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: getPortfolio,
  });
}
