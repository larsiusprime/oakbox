"""OAK box's own settings: where projects are kept, which projects it knows about, and display.

Stored as JSON in the per-user config folder (``%APPDATA%\\OAK box`` on Windows,
``~/.config/oakbox`` on Linux). Projects can live anywhere, so OAK box keeps a list
of their folders by project id.

``OAKBOX_HOME`` (tests, CI, power users) puts everything in one folder: projects in
it, and these settings in ``<OAKBOX_HOME>/.oakbox``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    storage_location: str | None = Field(default=None, description="None: the default, Documents/OAK box.")
    projects: dict[str, str] = Field(default_factory=dict, description="Project id -> project folder.")
    density: Literal["compact", "comfortable"] | None = Field(
        default=None, description="None: compact, or comfortable on touch screens (SPEC D43)."
    )
    large_text: bool = False
    high_contrast: bool = False
    recent: list[str] = Field(default_factory=list, description="Project ids, most recently opened first.")
    census_api_key: str | None = Field(default=None, description="The user's own, for the Census enrichment (F3e).")


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
            found = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=5)
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
    try:
        return AppSettings.model_validate_json(_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return AppSettings()


def save(s: AppSettings) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(s.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)


def storage_location() -> Path:
    s = load()
    return Path(s.storage_location) if s.storage_location else default_storage()
