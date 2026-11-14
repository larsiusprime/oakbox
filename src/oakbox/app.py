"""The app service: a local HTTP API for the UI, plus the built UI itself.

Binds to 127.0.0.1 only. The UI talks to it over JSON, and polls a running step for
its progress (docs/ARCHITECTURE.md). Types are pydantic models, exported as OpenAPI
for the TypeScript client.
"""

from __future__ import annotations

import mimetypes
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from oakbox import __version__, applog
from oakbox.datafiles import BaseModel
from oakbox.errors import NotFound, NotReady
from oakbox.routes import (
    app_settings,
    bring_in,
    clean,
    engines,
    groups,
    maps,
    model,
    outliers,
    projects,
    steps,
    values,
    wizard,
)

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


class LogInfo(BaseModel):
    folder: str
    file: str


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
    applog.logger().info("OAK box %s started (OpenAVMKit %s)", __version__, _openavmkit_version())
    yield
    from oakbox import steps

    steps.stop_all()  # the service is shutting down: its runs end with it


SLOW = 1.0  # seconds: a request taking longer is written to the log


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

    # Anything else is a bug: its traceback goes to OAK box's log (applog), and the page gets a reference to it,
    # with what failed, to copy. Starlette still raises it afterwards, so a console shows it too.
    @app.exception_handler(Exception)
    def failed(request: Request, e: Exception) -> JSONResponse:
        return JSONResponse(
            {"detail": None, "failure": applog.failure(request.method, request.url.path, e)}, status_code=500
        )

    # Slow requests are written to the log, with how long they took (and how many others were under way, as they
    # share the computer): what a slow click spent its time on can be read there afterwards.
    under_way = {"n": 0}

    @app.middleware("http")
    async def timed(request: Request, call_next):  # noqa: ANN001, ANN202 - Starlette's own types
        start = time.perf_counter()
        under_way["n"] += 1
        others = under_way["n"] - 1
        try:
            return await call_next(request)
        finally:
            under_way["n"] -= 1
            took = time.perf_counter() - start
            if took >= SLOW and request.url.path.startswith("/api/"):
                applog.logger().info(
                    "slow: %s %s took %.1f s (%d other requests under way)",
                    request.method,
                    request.url.path,
                    took,
                    others,
                )

    @app.get("/api/log")
    def log_info() -> LogInfo:
        """Where OAK box's log is."""
        return LogInfo(folder=str(applog.log_dir()), file=str(applog.log_file()))

    @app.post("/api/log/open")
    def log_open() -> None:
        """Show the log's folder in the file manager."""
        applog.open_folder()

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
    app.include_router(outliers.router)
    app.include_router(maps.router)
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
