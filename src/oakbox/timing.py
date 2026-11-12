"""Where a run's time goes (SPEC §5): every step's run leaves a record a user can send for a slow run to be diagnosed.

`out/oakbox/timing/<step>/`, the last run of each step, kept whether it finished or not:
- `timing.json`: the versions, this computer and its performance settings, the run's timeline (each progress line
  and when), its seconds, the CPU seconds and peak memory of its process and the worker processes it started, and how
  it ended.
- `trials.jsonl`: each tuning trial OpenAVMKit finished (its trial log, OPENAVMKIT_TRIAL_LOG): the model, its seconds,
  its params and score, the data it searched on. Written as it goes, so a run stopped halfway still leaves them.

Help › Save a performance report zips them with the runs' receipts and logs (report()).
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

TRIAL_LOG_ENV = "OPENAVMKIT_TRIAL_LOG"
SAMPLE_EVERY = 2.0  # seconds between looks at the run's processes
MAX_LINES = 5000  # timeline lines kept (a long run's progress details)


def folder(project_dir: Path, step: str) -> Path:
    return project_dir / "out" / "oakbox" / "timing" / step


class Recorder:
    """One run's record: started by steps.main before the run, finished after it however it ends."""

    def __init__(self, project_dir: Path, step: str):
        import shutil

        self.dir = folder(project_dir, step)
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.step = step
        self.t0 = time.time()
        self.lines: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.peak_mb = 0.0
        self.peak_workers = 0
        self.child_cpu: dict[int, float] = {}  # each worker's CPU seconds, as last seen
        self.done = threading.Event()
        os.environ[TRIAL_LOG_ENV] = str(self.dir / "trials.jsonl")  # the run's worker processes inherit it
        threading.Thread(target=self._sample, daemon=True).start()

    def line(self, kw: dict[str, Any]) -> None:
        """A progress line the run emitted (not its heartbeats)."""
        if kw.get("beat"):
            return
        with self.lock:
            if len(self.lines) < MAX_LINES:
                self.lines.append({"at": round(time.time() - self.t0, 2), **kw})

    def _sample(self) -> None:
        """Every couple of seconds: the memory of the run and its workers together, and each worker's CPU time
        (a worker's last reading counts once it's gone)."""
        try:
            import psutil
        except ImportError:
            return
        me = psutil.Process()
        while not self.done.wait(SAMPLE_EVERY):
            try:
                kids = me.children(recursive=True)
                rss = me.memory_info().rss
                for k in kids:
                    try:
                        rss += k.memory_info().rss
                        c = k.cpu_times()
                        self.child_cpu[k.pid] = c.user + c.system
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                self.peak_mb = max(self.peak_mb, rss / 2**20)
                self.peak_workers = max(self.peak_workers, len(kids))
            except Exception:  # noqa: BLE001 - a diagnostic: never stops the run
                pass

    def finish(self, error: str | None = None) -> None:
        self.done.set()
        record = {
            "step": self.step,
            "started": datetime.fromtimestamp(self.t0).isoformat(timespec="seconds"),
            "seconds": round(time.time() - self.t0, 2),
            "ended": "error" if error else "done",
            "error": error,
            **_about(),
            "process": _process(self),
            "timeline": self.lines,
            "trials": _trial_summary(self.dir / "trials.jsonl"),
        }
        try:
            (self.dir / "timing.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        except OSError:
            pass


_current: Recorder | None = None


def start(project_dir: Path, step: str) -> Recorder | None:
    """Start recording this process's run (steps.main). A failure to record never stops the run."""
    global _current
    try:
        _current = Recorder(project_dir, step)
    except Exception:  # noqa: BLE001
        _current = None
    return _current


def line(kw: dict[str, Any]) -> None:
    """A progress line, from steps.emit, when a run is being recorded."""
    if _current is not None:
        _current.line(kw)


def _version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _about() -> dict[str, Any]:
    """The versions, this computer, and the performance settings in force."""
    out: dict[str, Any] = {
        "oakbox": _version("oakbox"),
        "openavmkit": _version("openavmkit"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_logical": os.cpu_count(),
        "env": {k: os.environ.get(k) for k in ("OPENAVMKIT_TUNE_WORKERS", "OMP_NUM_THREADS") if os.environ.get(k)},
    }
    try:
        import psutil

        out["cpu_physical"] = psutil.cpu_count(logical=False)
        out["memory_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        from oakbox import appsettings, machine

        s = appsettings.load()
        out["machine"] = s.machine.model_dump() if s.machine else None
        out["performance"] = machine.resolve(s.performance, s.machine).model_dump()
    except Exception as e:  # noqa: BLE001
        out["machine_error"] = str(e)
    return out


def _process(r: Recorder) -> dict[str, Any]:
    """CPU seconds and peak memory: this process, and the workers it started."""
    out: dict[str, Any] = {"peak_mb_with_workers": round(r.peak_mb), "most_workers": r.peak_workers}
    try:
        import psutil

        c = psutil.Process().cpu_times()
        out["cpu_seconds"] = round(c.user + c.system, 1)
        out["worker_cpu_seconds"] = round(sum(r.child_cpu.values()), 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        import resource  # not on Windows

        kids = resource.getrusage(resource.RUSAGE_CHILDREN)
        out["worker_cpu_seconds_finished"] = round(kids.ru_utime + kids.ru_stime, 1)
    except Exception:  # noqa: BLE001
        pass
    return out


def _trial_summary(path: Path) -> list[dict[str, Any]]:
    """Per model: how many trials, their seconds in all, the slowest, and what they searched on."""
    if not path.is_file():
        return []
    by: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            t = json.loads(raw)
        except ValueError:
            continue
        m = by.setdefault(
            t.get("model", "?"),
            {"model": t.get("model"), "trials": 0, "seconds": 0.0, "slowest": 0.0, "pruned": 0, "searches": set()},
        )
        s = t.get("seconds") or 0.0
        m["trials"] += 1
        m["seconds"] += s
        m["slowest"] = max(m["slowest"], s)
        m["pruned"] += t.get("state") == "PRUNED"
        m["searches"].add((t.get("rows"), t.get("features"), t.get("cat_features"), t.get("folds")))
    return [
        {
            **{k: v for k, v in m.items() if k != "searches"},
            "seconds": round(m["seconds"], 1),
            "slowest": round(m["slowest"], 1),
            "searched_on": [
                {"rows": a, "features": b, "cat_features": c, "folds": d}
                for a, b, c, d in sorted(m["searches"], key=str)
            ],
        }
        for m in by.values()
    ]


# ---------- The report a user sends ----------

# Per step: what's kept beside the timing (receipts and what a run depended on; no data).
STEP_FILES = ("receipt.json", "settings.json")
LOG_TAIL = 400_000  # bytes of each run's log kept (its end: where it stopped)


def report(project_dir: Path) -> Path:
    """A zip of the project's run records, for diagnosing a slow run: each step's timing and trial log, its receipt,
    the end of its log, the project's settings for OpenAVMKit (file and field names, no data). Saved in the
    project folder."""
    base = project_dir / "out" / "oakbox"
    name = f"performance-report-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"
    out = project_dir / name
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("about.json", json.dumps(_about(), indent=1, default=str))
        timing = base / "timing"
        if timing.is_dir():
            for f in sorted(timing.rglob("*")):
                if f.is_file():
                    z.write(f, f"timing/{f.relative_to(timing).as_posix()}")
        if base.is_dir():
            for d in sorted(p for p in base.iterdir() if p.is_dir() and p.name != "timing"):
                for fname in STEP_FILES:
                    f = d / fname
                    if f.is_file():
                        z.write(f, f"runs/{d.name}/{fname}")
            for log in sorted(base.glob("*.log")):
                data = log.read_bytes()
                z.writestr(f"logs/{log.name}", data[-LOG_TAIL:])
        s = project_dir / "in" / "settings.json"
        if s.is_file():
            z.write(s, "settings.json")
        from oakbox import applog

        if app_log := applog.tail():  # OAK box's own log: the requests that failed, with their tracebacks
            z.writestr(f"logs/{applog.NAME}", app_log)
    return out
