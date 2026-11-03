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
    large_text: bool = False


class AppSettingsView(BaseModel):
    storage_location: str
    default_storage_location: str
    display: Display


class CensusKey(BaseModel):
    key: str


class StorageLocation(BaseModel):
    storage_location: str | None = Field(default=None, description="None resets to the default.")


def _settings_view() -> AppSettingsView:
    s = appsettings.load()
    return AppSettingsView(
        storage_location=str(appsettings.storage_location()),
        default_storage_location=str(appsettings.default_storage()),
        display=Display(density=s.density, large_text=s.large_text),
    )


@router.put("/api/app-settings/display")
def put_display(body: Display) -> AppSettingsView:
    """Density and large text (SPEC D43, View menu)."""
    s = appsettings.load()
    s.density, s.large_text = body.density, body.large_text
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
