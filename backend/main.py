"""Compatibility entrypoint: ``uvicorn backend.main:app``."""

from backend.app.main import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
