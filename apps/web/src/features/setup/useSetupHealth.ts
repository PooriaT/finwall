import { useQuery } from "@tanstack/react-query";
import { getSetupHealth } from "../../api/client";
import { queryKeys } from "../../api/queryClient";

export function useSetupHealth() {
  return useQuery({
    queryKey: queryKeys.setupHealth,
    queryFn: getSetupHealth,
  });
}
