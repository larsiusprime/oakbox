"""This computer: what OAK box found when it checked it, the tier that puts it in, and the performance settings
that follow (SPEC §5). Checked once on first run (and again when its memory or cores change), kept in OAK box's own
settings, not in projects: the same project gives the same values on any computer, only faster or slower.

The checks: memory and processor (instant), speed (a fixed piece of pandas and NumPy work like OAK box's own, in a
process of its own), the disk (writing in the projects folder), and graphics (in the page: WebGL's renderer and a
timed drawing of 20,000 parcels; the page sends what it found).
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Tier = Literal["light", "standard", "strong"]

# The test runs (perf/, 2026-11-05): a fold worker holds about 0.6 GB per 50,000 parcels; with one at a time,
# Finalize peaked at 1.51 GB at 50,000 parcels. Windows, a browser, Outlook, Teams, the CAMA client and antivirus
# leave a computer about this much less for OAK box.
OTHERS_GB = 5.5
BASE_GB = 0.5
PER_50K_GB = 1.0
WORKER_PER_50K_GB = 0.6
DOTS_ABOVE = 20_000  # Map detail "dots above 20,000 parcels": 20,000 dots froze a page 2.1 s at most

# Speed: seconds the speed work took on the reference machine (the test runs' 4-core 2.1 GHz cloud Xeon) = 100.
SPEED_REFERENCE_S = 0.6

SOFTWARE_RENDERERS = ("swiftshader", "llvmpipe", "softpipe", "basic render", "microsoft basic", "software")


class Machine(BaseModel):
    """What the check found."""

    checked_at: str = Field(description="When, local time, ISO 8601.")
    memory_gb: float = Field(description="Installed memory, GB.")
    memory_free_gb: float | None = Field(default=None, description="Free when it was checked, GB.")
    cores: int = Field(description="Physical processor cores.")
    threads: int = Field(description="Logical processors.")
    processor: str = Field(default="", description="The processor's name.")
    remote: bool = Field(default=False, description="A remote session (Remote Desktop, Citrix).")
    speed: int | None = Field(default=None, description="OAK box's speed work, the reference machine = 100.")
    disk_mb_s: int | None = Field(default=None, description="Writing in the projects folder, MB/s.")
    graphics: str | None = Field(default=None, description="The renderer WebGL named; None: no WebGL.")
    graphics_software: bool = Field(default=False, description="Maps are drawn by the processor, not graphics.")
    draw_ms: int | None = Field(default=None, description="Drawing 20,000 parcels on a map, ms.")
    cancelled: bool = Field(default=False, description="The check was cancelled: the safest settings (Light).")
    tier: Tier = "light"


FoldChoice = Literal["recommended", "one", "two", "cores"]
MapsChoice = Literal["recommended", "now", "click"]
Detail = Literal["max", "high", "medium", "low", "verylow"]
DetailChoice = Literal["recommended", "max", "high", "medium", "low", "verylow"]
StreetChoice = Literal["recommended", "on", "off"]


class Performance(BaseModel):
    """The performance settings: each "recommended" (follow the check) or the user's own choice."""

    fold_workers: FoldChoice = Field(default="recommended", description="Model training: folds at once.")
    maps: MapsChoice = Field(default="recommended", description="Maps right away, or when Show map is clicked.")
    map_detail: DetailChoice = Field(
        default="recommended",
        description=(
            "How far zoomed out parcel shapes are still drawn (squares beyond): max always; high until a quarter-acre"
            " lot is 1 px across, medium 8 px, low 16 px, verylow 32 px."
        ),
    )
    street_map: StreetChoice = Field(default="recommended", description="The street map under every map.")

    @field_validator("map_detail", mode="before")
    @classmethod
    def _old_detail(cls, v: object) -> object:
        """Saved before the levels (2026-11-12): always parcels (or shapes) is Max, Auto is Medium, and always squares
        (or dots), gone, the fewest parcels, Very low."""
        old = {"shapes": "max", "parcels": "max", "auto": "medium", "squares": "verylow", "dots": "verylow"}
        return old.get(v, v) if isinstance(v, str) else v


class Resolved(BaseModel):
    """What the settings come to on this computer."""

    fold_workers: Literal["one", "two", "cores"]
    folds_at_once: int = Field(description="How many cross-validation folds run at once.")
    maps: Literal["now", "click"]
    map_detail: Detail
    street_map: Literal["on", "off"]


def tier_of(m: Machine) -> Tier:
    """Memory decides, since memory is what fails; a slow processor or two cores is Light too."""
    if m.cancelled or m.memory_gb < 12 or m.cores <= 2 or (m.speed is not None and m.speed < 60):
        return "light"
    if m.memory_gb >= 24 and m.cores >= 6:
        return "strong"
    return "standard"


# OpenAVMKit's cross-validation folds (modeling.instructions.cv_folds, its default; OAK box doesn't change it). It
# never runs more fold workers than folds, however many cores there are.
CV_FOLDS = 5


def cores_workers(threads: int | None = None) -> int:
    """OpenAVMKit's own default, as it really runs: the logical processors less two, at least one, and never more
    than the folds (an 18-thread computer runs 5 at once, not 16)."""
    return max(1, min(CV_FOLDS, (threads or os.cpu_count() or 2) - 2))


def recommended(m: Machine | None) -> Resolved:
    """The settings the check recommends. No check yet: Standard's."""
    tier = m.tier if m else "standard"
    folds: Literal["one", "two", "cores"] = {"light": "one", "standard": "two", "strong": "cores"}[tier]  # type: ignore[assignment]
    software = bool(m and m.graphics_software)
    light = tier == "light" or software
    return Resolved(
        fold_workers=folds,
        folds_at_once=_folds(folds, m),
        maps="click" if light else "now",
        map_detail="low" if light else "medium",
        street_map="off" if light else "on",
    )


def _folds(choice: Literal["one", "two", "cores"], m: Machine | None) -> int:
    return {"one": 1, "two": 2, "cores": cores_workers(m.threads if m else None)}[choice]


def resolve(p: Performance, m: Machine | None) -> Resolved:
    """Each setting: the user's choice, or the recommendation."""
    r = recommended(m)
    folds = r.fold_workers if p.fold_workers == "recommended" else p.fold_workers
    return Resolved(
        fold_workers=folds,
        folds_at_once=_folds(folds, m),
        maps=r.maps if p.maps == "recommended" else p.maps,
        map_detail=r.map_detail if p.map_detail == "recommended" else p.map_detail,
        street_map=r.street_map if p.street_map == "recommended" else p.street_map,
    )


def apply_folds(settings: dict, folds: int | None = None) -> int:
    """For a Models or Finalize run, in its own process: how many cross-validation folds run at once
    (`cv_max_workers`, into the settings in memory, never the file). With one at a time, the tuning trials run one at
    a time too (`OPENAVMKIT_TUNE_WORKERS=1`): OpenAVMKit otherwise runs them on a thread pool in that one process,
    and two LightGBM trials at once there crash it now and then (a segmentation fault or a floating-point exception:
    measured, 7 runs in 11 on two slow cores, 1 in 3 on four; none in 11 with trials one at a time, in the same time).
    With more folds at once, each fold's process already runs its trials one at a time. The folds at once."""
    n = folds_at_once() if folds is None else folds
    settings.setdefault("modeling", {}).setdefault("instructions", {})["cv_max_workers"] = n
    if n == 1:
        os.environ["OPENAVMKIT_TUNE_WORKERS"] = "1"
    return n


def folds_at_once() -> int:
    """For a Models or Finalize run: how many cross-validation folds to run at once (OpenAVMKit's cv_max_workers).
    The values are the same either way (measured: bit-identical files), so it isn't part of any step's key."""
    from oakbox import appsettings

    s = appsettings.load()
    return resolve(s.performance, s.machine).folds_at_once


def memory_need_gb(parcels: int, workers: int) -> float:
    """About how much memory OAK box's heaviest step needs for a county this size (the test runs' figures)."""
    per = parcels / 50_000
    return BASE_GB + PER_50K_GB * per + WORKER_PER_50K_GB * per * max(0, workers - 1)


def memory_for_oakbox_gb(m: Machine) -> float:
    return max(0.5, m.memory_gb - OTHERS_GB)


def changed(m: Machine) -> bool:
    """Memory or cores changed since the check (a new computer, or one upgraded): time to check again. Never with
    OAKBOX_KEEP_MACHINE=1: the record stays as set (perf/ stands a profile's machine in for this one)."""
    if os.environ.get("OAKBOX_KEEP_MACHINE") == "1":
        return False
    b = basics()
    return abs(b["memory_gb"] - m.memory_gb) >= 1 or b["cores"] != m.cores


# ---------- The checks ----------


def basics() -> dict:
    """Memory, processor, cores, remote session: instant."""
    import psutil

    vm = psutil.virtual_memory()
    threads = psutil.cpu_count(logical=True) or os.cpu_count() or 1
    cores = psutil.cpu_count(logical=False) or threads
    return {
        "memory_gb": round(vm.total / 2**30, 1),
        "memory_free_gb": round(vm.available / 2**30, 1),
        "cores": cores,
        "threads": threads,
        "processor": processor_name(),
        "remote": remote_session(),
    }


def processor_name() -> str:
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(  # type: ignore[attr-defined]
                winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()  # type: ignore[attr-defined]
        if sys.platform == "darwin":
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            return out.stdout.strip()
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return platform.processor() or ""


def remote_session() -> bool:
    """Remote Desktop or Citrix (Windows says so in SESSIONNAME)."""
    name = os.environ.get("SESSIONNAME", "").upper()
    return name.startswith(("RDP-", "ICA-"))


def speed() -> int:
    """OAK box's speed work, timed in a process of its own (so this server's own work doesn't count), as a score."""
    out = subprocess.run(  # noqa: S603 - our own module
        [sys.executable, "-X", "utf8", "-m", "oakbox.machine", "speed"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    seconds = float(out.stdout.strip().splitlines()[-1])
    return max(1, round(100 * SPEED_REFERENCE_S / seconds))


def speed_work() -> float:
    """The work, timed (seconds; best of two). Like OAK box's steps: group, sort, quantile, join and a plain Python
    loop, on a million rows."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(0)
    n = 1_000_000
    df = pd.DataFrame(
        {
            "key": rng.permutation(n).astype(str),
            "group": rng.integers(0, 400, n),
            "area": rng.lognormal(7.5, 0.4, n),
            "price": rng.lognormal(12.5, 0.5, n),
        }
    )
    best = float("inf")
    for _ in range(2):
        t = time.perf_counter()
        g = pd.DataFrame(df.groupby("group").agg(price=("price", "median"), area=("area", "mean")))
        j = df.merge(g, left_on="group", right_index=True, suffixes=("", "_g"))
        j = j.sort_values(["group", "price"])
        q = j.groupby("group")["price"].quantile(np.array([0.1, 0.5, 0.9]))
        r = (j["price"] / j["area"]).rank(pct=True)
        total = 0.0
        for v in j["price"].to_numpy():
            total += v
        best = min(best, time.perf_counter() - t)
        del g, j, q, r
    return best


def disk(folder: Path, mb: int = 128) -> int | None:
    """Writing `mb` MB in `folder` (where projects are kept) and making sure it's on the disk: MB/s. None when it
    can't be written there."""
    block = os.urandom(4 * 2**20)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".oakbox-disk-", dir=folder)
    except OSError:
        return None
    try:
        t = time.perf_counter()
        with os.fdopen(fd, "wb") as f:
            for _ in range(mb // 4):
                f.write(block)
            f.flush()
            os.fsync(f.fileno())
        return max(1, round(mb / (time.perf_counter() - t)))
    except OSError:
        return None
    finally:
        try:
            os.remove(name)
        except OSError:
            pass


def software_renderer(name: str | None) -> bool:
    """No WebGL, or a renderer that draws with the processor."""
    return not name or any(s in name.lower() for s in SOFTWARE_RENDERERS)


def finish(found: dict) -> Machine:
    """The check's results (basics, speed, disk, and what the page found), with its time and tier."""
    m = Machine(checked_at=datetime.now().isoformat(timespec="seconds"), **found)
    m.graphics_software = software_renderer(m.graphics)
    m.tier = tier_of(m)
    return m


if __name__ == "__main__":
    if sys.argv[1:] == ["speed"]:
        print(f"{speed_work():.4f}")
