import type { AnalysisCharts } from "../../api/types";
import { formatLabel } from "./format";

export type LiveDataStatusItem = NonNullable<AnalysisCharts["live_data_status"]>[number];

export function marketPriceStatusFromAnalysis(
  analysis?: AnalysisCharts,
): LiveDataStatusItem | undefined {
  const marketStatus = analysis?.live_data_status?.find(
    (status) => status.domain.toLowerCase() === "market_prices",
  );
  if (marketStatus || !analysis) {
    return marketStatus;
  }
  return legacyPriceCompletenessStatus(analysis.price_completeness_status);
}

export function legacyPriceCompletenessStatus(
  priceCompletenessStatus: string,
): LiveDataStatusItem {
  return {
    availability: legacyAvailability(priceCompletenessStatus),
    domain: "market_prices",
    fallback_provider: null,
    fallback_used: false,
    last_attempted_at: "",
    metadata: {},
    provider: "Not configured",
    source: `Legacy chart metadata: ${formatLabel(priceCompletenessStatus)}`,
    safe_error_messages: [],
    warnings: [],
  };
}

export function normalizeAvailability(availability: string | null | undefined) {
  const normalized = availability?.trim().toLowerCase();
  if (
    normalized === "live" ||
    normalized === "partial" ||
    normalized === "unavailable" ||
    normalized === "static" ||
    normalized === "manual" ||
    normalized === "unknown"
  ) {
    return normalized;
  }
  return "unknown";
}

function legacyAvailability(priceCompletenessStatus: string) {
  const normalized = priceCompletenessStatus.trim().toLowerCase();
  if (normalized === "complete") {
    return "live";
  }
  if (normalized === "partial") {
    return "partial";
  }
  if (normalized === "unavailable" || normalized === "missing_prices") {
    return "unavailable";
  }
  return normalizeAvailability(normalized);
}
