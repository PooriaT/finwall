from finwall.report_history import (
    StoredRecommendationStatus,
    compare_recommendation_statuses,
)


def _status(ticker: str, status: str, confidence: str, risk: str, blocked: bool):
    return StoredRecommendationStatus(
        ticker, status, confidence, risk, blocked, "review"
    )


def test_compare_first_run_summary() -> None:
    comparison = compare_recommendation_statuses(
        (), (_status("NVDA", "hold", "medium", "low", False),), None, 1
    )
    assert comparison.summary.startswith("First saved report run")


def test_compare_detects_changes() -> None:
    comparison = compare_recommendation_statuses(
        (
            _status("NVDA", "hold", "medium", "low", False),
            _status("AAPL", "watch", "low", "medium", False),
        ),
        (
            _status("NVDA", "reduce", "low", "high", True),
            _status("PLTR", "watch", "medium", "medium", False),
        ),
        1,
        2,
    )
    assert len(comparison.changes) == 3
    assert any(change.change_type == "new_ticker" for change in comparison.changes)
    assert any(change.change_type == "removed_ticker" for change in comparison.changes)
    assert any("status_changed" in change.change_type for change in comparison.changes)


def test_compare_unchanged_summary() -> None:
    old = (_status("NVDA", "hold", "medium", "low", False),)
    new = (_status("NVDA", "hold", "medium", "low", False),)
    comparison = compare_recommendation_statuses(old, new, 1, 2)
    assert comparison.summary == "No recommendation changes were detected."
    assert comparison.changes == ()
