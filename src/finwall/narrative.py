"""Downstream narrative layer for deterministic Finwall outputs only.

This module may explain deterministic report evidence but must not compute
recommendation statuses, risk thresholds, or portfolio analytics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from finwall.config import settings
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
PROVIDER_DISABLED = "disabled"
PROVIDER_STATIC = "static"
PROVIDER_FAKE = "fake"
PROVIDER_OLLAMA = "ollama"

PROHIBITED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bguaranteed(?:\s+(?:return|profit|outcome))?\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+return\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+profit\b", re.IGNORECASE),
    re.compile(r"\brisk[-\s]?free\b", re.IGNORECASE),
    re.compile(r"\bcannot\s+lose\b", re.IGNORECASE),
    re.compile(r"\bwill\s+definitely\b", re.IGNORECASE),
    re.compile(r"\bmust\s+buy\b", re.IGNORECASE),
    re.compile(r"\bmust\s+sell\b", re.IGNORECASE),
    re.compile(r"\bbuy\s+now\b", re.IGNORECASE),
    re.compile(r"\bsell\s+now\b", re.IGNORECASE),
    re.compile(r"\bexecute\s+this\s+trade\b", re.IGNORECASE),
    re.compile(r"\bplace\s+this\s+order\b", re.IGNORECASE),
    re.compile(r"\btarget\s+price\s+will\s+be\b", re.IGNORECASE),
    re.compile(r"\bprice\s+will\s+reach\b", re.IGNORECASE),
    re.compile(r"\bi\s+recommend\s+buying\b", re.IGNORECASE),
    re.compile(r"\bi\s+recommend\s+selling\b", re.IGNORECASE),
    re.compile(r"\bfinancial\s+advice\b", re.IGNORECASE),
)

ALLOWED_FINANCIAL_ADVICE_DISCLAIMER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnot\s+financial\s+advice\b", re.IGNORECASE),
    re.compile(r"\bdoes\s+not\s+provide\s+financial\s+advice\b", re.IGNORECASE),
)

CURRENCY_PERCENT_PATTERN = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?%")
NUMERIC_LITERAL_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?")
TICKER_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")


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
    """Provider contract for narrative generation.

    Expected output shape from ``generate_narrative``::

        {
            "sections": [
                {
                    "section": "portfolio_overview",
                    "text": "...",
                    "evidence_keys_used": ["portfolio_snapshot"],
                }
            ],
            "warnings": [],
        }

    Providers should return a JSON-like object matching this shape.
    Finwall always validates provider output before producing final response.
    """

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


@dataclass(frozen=True)
class DisabledNarrativeProvider:
    name: str = "disabled"

    def generate_narrative(self, request: NarrativeRequest) -> object:
        return {"sections": [], "warnings": ["narrative provider disabled"]}


@dataclass(frozen=True)
class OllamaNarrativeProvider:
    base_url: str
    model: str
    timeout_seconds: float
    name: str = PROVIDER_OLLAMA

    def generate_narrative(self, request: NarrativeRequest) -> object:
        prompt = build_narrative_prompt(request)
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": narrative_response_schema(),
                "options": {"temperature": 0},
            }
        ).encode("utf-8")
        http_request = Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise ValueError(f"non-200 from ollama api: {response.status}")
                outer_raw = response.read().decode("utf-8")
        except (TimeoutError, ConnectionError, URLError, HTTPError) as exc:
            raise ValueError("failed to reach ollama api") from exc

        try:
            outer_payload = json.loads(outer_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid ollama api json response") from exc
        nested = outer_payload.get("response")
        if not isinstance(nested, str):
            raise ValueError("missing ollama response field")
        try:
            return json.loads(nested)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid nested ollama json payload") from exc


PROVIDER_BUILDERS: dict[str, Callable[[], NarrativeProvider]] = {
    PROVIDER_DISABLED: DisabledNarrativeProvider,
    PROVIDER_STATIC: StaticNarrativeProvider,
    PROVIDER_FAKE: lambda: StaticNarrativeProvider(name=PROVIDER_FAKE),
    PROVIDER_OLLAMA: lambda: OllamaNarrativeProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    ),
}


def build_narrative_provider(provider_name: str) -> NarrativeProvider:
    name = provider_name.strip().lower()
    normalized = name or PROVIDER_DISABLED
    builder = PROVIDER_BUILDERS.get(normalized)
    if builder is not None:
        return builder()
    return DisabledNarrativeProvider(name=normalized)


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


def narrative_response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "required": ["sections", "warnings"],
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section", "text", "evidence_keys_used"],
                    "properties": {
                        "section": {"type": "string", "enum": list(NARRATIVE_SECTIONS)},
                        "text": {"type": "string"},
                        "evidence_keys_used": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "uniqueItems": True,
                        },
                    },
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
    }


def build_narrative_prompt(request: NarrativeRequest) -> str:
    schema = json.dumps(narrative_response_schema(), indent=2)
    evidence_json = json.dumps(request.evidence, indent=2, sort_keys=True)
    return (
        "ROLE\n"
        "You are a constrained narrative formatter for Finwall deterministic reports.\n\n"
        "AUTHORITY RULES\n"
        "- Deterministic report fields are authoritative.\n"
        "- Risk warnings are authoritative.\n"
        "- Recommendation statuses are authoritative.\n\n"
        "YOU MUST NOT\n"
        "- Add unsupported claims, fabricated prices, holdings, metrics, news, or source links.\n"
        "- Fabricate risk warnings or claim Finwall executes trades.\n"
        "- Express guaranteed outcomes, guaranteed returns, or prediction certainty.\n"
        "- Give direct trade instructions (buy/sell now, place order, execute trade).\n"
        "- Override deterministic risk controls or recommendation statuses.\n"
        "- Add new buy/sell/hold recommendations.\n\n"
        "YOU MAY\n"
        "- Explain deterministic evidence in cautious decision-support language only.\n"
        "- State uncertainty when evidence is incomplete.\n"
        "- Repeat the decision-support disclaimer without adding financial advice.\n\n"
        "OUTPUT FORMAT\n"
        "- Return JSON only. No prose outside JSON.\n"
        "- Use only allowed section names and keep section text under max words.\n"
        "- Include evidence_keys_used for each section with at least one valid evidence key.\n"
        f"- Allowed section names: {', '.join(request.requested_sections)}\n"
        f"- Max words per section: {request.max_words}\n"
        f"- Style: {request.style}\n"
        f"- Required JSON schema:\n{schema}\n\n"
        "EVIDENCE\n"
        "Use only this evidence JSON as source of truth:\n"
        f"{evidence_json}"
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
    except Exception:  # noqa: BLE001
        return _fallback(provider.name, "provider error: provider call failed")
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
        if _has_prohibited_content(text):
            return _fallback(
                provider_name,
                "invalid narrative output: prohibited trading instruction",
            )
        if _has_unsupported_numeric_claim(text, request):
            return _fallback(
                provider_name, "invalid narrative output: unsupported numeric claim"
            )
        if _has_unsupported_ticker_claim(text, request):
            return _fallback(
                provider_name, "invalid narrative output: unsupported ticker claim"
            )
        if not isinstance(evidence_keys, list) or any(
            not isinstance(key, str) for key in evidence_keys
        ):
            return _fallback(
                provider_name, "invalid narrative output: invalid evidence_keys_used"
            )
        if not evidence_keys:
            return _fallback(
                provider_name, "invalid narrative output: empty evidence key list"
            )
        normalized_keys: list[str] = []
        seen_keys: set[str] = set()
        for key in evidence_keys:
            if key not in request.evidence:
                return _fallback(
                    provider_name, "invalid narrative output: unknown evidence key"
                )
            if key not in seen_keys:
                normalized_keys.append(key)
                seen_keys.add(key)
        if _has_unsupported_recommendation_status(text, request):
            return _fallback(
                provider_name,
                "invalid narrative output: recommendation override detected",
            )
        if _contradicts_risk_authority(text, request):
            return _fallback(
                provider_name, "invalid narrative output: risk warning contradiction"
            )
        sections.append(
            NarrativeSection(
                section=section,
                text=text.strip(),
                evidence_keys_used=tuple(normalized_keys),
            )
        )

    if not sections:
        if warnings_raw == ["narrative provider disabled"]:
            return NarrativeResponse(
                available=True,
                provider=provider_name,
                sections=tuple(),
                warnings=("narrative provider disabled",),
                fallback_used=False,
                error=None,
            )
        return _fallback(provider_name, "invalid narrative output: empty sections")

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


def _has_prohibited_content(text: str) -> bool:
    for allowed in ALLOWED_FINANCIAL_ADVICE_DISCLAIMER_PATTERNS:
        text = allowed.sub("", text)
    return any(pattern.search(text) for pattern in PROHIBITED_PATTERNS)


def _has_unsupported_numeric_claim(text: str, request: NarrativeRequest) -> bool:
    evidence_numbers = _extract_normalized_numeric_literals(
        json.dumps(request.evidence, sort_keys=True)
    )
    for token in CURRENCY_PERCENT_PATTERN.findall(text):
        if _normalize_numeric_token(token) not in evidence_numbers:
            return True
    return False


def _extract_normalized_numeric_literals(source: str) -> set[str]:
    return {
        _normalize_numeric_token(token)
        for token in NUMERIC_LITERAL_PATTERN.findall(source)
    }


def _normalize_numeric_token(token: str) -> str:
    cleaned = token.replace("$", "").replace(",", "").replace("%", "").strip()
    if not cleaned:
        return ""
    try:
        numeric = float(cleaned)
    except ValueError:
        return cleaned.lower()
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.12g}"


def _has_unsupported_ticker_claim(text: str, request: NarrativeRequest) -> bool:
    evidence_blob = json.dumps(request.evidence, sort_keys=True)
    for ticker in TICKER_PATTERN.findall(text):
        if ticker in {"JSON"}:
            continue
        if ticker not in evidence_blob:
            return True
    return False


def _contradicts_risk_authority(text: str, request: NarrativeRequest) -> bool:
    lowered = text.lower()
    risks_payload = request.evidence.get("risks_and_warnings", [])
    has_risk_warnings = _has_active_risk_warnings(risks_payload)
    contradiction_phrases = (
        "risk is low",
        "safe to buy",
        "ignore the stop-loss warning",
        "warning has been resolved",
        "buy more despite concentration warning",
    )
    return has_risk_warnings and any(p in lowered for p in contradiction_phrases)


def _has_active_risk_warnings(risks_payload: object) -> bool:
    if isinstance(risks_payload, list):
        for item in risks_payload:
            if isinstance(item, str) and item.strip():
                return True
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str) and value.strip():
                        return True
                    if isinstance(value, list) and any(
                        isinstance(inner, str) and inner.strip() for inner in value
                    ):
                        return True
    return False
