from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum

from finwall.fundamentals import (
    FundamentalAnalysisReport,
    FundamentalMetric,
    FundamentalSnapshot,
)


class FundamentalRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class FundamentalConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class FundamentalSignal:
    category: str
    status: str
    message: str
    metric_name: str | None = None
    metric_value: str | None = None


@dataclass(frozen=True)
class TickerFundamentalSummary:
    ticker: str
    company_name: str | None
    sector: str | None
    industry: str | None
    source: str
    data_status: str
    risk_level: FundamentalRiskLevel
    confidence: FundamentalConfidence
    revenue_trend: str
    profitability: str
    valuation_risk: str
    debt_risk: str
    company_context: str
    strengths: tuple[FundamentalSignal, ...]
    weaknesses: tuple[FundamentalSignal, ...]
    missing_information: tuple[str, ...]
    flags: tuple[str, ...]
    reasoning_inputs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FundamentalSummaryReport:
    holdings: tuple[TickerFundamentalSummary, ...]
    watchlist: tuple[TickerFundamentalSummary, ...]
    summary: str
    limitations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.+-]", "", value.strip())
    if cleaned in {"", "+", "-", ".", "+.", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_metric(
    metrics: tuple[FundamentalMetric, ...], *names: str
) -> FundamentalMetric | None:
    name_set = set(names)
    for metric in metrics:
        if metric.name in name_set:
            return metric
    return None


def summarize_fundamental_snapshot(
    snapshot: FundamentalSnapshot,
) -> TickerFundamentalSummary:
    strengths: list[FundamentalSignal] = []
    weaknesses: list[FundamentalSignal] = []
    missing: list[str] = []
    flags: set[str] = set()
    reasoning_inputs: list[str] = []
    parsed_failures = 0

    if snapshot.profile.available:
        country = snapshot.profile.country or "country unavailable"
        company_context = (
            f"{snapshot.profile.company_name or snapshot.ticker} in "
            f"{snapshot.profile.industry or 'industry unavailable'} "
            f"({snapshot.profile.sector or 'sector unavailable'}), {country}."
        )
    else:
        company_context = "Company profile unavailable."
        missing.append("company_profile")

    revenue_trend = "unknown"
    if not snapshot.revenue_growth.available or snapshot.revenue_growth.value is None:
        missing.append("revenue_growth")
        revenue_trend = "missing"
    else:
        value = _parse_number(snapshot.revenue_growth.value)
        if value is None:
            revenue_trend = "unparseable"
            parsed_failures += 1
            reasoning_inputs.append(
                f"revenue_growth_raw={snapshot.revenue_growth.value}"
            )
        elif value > 0:
            revenue_trend = "positive"
            strengths.append(
                FundamentalSignal(
                    "revenue",
                    "strength",
                    "Revenue growth is positive.",
                    "revenue_growth",
                    snapshot.revenue_growth.value,
                )
            )
        elif value < 0:
            revenue_trend = "negative"
            weaknesses.append(
                FundamentalSignal(
                    "revenue",
                    "weakness",
                    "Revenue growth is negative.",
                    "revenue_growth",
                    snapshot.revenue_growth.value,
                )
            )
            flags.add("weak_revenue_trend")
        else:
            revenue_trend = "flat"

    profitability = "unknown"
    prof_metrics = [
        m
        for m in snapshot.profitability
        if m.name
        in {
            "net_margin",
            "operating_margin",
            "gross_margin",
            "return_on_equity",
            "return_on_assets",
        }
    ]
    if not prof_metrics:
        missing.append("profitability_metrics")
        profitability = "missing"
    else:
        positives = negatives = 0
        for metric in prof_metrics:
            if not metric.available or metric.value is None:
                missing.append(f"profitability:{metric.name}")
                continue
            parsed = _parse_number(metric.value)
            if parsed is None:
                parsed_failures += 1
                reasoning_inputs.append(f"{metric.name}_raw={metric.value}")
                continue
            if parsed > 0:
                positives += 1
                strengths.append(
                    FundamentalSignal(
                        "profitability",
                        "strength",
                        f"{metric.name} is positive.",
                        metric.name,
                        metric.value,
                    )
                )
            elif parsed < 0:
                negatives += 1
                weaknesses.append(
                    FundamentalSignal(
                        "profitability",
                        "weakness",
                        f"{metric.name} is negative.",
                        metric.name,
                        metric.value,
                    )
                )
                flags.add("weak_profitability")
        profitability = (
            "positive"
            if positives and not negatives
            else "negative"
            if negatives and not positives
            else "mixed"
        )

    valuation_risk = "unknown"
    pe = _find_metric(snapshot.valuation, "pe_ratio", "forward_pe")
    ps = _find_metric(snapshot.valuation, "ps_ratio", "price_to_sales")
    peg = _find_metric(snapshot.valuation, "peg_ratio")
    if not snapshot.valuation:
        missing.append("valuation_metrics")
        valuation_risk = "missing"
    else:
        v_high = v_med = False
        for metric in [pe, ps, peg]:
            if metric is None:
                continue
            if not metric.available or metric.value is None:
                missing.append(f"valuation:{metric.name}")
                continue
            parsed = _parse_number(metric.value)
            if parsed is None or parsed < 0:
                parsed_failures += 1
                reasoning_inputs.append(f"{metric.name}_raw={metric.value}")
                continue
            if metric.name in {"pe_ratio", "forward_pe"} and parsed > 60:
                v_high = True
            elif metric.name in {"pe_ratio", "forward_pe"} and parsed >= 30:
                v_med = True
            elif metric.name in {"ps_ratio", "price_to_sales"} and parsed > 15:
                v_high = True
            elif metric.name == "peg_ratio" and parsed > 2:
                v_med = True
        if v_high:
            valuation_risk = "high"
            weaknesses.append(
                FundamentalSignal(
                    "valuation", "weakness", "Valuation metrics imply high risk."
                )
            )
            flags.add("high_valuation_risk")
        elif v_med:
            valuation_risk = "elevated"
        else:
            valuation_risk = "reasonable"

    debt_risk = "unknown"
    dte = _find_metric(snapshot.debt, "debt_to_equity", "total_debt_to_equity")
    nde = _find_metric(snapshot.debt, "net_debt_to_ebitda")
    cr = _find_metric(snapshot.debt, "current_ratio")
    if not snapshot.debt:
        missing.append("debt_metrics")
        debt_risk = "missing"
    else:
        d_high = False
        for metric in [dte, nde, cr]:
            if metric is None:
                continue
            if not metric.available or metric.value is None:
                missing.append(f"debt:{metric.name}")
                continue
            parsed = _parse_number(metric.value)
            if parsed is None:
                parsed_failures += 1
                reasoning_inputs.append(f"{metric.name}_raw={metric.value}")
                continue
            if metric.name in {"debt_to_equity", "total_debt_to_equity"} and parsed > 2:
                d_high = True
            if metric.name == "net_debt_to_ebitda" and parsed > 4:
                d_high = True
            if metric.name == "current_ratio" and parsed < 1:
                d_high = True
            if (
                metric.name in {"debt_to_equity", "total_debt_to_equity"}
                and parsed < 0.3
            ):
                strengths.append(
                    FundamentalSignal(
                        "debt",
                        "strength",
                        "Debt-to-equity is low.",
                        metric.name,
                        metric.value,
                    )
                )
        debt_risk = "high" if d_high else "moderate"
        if d_high:
            weaknesses.append(
                FundamentalSignal(
                    "debt", "weakness", "Debt or liquidity metrics imply elevated risk."
                )
            )
            flags.add("high_debt_risk")

    categories = [
        revenue_trend not in {"missing", "unknown"},
        profitability != "missing",
        valuation_risk != "missing",
        debt_risk != "missing",
        snapshot.profile.available,
    ]
    coverage = sum(categories)
    if coverage <= 1:
        flags.add("missing_fundamental_data")

    if revenue_trend == "negative" and profitability in {"negative", "mixed"}:
        flags.add("speculative_profile")
    if "high_valuation_risk" in flags and profitability in {
        "missing",
        "negative",
        "mixed",
    }:
        flags.add("speculative_profile")

    if "speculative_profile" in flags or "high_valuation_risk" in flags:
        risk = FundamentalRiskLevel.HIGH
    elif "high_debt_risk" in flags or weaknesses:
        risk = FundamentalRiskLevel.MEDIUM
    elif "missing_fundamental_data" in flags:
        risk = FundamentalRiskLevel.UNKNOWN
    else:
        risk = FundamentalRiskLevel.LOW

    if coverage <= 1 or parsed_failures > 1:
        confidence = FundamentalConfidence.LOW
    elif weaknesses or missing:
        confidence = FundamentalConfidence.MEDIUM
    else:
        confidence = FundamentalConfidence.HIGH

    if risk is not FundamentalRiskLevel.UNKNOWN and "missing_fundamental_data" in flags:
        risk = FundamentalRiskLevel.UNKNOWN

    return TickerFundamentalSummary(
        ticker=snapshot.ticker,
        company_name=snapshot.profile.company_name,
        sector=snapshot.profile.sector,
        industry=snapshot.profile.industry,
        source=snapshot.source,
        data_status=snapshot.data_status,
        risk_level=risk,
        confidence=confidence,
        revenue_trend=revenue_trend,
        profitability=profitability,
        valuation_risk=valuation_risk,
        debt_risk=debt_risk,
        company_context=company_context,
        strengths=tuple(strengths),
        weaknesses=tuple(weaknesses),
        missing_information=tuple(dict.fromkeys(missing)),
        flags=tuple(sorted(flags)),
        reasoning_inputs=tuple(reasoning_inputs),
    )


def build_fundamental_summary_report(
    raw_report: FundamentalAnalysisReport,
) -> FundamentalSummaryReport:
    holdings = tuple(summarize_fundamental_snapshot(s) for s in raw_report.holdings)
    watchlist = tuple(summarize_fundamental_snapshot(s) for s in raw_report.watchlist)
    return FundamentalSummaryReport(
        holdings=holdings,
        watchlist=watchlist,
        summary=(
            f"Fundamental summaries: {len(holdings)} holding ticker(s), "
            f"{len(watchlist)} watchlist ticker(s)."
        ),
        limitations=(
            "Fundamental summaries are deterministic decision-support "
            "inputs only, not recommendations.",
            "This summary does not perform valuation modeling or predict future returns.",
        ),
    )
