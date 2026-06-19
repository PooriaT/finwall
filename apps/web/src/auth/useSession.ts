import { useCallback, useEffect, useState } from "react";
import { getSession, logout as logoutRequest } from "../api/client";

type SessionState = {
  authenticated: boolean;
  loading: boolean;
  error: string | null;
};

export function useSession() {
  const [state, setState] = useState<SessionState>({
    authenticated: false,
    loading: true,
    error: null,
  });

  const refresh = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const session = await getSession();
      setState({
        authenticated: session.authenticated,
        loading: false,
        error: null,
      });
    } catch {
      setState({
        authenticated: false,
        loading: false,
        error: null,
      });
    }
  }, []);

  const logout = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      await logoutRequest();
      setState({
        authenticated: false,
        loading: false,
        error: null,
      });
    } catch {
      setState({
        authenticated: false,
        loading: false,
        error: "Logout failed. Try again.",
      });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    ...state,
    refresh,
    logout,
  };
}
