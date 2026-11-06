import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://bluesignal@localhost:5432/bluesignal",
)


def require_database_url() -> str:
    return DATABASE_URL
