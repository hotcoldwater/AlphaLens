import os
import sqlite3
from pathlib import Path
from typing import Any


def database_path() -> Path:
    configured = os.getenv("ALPHALENS_DATABASE_PATH", "data/alphalens.db")
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def database_url() -> str | None:
    """Use SQLite only when explicitly requested or when no Postgres URL exists."""
    if os.getenv("ALPHALENS_DATABASE_PATH"):
        return None
    configured = os.getenv("DATABASE_URL", "").strip()
    return configured or None


def using_postgres() -> bool:
    return database_url() is not None


def connect() -> Any:
    if using_postgres():
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError(
                "DATABASE_URL is configured but psycopg is not installed. "
                "Install the production requirements before starting the API."
            ) from error
        return psycopg.connect(database_url(), row_factory=dict_row)

    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def execute(connection: Any, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
    """Run portable store queries against SQLite or PostgreSQL."""
    if using_postgres():
        statement = statement.replace("?", "%s")
    return connection.execute(statement, parameters)


def initialize_schema() -> None:
    with connect() as connection:
        for statement in _schema_statements():
            execute(connection, statement)
        if not using_postgres():
            _add_column_if_missing(connection, "strategy_drafts", "strategy_id TEXT")
            _add_column_if_missing(connection, "strategy_drafts", "strategy_version INTEGER")
            _add_column_if_missing(connection, "strategy_drafts", "needs_clarification INTEGER NOT NULL DEFAULT 0")
            _add_column_if_missing(connection, "backtest_runs", "data_version TEXT NOT NULL DEFAULT 'unversioned'")
            _add_column_if_missing(connection, "backtest_runs", "strategy_id TEXT")
            _add_column_if_missing(connection, "backtest_runs", "strategy_version INTEGER")


def _schema_statements() -> tuple[str, ...]:
    return (
        """
        CREATE TABLE IF NOT EXISTS strategy_drafts (
            draft_id TEXT PRIMARY KEY,
            raw_input TEXT NOT NULL,
            strategy_json TEXT NOT NULL,
            status TEXT NOT NULL,
            missing_fields_json TEXT NOT NULL,
            assumptions_json TEXT NOT NULL,
            warnings_json TEXT NOT NULL,
            needs_confirmation INTEGER NOT NULL,
            needs_clarification INTEGER NOT NULL DEFAULT 0,
            strategy_id TEXT,
            strategy_version INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS strategy_versions (
            strategy_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            draft_id TEXT NOT NULL REFERENCES strategy_drafts(draft_id),
            strategy_json TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            PRIMARY KEY (strategy_id, version)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS backtest_runs (
            backtest_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            data_version TEXT NOT NULL DEFAULT 'unversioned',
            strategy_id TEXT,
            strategy_version INTEGER,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS strategy_versions_confirmed_at_idx ON strategy_versions (confirmed_at DESC)",
        "CREATE INDEX IF NOT EXISTS backtest_runs_strategy_created_at_idx ON backtest_runs (strategy_id, created_at DESC)",
    )


def _add_column_if_missing(connection: sqlite3.Connection, table: str, definition: str) -> None:
    column = definition.split()[0]
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
