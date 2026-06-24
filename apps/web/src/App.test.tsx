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
  data_warnings: [] as string[],
  live_data_status: [
    {
      domain: "market_prices",
      provider: "yfinance",
      source: "yfinance",
      availability: "live",
      last_attempted_at: "2026-01-01T00:00:00+00:00",
      fallback_used: false,
      fallback_provider: null as string | null,
      warnings: [] as string[],
      safe_error_messages: [] as string[],
      metadata: {},
    },
  ],
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

function analysisWithMarketAvailability(availability: string) {
  const analysis = structuredClone(analysisCharts);
  analysis.live_data_status = [
    {
      ...analysis.live_data_status[0],
      availability,
      provider: "test-provider",
      source: "test-source",
    },
  ];
  return analysis;
}

function analysisWithoutReportHistory() {
  const analysis = structuredClone(analysisCharts);
  analysis.charts.report_history_summary = chartSeries(
    "report_history_summary",
    "Report history summary",
  );
  return analysis;
}

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

function getChecklistItem(title: string) {
  const item = screen.getByText(title).closest("li");
  expect(item).toBeInTheDocument();
  return item as HTMLElement;
}

function formatAvailabilityForTest(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function countDashboardFetches(fetchMock: ReturnType<typeof vi.fn>) {
  const urls = fetchMock.mock.calls.map((call) => String(call[0]));
  return {
    portfolio: urls.filter((url) => url === "/api/v1/portfolio").length,
    analysis: urls.filter((url) =>
      url.startsWith("/api/v1/portfolio/analysis/charts"),
    ).length,
    audit: urls.filter((url) => url.startsWith("/api/v1/portfolio/audit")).length,
  };
}

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
    mockFetch({
      portfolio: emptyPortfolio,
      analysis: analysisWithoutReportHistory(),
      audit: { events: [] },
    });

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "No local portfolio data yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Finwall has no local portfolio state/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The frontend is read-only for portfolio data today/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/poetry run finwall --database finwall.db add-cash USD 1000/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(
        /poetry run finwall --database finwall.db add-holding AAPL 1 190 --sector Technology/,
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "No holdings yet" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Add a holding through the CLI so Finwall can calculate allocation, valuation, and risk context.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No cash balances yet" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Add cash so Finwall can distinguish available cash from invested value.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "No planned orders recorded" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Orders in Finwall are local planning records only; they are not broker orders.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "No watchlist items yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Add tickers you want to monitor without adding them as holdings.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "No saved report history yet" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Run a report with --save-run to populate this section."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "No audit events yet" })).toBeInTheDocument();
    expect(
      screen.getByText("Portfolio changes made through API paths will appear here."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Portfolio remains balanced.")).not.toBeInTheDocument();
    expect(screen.queryByText("Updated AAPL holding.")).not.toBeInTheDocument();
  });

  it("shows onboarding checklist guidance for an empty portfolio", async () => {
    const storageGetItem = vi.spyOn(Storage.prototype, "getItem");
    const storageSetItem = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = mockFetch({ portfolio: emptyPortfolio, audit: { events: [] } });

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Set up your dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Onboarding progress")).toHaveTextContent(
      "0 of 6 complete",
    );
    expect(
      screen.getByText("Add at least one cash balance so Finwall can show available cash."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Add at least one holding so dashboard valuation and allocation can become useful.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Set a risk profile so warnings and recommendation context can reflect your tolerance.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Set a goal so reports have a target context."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Add a timeline so reports can understand your target date."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Add a holding first, then use live-data status to confirm price availability.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("poetry run finwall --database finwall.db add-cash USD 1000")
        .length,
    ).toBeGreaterThan(0);
    expect(storageGetItem).not.toHaveBeenCalled();
    expect(storageSetItem).not.toHaveBeenCalled();
    expect(
      fetchMock.mock.calls.every((call) => {
        const init = call[1];
        return !init?.method || init.method === "GET";
      }),
    ).toBe(true);
  });

  it("marks portfolio setup onboarding items complete when data exists", async () => {
    mockFetch();

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Set up your dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Onboarding progress")).toHaveTextContent(
      "6 of 6 complete",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Setup checklist complete.",
    );
    expect(getChecklistItem("Add cash")).toHaveTextContent(
      "At least one cash balance is available.",
    );
    expect(getChecklistItem("Add first holding")).toHaveTextContent(
      "At least one holding is available.",
    );
    expect(getChecklistItem("Set risk profile")).toHaveTextContent(
      "Risk profile context is available.",
    );
    expect(getChecklistItem("Set goal")).toHaveTextContent(
      "At least one goal is available.",
    );
    expect(getChecklistItem("Set timeline")).toHaveTextContent(
      "The primary goal includes a timeline start date.",
    );
    expect(getChecklistItem("Verify live market data")).toHaveTextContent(
      "Market prices are Live for dashboard analysis.",
    );
  });

  it("treats partial market price status as complete onboarding data", async () => {
    mockFetch({ analysis: analysisWithMarketAvailability("partial") });

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Set up your dashboard" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Onboarding progress")).toHaveTextContent(
      "6 of 6 complete",
    );
    expect(getChecklistItem("Verify live market data")).toHaveTextContent(
      "Market prices are Partial for dashboard analysis.",
    );
  });

  it.each(["unavailable", "static", "manual", "unknown"])(
    "marks %s market price status as incomplete onboarding data",
    async (availability) => {
      mockFetch({ analysis: analysisWithMarketAvailability(availability) });

      renderAt("/dashboard");

      expect(
        await screen.findByRole("heading", { name: "Set up your dashboard" }),
      ).toBeInTheDocument();
      expect(screen.getByLabelText("Onboarding progress")).toHaveTextContent(
        "5 of 6 complete",
      );
      expect(getChecklistItem("Verify live market data")).toHaveTextContent(
        `Market price availability is ${availability.replace(/\b\w/g, (letter) =>
          letter.toUpperCase(),
        )}. Provider/source: test-provider / test-source.`,
      );
      expect(
        screen.getByText(
          "poetry run finwall market-data-check --ticker AAPL --historical-days 30 --json",
        ),
      ).toBeInTheDocument();
    },
  );

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

  it("preserves complete legacy price completeness fallback", async () => {
    const analysis: Record<string, unknown> = structuredClone(analysisCharts);
    delete analysis.live_data_status;
    analysis.price_completeness_status = "complete";
    mockFetch({ analysis });

    renderAt("/dashboard");

    const liveDataSection = await screen.findByRole("region", {
      name: "Market data readiness",
    });
    expect(screen.getByLabelText("Onboarding progress")).toHaveTextContent(
      "6 of 6 complete",
    );
    expect(getChecklistItem("Verify live market data")).toHaveTextContent(
      "Market prices are Live for dashboard analysis.",
    );
    expect(within(liveDataSection).getByText("Live")).toBeInTheDocument();
    expect(
      within(liveDataSection).getByText("Legacy chart metadata: Complete"),
    ).toBeInTheDocument();
    expect(
      within(liveDataSection).queryByRole("button", { name: "Retry status check" }),
    ).not.toBeInTheDocument();
  });

  it("preserves partial legacy price completeness fallback as retryable", async () => {
    const analysis: Record<string, unknown> = structuredClone(analysisCharts);
    delete analysis.live_data_status;
    analysis.price_completeness_status = "partial";
    mockFetch({ analysis });

    renderAt("/dashboard");

    const liveDataSection = await screen.findByRole("region", {
      name: "Market data readiness",
    });
    expect(screen.getByLabelText("Onboarding progress")).toHaveTextContent(
      "6 of 6 complete",
    );
    expect(getChecklistItem("Verify live market data")).toHaveTextContent(
      "Market prices are Partial for dashboard analysis.",
    );
    expect(within(liveDataSection).getByText("Partial")).toBeInTheDocument();
    expect(
      within(liveDataSection).getByText("Legacy chart metadata: Partial"),
    ).toBeInTheDocument();
    expect(
      within(liveDataSection).getByRole("button", { name: "Retry status check" }),
    ).toBeInTheDocument();
  });

  it("renders live-data provider details, fallback, warnings, and safe errors", async () => {
    const analysis = structuredClone(analysisCharts);
    analysis.data_warnings = ["AAPL price is delayed."];
    analysis.live_data_status = [
      {
        domain: "market_prices",
        provider: "primary-provider",
        source: "provider-api",
        availability: "partial",
        last_attempted_at: "2026-01-01T00:00:00+00:00",
        fallback_used: true,
        fallback_provider: "backup-provider",
        warnings: ["MSFT price is missing."],
        safe_error_messages: ["Provider returned a rate limit response."],
        metadata: {
          api_token: "raw-secret-token",
        },
      },
    ];
    mockFetch({ analysis });

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Market data readiness" })).toBeInTheDocument();
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(
      screen.getByText("Partial: some requested items were available and some are missing."),
    ).toBeInTheDocument();
    expect(screen.getByText("primary-provider")).toBeInTheDocument();
    expect(screen.getByText("provider-api")).toBeInTheDocument();
    expect(screen.getByText("Fallback provider: backup-provider")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Jan 1, 2026|Dec 31, 2025/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("AAPL price is delayed.")).toBeInTheDocument();
    expect(screen.getByText("MSFT price is missing.")).toBeInTheDocument();
    expect(screen.getByText("Provider returned a rate limit response.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry status check" })).toBeInTheDocument();
    expect(screen.queryByText("raw-secret-token")).not.toBeInTheDocument();
  });

  it.each([
    ["static", "Static: configured source is static, test, or fixture data."],
    ["manual", "Manual: user-supplied values were used."],
    ["unknown", "Unknown: provider configured, but this surface has not been evaluated yet."],
  ])("explicitly labels %s live-data status", async (availability, description) => {
    mockFetch({ analysis: analysisWithMarketAvailability(availability) });

    renderAt("/dashboard");

    expect(await screen.findByText(formatAvailabilityForTest(availability))).toBeInTheDocument();
    expect(screen.getByText(description)).toBeInTheDocument();
  });

  it("keeps unavailable live-data status visible", async () => {
    mockFetch({ analysis: analysisWithMarketAvailability("unavailable") });

    renderAt("/dashboard");

    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(
      screen.getByText("Unavailable: the provider could not return usable data."),
    ).toBeInTheDocument();
    expect(screen.getByText("test-provider")).toBeInTheDocument();
    expect(screen.getByText("test-source")).toBeInTheDocument();
  });

  it("refreshes dashboard queries from the live-data retry button", async () => {
    const analysis = analysisWithMarketAvailability("partial");
    analysis.data_warnings = ["Some market prices are missing."];
    const fetchMock = mockFetch({ analysis });

    renderAt("/dashboard");

    await screen.findByRole("button", { name: "Retry status check" });
    const beforeCounts = countDashboardFetches(fetchMock);

    fireEvent.click(screen.getByRole("button", { name: "Retry status check" }));

    await waitFor(() => {
      const afterCounts = countDashboardFetches(fetchMock);
      expect(afterCounts.portfolio).toBeGreaterThan(beforeCounts.portfolio);
      expect(afterCounts.analysis).toBeGreaterThan(beforeCounts.analysis);
      expect(afterCounts.audit).toBeGreaterThan(beforeCounts.audit);
    });
  });

  it("refreshes dashboard queries from the analysis error state", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/auth/session") {
        return Promise.resolve(jsonResponse({ authenticated: true }));
      }
      if (url === "/api/v1/portfolio") {
        return Promise.resolve(jsonResponse(populatedPortfolio));
      }
      if (url.startsWith("/api/v1/portfolio/analysis/charts")) {
        return Promise.resolve(jsonResponse({ detail: "error" }, { status: 500 }));
      }
      if (url.startsWith("/api/v1/portfolio/audit")) {
        return Promise.resolve(jsonResponse(auditPreview));
      }

      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Analysis status could not load" }),
    ).toBeInTheDocument();
    const beforeCounts = countDashboardFetches(fetchMock);

    fireEvent.click(screen.getAllByRole("button", { name: "Refresh dashboard data" })[0]);

    await waitFor(() => {
      const afterCounts = countDashboardFetches(fetchMock);
      expect(afterCounts.portfolio).toBeGreaterThan(beforeCounts.portfolio);
      expect(afterCounts.analysis).toBeGreaterThan(beforeCounts.analysis);
      expect(afterCounts.audit).toBeGreaterThan(beforeCounts.audit);
    });
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
