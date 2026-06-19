import { afterEach, describe, expect, it, vi } from "vitest";
import { getAnalysisCharts, getPortfolio, getPortfolioAudit } from "./client";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
      ...init.headers,
    },
    ...init,
  });
}

describe("API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches portfolio data with cookie credentials and no API token header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ name: "Primary" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getPortfolio()).resolves.toEqual({ name: "Primary" });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/portfolio", {
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
  });

  it("passes typed query params for charts and audit requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ charts: {} }))
      .mockResolvedValueOnce(jsonResponse({ events: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await getAnalysisCharts({ report_history_limit: 5 });
    await getPortfolioAudit({ limit: 25 });

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/portfolio/analysis/charts?report_history_limit=5",
    );
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/portfolio/audit?limit=25");
  });
});
