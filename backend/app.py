"""ASGI entry point for legacy deployment commands such as ``python app.py``."""

import os

from app.main import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("UVICORN_RELOAD", "false").strip().lower() == "true",
    )
