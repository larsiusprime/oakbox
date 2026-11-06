"""OAK box's own settings: where projects are kept, which projects it knows about, display, and this computer.

Stored as JSON in the per-user config folder (``%APPDATA%\\OAK box`` on Windows,
``~/.config/oakbox`` on Linux). Projects can live anywhere, so OAK box keeps a list
of their folders by project id.

``OAKBOX_HOME`` (tests, CI, power users) puts everything in one folder: projects in
it, and these settings in ``<OAKBOX_HOME>/.oakbox``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from oakbox import atomic
from oakbox.machine import Machine, Performance

# One change to the settings at a time (the menus' thread and the app's requests both write them).
LOCK = threading.Lock()

# The street map under every map (SPEC §3.11): OpenFreeMap's vector tiles, free, with no key, meant for apps like
# this one (openfreemap.org), in its light grey style, so what OAK box draws reads on top. Its address can be set
# (map_style) to a tile server of one's own.
MAP_STYLE = "https://tiles.openfreemap.org/styles/positron"

# Zoom levels in percent, as browsers step them (View › Zoom in / Zoom out, Ctrl+mouse wheel).
ZOOMS = (67, 75, 80, 90, 100, 110, 125, 150, 175, 200)


def zoom_step(zoom: int, by: int) -> int:
    """The level `by` steps from `zoom` (0: actual size), within the levels."""
    if by == 0:
        return 100
    nearest = min(range(len(ZOOMS)), key=lambda i: abs(ZOOMS[i] - zoom))
    return ZOOMS[max(0, min(len(ZOOMS) - 1, nearest + by))]


class AppSettings(BaseModel):
    storage_location: str | None = Field(default=None, description="None: the default, Documents/OAK box.")
    projects: dict[str, str] = Field(default_factory=dict, description="Project id -> project folder.")
    density: Literal["default", "compact"] | None = Field(
        default=None, description="None: default. Compact: a Windows 2000 dialog's density (SPEC D43)."
    )

    @field_validator("density", mode="before")
    @classmethod
    def _gone_density(cls, v: object) -> object:
        """Comfortable is gone (2026-11-03): a setting that still says it reads as the default."""
        return None if v == "comfortable" else v

    zoom: int = Field(default=100, description="Text and layout size, in percent (one of ZOOMS; SPEC D43).")

    @field_validator("zoom", mode="before")
    @classmethod
    def _a_level(cls, v: object) -> object:
        """Any number reads as the nearest level."""
        return min(ZOOMS, key=lambda z: abs(z - int(v)))  # type: ignore[arg-type]

    @model_validator(mode="before")
    @classmethod
    def _large_text_is_zoom(cls, data: object) -> object:
        """Large text is gone (2026-11-03): a setting that had it on opens at 125%."""
        if isinstance(data, dict) and data.get("large_text") and "zoom" not in data:
            data = {**data, "zoom": 125}
        return data

    recent: list[str] = Field(default_factory=list, description="Project ids, most recently opened first.")
    census_api_key: str | None = Field(default=None, description="The user's own, for the Census enrichment (F3e).")
    machine: Machine | None = Field(default=None, description="What the computer check found (SPEC §5); None: not yet.")
    performance: Performance = Field(default_factory=Performance, description="The performance settings (SPEC §5).")
    map_style: str | None = Field(
        default=None, description="The street map's MapLibre style address; None: OpenFreeMap's (MAP_STYLE)."
    )


def _override() -> Path | None:
    env = os.environ.get("OAKBOX_HOME")
    return Path(env) if env else None


def config_dir() -> Path:
    if (home := _override()) is not None:
        return home / ".oakbox"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "OAK box"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "oakbox"


def documents_dir() -> Path:
    """The user's Documents folder, wherever Windows or the desktop has put it (e.g. OneDrive)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _GUID(ctypes.Structure):
                _fields_ = [
                    ("d1", wintypes.DWORD),
                    ("d2", wintypes.WORD),
                    ("d3", wintypes.WORD),
                    ("d4", ctypes.c_ubyte * 8),
                ]

            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            folder = _GUID(
                0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)
            )
            out = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
            if shell32.SHGetKnownFolderPath(ctypes.byref(folder), 0, None, ctypes.byref(out)) == 0 and out.value:
                path = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)  # type: ignore[attr-defined]
                return path
        except (OSError, AttributeError):
            pass
    else:
        try:
            found = subprocess.run(
                ["xdg-user-dir", "DOCUMENTS"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            if found.returncode == 0 and found.stdout.strip() and Path(found.stdout.strip()) != Path.home():
                return Path(found.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    return Path.home() / "Documents"


def default_storage() -> Path:
    return _override() or documents_dir() / "OAK box"


def legacy_storage() -> Path:
    """Where the first builds kept projects; still searched so they keep appearing."""
    return documents_dir() / "Oakbox"


def _path() -> Path:
    return config_dir() / "settings.json"


def load() -> AppSettings:
    """The settings. A file that can't be read whole (edited by hand, damaged, from a newer OAK box) gives what can
    still be read of it, the rest as default, and a copy is kept beside it before the next save writes over it: the
    list of where projects are is never lost to one bad setting."""
    path = _path()
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return AppSettings()
    try:
        return AppSettings.model_validate_json(data)
    except (ValueError, TypeError):  # TypeError: a validator handed a value of the wrong kind (a zoom of null)
        _keep_damaged(path, data)
        return _salvage(data)


DAMAGED = "settings.damaged.json"


def _keep_damaged(path: Path, data: bytes) -> None:
    """A copy of a settings file that can't be read, beside it, for someone to look at."""
    copy = path.with_name(DAMAGED)
    try:
        if not copy.is_file() or copy.read_bytes() != data:
            copy.write_bytes(data)
    except OSError:
        pass  # the settings still load; only the copy is missing


def _salvage(data: bytes) -> AppSettings:
    """Each setting that reads on its own, and each project folder that's a name and a folder."""
    try:
        raw = json.loads(data)
    except ValueError:
        return AppSettings()
    if not isinstance(raw, dict):
        return AppSettings()
    kept: dict[str, object] = {}
    for key, value in raw.items():
        if key == "projects" and isinstance(value, dict):
            value = {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str)}
        try:
            AppSettings.model_validate({key: value})
        except (ValueError, TypeError):
            continue
        kept[key] = value
    try:
        return AppSettings.model_validate(kept)
    except (ValueError, TypeError):
        return AppSettings()


def save(s: AppSettings) -> None:
    atomic.save_text(_path(), s.model_dump_json(indent=2))


def map_style() -> str:
    """The street map's style address: the one set in the settings (a tile server of one's own), else MAP_STYLE."""
    return load().map_style or MAP_STYLE


def storage_location() -> Path:
    s = load()
    return Path(s.storage_location) if s.storage_location else default_storage()
