"""Model engines that don't come with OAK box: XGBoost and CatBoost (SPEC §6, Optional engines).

Together they'd add about 560 MB to every install, for engines LightGBM already covers, so the bundle leaves them
out and fetches one when the user first asks for it (or ticks it in the installer). What to fetch is fixed when the
bundle is built: `engines.json`, beside this module, lists each engine's wheels for this platform, from uv.lock, with
their sha256 (packaging/engines_manifest.py). Nothing else is downloaded, and a wheel that doesn't match is refused.

Each engine unpacks into a folder of its own, per user (%LOCALAPPDATA%\\OAK box\\engines\\<engine> on Windows,
~/.local/share/oakbox/engines/<engine> on Linux; <OAKBOX_HOME>/.oakbox/engines with OAKBOX_HOME), so removing one is
deleting its folder. `activate()` puts the installed ones after the bundle's own site-packages on sys.path, and on
PYTHONPATH for the processes a run starts. A folder written for other wheels (an older OAK box's) is left off, so
the engine reads as not installed and is fetched again.

From a checkout there's no engines.json: an engine is there if uv installed it (uv sync --extra xgboost).

    python -m oakbox.engines list
    python -m oakbox.engines install xgboost catboost
    python -m oakbox.engines remove xgboost
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Engine key (as model.ENGINES has it) -> (its name, the module that has to import).
OPTIONAL: dict[str, tuple[str, str]] = {"xgboost": ("XGBoost", "xgboost"), "catboost": ("CatBoost", "catboost")}
MARKER = "engine.json"


class Wheel(BaseModel):
    filename: str
    url: str
    sha256: str
    size: int


class EngineFiles(BaseModel):
    wheels: list[Wheel]
    disk: int = Field(description="Bytes once unpacked.")

    @property
    def download(self) -> int:
        return sum(w.size for w in self.wheels)


class Manifest(BaseModel):
    platform: str
    engines: dict[str, EngineFiles]


class Install(BaseModel):
    """One engine's download, while it runs and after."""

    status: Literal["running", "done", "failed", "stopped"]
    done: int = 0
    total: int = 0
    unpacking: bool = False
    error: str | None = None


class EngineState(BaseModel):
    key: str
    name: str
    installed: bool
    can_install: bool = Field(description="Bundles can; a checkout installs with uv sync --extra <key>.")
    download: int | None = Field(default=None, description="Bytes to download.")
    disk: int | None = Field(default=None, description="Bytes on disk once installed.")
    install: Install | None = None


class Stopped(Exception):
    pass


# ---------- Where, and what ----------


def engines_dir() -> Path:
    home = os.environ.get("OAKBOX_HOME")
    if home:
        return Path(home) / ".oakbox" / "engines"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "OAK box" / "engines"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "oakbox" / "engines"


def manifest_path() -> Path:
    return Path(__file__).with_name("engines.json")


def manifest() -> Manifest | None:
    p = manifest_path()
    return Manifest.model_validate_json(p.read_text(encoding="utf-8")) if p.is_file() else None


def _site(key: str) -> Path:
    return engines_dir() / key / "site"


def _current(key: str, m: Manifest | None) -> bool:
    """The engine's folder holds exactly the wheels this OAK box lists for it."""
    if m is None or key not in m.engines:
        return False
    try:
        had = json.loads((engines_dir() / key / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return had.get("wheels") == [w.filename for w in m.engines[key].wheels]


def activate() -> None:
    """Make installed engines importable here and in the processes started from here: after the bundle's own
    site-packages, so its libraries always win."""
    m = manifest()
    paths = [str(_site(k)) for k in OPTIONAL if _current(k, m)]
    for p in paths:
        if p not in sys.path:
            sys.path.append(p)
    if paths:
        have = [x for x in os.environ.get("PYTHONPATH", "").split(os.pathsep) if x]
        os.environ["PYTHONPATH"] = os.pathsep.join(have + [p for p in paths if p not in have])
    import importlib

    importlib.invalidate_caches()


def installed(key: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(OPTIONAL[key][1]) is not None


def missing(keys: set[str] | list[str]) -> list[str]:
    """Of these engine keys, the optional ones not installed, by name."""
    return [OPTIONAL[k][0] for k in OPTIONAL if k in keys and not installed(k)]


def states() -> list[EngineState]:
    m = manifest()
    out = []
    for key, (name, _) in OPTIONAL.items():
        files = m.engines.get(key) if m else None
        job = _jobs.get(key)
        out.append(
            EngineState(
                key=key,
                name=name,
                installed=installed(key),
                can_install=files is not None,
                download=files.download if files else None,
                disk=files.disk if files else None,
                install=job.model_copy() if job else None,
            )
        )
    return out


# ---------- Installing ----------


def _fetch(w: Wheel, to: Path, progress: Callable[[int], None], stop: threading.Event) -> None:
    import urllib.request

    from oakbox.net import USER_AGENT

    req = urllib.request.Request(w.url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    got = 0
    with urllib.request.urlopen(req, timeout=60) as r, to.open("wb") as f:  # noqa: S310 - a URL from engines.json
        while chunk := r.read(1 << 20):
            if stop.is_set():
                raise Stopped
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            progress(len(chunk))
    if got != w.size or h.hexdigest() != w.sha256:
        raise RuntimeError(f"{w.filename} didn't download whole (its checksum doesn't match). Try again.")


def _unpack(wheel: Path, site: Path) -> None:
    """A wheel into a site-packages folder, as pip would for a --target install: its <name>.data/purelib and
    platlib merged in; scripts, headers and data left out (nothing here runs them)."""
    with zipfile.ZipFile(wheel) as z:
        for info in z.infolist():
            parts = Path(info.filename).parts
            if not parts or info.is_dir():
                continue
            if parts[0].endswith(".data"):
                if len(parts) < 3 or parts[1] not in ("purelib", "platlib"):
                    continue
                parts = parts[2:]
            dest = site.joinpath(*parts)
            if site.resolve() not in dest.resolve().parents:
                raise RuntimeError(f"{wheel.name} has a file outside its folder: {info.filename}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(info))  # one file at a time (XGBoost's largest is 144 MB)


def install(key: str, progress: Callable[[int, int], None] | None = None, stop: threading.Event | None = None) -> None:
    """Download, check and unpack one engine; on any failure (or a stop) nothing is left behind and an installed
    copy, if there was one, stays as it was."""
    m = manifest()
    if m is None or key not in m.engines:
        raise RuntimeError(f"This OAK box can't download {OPTIONAL[key][0]}: run uv sync --extra {key}.")
    files, stop = m.engines[key], stop or threading.Event()
    root = engines_dir()
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f".{key}-{uuid.uuid4().hex[:8]}"
    (tmp / "site").mkdir(parents=True)
    done, total = 0, files.download

    def step(n: int) -> None:
        nonlocal done
        done += n
        if progress:
            progress(done, total)

    try:
        for w in files.wheels:
            _fetch(w, tmp / w.filename, step, stop)
        if progress:
            progress(-1, total)  # unpacking
        for w in files.wheels:
            _unpack(tmp / w.filename, tmp / "site")
            (tmp / w.filename).unlink()
        if stop.is_set():
            raise Stopped
        (tmp / MARKER).write_text(
            json.dumps({"wheels": [w.filename for w in files.wheels], "at": time.time()}), encoding="utf-8"
        )
        _replace(root / key, tmp)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    activate()


def _replace(final: Path, new: Path) -> None:
    if final.exists():
        old = final.with_name(f".{final.name}-old-{uuid.uuid4().hex[:8]}")
        final.rename(old)  # Windows: refused while a run has its files open; nothing changed then
        new.rename(final)
        shutil.rmtree(old, ignore_errors=True)
    else:
        new.rename(final)


def remove(key: str) -> None:
    folder = engines_dir() / key
    if not folder.exists():
        return
    gone = folder.with_name(f".{key}-gone-{uuid.uuid4().hex[:8]}")
    try:
        folder.rename(gone)
    except OSError as e:
        raise RuntimeError(f"{OPTIONAL[key][0]} is in use: let the run that uses it finish, then try again.") from e
    shutil.rmtree(gone, ignore_errors=True)
    p = str(_site(key))
    if p in sys.path:
        sys.path.remove(p)
    os.environ["PYTHONPATH"] = os.pathsep.join(x for x in os.environ.get("PYTHONPATH", "").split(os.pathsep) if x != p)
    import importlib

    importlib.invalidate_caches()


def tidy() -> None:
    """Leftovers of an install or removal the app was closed during."""
    root = engines_dir()
    if root.is_dir():
        for p in root.iterdir():
            if p.name.startswith(".") and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)


# ---------- Installing from the app: one at a time per engine, in the background ----------

_jobs: dict[str, Install] = {}
_stops: dict[str, threading.Event] = {}
_lock = threading.Lock()


def start(key: str) -> Install:
    with _lock:
        if key in _jobs and _jobs[key].status == "running":
            return _jobs[key]
        m = manifest()
        if m is None or key not in m.engines:
            raise ValueError(f"This OAK box can't download {OPTIONAL[key][0]}: run uv sync --extra {key}.")
        job = Install(status="running", total=m.engines[key].download)
        stop = threading.Event()
        _jobs[key], _stops[key] = job, stop

    def progress(done: int, total: int) -> None:
        if done < 0:
            job.unpacking = True
        else:
            job.done, job.total = done, total

    def go() -> None:
        try:
            install(key, progress, stop)
            job.status = "done"
        except Stopped:
            job.status = "stopped"
        except Exception as e:  # noqa: BLE001 - shown to the user
            job.status, job.error = "failed", _say(e)

    threading.Thread(target=go, daemon=True).start()
    return job


def stop(key: str) -> None:
    if key in _stops:
        _stops[key].set()


def forget(key: str) -> None:
    """The finished job's outcome has been seen."""
    with _lock:
        if key in _jobs and _jobs[key].status != "running":
            del _jobs[key]


def _say(e: Exception) -> str:
    import urllib.error

    if isinstance(e, urllib.error.URLError | TimeoutError | ConnectionError):
        return "It couldn't download: check the internet connection, then try again."
    if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
        return "There isn't enough disk space for it."
    return str(e)


# ---------- From the command line (the installer runs this) ----------


def _mb(n: int | None) -> str:
    return f"{n / 1e6:.0f} MB" if n else "?"


def main(argv: list[str] | None = None) -> int:
    import argparse

    from oakbox.net import use_system_certificates

    use_system_certificates()
    p = argparse.ArgumentParser(prog="python -m oakbox.engines")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for cmd in ("install", "remove"):
        sub.add_parser(cmd).add_argument("engines", nargs="+", choices=list(OPTIONAL))
    args = p.parse_args(argv)
    activate()
    if args.cmd == "list":
        for s in states():
            how = "installed" if s.installed else f"not installed ({_mb(s.download)} download, {_mb(s.disk)} on disk)"
            print(f"{s.key:10} {how}")
        return 0
    for key in args.engines:
        if args.cmd == "remove":
            remove(key)
            print(f"{OPTIONAL[key][0]} removed")
            continue
        if _current(key, manifest()):
            print(f"{OPTIONAL[key][0]} is installed already")  # e.g. an update that keeps the installer's ticks
            continue
        last = [0.0]

        def show(done: int, total: int, name: str = OPTIONAL[key][0], last: list[float] = last) -> None:
            if done < 0:
                print(f"{name}: unpacking", flush=True)
            elif time.time() - last[0] > 2 or done == total:
                last[0] = time.time()
                print(f"{name}: {_mb(done)} of {_mb(total)}", flush=True)

        try:
            install(key, show)
        except Exception as e:  # noqa: BLE001
            print(f"{OPTIONAL[key][0]}: {_say(e)}", file=sys.stderr)
            return 1
        print(f"{OPTIONAL[key][0]} installed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
