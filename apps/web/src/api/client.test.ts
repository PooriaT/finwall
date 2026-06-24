import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getAnalysisCharts,
  getPortfolio,
  getPortfolioAudit,
  getSetupHealth,
  getSession,
  login,
  logout,
} from "./client";

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

  it("fetches setup health with cookie credentials and no API token header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ backend: { status: "ok" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSetupHealth()).resolves.toEqual({ backend: { status: "ok" } });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/setup/health", {
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
  });

  it("logs in with a JSON body and cookie credentials", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ authenticated: true }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(login("secret")).resolves.toEqual({ authenticated: true });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/login", {
      credentials: "include",
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ token: "secret" }),
    });
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
  });

  it("checks and clears session state with cookie credentials", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSession()).resolves.toEqual({ authenticated: true });
    await expect(logout()).resolves.toEqual({ authenticated: false });

    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/v1/auth/session",
      {
        credentials: "include",
        headers: {
          Accept: "application/json",
        },
      },
    ]);
    expect(fetchMock.mock.calls[1]).toEqual([
      "/api/v1/auth/logout",
      {
        credentials: "include",
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      },
    ]);
  });
});
