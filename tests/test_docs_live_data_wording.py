from pathlib import Path

DOC_PATHS = (
    Path("README.md"),
    Path("docs/configuration.md"),
    Path("docs/cli-workflows.md"),
    Path("docs/frontend.md"),
    Path("docs/api-admin.md"),
    Path("docs/safety-limits.md"),
)

STALE_PRIMARY_PATH_PHRASES = (
    "set FINWALL_MARKET_DATA_PROVIDER to enable live data",
    "configure FINWALL_MARKET_DATA_PROVIDER to enable live data",
    "FINWALL_MARKET_DATA_PROVIDER is required for live data",
    "set provider to get live data",
)


def test_live_data_docs_do_not_require_provider_env_for_normal_workflows() -> None:
    docs_text = "\n".join(path.read_text() for path in DOC_PATHS)
    normalized = docs_text.lower()

    for phrase in STALE_PRIMARY_PATH_PHRASES:
        assert phrase.lower() not in normalized

    assert "override/debug" in normalized
    assert "users do not need to set `finwall_market_data_provider`" in normalized
