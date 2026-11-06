"""A pipeline step's machinery, the same for every step (Bring in data, Model groups, Check sales, Check my values,
Prepare the fields, the variable tests, the models).

Each step runs OpenAVMKit in a process of its own (`python -m oakbox.<module> <project id>`), which prints a JSON
line at each part; the app follows them as the step's job. A finished run leaves a folder, out/oakbox/<module>/,
holding its receipt (receipt.json) and what it depended on (settings.json): the step is out of date when what it
depends on now hashes differently, and accepted (Looks right) when the hash it was accepted at is still the one.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, cast

import pydantic
from pydantic import Field

from oakbox.datafiles import BaseModel

if TYPE_CHECKING:
    from oakbox.projects import Project

Status = Literal["never", "running", "failed", "stopped", "done"]


# ---------- The job, from the app ----------


class Progress(BaseModel):
    step: str
    message: str
    fraction: float | None
    at: float = Field(description="Seconds since the run started.")


class Job(BaseModel):
    status: Literal["running", "failed", "stopped", "done"]
    started: float
    steps: list[Progress] = Field(default_factory=list)
    error: str | None = None
    elapsed: float = Field(default=0.0, description="Seconds since it started, as of this answer.")
    quiet: float = Field(default=0.0, description="Seconds since the run last said anything (it says so every 2).")
    detail: str | None = Field(default=None, description="What the current step is doing: 'Parks (2 of 4)'.")
    sub: float | None = Field(default=None, description="How far through the current step, 0-1, when known.")
    part: str | None = Field(default=None, description="The current step can be skipped: its name.")
    skipping: list[str] = Field(default_factory=list, description="Parts asked to be skipped.")
    heard: float = Field(default=0.0, exclude=True, description="When the run last said anything (epoch).")


_jobs: dict[str, Job] = {}
_procs: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


# ---------- Where things are in a project (docs/ARCHITECTURE.md, "A project on disk") ----------

Notebook = Literal["1-assemble", "2-clean"]  # OpenAVMKit's notebooks whose output a later step starts from


def out_dir(project_dir: Path, module: str) -> Path:
    """OAK box's own folder for a step: its last finished run (receipt.json, settings.json, its tables)."""
    return project_dir / "out" / "oakbox" / module


def settings_path(project_dir: Path) -> Path:
    """The project's settings as written for OpenAVMKit (projects.write_settings)."""
    return project_dir / "in" / "settings.json"


def handoff(project_dir: Path, notebook: Notebook) -> Path:
    """A notebook's hand-off as OpenAVMKit writes it (write_notebook_output_sup): out/<notebook>-sup.pickle."""
    return project_dir / "out" / f"{notebook}-sup.pickle"


def look_dir(project_dir: Path) -> Path:
    """Where OpenAVMKit writes a notebook's tables to look at (Parquet, and the formats asked for)."""
    return project_dir / "out" / "look"


def look(project_dir: Path, name: str) -> Path:
    """One of those tables, as Parquet: look(pdir, "2-clean-universe")."""
    return look_dir(project_dir) / f"{name}.parquet"


APP_PID = "OAKBOX_APP_PID"  # a run's environment: the app that started it, which it doesn't outlive (die_with_app)


def command(module: str, project_id: str) -> list[str]:
    """How a step's process is started (tests start something else here)."""
    return [sys.executable, "-X", "utf8", "-m", f"oakbox.{module}", project_id]


def start(project_id: str, project_dir: Path, module: str) -> Job:
    """Run `python -m oakbox.<module> <project id>` in a process of its own, following the JSON step lines it
    prints. One run per module and project at a time; its log is out/oakbox/<module>.log.

    On Linux and macOS the run leads a process group of its own, so stopping it reaches every process it started
    (OpenAVMKit's workers), and none of them gets the terminal's Ctrl+C meant for the app."""
    key = f"{module}:{project_id}"
    with _lock:
        if key in _jobs and _jobs[key].status == "running":
            raise ValueError("It's already running.")
        log = out_dir(project_dir, module).with_suffix(".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as err:  # the run has its own handle; the app keeps none open
            proc = subprocess.Popen(  # noqa: S603 - our own module, with the project's id
                command(module, project_id),
                stdout=subprocess.PIPE,
                stderr=err,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**child_env(), APP_PID: str(os.getpid())},
                start_new_session=sys.platform != "win32",
            )
        job = Job(status="running", started=time.time(), heard=time.time())
        _jobs[key], _procs[key] = job, proc

    def follow() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # OpenAVMKit prints as it goes
            if not isinstance(msg, dict):
                continue
            job.heard = time.time()
            if "step" in msg:
                job.steps.append(
                    Progress(
                        step=msg["step"],
                        message=msg["message"],
                        fraction=msg.get("fraction"),
                        at=time.time() - job.started,
                    )
                )
                job.detail, job.sub, job.part = None, None, msg.get("part")
            elif "detail" in msg:
                job.detail, job.sub = msg["detail"], msg.get("sub")
                job.part = msg.get("part") or job.part
        code = proc.wait()
        if job.status == "running":
            if code == 0:
                job.status = "done"
            else:
                job.status = "failed"
                lines = log.read_text(errors="replace", encoding="utf-8").strip().splitlines() if log.is_file() else []
                job.error = failure(code, lines)

    threading.Thread(target=follow, daemon=True).start()
    return job


OUT_OF_MEMORY = "It ran out of memory. Close other programs and run it again, or try fewer variables or models."
_KILLED = (-9, 137, 0xC0000017, 3221225495)  # SIGKILL (the out-of-memory killer), as a code or a shell's 128 + 9;
# Windows' STATUS_NO_MEMORY and STATUS_COMMITMENT_LIMIT
_ERROR_LINE = re.compile(r"^[A-Za-z_][\w.]*(Error|Exception)\b")


def failure(code: int, lines: list[str]) -> str:
    """What to tell the user when a run stops with `code`, from the end of its log: running out of memory said as
    that (the process killed, a MemoryError, or a worker of its killed), else the exception the log ends with, not
    whatever it printed last (a warning's second line, say)."""
    tail = lines[-200:]
    if code in _KILLED or any(
        x.startswith(("MemoryError", "numpy.core._exceptions._ArrayMemoryError", "numpy._core._exceptions"))
        or "TerminatedWorkerError" in x
        or "Unable to allocate" in x
        for x in tail
    ):
        return OUT_OF_MEMORY
    for x in reversed(tail):
        if _ERROR_LINE.match(x):
            return x
    return tail[-1] if tail else f"stopped with code {code}"


def child_env() -> dict[str, str]:
    """A run's environment: Python's UTF-8 mode, so OpenAVMKit reads, writes and prints UTF-8 on Windows too (not
    the code page, cp1252, which can't write a "−"); and the user's keys for public data."""
    return {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONWARNINGS": "ignore::DeprecationWarning",
        **_keys(),
    }


def _keys() -> dict[str, str]:
    """The user's own keys for public data, from OAK box's settings, as OpenAVMKit reads them."""
    from oakbox import appsettings

    key = appsettings.load().census_api_key
    return {"CENSUS_API_KEY": key} if key else {}


def stop(project_id: str, module: str) -> None:
    """Stop a run and every process it started; the page isn't kept waiting while they go."""
    key = f"{module}:{project_id}"
    proc = _procs.get(key)
    job = _jobs.get(key)
    if proc is None or job is None or job.status != "running":
        return
    job.status = "stopped"
    threading.Thread(target=end, args=(proc,), daemon=True).start()


def stop_all() -> None:
    """Stop every run going, and every process they started, and wait until they've gone: when the app closes, no
    process of OAK box's is left behind. Safe to call more than once."""
    with _lock:
        going = [(key, p) for key, p in _procs.items() if p.poll() is None]
    for key, _ in going:
        if (j := _jobs.get(key)) is not None and j.status == "running":
            j.status = "stopped"
    threads = [threading.Thread(target=end, args=(p,)) for _, p in going]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def end(proc: subprocess.Popen, grace: float = 3.0) -> None:
    """End a run's process and every process it started: asked to stop, then killed if still there after `grace`
    seconds. On Linux and macOS its whole process group (see start), which also takes workers started after the
    family was listed."""
    import psutil

    try:
        family = [psutil.Process(proc.pid), *psutil.Process(proc.pid).children(recursive=True)]
    except psutil.NoSuchProcess:
        family = []
    group = proc.pid if sys.platform != "win32" else None

    def signal_all(sig: int) -> None:
        if group is not None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(group, sig)
        for p in family:
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                if sig == _KILL:
                    p.kill()
                else:
                    p.send_signal(sig)

    signal_all(signal.SIGTERM)
    _, alive = psutil.wait_procs(family, timeout=grace)
    if alive or group is not None:
        signal_all(_KILL)  # the group again too: a worker started meanwhile isn't in the family
        psutil.wait_procs(alive, timeout=grace)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=grace)


_KILL = getattr(signal, "SIGKILL", signal.SIGTERM)  # Windows: psutil's kill() is TerminateProcess


def job(project_id: str, module: str) -> Job | None:
    j = _jobs.get(f"{module}:{project_id}")
    if j is not None and j.status == "running":
        now = time.time()
        j.elapsed, j.quiet = now - j.started, now - j.heard
    return j


def running_projects() -> list[str]:
    """The ids of the projects with a run going now, whichever step."""
    return sorted({key.split(":", 1)[1] for key, j in _jobs.items() if j.status == "running"})


def skip_path(project_dir: Path, module: str) -> Path:
    """Where the app asks a running run to skip a part (one name per line): the run checks it at each checkpoint."""
    return out_dir(project_dir, module).with_suffix(".skip")


def skip(project_id: str, project_dir: Path, part: str, module: str) -> None:
    """Ask a running run to skip one part: it stops at its next checkpoint, and the run carries on."""
    j = _jobs.get(f"{module}:{project_id}")
    if j is None or j.status != "running":
        raise ValueError("Nothing is running.")
    path = skip_path(project_dir, module)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(part + "\n")
    if part not in j.skipping:
        j.skipping.append(part)


# ---------- In the run ----------

_emit_lock = threading.Lock()


def emit(**kw) -> None:
    """One line of progress for the app, on the real stdout: enrichments capture what OpenAVMKit prints, and the
    heartbeat writes from its own thread."""
    out = sys.__stdout__
    if out is None:
        return
    with _emit_lock:
        out.write(json.dumps(kw) + "\n")
        out.flush()


HEARTBEAT = 2.0  # seconds between "still working" lines from a run


@contextmanager
def heartbeat() -> Iterator[None]:
    """Says "still working" every couple of seconds while OpenAVMKit is busy, so the app can tell a long part from
    a stuck run."""
    done = threading.Event()

    def beat() -> None:
        while not done.wait(HEARTBEAT):
            emit(beat=True)

    threading.Thread(target=beat, daemon=True).start()
    try:
        yield
    finally:
        done.set()


def skipper(path: Path) -> Callable[[str], bool]:
    """The run's skip check: is this part in the skip file? Read at most every half second."""
    seen: dict[str, object] = {"at": 0.0, "parts": set()}

    def check(part: str) -> bool:
        now = time.time()
        if now - cast(float, seen["at"]) > 0.5:
            seen["at"] = now
            try:
                seen["parts"] = set(path.read_text(encoding="utf-8").split())
            except OSError:
                seen["parts"] = set()
        return part in cast(set, seen["parts"])

    return check


def written(caught, what: str) -> None:
    """OpenAVMKit's write_notebook_output_sup catches its own errors and only warns ("Failed to output sup"), which
    leaves a step's hand-off half written: here it fails the run, saying why."""
    for w in caught:
        text = str(w.message)
        if text.startswith("Failed to output sup"):
            reason = text.removeprefix("Failed to output sup:").strip()
            raise RuntimeError(f"OpenAVMKit couldn't write {what}: {reason}")


def engine_notes(caught) -> list:
    """OpenAVMKit's own warnings among those a run caught (not pandas' or numpy's): what its receipt's notes say."""
    return [w for w in caught if "openavmkit" in str(w.filename) and issubclass(w.category, UserWarning)]


def workdir(final: Path) -> Path:
    """An empty folder beside a run's output, to write into until it's finished."""
    tmp = final.with_suffix(".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    return tmp


def publish(tmp: Path, final: Path) -> None:
    """Put a finished run's folder in place of the last run's: the old one is moved aside first and removed after,
    so a run that fails halfway leaves the last one as it was."""
    old = final.with_suffix(".old")
    shutil.rmtree(old, ignore_errors=True)
    if final.exists():
        os.replace(final, old)
    os.replace(tmp, final)
    shutil.rmtree(old, ignore_errors=True)


def read_settings(project_dir: Path) -> dict:
    """The project's settings as written for OpenAVMKit (in/settings.json), as they stand."""
    return json.loads(settings_path(project_dir).read_text(encoding="utf-8"))


def engine_settings(project_dir: Path) -> dict:
    """The same, as OpenAVMKit reads them (its defaults filled in)."""
    from openavmkit.utilities.settings import load_settings

    return cast(dict, load_settings(str(settings_path(project_dir)), warning=False))


# The files the runs write, in words (by the start of their name).
WRITTEN = {
    "1-assemble-sup.pickle": "the parcel universe and sales together: what notebook 2 (clean) starts from",
    "1-assemble-universe": "the parcel universe, with each parcel's model group",
    "1-assemble-sales-hydrated": "the sales, each with its parcel's fields and model group",
    "1-assemble-sales": "the sales record",
    "2-clean-sup.pickle": "the parcels and the sales for modeling: what notebook 3 (model) starts from",
    "2-clean-universe": "the parcel universe, filled and clustered",
    "2-clean-sales-hydrated": "the sales for modeling, each with its parcel's fields",
    "2-clean-sales": "the sales record",
}


def what_written(name: str) -> str:
    """What a file a run wrote holds, in words."""
    return next((what for prefix, what in WRITTEN.items() if name.startswith(prefix)), "")


def key_hash(key: Any) -> str:
    """A short fingerprint of what a step depends on."""
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]


def die_with_app(every: float = 1.0) -> None:
    """In a run: when the app that started it is gone, however it went (closed, crashed, killed), end every process
    the run started, then the run itself. The app stops its runs as it closes (stop_all); this covers the ways it
    can't. A run started by hand (no OAKBOX_APP_PID) has no app to follow."""
    pid = os.environ.get(APP_PID)
    if not pid:
        return
    import psutil

    try:
        app = psutil.Process(int(pid))
    except (ValueError, psutil.NoSuchProcess):
        app = None

    def watch() -> None:
        # is_running() also notices the app's number taken by a new process (it compares start times).
        while app is not None and app.is_running():
            time.sleep(every)
        with contextlib.suppress(psutil.Error):
            for child in psutil.Process().children(recursive=True):
                with contextlib.suppress(psutil.Error):
                    child.kill()
        os._exit(1)

    threading.Thread(target=watch, daemon=True).start()


def main(run: Callable[[str], None]) -> None:
    """A step's process: run it for the project named on the command line; on an error, the log's last line says
    what went wrong (the app shows it)."""
    die_with_app()
    from oakbox.net import use_system_certificates

    use_system_certificates()
    from oakbox import engines

    engines.activate()  # the app passes PYTHONPATH on; this covers a run started by hand
    try:
        run(sys.argv[1])
    except Exception as e:  # noqa: BLE001 - the app shows the last line of the log
        traceback.print_exc()
        print(f"{type(e).__name__}: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


# ---------- The step's state, from the app ----------

R = TypeVar("R", bound=pydantic.BaseModel)


def read(base: Path, model: type[R]) -> tuple[R | None, dict | None]:
    """A finished run's receipt and what it depended on; nothing if it never ran, or if an earlier OAK box wrote a
    receipt this one can't read (run it again)."""
    if not (base / "receipt.json").is_file():
        return None, None
    path = base / "settings.json"
    try:
        ran = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        return model.model_validate_json((base / "receipt.json").read_text(encoding="utf-8")), ran
    except ValueError:
        return None, None


class RunView(BaseModel):
    """What every step's screen is told: where it is, and whether its last run still holds."""

    status: Status
    job: Job | None
    stale: bool = Field(description="Something it depends on changed since it ran.")
    blocked: list[str] = Field(description="What stops it running.")


@dataclass
class State(Generic[R]):
    status: Status
    job: Job | None
    receipt: R | None
    ran: dict | None
    stale: bool
    accepted: bool
    waiting: str | None = None
    now: str | None = field(default=None, repr=False)


def _hash_field(ran: dict) -> str | None:
    return ran.get("hash")


@dataclass(frozen=True)
class Step(Generic[R]):
    """One step: its module, its title (what its run is called: "Check sales"), its receipt, what it depends on now
    (`key`), and the fingerprint its last run left (`ran_hash`, from what the run wrote to settings.json: by default
    its "hash"). `place` is where its Looks right is, when that isn't the title (its tab: "Sales").

    A step is out of date when its own calls change or the step it starts from (`after`) has run again since
    (its key holds that step's `ran_at`); nothing further back. A change further back shows where it was made, and
    every step after that one waits for it: a step can start, and be accepted, only once each step before it is
    accepted on an up-to-date run."""

    module: str
    title: str
    receipt: type[R]
    key: Callable[[Project, Path], Any]
    after: Step | None = None
    ran_hash: Callable[[dict], str | None] = _hash_field
    again: str = "Run it again first: something changed since it ran."
    place: str | None = None  # where its Looks right is, in words, when not its title: "Sales" (its tab), not the run

    def out_dir(self, project_dir: Path) -> Path:
        return out_dir(project_dir, self.module)

    def ran(self, project_dir: Path) -> tuple[R | None, dict | None]:
        return read(self.out_dir(project_dir), self.receipt)

    def ran_at(self, project_dir: Path) -> str | None:
        """When its last run finished: what a step after it follows. A new run puts every step after it out of
        date."""
        r, _ = self.ran(project_dir)
        return cast(str | None, getattr(r, "ran_at", None)) if r else None

    def now(self, project: Project, project_dir: Path) -> str:
        return key_hash(self.key(project, project_dir))

    def state(self, project: Project, project_dir: Path, now: str | None = None, check: bool = True) -> State[R]:
        """Its job, receipt and whether the receipt still holds; and what an earlier step needs first, if anything.
        `check=False` when what it depends on can't be worked out yet (it's blocked): then it isn't called out of
        date."""
        s = self._own(project, project_dir, now, check)
        s.waiting = self.waiting(project, project_dir)
        s.accepted = s.accepted and s.waiting is None
        return s

    def waiting(self, project: Project, project_dir: Path) -> str | None:
        """What the earliest step before this one that isn't accepted on an up-to-date run needs, in words; None
        when each is."""
        if self.after is None:
            return None
        up = self.after.waiting(project, project_dir)
        if up:
            return up
        s = self.after._own(project, project_dir)
        if s.accepted:
            return None
        if s.receipt is not None and s.stale:
            return f"Run {self.after.title} again first: something it depends on changed since it ran."
        return f"Press Looks right on {self.after.place or self.after.title} first: this starts from what it wrote."

    def _own(self, project: Project, project_dir: Path, now: str | None = None, check: bool = True) -> State[R]:
        r, ran = self.ran(project_dir)
        j = job(project.id, self.module)
        if check and now is None:
            now = self.now(project, project_dir)
        stale = bool(r and ran and now and self.ran_hash(ran) != now)
        return State(
            status=j.status if j else ("done" if r else "never"),
            job=j,
            receipt=r,
            ran=ran,
            stale=stale,
            accepted=bool(r and now and not stale and project.accepted.get(self.module) == now),
            now=now,
        )

    def accepted(self, project: Project, project_dir: Path) -> bool:
        """Looks right was pressed on its last run, and nothing it depends on has changed since."""
        return self.state(project, project_dir).accepted

    def accept(self, project: Project, project_dir: Path) -> None:
        s = self.state(project, project_dir)
        if s.waiting:
            raise ValueError(s.waiting)
        if s.receipt is None or s.stale or s.now is None:
            raise ValueError(self.again)
        project.accepted[self.module] = s.now

    def start(self, project_id: str, project_dir: Path, blocked: list[str]) -> Job:
        if blocked:
            raise ValueError(blocked[0])
        return start(project_id, project_dir, self.module)

    def stop(self, project_id: str) -> None:
        stop(project_id, self.module)

    def job(self, project_id: str) -> Job | None:
        return job(project_id, self.module)
