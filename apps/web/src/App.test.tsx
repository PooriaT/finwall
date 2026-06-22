import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { queryClient, queryKeys } from "./api/queryClient";
import App from "./App";

function renderAt(pathname: string) {
  window.history.pushState({}, "", pathname);
  return render(<App />);
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
      ...init.headers,
    },
    ...init,
  });
}

const emptyPortfolio = {
  name: "Primary",
  cash_balances: [],
  holdings: [],
  active_orders: [],
  watchlist: [],
  goals: [],
  risk_profile: null,
};

const populatedPortfolio = {
  name: "Primary",
  cash_balances: [{ currency: "USD", amount: 1250.5 }],
  holdings: [
    {
      ticker: "AAPL",
      share_count: 10,
      average_purchase_price: 150,
      sector: "Technology",
    },
  ],
  active_orders: [
    {
      ticker: "MSFT",
      side: "buy",
      order_type: "limit",
      share_count: 3,
      limit_price: 310,
      stop_price: null,
    },
  ],
  watchlist: [{ ticker: "NVDA", note: "Wait for earnings" }],
  goals: [
    {
      name: "Retirement",
      target_amount: 100000,
      timeline: {
        start_date: "2026-01-01",
        target_date: "2036-01-01",
      },
    },
  ],
  risk_profile: {
    level: "moderate",
    notes: "Balanced exposure",
  },
};

function chartPoint(
  key: string,
  label: string,
  value: string | null,
  percent: string | null = null,
  status = "available",
  metadata: Record<string, unknown> = {},
) {
  return {
    key,
    label,
    value,
    percent,
    status,
    metadata,
  };
}

function chartSeries(
  key = "series",
  title = "Series",
  points: unknown[] = [],
  warnings: string[] = [],
) {
  return {
    key,
    title,
    points,
    warnings,
  };
}

const analysisCharts = {
  portfolio_name: "Primary",
  valuation_status: "complete",
  price_completeness_status: "complete",
  data_warnings: [],
  charts: {
    allocation_by_holding: chartSeries("allocation_by_holding", "Allocation by holding", [
      chartPoint("AAPL", "AAPL", "1750.00", "58.33"),
      chartPoint("MSFT", "MSFT", "1250.00", "41.67"),
    ]),
    allocation_by_sector: chartSeries("allocation_by_sector", "Allocation by sector"),
    cash_vs_invested: chartSeries("cash_vs_invested", "Cash vs invested", [
      chartPoint("cash", "Cash", "1250.50", "29.42"),
      chartPoint("invested", "Invested", "3000.00", "70.58"),
    ]),
    unrealized_gain_loss_by_holding: chartSeries(
      "unrealized_gain_loss_by_holding",
      "Unrealized gain/loss by holding",
      [
        chartPoint("AAPL", "AAPL", "250.00", "16.67"),
        chartPoint("MSFT", "MSFT", "-125.50", "-9.12"),
      ],
    ),
    risk_warnings_by_severity: chartSeries(
      "risk_warnings_by_severity",
      "Risk warnings by severity",
      [
        chartPoint("high", "high", "1", null, "available", {
          warning_codes: ["missing_price"],
          messages: ["MSFT price data is missing."],
        }),
        chartPoint("medium", "medium", "2", null, "available", {
          warning_codes: ["concentration", "stop_protection"],
          messages: ["AAPL is concentrated.", "Stop protection is missing."],
        }),
      ],
    ),
    report_history_summary: chartSeries("report_history_summary", "Report history summary", [
      {
        key: "1",
        label: "2026-06-19T15:30:00Z",
        value: "1",
        percent: null,
        status: "available",
        metadata: {
          report_id: 1,
          created_at: "2026-06-19T15:30:00Z",
          command_context: "scheduled",
          valuation_status: "complete",
          price_completeness_status: "complete",
          recommendation_summary: "Hold current positions.",
          report_summary: "Portfolio remains balanced.",
        },
      },
    ]),
  },
};

const auditPreview = {
  events: [
    {
      id: 10,
      portfolio_name: "Primary",
      changed_at: "2026-06-19T16:00:00Z",
      actor: "admin",
      source: "web",
      action: "upsert",
      entity_type: "holding",
      entity_id: "AAPL",
      status: "succeeded",
      summary: "Updated AAPL holding.",
      before_json: null,
      after_json: null,
      safe_error_message: null,
    },
  ],
};

type MockFetchOptions = {
  authenticated?: boolean;
  portfolio?: unknown;
  analysis?: unknown;
  audit?: unknown;
  sessionStatus?: number;
  portfolioStatus?: number;
  logoutStatus?: number;
};

function mockFetch({
  authenticated = true,
  portfolio = populatedPortfolio,
  analysis = analysisCharts,
  audit = auditPreview,
  sessionStatus,
  portfolioStatus = 200,
  logoutStatus = 200,
}: MockFetchOptions = {}) {
  let currentAuthenticated = authenticated;
  const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    const url = String(input);

    if (url === "/api/v1/auth/session") {
      return Promise.resolve(
        jsonResponse(
          { authenticated: currentAuthenticated },
          { status: sessionStatus ?? (currentAuthenticated ? 200 : 401) },
        ),
      );
    }
    if (url === "/api/v1/auth/login") {
      currentAuthenticated = true;
      return Promise.resolve(jsonResponse({ authenticated: true }));
    }
    if (url === "/api/v1/auth/logout") {
      currentAuthenticated = logoutStatus >= 400;
      return Promise.resolve(
        jsonResponse(
          { authenticated: currentAuthenticated },
          { status: logoutStatus },
        ),
      );
    }
    if (url === "/api/v1/portfolio") {
      return Promise.resolve(jsonResponse(portfolio, { status: portfolioStatus }));
    }
    if (url.startsWith("/api/v1/portfolio/analysis/charts")) {
      return Promise.resolve(jsonResponse(analysis));
    }
    if (url.startsWith("/api/v1/portfolio/audit")) {
      return Promise.resolve(jsonResponse(audit));
    }

    return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders the layout navigation and safety note", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(screen.getByRole("link", { name: "Finwall dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByLabelText("Safety note")).toHaveTextContent(
      "decision-support only",
    );
    await screen.findByRole("heading", { name: "Portfolio overview" });
  });

  it("shows the session loading state before rendering the dashboard", () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise(() => {})));

    renderAt("/dashboard");

    expect(screen.getByRole("heading", { name: "Checking session" })).toBeInTheDocument();
  });

  it("requires an authenticated session before rendering dashboard data", async () => {
    const fetchMock = mockFetch({ authenticated: false });

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/session");
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/v1/portfolio")).toBe(
      false,
    );
  });

  it("returns to login when a session refetch fails after prior authentication", async () => {
    let sessionValid = true;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url === "/api/v1/auth/session") {
        if (!sessionValid) {
          return Promise.resolve(
            jsonResponse({ detail: "invalid" }, { status: 401 }),
          );
        }
        return Promise.resolve(jsonResponse({ authenticated: true }));
      }
      if (url === "/api/v1/portfolio") {
        return Promise.resolve(jsonResponse(populatedPortfolio));
      }
      if (url.startsWith("/api/v1/portfolio/analysis/charts")) {
        return Promise.resolve(jsonResponse(analysisCharts));
      }
      if (url.startsWith("/api/v1/portfolio/audit")) {
        return Promise.resolve(jsonResponse(auditPreview));
      }

      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Portfolio overview" })).toBeInTheDocument();

    sessionValid = false;
    await queryClient.refetchQueries({ queryKey: queryKeys.session });

    expect(await screen.findByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Portfolio overview" })).not.toBeInTheDocument();
  });

  it("renders the dashboard portfolio loading state", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/auth/session") {
        return Promise.resolve(jsonResponse({ authenticated: true }));
      }
      if (url === "/api/v1/portfolio") {
        return new Promise(() => {});
      }
      return Promise.resolve(jsonResponse(analysisCharts));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Loading portfolio" })).toBeInTheDocument();
  });

  it("renders the dashboard portfolio error state", async () => {
    mockFetch({
      portfolio: { detail: "error" },
      portfolioStatus: 500,
    });

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Portfolio data could not load" }),
    ).toBeInTheDocument();
  });

  it("renders the empty portfolio state", async () => {
    mockFetch({ portfolio: emptyPortfolio, audit: { events: [] } });

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Portfolio is empty" })).toBeInTheDocument();
    expect(screen.getByText("No holdings available.")).toBeInTheDocument();
    expect(screen.getByText("No cash balances available.")).toBeInTheDocument();
  });

  it("renders portfolio summary and backend-owned dashboard sections", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(screen.getByText("Retirement")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Market data readiness" })).toBeInTheDocument();
    expect(screen.getByText("Portfolio remains balanced.")).toBeInTheDocument();
    expect(screen.getByText("Updated AAPL holding.")).toBeInTheDocument();
  });

  it("renders the dashboard chart section", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Allocation by holding" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cash vs invested" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Unrealized gain/loss by holding" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Risk warnings by severity" }),
    ).toBeInTheDocument();
  });

  it("renders allocation chart labels, values, and fallback table", async () => {
    mockFetch();

    renderAt("/dashboard");

    const table = await screen.findByRole("table", {
      name: "Allocation by holding fallback table",
    });
    expect(within(table).getByText("AAPL")).toBeInTheDocument();
    expect(within(table).getByText("58.33%")).toBeInTheDocument();
    expect(within(table).getByText("1750.00")).toBeInTheDocument();
  });

  it("renders cash vs invested labels, values, and fallback table", async () => {
    mockFetch();

    renderAt("/dashboard");

    const table = await screen.findByRole("table", {
      name: "Cash vs invested fallback table",
    });
    expect(within(table).getByText("Cash")).toBeInTheDocument();
    expect(within(table).getByText("1250.50")).toBeInTheDocument();
    expect(within(table).getByText("Invested")).toBeInTheDocument();
    expect(within(table).getByText("3000.00")).toBeInTheDocument();
  });

  it("does not mark complete cash valuation data as partial", async () => {
    mockFetch();

    renderAt("/dashboard");

    await screen.findByRole("table", {
      name: "Cash vs invested fallback table",
    });
    expect(screen.queryByText("Valuation status: Complete.")).not.toBeInTheDocument();
    expect(screen.queryByText("Partial data visible")).not.toBeInTheDocument();
  });

  it("renders unrealized gain/loss positive and negative values", async () => {
    mockFetch();

    renderAt("/dashboard");

    const table = await screen.findByRole("table", {
      name: "Unrealized gain/loss fallback table",
    });
    expect(within(table).getByText("250.00")).toBeInTheDocument();
    expect(within(table).getByText("-125.50")).toBeInTheDocument();
  });

  it("renders risk warning severity counts and summaries", async () => {
    mockFetch();

    renderAt("/dashboard");

    const table = await screen.findByRole("table", {
      name: "Risk warnings by severity fallback table",
    });
    expect(within(table).getByText("High")).toBeInTheDocument();
    expect(within(table).getByText("Medium")).toBeInTheDocument();
    expect(within(table).getByText("1")).toBeInTheDocument();
    expect(within(table).getByText("2")).toBeInTheDocument();
    expect(within(table).getByText(/MSFT price data is missing/)).toBeInTheDocument();
  });

  it("renders an empty chart series state", async () => {
    const analysis = structuredClone(analysisCharts);
    analysis.charts.allocation_by_holding = chartSeries(
      "allocation_by_holding",
      "Allocation by holding",
    );
    mockFetch({ analysis });

    renderAt("/dashboard");

    await screen.findByRole("heading", { name: "Allocation by holding" });
    expect(screen.getByText("No chart data available.")).toBeInTheDocument();
  });

  it("describes default live provider without env setup instructions", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(
      await screen.findByText(/Default live provider status is reported/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Set FINWALL_MARKET_DATA_PROVIDER/),
    ).not.toBeInTheDocument();
  });

  it("renders missing-price chart points as unavailable", async () => {
    const analysis = structuredClone(analysisCharts);
    analysis.charts.allocation_by_holding = chartSeries(
      "allocation_by_holding",
      "Allocation by holding",
      [
        chartPoint("AAPL", "AAPL", "1750.00", "58.33"),
        chartPoint("MSFT", "MSFT", null, null, "missing_price", {
          missing_price_message: "Price unavailable for MSFT.",
        }),
        chartPoint("TSLA", "TSLA", "not-a-number", "not-a-percent"),
      ],
    );
    mockFetch({ analysis });

    renderAt("/dashboard");

    const table = await screen.findByRole("table", {
      name: "Allocation by holding fallback table",
    });
    expect(within(table).getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(within(table).getByText("Price unavailable for MSFT.")).toBeInTheDocument();
    expect(within(table).getByText("Value unavailable")).toBeInTheDocument();
  });

  it("renders chart warnings and partial valuation status visibly", async () => {
    const analysis = structuredClone(analysisCharts);
    analysis.valuation_status = "missing_prices";
    analysis.price_completeness_status = "partial";
    analysis.charts.cash_vs_invested = chartSeries(
      "cash_vs_invested",
      "Cash vs invested",
      [
        chartPoint("cash", "Cash", "1250.50", "100.00"),
        chartPoint("invested", "Invested", null, null),
      ],
      ["MSFT: price missing"],
    );
    mockFetch({ analysis });

    renderAt("/dashboard");

    expect(await screen.findAllByText("Partial data visible")).not.toHaveLength(0);
    expect(screen.getAllByText("MSFT: price missing").length).toBeGreaterThan(0);
    expect(screen.getByText("Valuation status: Missing Prices.")).toBeInTheDocument();
    expect(screen.getByText("Price completeness status: Partial.")).toBeInTheDocument();
  });

  it("renders the holdings table", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Current holdings" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "AAPL" })).toBeInTheDocument();
    expect(screen.getByText("Technology")).toBeInTheDocument();
  });

  it("renders the cash table", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Cash balances" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "USD" })).toBeInTheDocument();
    expect(screen.getByText("1,250.5")).toBeInTheDocument();
  });

  it("renders the active orders table", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Open order plan" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "MSFT" })).toBeInTheDocument();
    expect(screen.getByText("Limit")).toBeInTheDocument();
    expect(screen.getByText("310")).toBeInTheDocument();
  });

  it("renders the watchlist table", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Tracked ideas" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "NVDA" })).toBeInTheDocument();
    expect(screen.getByText("Wait for earnings")).toBeInTheDocument();
  });

  it("renders the login page", () => {
    renderAt("/login");

    expect(screen.getByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
    expect(screen.getByLabelText("App token")).toBeInTheDocument();
  });

  it("refreshes session after login from the protected dashboard fallback", async () => {
    const fetchMock = mockFetch({ authenticated: false });

    renderAt("/dashboard");
    fireEvent.change(await screen.findByLabelText("App token"), {
      target: { value: "secret" },
    });
    fireEvent.submit(screen.getByRole("form", { name: "Login form" }));

    expect(
      await screen.findByRole("heading", { name: "Portfolio overview" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/dashboard");
    expect(fetchMock.mock.calls.slice(0, 3).map((call) => call[0])).toEqual([
      "/api/v1/auth/session",
      "/api/v1/auth/login",
      "/api/v1/auth/session",
    ]);
  });

  it("submits login, clears token state, and navigates to the dashboard", async () => {
    const fetchMock = mockFetch();
    const storageSetItem = vi.spyOn(Storage.prototype, "setItem");

    renderAt("/login");
    fireEvent.change(screen.getByLabelText("App token"), {
      target: { value: "secret" },
    });
    fireEvent.submit(screen.getByRole("form", { name: "Login form" }));

    await waitFor(() => expect(window.location.pathname).toBe("/dashboard"));
    expect(
      await screen.findByRole("heading", { name: "Portfolio overview" }),
    ).toBeInTheDocument();
    expect(storageSetItem).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ token: "secret" }));
  });

  it("shows a safe error after failed login and clears the input", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid" }, { status: 401 })),
    );

    renderAt("/login");
    const tokenInput = screen.getByLabelText("App token");

    fireEvent.change(tokenInput, { target: { value: "secret" } });
    fireEvent.submit(screen.getByRole("form", { name: "Login form" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Login failed. Check the token and try again.",
    );
    expect(tokenInput).toHaveValue("");
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("logs out and returns to the login route", async () => {
    const fetchMock = mockFetch();

    renderAt("/dashboard");
    await screen.findByRole("heading", { name: "Current holdings" });

    expect(queryClient.getQueryData(queryKeys.portfolio)).toBeDefined();
    expect(queryClient.getQueriesData({ queryKey: ["analysis"] })).toHaveLength(1);
    expect(queryClient.getQueriesData({ queryKey: ["audit"] })).toHaveLength(1);

    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(screen.getByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some((call) => call[0] === "/api/v1/auth/logout")).toBe(
      true,
    );
    expect(queryClient.getQueryData(queryKeys.portfolio)).toBeUndefined();
    expect(queryClient.getQueriesData({ queryKey: ["analysis"] })).toHaveLength(0);
    expect(queryClient.getQueriesData({ queryKey: ["audit"] })).toHaveLength(0);
  });

  it("keeps the dashboard authenticated when logout fails", async () => {
    mockFetch({ logoutStatus: 500 });

    renderAt("/dashboard");
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Logout failed. Try again.",
    );
    expect(
      screen.getByRole("heading", { name: "Portfolio overview" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/dashboard");
  });

  it("renders the not-found page for unknown paths", () => {
    renderAt("/missing");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
