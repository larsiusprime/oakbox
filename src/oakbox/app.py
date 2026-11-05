"""The app service: a local HTTP API for the UI, plus the built UI itself.

Binds to 127.0.0.1 only. The UI talks to it over JSON, and polls a running step for
its progress (docs/ARCHITECTURE.md). Types are pydantic models, exported as OpenAPI
for the TypeScript client.
"""

from __future__ import annotations

import mimetypes
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from oakbox import __version__
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound, NotReady
from oakbox.routes import app_settings, bring_in, clean, engines, groups, model, projects, steps, values, wizard

WEB_DIST = Path(__file__).parent / "web"

# Python guesses content types from the Windows registry, where other software often
# maps .js to text/plain; browsers then refuse to run the UI's module scripts. Pin the
# types of everything the UI ships.
UI_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".wasm": "application/wasm",
}


def pin_ui_content_types() -> None:
    for ext, content_type in UI_TYPES.items():
        mimetypes.add_type(content_type, ext)


class Versions(BaseModel):
    version: str
    openavmkit: str


def _openavmkit_version() -> str:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as package_version

    try:
        return package_version("openavmkit")
    except PackageNotFoundError:
        return "unknown"


def _warm_engine() -> None:
    import openavmkit.data  # noqa: F401


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Importing OpenAVMKit takes seconds; start it now so the first project opened doesn't wait.
    threading.Thread(target=_warm_engine, daemon=True).start()
    yield


def create_app() -> FastAPI:
    pin_ui_content_types()
    # The API's own version, not the app's (that's /api/version): web/openapi.json is checked in, and shouldn't
    # change with every release.
    app = FastAPI(title="OAK box", version="1", lifespan=_lifespan)

    # What a route didn't catch itself: an earlier step to do first (409), or something not there (404), in the
    # same shape as an HTTPException's answer. Anything else is a bug: a 500, its traceback in the log.
    @app.exception_handler(NotReady)
    def not_ready(_request: Request, e: NotReady) -> JSONResponse:
        return JSONResponse({"detail": str(e)}, status_code=409)

    @app.exception_handler(NotFound)
    def not_found(_request: Request, e: NotFound) -> JSONResponse:
        return JSONResponse({"detail": f"Not found: {e}"}, status_code=404)

    @app.get("/api/version")
    def version() -> Versions:
        return Versions(version=__version__, openavmkit=_openavmkit_version())

    # FastAPI matches routes in the order they're registered: the SPA's catch-all comes after them all.
    app.include_router(app_settings.router)
    app.include_router(projects.router)
    app.include_router(wizard.router)
    app.include_router(steps.router)
    app.include_router(bring_in.router)
    app.include_router(groups.router)
    app.include_router(clean.router)
    app.include_router(model.router)
    app.include_router(values.router)
    app.include_router(engines.router)

    if WEB_DIST.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Any:
            candidate = WEB_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app
