"""Model engines OAK box downloads when first asked for (oakbox/engines.py): which are installed, and fetching or
removing one."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from oakbox import engines

router = APIRouter()

Key = Literal["xgboost", "catboost"]


@router.get("/api/engines")
def list_engines() -> list[engines.EngineState]:
    """Each optional engine: installed or not, its sizes, and a download in progress (or just finished)."""
    return engines.states()


@router.post("/api/engines/{key}/install")
def install_engine(key: Key) -> list[engines.EngineState]:
    """Start downloading it, in the background; GET /api/engines follows it."""
    try:
        engines.start(key)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return engines.states()


@router.post("/api/engines/{key}/stop")
def stop_engine_install(key: Key) -> list[engines.EngineState]:
    engines.stop(key)
    return engines.states()


@router.post("/api/engines/{key}/seen")
def forget_engine_install(key: Key) -> list[engines.EngineState]:
    """A finished download's outcome has been shown."""
    engines.forget(key)
    return engines.states()


@router.delete("/api/engines/{key}")
def remove_engine(key: Key) -> list[engines.EngineState]:
    try:
        engines.remove(key)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return engines.states()
