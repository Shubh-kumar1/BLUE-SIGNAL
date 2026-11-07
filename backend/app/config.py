import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://bluesignal@localhost:5432/bluesignal",
)

# Hosted PostgreSQL providers commonly expose the legacy postgres:// scheme.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL.startswith("postgresql://") and "+psycopg://" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def require_database_url() -> str:
    return DATABASE_URL
