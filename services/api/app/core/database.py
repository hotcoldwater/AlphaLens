import os
import sqlite3
from pathlib import Path


def database_path() -> Path:
    configured = os.getenv("ALPHALENS_DATABASE_PATH", "data/alphalens.db")
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategy_drafts (
                draft_id TEXT PRIMARY KEY,
                raw_input TEXT NOT NULL,
                strategy_json TEXT NOT NULL,
                status TEXT NOT NULL,
                missing_fields_json TEXT NOT NULL,
                assumptions_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                needs_confirmation INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategy_versions (
                strategy_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                draft_id TEXT NOT NULL REFERENCES strategy_drafts(draft_id),
                strategy_json TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                PRIMARY KEY (strategy_id, version)
            );
            """
        )
