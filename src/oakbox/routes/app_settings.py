"""OAK box's own settings on this computer: the display, where projects are kept, the Census API key."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from oakbox import appsettings
from oakbox.datafiles import BaseModel

router = APIRouter()


class Display(BaseModel):
    """How the app looks (SPEC D43, View menu)."""

    density: Literal["default", "compact"] | None = Field(
        default=None, description="None: default. Compact: a Windows 2000 dialog's density."
    )
    zoom: int = Field(default=100, description="Text and layout size, in percent.")


class ZoomStep(BaseModel):
    by: Literal[-1, 0, 1] = Field(description="A level larger (1) or smaller (-1), or actual size (0).")


class AppSettingsView(BaseModel):
    storage_location: str
    default_storage_location: str
    display: Display
    map_style: str = Field(description="The street map's MapLibre style address (appsettings.map_style).")


class CensusKey(BaseModel):
    key: str


class StorageLocation(BaseModel):
    storage_location: str | None = Field(default=None, description="None resets to the default.")


def _settings_view() -> AppSettingsView:
    s = appsettings.load()
    return AppSettingsView(
        storage_location=str(appsettings.storage_location()),
        default_storage_location=str(appsettings.default_storage()),
        display=Display(density=s.density, zoom=s.zoom),
        map_style=s.map_style or appsettings.MAP_STYLE,
    )


@router.put("/api/app-settings/display")
def put_display(body: Display) -> AppSettingsView:
    """Density and zoom (SPEC D43, View menu)."""
    s = appsettings.load()
    s.density, s.zoom = body.density, appsettings.AppSettings(zoom=body.zoom).zoom
    appsettings.save(s)
    return _settings_view()


@router.post("/api/app-settings/zoom")
def post_zoom(body: ZoomStep) -> AppSettingsView:
    """A zoom level larger, smaller, or actual size (View menu, Ctrl+= / Ctrl+- / Ctrl+0, Ctrl+mouse wheel)."""
    with appsettings.LOCK:
        s = appsettings.load()
        s.zoom = appsettings.zoom_step(s.zoom, body.by)
        appsettings.save(s)
    return _settings_view()


@router.get("/api/app-settings")
def get_app_settings() -> AppSettingsView:
    return _settings_view()


@router.put("/api/app-settings/storage-location")
def put_storage_location(body: StorageLocation) -> AppSettingsView:
    """Where new projects are kept. Existing projects stay where they are."""
    s = appsettings.load()
    if body.storage_location:
        folder = Path(body.storage_location).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(422, f"OAK box can't use that folder: {e.strerror or e}") from e
        s.storage_location = str(folder)
    else:
        s.storage_location = None
    appsettings.save(s)
    return _settings_view()


@router.put("/api/census-key")
def put_census_key(body: CensusKey) -> None:
    """Save the user's Census API key on this computer (OAK box's settings, not the project); empty forgets it."""
    s = appsettings.load()
    s.census_api_key = body.key.strip() or None
    appsettings.save(s)
