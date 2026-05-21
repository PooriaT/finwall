import json
from decimal import Decimal

from finwall.models import Holding, Portfolio
from finwall.narrative import (
    NARRATIVE_SECTIONS,
    DisabledNarrativeProvider,
    NarrativeRequest,
    OllamaNarrativeProvider,
    StaticNarrativeProvider,
    build_narrative_evidence,
    build_narrative_prompt,
    build_narrative_provider,
    generate_narrative,
    validate_narrative_response,
)
from finwall.recommendations import build_recommendation_report
from finwall.reports import build_decision_support_report
from finwall.risk import assess_portfolio_risk
from finwall.snapshot import generate_snapshot


def _request() -> NarrativeRequest:
    portfolio = Portfolio(
        name="p", holdings=(Holding("NVDA", Decimal("1"), Decimal("100")),)
    )
    snapshot = generate_snapshot(portfolio, {"NVDA": Decimal("120")})
    risk = assess_portfolio_risk(portfolio, snapshot)
    rec = build_recommendation_report(portfolio, snapshot, risk)
    report = build_decision_support_report(portfolio, snapshot, risk, rec)
    evidence = build_narrative_evidence(report)
    return NarrativeRequest(
        evidence=evidence,
        requested_sections=NARRATIVE_SECTIONS,
        max_words=500,
        style="plain_english",
    )


def test_build_evidence_and_prompt_constraints() -> None:
    request = _request()
    assert "portfolio_snapshot" in request.evidence
    prompt = build_narrative_prompt(request)
    assert "Use ONLY the provided structured evidence" in prompt
    assert "Do not invent prices" in prompt


def test_validate_valid_response() -> None:
    request = _request()
    response = validate_narrative_response(
        {
            "sections": [
                {
                    "section": "portfolio_overview",
                    "text": "Portfolio value and risk are summarized from deterministic outputs.",
                    "evidence_keys_used": ["portfolio_snapshot", "risks_and_warnings"],
                }
            ],
            "warnings": [],
        },
        request,
        "fake",
    )
    assert response.available is True
    assert response.fallback_used is False


def test_validate_fallback_cases() -> None:
    request = _request()
    invalid = validate_narrative_response({"bad": []}, request, "fake")
    assert invalid.fallback_used is True

    prohibited = validate_narrative_response(
        {
            "sections": [
                {
                    "section": "portfolio_overview",
                    "text": "This is guaranteed.",
                    "evidence_keys_used": ["portfolio_snapshot"],
                }
            ],
            "warnings": [],
        },
        request,
        "fake",
    )
    assert prohibited.fallback_used is True


def test_disabled_provider_and_exception_fallback() -> None:
    request = _request()
    disabled = generate_narrative(request, DisabledNarrativeProvider())
    assert disabled.available is True
    assert disabled.fallback_used is False

    class Boom:
        name = "boom"

        def generate_narrative(self, request):
            raise RuntimeError("timeout")

    failed = generate_narrative(request, Boom())
    assert failed.fallback_used is True
    assert "provider error" in (failed.error or "")


def test_build_narrative_provider_from_settings_name() -> None:
    assert build_narrative_provider("disabled").name == "disabled"
    assert build_narrative_provider("").name == "disabled"
    assert build_narrative_provider("static").name == "static"
    assert build_narrative_provider("fake").name == "fake"
    assert build_narrative_provider("unknown").name == "unknown"


def test_unsupported_recommendation_status_triggers_fallback() -> None:
    request = _request()
    response = validate_narrative_response(
        {
            "sections": [
                {
                    "section": "recommendation_context",
                    "text": "Deterministic status=strong_buy for NVDA.",
                    "evidence_keys_used": ["holding_recommendations"],
                }
            ],
            "warnings": [],
        },
        request,
        "fake",
    )
    assert response.fallback_used is True
    assert "unsupported recommendation status" in (response.error or "")


def test_unknown_provider_falls_back_without_crashing() -> None:
    request = _request()
    provider = build_narrative_provider("unknown")
    response = generate_narrative(request, provider)
    assert response.available is True
    assert response.fallback_used is False
    assert response.provider == "unknown"


def test_invalid_provider_output_falls_back_safely() -> None:
    request = _request()

    class InvalidPayloadProvider:
        name = "fake"

        def generate_narrative(self, request):
            return {"sections": "bad", "warnings": []}

    response = generate_narrative(request, InvalidPayloadProvider())
    assert response.fallback_used is True
    assert "invalid narrative output" in (response.error or "")
    assert "source of truth" in response.sections[0].text.lower()


def test_provider_exception_sanitized_error_message() -> None:
    request = _request()

    class SecretBoomProvider:
        name = "fake"

        def generate_narrative(self, request):
            raise RuntimeError("token=abc123\ntraceback details")

    response = generate_narrative(request, SecretBoomProvider())
    assert response.fallback_used is True
    assert response.error == "provider error: provider call failed"
    assert "abc123" not in (response.error or "")
    assert "traceback" not in (response.error or "").lower()


def test_static_and_disabled_provider_json_shape() -> None:
    request = _request()
    static_response = generate_narrative(request, StaticNarrativeProvider())
    assert isinstance(static_response.as_dict()["sections"], list)
    assert isinstance(static_response.as_dict()["warnings"], list)

    disabled_response = generate_narrative(request, DisabledNarrativeProvider())
    payload = disabled_response.as_dict()
    assert isinstance(payload["sections"], list)
    assert isinstance(payload["warnings"], list)


def test_ollama_provider_success_parses_nested_json(monkeypatch) -> None:
    request = _request()

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            payload = json.dumps(
                {
                    "response": json.dumps(
                        {
                            "sections": [
                                {
                                    "section": "portfolio_overview",
                                    "text": "From deterministic evidence.",
                                    "evidence_keys_used": ["portfolio_snapshot"],
                                }
                            ],
                            "warnings": [],
                        }
                    )
                }
            )
            return payload.encode("utf-8")

    monkeypatch.setattr(
        "finwall.narrative.urlopen", lambda *args, **kwargs: FakeResponse()
    )
    provider = OllamaNarrativeProvider("http://localhost:11434", "gemma3:latest", 30.0)
    raw = provider.generate_narrative(request)
    assert isinstance(raw, dict)
    assert raw["sections"][0]["section"] == "portfolio_overview"


def test_ollama_provider_failures_raise_value_error(monkeypatch) -> None:
    request = _request()
    provider = OllamaNarrativeProvider("http://localhost:11434", "gemma3:latest", 30.0)

    def _expect_failure(fake_urlopen) -> None:
        monkeypatch.setattr("finwall.narrative.urlopen", fake_urlopen)
        try:
            provider.generate_narrative(request)
            assert False, "expected ValueError"
        except ValueError:
            assert True

    _expect_failure(lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
    _expect_failure(
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionRefusedError())
    )

    class Non200:
        status = 503

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"response":"{}"}'

    _expect_failure(lambda *args, **kwargs: Non200())

    class InvalidOuter:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b"{not-json"

    _expect_failure(lambda *args, **kwargs: InvalidOuter())

    class MissingResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"model":"gemma3"}'

    _expect_failure(lambda *args, **kwargs: MissingResponse())

    class InvalidNested:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"response":"{oops"}'

    _expect_failure(lambda *args, **kwargs: InvalidNested())


def test_build_narrative_provider_ollama_registered() -> None:
    provider = build_narrative_provider("ollama")
    assert provider.name == "ollama"
