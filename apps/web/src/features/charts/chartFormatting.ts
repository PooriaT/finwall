const displayNumberFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
});

export function formatChartNumber(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "Unavailable";
  }
  return displayNumberFormatter.format(value);
}

export function formatRawValue(value: string | null | undefined): string {
  const text = value?.trim();
  return text || "Unavailable";
}

export function formatRawPercent(value: string | null | undefined): string {
  const text = value?.trim();
  return text ? `${text}%` : "Unavailable";
}

export function formatStatus(value: string | null | undefined): string {
  const text = value?.trim();
  if (!text) {
    return "Unavailable";
  }
  return text
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}
