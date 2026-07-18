"""Export/import strategy_drafts, strategy_versions, and backtest_runs rows.

Both commands operate on whichever database `services/api/app/core/database.py`
resolves at invocation time (DATABASE_URL for Postgres, otherwise the local
SQLite file at ALPHALENS_DATABASE_PATH) -- the same resolution the API process
itself uses. The typical workflow to move local SQLite dev data into Neon:

    # 1. export from the local SQLite dev database (DATABASE_URL unset)
    python -m scripts.db_data_tool export --output data/db_export

    # 2. import into Neon (DATABASE_URL set to the Neon connection string)
    DATABASE_URL=postgresql://... python -m scripts.db_data_tool import --input data/db_export

Import is safe to re-run: rows whose primary key already exists in the
target database are skipped rather than overwritten.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.api.app.core.database import connect, execute, initialize_schema, using_postgres  # noqa: E402

ALL_TABLES = ("strategy_drafts", "strategy_versions", "backtest_runs")


def _parse_tables(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ALL_TABLES
    requested = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = [table for table in requested if table not in ALL_TABLES]
    if unknown:
        raise ValueError(f"unknown table(s): {', '.join(unknown)} (choose from {', '.join(ALL_TABLES)})")
    return requested


def export_data(output_dir: Path, tables: tuple[str, ...]) -> None:
    initialize_schema()
    output_dir.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        for table in tables:
            rows = execute(connection, f"SELECT * FROM {table}").fetchall()
            records = [dict(row) for row in rows]
            (output_dir / f"{table}.json").write_text(
                json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"exported {len(records)} row(s) from {table} -> {output_dir / f'{table}.json'}")


def import_data(input_dir: Path, tables: tuple[str, ...]) -> None:
    initialize_schema()
    with connect() as connection:
        for table in tables:
            source = input_dir / f"{table}.json"
            if not source.exists():
                print(f"skip {table}: {source} not found")
                continue
            records = json.loads(source.read_text(encoding="utf-8"))
            if not records:
                print(f"skip {table}: no rows in {source}")
                continue
            columns = list(records[0].keys())
            column_list = ", ".join(columns)
            placeholders = ", ".join("?" for _ in columns)
            # Any conflict (primary key or unique index) is skipped rather than
            # overwritten, so a partially-applied import can be safely re-run.
            verb = "INSERT" if using_postgres() else "INSERT OR IGNORE"
            conflict_clause = "ON CONFLICT DO NOTHING" if using_postgres() else ""
            statement = f"{verb} INTO {table} ({column_list}) VALUES ({placeholders}) {conflict_clause}".strip()
            for record in records:
                execute(connection, statement, tuple(record[column] for column in columns))
            print(f"imported up to {len(records)} row(s) into {table} from {source} (existing keys skipped)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Dump rows from the currently configured database to JSON files")
    export_parser.add_argument("--output", required=True, type=Path, help="Directory to write <table>.json files into")
    export_parser.add_argument("--tables", help=f"Comma-separated subset of {', '.join(ALL_TABLES)} (default: all)")

    import_parser = subparsers.add_parser("import", help="Load <table>.json files into the currently configured database")
    import_parser.add_argument("--input", required=True, type=Path, help="Directory containing <table>.json files")
    import_parser.add_argument("--tables", help=f"Comma-separated subset of {', '.join(ALL_TABLES)} (default: all)")

    args = parser.parse_args()
    tables = _parse_tables(args.tables)

    if args.command == "export":
        export_data(args.output, tables)
    else:
        import_data(args.input, tables)


if __name__ == "__main__":
    main()
