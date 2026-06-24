import { QueryClient } from "@tanstack/react-query";

export const queryKeys = {
  session: ["session"] as const,
  setupHealth: ["setup", "health"] as const,
  portfolio: ["portfolio"] as const,
  analysisCharts: ["analysis", "charts"] as const,
  auditPreview: (limit: number) => ["audit", { limit }] as const,
};

export function createFinwallQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });
}

export const queryClient = createFinwallQueryClient();
