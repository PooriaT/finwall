"""Downstream narrative layer for deterministic Finwall outputs only.

This module may explain deterministic report evidence but must not compute
recommendation statuses, risk thresholds, or portfolio analytics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from finwall.fundamental_summary import FundamentalSummaryReport
from finwall.news_summary import NewsSummaryReport
from finwall.reports import DecisionSupportReport
from finwall.technical_analysis import TechnicalAnalysisReport

NARRATIVE_SECTIONS: tuple[str, ...] = (
    "portfolio_overview",
    "risk_context",
    "recommendation_context",
    "action_plan",
    "limitations",
)
PROHIBITED_PHRASES: tuple[str, ...] = (
    "guaranteed",
    "risk-free",
    "sure profit",
    "must buy",
    "must sell",
    "execute trade",
    "financial advice",
)


@dataclass(frozen=True)
class NarrativeRequest:
    evidence: dict[str, object]
    requested_sections: tuple[str, ...]
    max_words: int
    style: str


@dataclass(frozen=True)
class NarrativeSection:
    section: str
    text: str
    evidence_keys_used: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeResponse:
    available: bool
    provider: str
    sections: tuple[NarrativeSection, ...]
    warnings: tuple[str, ...]
    fallback_used: bool
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "provider": self.provider,
            "sections": [
                {
                    "section": section.section,
                    "text": section.text,
                    "evidence_keys_used": list(section.evidence_keys_used),
                }
                for section in self.sections
            ],
            "warnings": list(self.warnings),
            "fallback_used": self.fallback_used,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)


class NarrativeProvider(Protocol):
    name: str

    def generate_narrative(self, request: NarrativeRequest) -> object: ...


@dataclass(frozen=True)
class StaticNarrativeProvider:
    name: str = "static"

    def generate_narrative(self, request: NarrativeRequest) -> object:
        sections: list[dict[str, object]] = []
        for section in request.requested_sections:
            if section == "portfolio_overview":
                text = (
                    "This summary is derived from deterministic report fields. "
                    "Review portfolio snapshot and valuation status before decisions."
                )
                keys = ["portfolio_snapshot", "risks_and_warnings"]
            elif section == "risk_context":
                text = (
                    "Risk warnings and limitations are deterministic outputs and should "
                    "be reviewed before any changes."
                )
                keys = ["risks_and_warnings", "limitations"]
            elif section == "recommendation_context":
                text = (
                    "Recommendation statuses come from deterministic logic and are "
                    "not overridden by this narrative layer."
                )
                keys = ["holding_recommendations", "cash_allocation_plan"]
            elif section == "action_plan":
                text = "Action-plan points are restated from the deterministic final action plan."
                keys = ["final_action_plan"]
            else:
                text = (
                    "Narrative limitations follow deterministic report limitations "
                    "and missing data notes."
                )
                keys = ["limitations"]
            sections.append(
                {"section": section, "text": text, "evidence_keys_used": keys}
            )
        return {"sections": sections, "warnings": []}


def build_narrative_provider(provider_name: str) -> NarrativeProvider:
    name = provider_name.strip().lower()
    if name in {"", "disabled"}:
        return DisabledNarrativeProvider()
    if name in {"static", "fake"}:
        return StaticNarrativeProvider(name=name)
    return DisabledNarrativeProvider(name=name)


@dataclass(frozen=True)
class DisabledNarrativeProvider:
    name: str = "disabled"

    def generate_narrative(self, request: NarrativeRequest) -> object:
        return {"sections": [], "warnings": ["narrative provider disabled"]}


def build_narrative_evidence(
    decision_report: DecisionSupportReport,
    *,
    news_summary: NewsSummaryReport | None = None,
    technical_report: TechnicalAnalysisReport | None = None,
    fundamental_summary_report: FundamentalSummaryReport | None = None,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "disclaimer": decision_report.disclaimer,
        "portfolio_snapshot": decision_report.portfolio_snapshot,
        "market_condition": decision_report.market_condition.__dict__,
        "holding_recommendations": list(decision_report.holding_recommendations),
        "cash_allocation_plan": decision_report.cash_allocation_plan,
        "suggested_orders": decision_report.suggested_orders.__dict__,
        "strategy_assessment": decision_report.strategy_assessment.__dict__,
        "risks_and_warnings": decision_report.risks_and_warnings,
        "final_action_plan": decision_report.final_action_plan.__dict__,
        "limitations": list(decision_report.limitations),
    }
    if news_summary is not None:
        evidence["news_summary"] = news_summary.as_dict()
    if technical_report is not None:
        evidence["technical_summary"] = technical_report.as_dict()
    if fundamental_summary_report is not None:
        evidence["fundamental_summary"] = fundamental_summary_report.as_dict()
    return evidence


def build_narrative_prompt(request: NarrativeRequest) -> str:
    return (
        "You are a constrained narrative rewriter for Finwall. "
        "Use ONLY the provided structured evidence. "
        "Do not invent prices, holdings, metrics, articles, source links, "
        "market data, recommendations, or risk warnings. "
        "Do not override deterministic recommendation statuses. "
        "Do not override risk-engine warnings. "
        "Do not imply guaranteed outcomes. Do not claim Finwall executes trades. "
        "Do not provide personalized financial advice. "
        "State when evidence is missing or incomplete. "
        "Keep output decision-support oriented.\n"
        "Return JSON object with keys: sections, warnings.\n"
        f"Allowed section names: {', '.join(request.requested_sections)}\n"
        f"Max words per section: {request.max_words}\n"
        f"Style: {request.style}\n"
        f"Evidence JSON:\n{json.dumps(request.evidence, indent=2, sort_keys=True)}"
    )


def _fallback(provider: str, warning: str) -> NarrativeResponse:
    sections = (
        NarrativeSection(
            section="portfolio_overview",
            text=(
                "Deterministic Finwall analysis remains the source of truth. Review "
                "risk warnings and missing data before taking any action."
            ),
            evidence_keys_used=("portfolio_snapshot", "risks_and_warnings"),
        ),
    )
    return NarrativeResponse(
        available=False,
        provider=provider,
        sections=sections,
        warnings=(warning,),
        fallback_used=True,
        error=warning,
    )


def generate_narrative(
    request: NarrativeRequest,
    provider: NarrativeProvider,
) -> NarrativeResponse:
    try:
        raw = provider.generate_narrative(request)
    except Exception as exc:  # noqa: BLE001
        return _fallback(provider.name, f"provider error: {exc}")
    return validate_narrative_response(raw, request, provider.name)


def validate_narrative_response(
    raw: object, request: NarrativeRequest, provider_name: str
) -> NarrativeResponse:
    if not isinstance(raw, dict):
        return _fallback(provider_name, "invalid narrative output: expected object")
    if "sections" not in raw or "warnings" not in raw:
        return _fallback(
            provider_name, "invalid narrative output: missing required keys"
        )
    sections_raw = raw.get("sections")
    warnings_raw = raw.get("warnings")
    if not isinstance(sections_raw, list) or not isinstance(warnings_raw, list):
        return _fallback(provider_name, "invalid narrative output: wrong types")

    sections: list[NarrativeSection] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            return _fallback(provider_name, "invalid section payload")
        section = item.get("section")
        text = item.get("text")
        evidence_keys = item.get("evidence_keys_used")
        if section not in NARRATIVE_SECTIONS:
            return _fallback(provider_name, f"unknown section: {section}")
        if not isinstance(text, str) or not text.strip():
            return _fallback(provider_name, f"empty text for section: {section}")
        lowered = text.lower()
        if any(term in lowered for term in PROHIBITED_PHRASES):
            return _fallback(provider_name, "prohibited phrasing detected")
        if not isinstance(evidence_keys, list) or any(
            not isinstance(key, str) for key in evidence_keys
        ):
            return _fallback(provider_name, "invalid evidence_keys_used")
        for key in evidence_keys:
            if key not in request.evidence:
                return _fallback(provider_name, f"unknown evidence key: {key}")
        if _has_unsupported_recommendation_status(text, request):
            return _fallback(
                provider_name, "unsupported recommendation status override"
            )
        sections.append(
            NarrativeSection(
                section=section,
                text=text.strip(),
                evidence_keys_used=tuple(evidence_keys),
            )
        )

    warnings = tuple(str(item) for item in warnings_raw)
    return NarrativeResponse(
        available=True,
        provider=provider_name,
        sections=tuple(sections),
        warnings=warnings,
        fallback_used=False,
        error=None,
    )


def _has_unsupported_recommendation_status(
    text: str, request: NarrativeRequest
) -> bool:
    allowed_statuses = {
        str(item.get("status", "")).strip().lower()
        for item in request.evidence.get("holding_recommendations", [])
        if isinstance(item, dict)
    }
    allowed_statuses.add(
        str(request.evidence.get("cash_allocation_plan", {}).get("status", ""))
        .strip()
        .lower()
    )
    allowed_statuses.discard("")

    for match in re.findall(r"status\s*[:=]\s*([a-z_]+)", text.lower()):
        if match and match not in allowed_statuses:
            return True
    return False


def format_narrative_markdown(response: NarrativeResponse) -> str:
    labels = {
        "portfolio_overview": "Portfolio Overview",
        "risk_context": "Risk Context",
        "recommendation_context": "Recommendation Context",
        "action_plan": "Action Plan Explanation",
        "limitations": "Limitations",
    }
    lines = ["## Narrative Summary", ""]
    for section in response.sections:
        lines.append(f"### {labels.get(section.section, section.section)}")
        lines.append(section.text)
        lines.append("")
    if response.warnings:
        lines.append("### Narrative Warnings")
        for warning in response.warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines).strip()
