#!/usr/bin/env python3
"""One-time migration of legacy BlueSignal SQLite data to PostgreSQL."""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import require_database_url  # noqa: E402


TABLES = ("users", "posts", "reports", "votes")

COLUMNS = {
    "users": (
        "id", "username", "email", "password", "role", "full_name",
        "authenticity_score", "created_at",
    ),
    "posts": (
        "id", "user_id", "title", "description", "media_url", "latitude",
        "longitude", "location_name", "status", "created_at",
    ),
    "reports": (
        "id", "post_id", "user_id", "urgency_level", "flood_type",
        "confidence_score", "verified", "ai_summary", "latitude",
        "longitude", "location_name", "created_at",
    ),
    "votes": (
        "id", "post_id", "user_id", "vote_type", "created_at", "updated_at",
    ),
}


def parse_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def read_sqlite(path: Path) -> dict[str, list[dict]]:
    if not path.is_file():
        raise SystemExit(f"SQLite database not found: {path}")

    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = sorted(set(TABLES) - tables)
        if missing:
            raise SystemExit(f"SQLite schema is missing tables: {', '.join(missing)}")

        data = {}
        for table in TABLES:
            existing = {
                row["name"] for row in connection.execute(
                    f"PRAGMA table_info({table})"
                )
            }
            missing_columns = sorted(set(COLUMNS[table]) - existing)
            if missing_columns:
                raise SystemExit(
                    f"SQLite table '{table}' is missing columns: "
                    f"{', '.join(missing_columns)}"
                )

            columns = ", ".join(COLUMNS[table])
            data[table] = [
                dict(row)
                for row in connection.execute(
                    f"SELECT {columns} FROM {table} ORDER BY id"
                )
            ]

        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise SystemExit(
                f"SQLite foreign-key check failed with {len(foreign_key_errors)} row(s)"
            )
        return data
    finally:
        connection.close()


def normalize_rows(table: str, rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        row = dict(row)
        if table == "reports":
            row["verified"] = bool(row["verified"])
        for column in ("created_at", "updated_at"):
            if column in row:
                row[column] = parse_datetime(row[column])
        normalized.append(row)
    return normalized


def check_destination_schema(engine) -> None:
    inspector = inspect(engine)
    missing_tables = sorted(set(TABLES) - set(inspector.get_table_names()))
    if missing_tables:
        raise SystemExit(
            "Destination schema is missing tables: " + ", ".join(missing_tables)
        )

    for table, expected_columns in COLUMNS.items():
        actual_columns = {
            column["name"] for column in inspector.get_columns(table)
        }
        missing_columns = sorted(set(expected_columns) - actual_columns)
        if missing_columns:
            raise SystemExit(
                f"Destination table '{table}' is missing columns: "
                + ", ".join(missing_columns)
            )


def check_destination_empty(connection, data: dict[str, list[dict]]) -> None:
    for table in TABLES:
        count = connection.execute(
            text(f'SELECT COUNT(*) FROM "{table}"')
        ).scalar_one()
        if count:
            raise RuntimeError(
                f"Refusing to migrate: destination table '{table}' already has "
                f"{count} row(s)"
            )
        source_ids = [row["id"] for row in data[table]]
        if len(source_ids) != len(set(source_ids)):
            raise RuntimeError(f"Source table '{table}' contains duplicate IDs")


def import_rows(engine, data: dict[str, list[dict]]) -> None:
    sql_tables = {}
    from app.models import Report, User, Post, Vote  # noqa: E402

    sql_tables["users"] = User.__table__
    sql_tables["posts"] = Post.__table__
    sql_tables["reports"] = Report.__table__
    sql_tables["votes"] = Vote.__table__

    with engine.begin() as connection:
        check_destination_empty(connection, data)
        for table in TABLES:
            rows = normalize_rows(table, data[table])
            if not rows:
                continue
            connection.execute(sql_tables[table].insert(), rows)
            print(f"{table}: inserted {len(rows)} row(s)")

        for table in TABLES:
            quoted_table = connection.dialect.identifier_preparer.quote(table)
            connection.execute(text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE(MAX(id), 1),
                    MAX(id) IS NOT NULL
                )
                FROM {quoted_table}
                """
            ))


def verify_counts(engine, data: dict[str, list[dict]]) -> None:
    with engine.connect() as connection:
        for table in TABLES:
            source_count = len(data[table])
            source_ids = {row["id"] for row in data[table]}
            target_count = connection.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar_one()
            target_ids = set(connection.execute(
                text(f"SELECT id FROM {table}")
            ).scalars())
            if target_count != source_count or target_ids != source_ids:
                raise RuntimeError(
                    f"Migration verification failed for {table}: "
                    f"source={source_count}, target={target_count}"
                )
            print(f"{table}: migrated {source_count}, PostgreSQL has {target_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy BlueSignal SQLite data to PostgreSQL."
    )
    parser.add_argument(
        "sqlite_path",
        nargs="?",
        type=Path,
        default=Path("bluesignal.db"),
        help="Legacy SQLite file (default: bluesignal.db)",
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL URL; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the SQLite source without writing PostgreSQL",
    )
    args = parser.parse_args()

    data = read_sqlite(args.sqlite_path)
    print(
        "SQLite source counts: "
        + ", ".join(f"{table}={len(data[table])}" for table in TABLES)
    )
    if args.dry_run:
        print("Dry run successful; PostgreSQL was not changed.")
        return

    database_url = args.database_url or require_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise SystemExit(f"Cannot connect to PostgreSQL: {exc}") from exc
        check_destination_schema(engine)
        import_rows(engine, data)
        verify_counts(engine, data)
        print("SQLite data migration completed successfully.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
