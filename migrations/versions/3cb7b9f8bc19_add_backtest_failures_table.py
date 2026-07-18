"""add backtest_failures table

Part of Phase 12 (실행 상태 관리): previously a failed backtest execution
returned an error to the caller but left no trace anywhere, so there was no
way to see later that a run had failed. Mirrors
services/api/app/core/database.py::_schema_statements() the same way the
baseline revision does -- IF NOT EXISTS makes this a safe no-op if the app's
own bootstrap already created the table.

Revision ID: 3cb7b9f8bc19
Revises: d8e394b29b8f
Create Date: 2026-07-18 12:17:53.040775

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3cb7b9f8bc19'
down_revision: Union[str, Sequence[str], None] = 'd8e394b29b8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_failures (
            id TEXT PRIMARY KEY,
            draft_id TEXT,
            strategy_id TEXT,
            strategy_version INTEGER,
            error_message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS backtest_failures_strategy_created_at_idx "
        "ON backtest_failures (strategy_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS backtest_failures_strategy_created_at_idx")
    op.execute("DROP TABLE IF EXISTS backtest_failures")
