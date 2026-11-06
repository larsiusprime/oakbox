"""OAK box's own settings on this computer: the display, where projects are kept, the Census API key, and the
computer check with its performance settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from oakbox import appsettings
from oakbox import machine as computer
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
    census_key_end: str | None = Field(description="The saved Census API key's last four characters; None: none.")
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
        census_key_end=s.census_api_key[-4:] if s.census_api_key else None,
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


# ---------- This computer: the check and the performance settings (SPEC §5) ----------


class MachineView(BaseModel):
    """What the check found, and the performance settings: as set, as recommended, and what they come to."""

    machine: computer.Machine | None = Field(description="None: not checked yet (first run).")
    changed: bool = Field(description="Its memory or cores changed since the check: check again.")
    performance: computer.Performance
    recommended: computer.Resolved
    resolved: computer.Resolved
    cores_workers: int = Field(description="How many folds 'as many as the cores allow' runs at once.")
    memory_for_oakbox_gb: float | None = Field(description="Memory left for OAK box once the rest have theirs.")


class Basics(BaseModel):
    memory_gb: float
    memory_free_gb: float
    cores: int
    threads: int
    processor: str
    remote: bool


class Speed(BaseModel):
    speed: int = Field(description="The reference machine = 100.")


class Disk(BaseModel):
    disk_mb_s: int | None = Field(description="None: the projects folder couldn't be written.")


class Found(BaseModel):
    """Everything the check found, the page's graphics test included."""

    memory_gb: float
    memory_free_gb: float | None = None
    cores: int
    threads: int
    processor: str = ""
    remote: bool = False
    speed: int | None = None
    disk_mb_s: int | None = None
    graphics: str | None = None
    draw_ms: int | None = None
    cancelled: bool = False


def _machine_view() -> MachineView:
    s = appsettings.load()
    m = s.machine
    return MachineView(
        machine=m,
        changed=bool(m and not m.cancelled and computer.changed(m)),
        performance=s.performance,
        recommended=computer.recommended(m),
        resolved=computer.resolve(s.performance, m),
        cores_workers=computer.cores_workers(m.threads if m else None),
        memory_for_oakbox_gb=round(computer.memory_for_oakbox_gb(m), 1) if m else None,
    )


@router.get("/api/machine")
def get_machine() -> MachineView:
    return _machine_view()


@router.post("/api/machine/basics")
def check_basics() -> Basics:
    """Memory, processor, cores, remote session (instant)."""
    return Basics(**computer.basics())


@router.post("/api/machine/speed")
def check_speed() -> Speed:
    """OAK box's speed work, timed (a few seconds)."""
    return Speed(speed=computer.speed())


@router.post("/api/machine/disk")
def check_disk() -> Disk:
    """Writing in the projects folder (a second or two)."""
    return Disk(disk_mb_s=computer.disk(appsettings.storage_location()))


@router.put("/api/machine")
def put_machine(body: Found) -> MachineView:
    """Keep what the check found; its tier then decides every setting left at Recommended."""
    with appsettings.LOCK:
        s = appsettings.load()
        s.machine = computer.finish(body.model_dump())
        appsettings.save(s)
    return _machine_view()


@router.put("/api/performance")
def put_performance(body: computer.Performance) -> MachineView:
    with appsettings.LOCK:
        s = appsettings.load()
        s.performance = body
        appsettings.save(s)
    return _machine_view()
