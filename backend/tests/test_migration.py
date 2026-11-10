import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.migrate_sqlite_to_postgres import read_sqlite


BACKEND_DIR = Path(__file__).resolve().parents[1]


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="bluesignal-migration-tests-")
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

    def test_alembic_initial_revision_creates_application_tables(self):
        database_url = f"sqlite:///{self.directory / 'alembic.db'}"
        environment = os.environ.copy()
        environment["DATABASE_URL"] = database_url
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        with sqlite3.connect(self.directory / "alembic.db") as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue({"users", "posts", "reports", "votes", "ai_jobs", "alembic_version"} <= tables)
            self.assertEqual(
                connection.execute("SELECT version_num FROM alembic_version").fetchone()[0],
                "0003_durable_ai_jobs",
            )
            report_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(reports)")
            }
            self.assertIn("image_classification", report_columns)
            ai_job_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(ai_jobs)")
            }
            self.assertTrue(
                {"report_id", "image_filename", "status", "attempts", "locked_at", "last_error"}
                <= ai_job_columns
            )

    def test_sqlite_import_validation_reads_legacy_records_without_mutating_source(self):
        source = self.directory / "legacy.db"
        with sqlite3.connect(source) as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY, username TEXT NOT NULL, email TEXT NOT NULL,
                    password TEXT NOT NULL, role TEXT NOT NULL, full_name TEXT,
                    authenticity_score INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL, description TEXT NOT NULL, media_url TEXT,
                    latitude REAL, longitude REAL, location_name TEXT, status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE reports (
                    id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL REFERENCES posts(id),
                    user_id INTEGER NOT NULL REFERENCES users(id), urgency_level TEXT,
                    flood_type TEXT, confidence_score REAL, verified INTEGER NOT NULL,
                    ai_summary TEXT, latitude REAL, longitude REAL, location_name TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE votes (
                    id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL REFERENCES posts(id),
                    user_id INTEGER NOT NULL REFERENCES users(id), vote_type TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(post_id, user_id)
                );
                INSERT INTO users VALUES
                    (7, 'legacy-citizen', 'legacy@example.com', 'old-hash', 'citizen',
                     'Legacy Citizen', 3, '2024-01-02T03:04:05+00:00');
                INSERT INTO posts VALUES
                    (11, 7, 'Flood', 'Water rising', '/uploads/old.jpg', 10, 20,
                     'Legacy Town', 'verified', '2024-01-02T03:04:05+00:00');
                INSERT INTO reports VALUES
                    (13, 11, 7, 'Urgent Panic', 'Urban Flooding', 0.9, 1,
                     'Legacy summary', 10, 20, 'Legacy Town', '2024-01-02T03:04:05+00:00');
                INSERT INTO votes VALUES
                    (17, 11, 7, 'up', '2024-01-02T03:04:05+00:00',
                     '2024-01-02T03:04:05+00:00');
                """
            )

        source_size = source.stat().st_size
        imported = read_sqlite(source)
        self.assertEqual(
            {table: len(rows) for table, rows in imported.items()},
            {"users": 1, "posts": 1, "reports": 1, "votes": 1},
        )
        self.assertEqual(imported["users"][0]["id"], 7)
        self.assertTrue(imported["reports"][0]["verified"])
        self.assertEqual(imported["votes"][0]["id"], 17)
        self.assertEqual(source.stat().st_size, source_size)


if __name__ == "__main__":
    unittest.main()
