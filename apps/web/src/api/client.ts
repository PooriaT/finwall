import type {
  AnalysisCharts,
  AnalysisChartsQuery,
  Portfolio,
  PortfolioAudit,
  PortfolioAuditQuery,
} from "./types";

const DEFAULT_API_BASE_URL = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

type QueryValue = string | number | boolean | null | undefined;

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_FINWALL_API_BASE_URL;
  return configured?.trim() || DEFAULT_API_BASE_URL;
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const baseUrl = apiBaseUrl().replace(/\/$/, "");
  const url = new URL(`${baseUrl}${path}`, window.location.origin);

  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined) {
      url.searchParams.set(key, String(value));
    }
  }

  if (url.origin === window.location.origin) {
    return `${url.pathname}${url.search}${url.hash}`;
  }
  return url.toString();
}

async function parseJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

async function requestJson<T>(
  path: string,
  query?: Record<string, QueryValue>,
): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });
  const body = await parseJson(response);

  if (!response.ok) {
    throw new ApiError(response.statusText || "API request failed", response.status, body);
  }

  return body as T;
}

export function getPortfolio(): Promise<Portfolio> {
  return requestJson<Portfolio>("/v1/portfolio");
}

export function getAnalysisCharts(
  query: AnalysisChartsQuery = {},
): Promise<AnalysisCharts> {
  return requestJson<AnalysisCharts>("/v1/portfolio/analysis/charts", query);
}

export function getPortfolioAudit(
  query: PortfolioAuditQuery = {},
): Promise<PortfolioAudit> {
  return requestJson<PortfolioAudit>("/v1/portfolio/audit", query);
}
