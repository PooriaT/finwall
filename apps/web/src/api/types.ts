import type { components, operations } from "./generated/schema";

type JsonResponse<Operation> = Operation extends {
  responses: {
    200: {
      content: {
        "application/json": infer Body;
      };
    };
  };
}
  ? Body
  : never;

type QueryParams<Operation> = Operation extends {
  parameters: {
    query?: infer Query;
  };
}
  ? Query
  : never;

export type Portfolio = JsonResponse<
  operations["read_portfolio_api_v1_portfolio_get"]
>;

export type AnalysisCharts = JsonResponse<
  operations["portfolio_analysis_charts_api_v1_portfolio_analysis_charts_get"]
>;

export type PortfolioAudit = JsonResponse<
  operations["read_portfolio_audit_api_v1_portfolio_audit_get"]
>;

export type SetupHealth = JsonResponse<
  operations["setup_health_api_v1_setup_health_get"]
>;

export type AnalysisChartsQuery = QueryParams<
  operations["portfolio_analysis_charts_api_v1_portfolio_analysis_charts_get"]
>;

export type PortfolioAuditQuery = QueryParams<
  operations["read_portfolio_audit_api_v1_portfolio_audit_get"]
>;

export type AuthSession = JsonResponse<
  operations["auth_session_api_v1_auth_session_get"]
>;

export type ChartSeries = components["schemas"]["ChartSeriesResponse"];
export type ChartPoint = components["schemas"]["ChartPointResponse"];
