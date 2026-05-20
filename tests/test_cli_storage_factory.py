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


def test_explicit_database_flag_sets_override(monkeypatch) -> None:
    captured = {}

    class _Store:
        def initialize(self):
            raise RuntimeError("stop")

    def _fake_factory(**kwargs):
        captured.update(kwargs)
        return _Store()

    monkeypatch.setattr("finwall.cli.build_portfolio_store", _fake_factory)

    with pytest.raises(RuntimeError, match="stop"):
        run(["--database", "finwall.db", "snapshot"])

    assert captured["cli_database_override"] is True
