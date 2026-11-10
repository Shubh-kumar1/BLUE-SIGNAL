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

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:3001",
    "https://blue-signal.vercel.app",
    "https://blue-signal-1648rv5mv-shubhamraj9493-9503s-projects.vercel.app",
)


def require_database_url() -> str:
    return DATABASE_URL


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS")
    values = configured.split(",") if configured is not None else DEFAULT_CORS_ORIGINS
    return [origin.strip().rstrip("/") for origin in values if origin.strip()]
