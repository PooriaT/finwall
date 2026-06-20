import type { ChartPoint, ChartSeries } from "../../api/types";
import { formatRawPercent, formatRawValue, formatStatus } from "./chartFormatting";

export type DisplayChartPoint = {
  key: string;
  label: string;
  rawValue: string | null;
  rawPercent: string | null;
  value: number | null;
  percent: number | null;
  status: string;
  statusLabel: string;
  metadata: Record<string, unknown>;
  unavailableReason: string | null;
};

export function parseChartNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function adaptChartSeries(series: ChartSeries): DisplayChartPoint[] {
  return series.points.map((point) => adaptChartPoint(point));
}

export function displayValue(point: DisplayChartPoint): string {
  return point.value === null ? "Unavailable" : formatRawValue(point.rawValue);
}

export function displayPercent(point: DisplayChartPoint): string {
  return point.percent === null ? "Unavailable" : formatRawPercent(point.rawPercent);
}

export function seriesWarnings(series: ChartSeries): string[] {
  return (series.warnings ?? []).filter((warning) => warning.trim().length > 0);
}

export function hasUnavailablePoints(points: DisplayChartPoint[]): boolean {
  return points.some((point) => point.value === null || point.status !== "available");
}

export function metadataString(
  metadata: Record<string, unknown>,
  key: string,
): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim() ? value : null;
}

export function metadataStringList(
  metadata: Record<string, unknown>,
  key: string,
): string[] {
  const value = metadata[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

export function riskWarningSummary(point: DisplayChartPoint): string {
  const codes = metadataStringList(point.metadata, "warning_codes");
  const messages = metadataStringList(point.metadata, "messages");
  const parts = [];
  if (codes.length > 0) {
    parts.push(`Codes: ${codes.join(", ")}`);
  }
  if (messages.length > 0) {
    parts.push(messages.join(" "));
  }
  return parts.join(" ");
}

function adaptChartPoint(point: ChartPoint): DisplayChartPoint {
  const metadata = point.metadata ?? {};
  const status = point.status || "available";
  const value = parseChartNumber(point.value);
  const percent = parseChartNumber(point.percent);
  return {
    key: point.key,
    label: point.label,
    rawValue: point.value,
    rawPercent: point.percent ?? null,
    value,
    percent,
    status,
    statusLabel: formatStatus(status),
    metadata,
    unavailableReason: unavailableReason(point, value),
  };
}

function unavailableReason(point: ChartPoint, parsedValue: number | null): string | null {
  const metadata = point.metadata ?? {};
  if (point.status !== "available") {
    return (
      metadataString(metadata, "missing_price_message") ??
      metadataString(metadata, "price_status") ??
      formatStatus(point.status)
    );
  }
  if (parsedValue === null) {
    return "Value unavailable";
  }
  return null;
}
