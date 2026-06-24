import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../api/queryClient";
import { ActiveOrdersTable } from "../features/dashboard/ActiveOrdersTable";
import { AuditPreview } from "../features/dashboard/AuditPreview";
import { CashTable } from "../features/dashboard/CashTable";
import { DashboardSummary } from "../features/dashboard/DashboardSummary";
import { EmptyState } from "../features/dashboard/EmptyState";
import { ErrorState } from "../features/dashboard/ErrorState";
import { HoldingsTable } from "../features/dashboard/HoldingsTable";
import { LatestReportCard } from "../features/dashboard/LatestReportCard";
import { LiveDataStatus } from "../features/dashboard/LiveDataStatus";
import { LoadingState } from "../features/dashboard/LoadingState";
import { OnboardingChecklist } from "../features/dashboard/OnboardingChecklist";
import { useDashboardData } from "../features/dashboard/useDashboardData";
import { WatchlistTable } from "../features/dashboard/WatchlistTable";
import { DashboardCharts } from "../features/charts/DashboardCharts";
import { SetupHealthPanel } from "../features/setup/SetupHealthPanel";

type DashboardPageProps = {
  authError?: string | null;
  onLogout?: () => void | Promise<void>;
};

export default function DashboardPage({ authError, onLogout }: DashboardPageProps) {
  const queryClient = useQueryClient();
  const { portfolioQuery, analysisChartsQuery, auditPreviewQuery } =
    useDashboardData();
  const refreshDashboardData = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.portfolio });
    void queryClient.invalidateQueries({ queryKey: queryKeys.analysisCharts });
    void queryClient.invalidateQueries({ queryKey: queryKeys.auditPreview(5) });
  };
  const isRefreshingDashboard =
    portfolioQuery.isFetching ||
    analysisChartsQuery.isFetching ||
    auditPreviewQuery.isFetching;

  if (portfolioQuery.isPending) {
    return (
      <section className="dashboard-page" aria-labelledby="dashboard-title">
        <DashboardHeader onLogout={onLogout} />
        <LoadingState
          title="Loading portfolio"
          message="Loading portfolio summary, holdings, cash, orders, and watchlist."
        />
      </section>
    );
  }

  if (portfolioQuery.isError) {
    return (
      <section className="dashboard-page" aria-labelledby="dashboard-title">
        <DashboardHeader onLogout={onLogout} />
        <ErrorState
          title="Portfolio data could not load"
          message="The portfolio endpoint returned an error. No dashboard data is being shown."
        />
      </section>
    );
  }

  const portfolio = portfolioQuery.data;
  const holdings = portfolio.holdings ?? [];
  const cashBalances = portfolio.cash_balances ?? [];
  const activeOrders = portfolio.active_orders ?? [];
  const watchlist = portfolio.watchlist ?? [];
  const isEmptyPortfolio =
    holdings.length === 0 &&
    cashBalances.length === 0 &&
    activeOrders.length === 0 &&
    watchlist.length === 0 &&
    (portfolio.goals ?? []).length === 0 &&
    !portfolio.risk_profile;

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-title">
      <DashboardHeader onLogout={onLogout} />
      {authError ? (
        <p className="form-error" role="alert">
          {authError}
        </p>
      ) : null}

      {isEmptyPortfolio ? <EmptyState /> : null}

      <OnboardingChecklist
        portfolio={portfolio}
        analysis={analysisChartsQuery.data}
      />

      <SetupHealthPanel />

      <DashboardSummary
        portfolio={portfolio}
        analysis={analysisChartsQuery.data}
      />

      <div className="dashboard-grid">
        {analysisChartsQuery.isPending ? (
          <LoadingState
            title="Loading analysis status"
            message="Loading backend chart metadata and live-data status."
          />
        ) : analysisChartsQuery.isError ? (
          <div className="state-card error-state">
            <h2>Analysis status could not load</h2>
            <p>
              Portfolio data is visible, but chart metadata and live-data status
              are unavailable.
            </p>
            <button
              className="retry-button"
              type="button"
              onClick={refreshDashboardData}
              disabled={isRefreshingDashboard}
            >
              {isRefreshingDashboard ? "Refreshing..." : "Refresh dashboard data"}
            </button>
          </div>
        ) : (
          <>
            <LiveDataStatus
              analysis={analysisChartsQuery.data}
              isRetrying={isRefreshingDashboard}
              onRetry={refreshDashboardData}
            />
            <LatestReportCard analysis={analysisChartsQuery.data} />
          </>
        )}
      </div>

      {analysisChartsQuery.isPending ? (
        <LoadingState
          title="Loading dashboard charts"
          message="Loading chart-ready portfolio analysis series."
        />
      ) : analysisChartsQuery.isError ? (
        <div className="state-card error-state">
          <h2>Dashboard charts could not load</h2>
          <p>
            Portfolio tables are visible, but chart-ready analysis data is
            unavailable.
          </p>
          <button
            className="retry-button"
            type="button"
            onClick={refreshDashboardData}
            disabled={isRefreshingDashboard}
          >
            {isRefreshingDashboard ? "Refreshing..." : "Refresh dashboard data"}
          </button>
        </div>
      ) : (
        <DashboardCharts analysis={analysisChartsQuery.data} />
      )}

      <HoldingsTable holdings={holdings} />
      <CashTable cashBalances={cashBalances} />
      <ActiveOrdersTable activeOrders={activeOrders} />
      <WatchlistTable watchlist={watchlist} />

      {auditPreviewQuery.isPending ? (
        <LoadingState
          title="Loading audit preview"
          message="Loading the latest portfolio audit events."
        />
      ) : auditPreviewQuery.isError ? (
        <ErrorState
          title="Audit preview could not load"
          message="Portfolio data is visible, but recent audit events are unavailable."
        />
      ) : (
        <AuditPreview audit={auditPreviewQuery.data} />
      )}
    </section>
  );
}

function DashboardHeader({ onLogout }: Pick<DashboardPageProps, "onLogout">) {
  return (
    <div className="dashboard-hero">
      <div>
        <p className="eyebrow">Dashboard</p>
        <h1 id="dashboard-title">Portfolio overview</h1>
        <p>
          Read-only portfolio state, backend analysis status, report metadata, and
          recent audit activity.
        </p>
      </div>
      {onLogout ? (
        <button className="secondary-button" type="button" onClick={() => void onLogout()}>
          Log out
        </button>
      ) : null}
    </div>
  );
}
