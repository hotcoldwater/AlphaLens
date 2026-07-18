from scripts.db_data_tool import export_data, import_data
from services.api.app.schemas.strategy_parse_schema import StrategyParseResult
from services.api.app.services.strategy_draft_store import StrategyDraftStore
from tests.unit.test_strategy_schema import valid_strategy


def test_export_then_import_moves_drafts_and_versions_between_databases(monkeypatch, tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    export_dir = tmp_path / "export"

    monkeypatch.setenv("ALPHALENS_DATABASE_PATH", str(source_path))
    store = StrategyDraftStore()
    draft = store.create("삼성전자 SMA 교차 전략", StrategyParseResult(strategy=valid_strategy()))
    confirmed = store.confirm(draft.draft_id)
    export_data(export_dir, ("strategy_drafts", "strategy_versions", "backtest_runs"))
    assert (export_dir / "strategy_drafts.json").exists()
    assert (export_dir / "backtest_runs.json").exists()

    monkeypatch.setenv("ALPHALENS_DATABASE_PATH", str(target_path))
    import_data(export_dir, ("strategy_drafts", "strategy_versions", "backtest_runs"))

    target_store = StrategyDraftStore()
    loaded = target_store.get(draft.draft_id)
    assert loaded.raw_input == "삼성전자 SMA 교차 전략"
    assert loaded.strategy_id == confirmed.strategy_id


def test_import_is_idempotent_and_does_not_duplicate_rows(monkeypatch, tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    export_dir = tmp_path / "export"

    monkeypatch.setenv("ALPHALENS_DATABASE_PATH", str(source_path))
    store = StrategyDraftStore()
    store.create("전략", StrategyParseResult(strategy=valid_strategy()))
    export_data(export_dir, ("strategy_drafts",))

    monkeypatch.setenv("ALPHALENS_DATABASE_PATH", str(target_path))
    import_data(export_dir, ("strategy_drafts",))
    import_data(export_dir, ("strategy_drafts",))

    import sqlite3
    with sqlite3.connect(target_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM strategy_drafts").fetchone()[0]
    assert count == 1
