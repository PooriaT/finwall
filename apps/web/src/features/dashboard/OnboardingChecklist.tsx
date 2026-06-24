import type { AnalysisCharts, Portfolio } from "../../api/types";
import { formatLabel } from "./format";
import {
  marketPriceStatusFromAnalysis,
  normalizeAvailability,
} from "./liveDataStatusFallback";

type OnboardingChecklistProps = {
  portfolio: Portfolio;
  analysis?: AnalysisCharts;
};

type ChecklistItem = {
  key: string;
  title: string;
  complete: boolean;
  status: string;
  message: string;
  command: string;
};

const LIVE_MARKET_AVAILABILITIES = new Set(["live", "partial"]);

export function OnboardingChecklist({
  portfolio,
  analysis,
}: OnboardingChecklistProps) {
  const items = buildChecklistItems(portfolio, analysis);
  const completeCount = items.filter((item) => item.complete).length;
  const isComplete = completeCount === items.length;

  return (
    <section className="onboarding-card" aria-labelledby="onboarding-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">First Run Checklist</p>
          <h2 id="onboarding-title">Set up your dashboard</h2>
        </div>
        <p className="onboarding-progress" aria-label="Onboarding progress">
          {completeCount} of {items.length} complete
        </p>
      </div>
      <p className="muted">
        Use the CLI for now to add portfolio context. This checklist is read-only
        and updates from backend portfolio and analysis data.
      </p>
      {isComplete ? (
        <p className="onboarding-success" role="status">
          Setup checklist complete. Live-data-backed dashboard context is available.
        </p>
      ) : null}
      <ul className="onboarding-list">
        {items.map((item) => (
          <li
            className={`onboarding-item${
              item.complete ? " onboarding-item-complete" : ""
            }`}
            key={item.key}
          >
            <div className="onboarding-item-header">
              <strong>{item.title}</strong>
              <span>{item.status}</span>
            </div>
            <p>{item.message}</p>
            {!item.complete ? (
              <code className="onboarding-command">{item.command}</code>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function buildChecklistItems(
  portfolio: Portfolio,
  analysis?: AnalysisCharts,
): ChecklistItem[] {
  const cashBalances = portfolio.cash_balances ?? [];
  const holdings = portfolio.holdings ?? [];
  const goals = portfolio.goals ?? [];
  const primaryGoal = goals[0];

  return [
    {
      key: "cash",
      title: "Add cash",
      complete: cashBalances.length > 0,
      status: cashBalances.length > 0 ? "Complete" : "Incomplete",
      message:
        cashBalances.length > 0
          ? "At least one cash balance is available."
          : "Add at least one cash balance so Finwall can show available cash.",
      command: "poetry run finwall --database finwall.db add-cash USD 1000",
    },
    {
      key: "holding",
      title: "Add first holding",
      complete: holdings.length > 0,
      status: holdings.length > 0 ? "Complete" : "Incomplete",
      message:
        holdings.length > 0
          ? "At least one holding is available."
          : "Add at least one holding so dashboard valuation and allocation can become useful.",
      command:
        "poetry run finwall --database finwall.db add-holding AAPL 1 190 --sector Technology",
    },
    {
      key: "risk",
      title: "Set risk profile",
      complete: Boolean(portfolio.risk_profile),
      status: portfolio.risk_profile ? "Complete" : "Incomplete",
      message: portfolio.risk_profile
        ? "Risk profile context is available."
        : "Set a risk profile so warnings and recommendation context can reflect your tolerance.",
      command:
        'poetry run finwall --database finwall.db set-risk moderate --notes "Example only"',
    },
    {
      key: "goal",
      title: "Set goal",
      complete: goals.length > 0,
      status: goals.length > 0 ? "Complete" : "Incomplete",
      message:
        goals.length > 0
          ? "At least one goal is available."
          : "Set a goal so reports have a target context.",
      command:
        'poetry run finwall --database finwall.db set-goal "Example goal" --target-amount 10000',
    },
    {
      key: "timeline",
      title: "Set timeline",
      complete: Boolean(primaryGoal?.timeline?.start_date),
      status: primaryGoal?.timeline?.start_date ? "Complete" : "Incomplete",
      message: primaryGoal?.timeline?.start_date
        ? "The primary goal includes a timeline start date."
        : "Add a timeline so reports can understand your target date.",
      command:
        "poetry run finwall --database finwall.db set-timeline 2026-01-01 --target-date 2026-12-31",
    },
    buildLiveMarketDataItem(holdings.length > 0, analysis),
  ];
}

function buildLiveMarketDataItem(
  hasHoldings: boolean,
  analysis?: AnalysisCharts,
): ChecklistItem {
  const marketStatus = marketPriceStatusFromAnalysis(analysis);
  const availability = normalizeAvailability(marketStatus?.availability);
  const complete = LIVE_MARKET_AVAILABILITIES.has(availability);

  if (!hasHoldings) {
    return {
      key: "live-market-data",
      title: "Verify live market data",
      complete: false,
      status: "Pending",
      message:
        "Add a holding first, then use live-data status to confirm price availability.",
      command:
        "poetry run finwall market-data-check --ticker AAPL --historical-days 30 --json",
    };
  }

  if (complete) {
    return {
      key: "live-market-data",
      title: "Verify live market data",
      complete,
      status: "Complete",
      message: `Market prices are ${formatLabel(availability)} for dashboard analysis.`,
      command:
        "poetry run finwall market-data-check --ticker AAPL --historical-days 30 --json",
    };
  }

  const sourceDetails = [marketStatus?.provider, marketStatus?.source]
    .filter(Boolean)
    .join(" / ");
  const sourceMessage = sourceDetails ? ` Provider/source: ${sourceDetails}.` : "";

  return {
    key: "live-market-data",
    title: "Verify live market data",
    complete: false,
    status: "Incomplete",
    message: `Market price availability is ${formatLabel(availability)}.${sourceMessage}`,
    command:
      "poetry run finwall market-data-check --ticker AAPL --historical-days 30 --json",
  };
}
