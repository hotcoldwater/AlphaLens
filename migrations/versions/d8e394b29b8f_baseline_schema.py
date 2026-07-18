"""baseline schema

Mirrors the tables `services/api/app/core/database.py::_schema_statements()`
has bootstrapped via `CREATE TABLE IF NOT EXISTS` on every process start
since Phase 7. That bootstrap keeps running unchanged for backward
compatibility, so this revision intentionally uses `IF NOT EXISTS` /
`IF EXISTS` guards too: running `alembic upgrade head` against a database
the app already created is a safe no-op, and running it against a brand
new database (fresh Postgres, CI, a new contributor's machine) provisions
the schema without needing the API process to start first. Schema changes
from here on should be added as new revisions instead of growing the old
SQLite-only `_add_column_if_missing` backfill list.

Revision ID: d8e394b29b8f
Revises:
Create Date: 2026-07-18 00:11:14.932196

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd8e394b29b8f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
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
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS strategy_versions (
            strategy_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            draft_id TEXT NOT NULL REFERENCES strategy_drafts(draft_id),
            strategy_json TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            PRIMARY KEY (strategy_id, version)
        )
        """
    )
    op.execute(
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
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS strategy_versions_confirmed_at_idx "
        "ON strategy_versions (confirmed_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS backtest_runs_strategy_created_at_idx "
        "ON backtest_runs (strategy_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS backtest_runs_strategy_created_at_idx")
    op.execute("DROP INDEX IF EXISTS strategy_versions_confirmed_at_idx")
    op.execute("DROP TABLE IF EXISTS backtest_runs")
    op.execute("DROP TABLE IF EXISTS strategy_versions")
    op.execute("DROP TABLE IF EXISTS strategy_drafts")
