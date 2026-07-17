import sqlite3

from services.api.app.schemas.strategy_parse_schema import StrategyParseResult
from services.api.app.services.strategy_draft_store import StrategyDraftStore
from tests.unit.test_strategy_schema import valid_strategy


def test_strategy_draft_and_version_survive_store_recreation(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHALENS_DATABASE_PATH", str(tmp_path / "alphalens.db"))
    result = StrategyParseResult(strategy=valid_strategy())

    first_store = StrategyDraftStore()
    draft = first_store.create("SMA 전략", result)
    second_store = StrategyDraftStore()

    loaded = second_store.get(draft.draft_id)
    assert loaded.raw_input == "SMA 전략"
    assert loaded.strategy.strategy_name == "Sample SMA strategy"

    confirmed = second_store.confirm(draft.draft_id)
    assert confirmed.version == 1
    assert confirmed.status == "CONFIRMED"

    retried_confirmation = second_store.confirm(draft.draft_id)
    assert retried_confirmation.strategy_id == confirmed.strategy_id
    assert retried_confirmation.version == confirmed.version

    with sqlite3.connect(tmp_path / "alphalens.db") as connection:
        count = connection.execute("SELECT COUNT(*) FROM strategy_versions").fetchone()[0]
    assert count == 1
