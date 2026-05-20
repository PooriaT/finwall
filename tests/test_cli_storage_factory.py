import pytest

from finwall.cli import run


class _SentinelStore:
    def initialize(self):
        raise RuntimeError("factory-store-used")


def test_cli_uses_storage_factory(monkeypatch) -> None:
    monkeypatch.setattr(
        "finwall.cli.build_portfolio_store", lambda **_: _SentinelStore()
    )
    with pytest.raises(RuntimeError, match="factory-store-used"):
        run(["snapshot"])
