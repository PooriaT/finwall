import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSession, logout as logoutRequest } from "../api/client";
import { queryKeys } from "../api/queryClient";

export function useSession() {
  const queryClient = useQueryClient();
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const sessionQuery = useQuery({
    queryKey: queryKeys.session,
    queryFn: getSession,
  });
  const { refetch } = sessionQuery;

  const refresh = useCallback(async () => {
    setLogoutError(null);
    await refetch();
  }, [refetch]);

  const logout = useCallback(async () => {
    setLogoutError(null);
    try {
      const session = await logoutRequest();
      queryClient.setQueryData(queryKeys.session, session);
      queryClient.removeQueries({ queryKey: queryKeys.portfolio });
      queryClient.removeQueries({ queryKey: ["analysis"] });
      queryClient.removeQueries({ queryKey: ["audit"] });
      return true;
    } catch {
      setLogoutError("Logout failed. Try again.");
      return false;
    }
  }, [queryClient]);

  return {
    authenticated: sessionQuery.isSuccess
      ? sessionQuery.data.authenticated
      : false,
    loading: sessionQuery.isPending,
    error: logoutError,
    refresh,
    logout,
  };
}
