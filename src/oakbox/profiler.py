"""Where a slow request spent its time: a sampling profiler for the service, so a slow click can be diagnosed from
the log alone.

While any request is under way, a thread looks at every thread's stack every few milliseconds (sys._current_frames:
cheap; a look keeps what it saw as it is, and only a request that turns out slow has its looks made sense of).

Whose a look is: whatever runs on a worker thread for a request (a route function that isn't async, its
dependencies) runs wrapped (install), so while it runs, the thread it runs on is known to be that request's. The
service's own thread (the event loop: reading requests, turning answers into JSON) is shared by every request under
way, and is reported as such. Work on a thread of another request under way is "another request working at the same
time": they shared the computer.

When a request turns out slow (app.SLOW), the log gets where its time went: the deepest frames in OAK box's and
OpenAVMKit's own code, each with the path of calls that led there and the library it was inside (pandas, pyarrow, ...);
the functions that took most, counting what they call; and the other work at the same time.

A look can't tell running from waiting on Python's lock (the GIL) while another thread runs; "at the same time" is what
says it shared it.
"""

from __future__ import annotations

import contextvars
import functools
import importlib.util
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from types import CodeType, FrameType
from typing import Any

EVERY = 0.01  # seconds between looks
ON = os.environ.get("OAKBOX_PROFILE", "1") != "0"  # OAKBOX_PROFILE=0: no looks (slow requests still logged)
MAX_DEPTH = 120  # frames looked at in one stack
TOP = 8  # places listed per slow request

# A thread whose innermost Python frame is in one of these is waiting, not working: a thread pool's idle worker,
# the event loop between events, a lock.
_IDLE_FILES = (
    "threading.py",
    "queue.py",
    "selectors.py",
    "concurrent/futures/thread.py",
    "concurrent\\futures\\thread.py",
)

Stack = tuple[tuple[CodeType, ...], int]  # a look at a thread: its code objects (innermost first), the deepest own line


@dataclass
class _Request:
    scope: MutableMapping[str, Any]
    looks: int = 0  # looks while it was under way
    own: Counter[Stack] = field(default_factory=Counter)  # its threads
    shared: Counter[Stack] = field(default_factory=Counter)  # the service's own thread, shared by all under way
    others: Counter[str] = field(default_factory=Counter)  # another request's route → looks at it working


_lock = threading.Lock()
_under_way: dict[int, _Request] = {}
_owners: dict[int, int] = {}  # thread → the request (its key) a route is running for on it
_current: contextvars.ContextVar[int | None] = contextvars.ContextVar("oakbox_request", default=None)
_loop: int | None = None  # the event loop's thread
_wake = threading.Event()
_thread: threading.Thread | None = None


def start(scope: MutableMapping[str, Any]) -> int:
    """A request begins (on the event loop, in the middleware): its looks start to be kept, and what runs for it
    knows it's its. The number is what finish() takes."""
    global _thread, _loop
    key = id(scope)
    if not ON:
        return key
    _current.set(key)
    with _lock:
        _loop = threading.get_ident()
        _under_way[key] = _Request(scope)
        if _thread is None:
            _thread = threading.Thread(target=_run, name="oakbox-profiler", daemon=True)
            _thread.start()
    _wake.set()
    return key


def finish(key: int) -> _Request | None:
    with _lock:
        return _under_way.pop(key, None)


def _owned(call: Callable[..., Any]) -> Callable[..., Any]:
    """A route function or dependency that, while it runs, marks the thread it runs on as its request's."""

    @functools.wraps(call)
    def owned(*args: Any, **kwargs: Any) -> Any:
        key = _current.get()
        if key is None:
            return call(*args, **kwargs)
        ident = threading.get_ident()
        before = _owners.get(ident)
        _owners[ident] = key
        try:
            return call(*args, **kwargs)
        finally:
            if before is None:
                _owners.pop(ident, None)
            else:
                _owners[ident] = before

    owned._oakbox_owned = True  # type: ignore[attr-defined]
    return owned


# The wrapper's own code: where a path of calls stops (above it is the framework).
_WRAPPER: CodeType = next(c for c in _owned.__code__.co_consts if isinstance(c, CodeType) and c.co_name == "owned")


def install() -> None:
    """Mark every worker thread's work with the request it's for: whatever runs on one (a route that isn't async, its
    dependencies, anything they hand to a thread) gets there through anyio's to_thread.run_sync, which carries the
    request's context along; wrapped, it marks the thread as that request's while it runs. (FastAPI's own route
    objects can't be wrapped instead: included routers' routes are copied anew for every request.)"""
    import anyio.to_thread

    run_sync = anyio.to_thread.run_sync
    if getattr(run_sync, "_oakbox_owned", False):
        return

    @functools.wraps(run_sync)
    async def owned_run_sync(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await run_sync(_owned(func), *args, **kwargs)

    owned_run_sync._oakbox_owned = True  # type: ignore[attr-defined]
    anyio.to_thread.run_sync = owned_run_sync


def _route_name(scope: MutableMapping[str, Any]) -> str:
    f = scope.get("endpoint")  # set once the router has picked the route
    return getattr(f, "__name__", "?")


def _own_dirs() -> tuple[str, ...]:
    """Where OAK box's and OpenAVMKit's own files are (their folders, with a separator at the end)."""
    out = [os.path.dirname(os.path.abspath(__file__))]
    try:
        spec = importlib.util.find_spec("openavmkit")
        if spec and spec.origin:
            out.append(os.path.dirname(os.path.abspath(spec.origin)))
    except (ImportError, ValueError):
        pass
    return tuple(d + os.sep for d in out)


_OWN_DIRS = _own_dirs()
_own_code: dict[CodeType, bool] = {}


def _own(code: CodeType) -> bool:
    o = _own_code.get(code)
    if o is None:
        o = _own_code[code] = (
            code.co_filename.startswith(_OWN_DIRS)
            and code is not _WRAPPER
            and not code.co_filename.endswith("__main__.py")  # the service itself, under every look at the event loop
        )
    return o


def _short(filename: str) -> str:
    """oakbox/wizard/checks.py, openavmkit/data.py: from the package's own name on."""
    for d in _OWN_DIRS:
        if filename.startswith(d):
            return (os.path.basename(d.rstrip("/\\")) + "/" + filename[len(d) :]).replace("\\", "/")
    return filename


def _library(filename: str) -> str:
    p = filename.replace("\\", "/")
    i = p.rfind("site-packages/")
    if i >= 0:
        return p[i + len("site-packages/") :].split("/", 1)[0]
    return p.rsplit("/", 1)[-1].removesuffix(".py")


def _idle(frame: FrameType) -> bool:
    f = frame.f_code.co_filename
    name = frame.f_code.co_name
    return (
        f.endswith(_IDLE_FILES)
        or (f.endswith("base_events.py") and name == "_run_once")
        # Windows: the event loop waiting on its completion port
        or (f.endswith("windows_events.py") and name in ("_poll", "select", "_wait_for_handle"))
    )


def _look() -> None:
    """One look at every working thread, kept as it is (its code objects, its deepest own line), to be made sense of
    only for a request that turns out slow: a look itself does as little as it can, so it slows nothing down.

    The other threads' stacks are read with no thread switch in between (sys.setswitchinterval): a thread that ran on
    meanwhile could leave a frame it had finished with, and reading that one crashes the process (it did: a
    segmentation fault in a look, a 888,000-row file being read on another thread)."""
    me = threading.get_ident()
    with _lock:  # before the stacks: taking a lock can let another thread run
        requests = dict(_under_way)
        owners = dict(_owners)
        loop = _loop
    seen_now: list[tuple[int, list[CodeType], int]] = []
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1.0)  # no other thread runs until this look is done (well under a millisecond)
    try:
        frames = sys._current_frames()  # noqa: SLF001 - the one way to see other threads' stacks
        f: FrameType | None = None
        for ident, top in frames.items():
            if ident == me or _idle(top) or (ident not in owners and ident != loop):
                continue
            codes: list[CodeType] = []
            line = 0
            f = top
            while f is not None and len(codes) < MAX_DEPTH:
                c = f.f_code
                if not line and _own(c):
                    line = f.f_lineno or -1
                codes.append(c)
                f = f.f_back
            seen_now.append((ident, codes, line))
        frames = f = None  # no frame of another thread kept past the look
    finally:
        sys.setswitchinterval(interval)
    for r in requests.values():
        r.looks += 1
    for ident, codes, line in seen_now:
        key = owners.get(ident)
        seen: Stack = (tuple(codes), line)
        if key is None:  # the event loop: every request under way shares it
            for r in requests.values():
                r.shared[seen] += 1
            continue
        req = requests.get(key)
        if req is None:
            continue
        req.own[seen] += 1
        name = _route_name(req.scope)
        for k, r in requests.items():
            if k != key:
                r.others[name] += 1


def _run() -> None:
    while True:
        _wake.wait()
        with _lock:
            if not _under_way:
                _wake.clear()
                continue
        try:
            _look()
        except Exception:  # noqa: BLE001 - a look that failed (a thread ended under it) is skipped, never a failure
            pass
        time.sleep(EVERY)


_FRAMEWORK = ("fastapi", "starlette", "pydantic", "uvicorn", "anyio")


def _place(codes: tuple[CodeType, ...], line: int) -> tuple[str, str]:
    """The path of own calls up to the route (the deepest own frame with its line first), and the library the deepest
    one was inside. With no own code on it (the event loop turning an answer into JSON): the framework function."""
    inner = ""
    path: list[str] = []
    for code in codes:  # innermost first
        if code is _WRAPPER:
            break
        if not _own(code):
            if not path and not inner:
                inner = _library(code.co_filename)
            continue
        if not path:
            path.append(f"{_short(code.co_filename)}:{line if line > 0 else '?'} {code.co_name}")
        elif path[-1].rsplit(" ", 1)[-1] != code.co_name:
            path.append(code.co_name)
    if not path:
        frame = next((c for c in codes if _library(c.co_filename) in _FRAMEWORK), None)
        if frame is not None:
            path.append(f"{_library(frame.co_filename)} {frame.co_name}")
            if inner == _library(frame.co_filename):
                inner = ""
    return " ‹ ".join(path) or "?", inner


def report(r: _Request, took: float) -> str:
    """The lines a slow request adds to the log: where its time went."""
    if r.looks == 0:
        return ""
    per = took / r.looks

    def row(n: int, what: str) -> str:
        return f"  {100 * n / r.looks:4.0f}% {n * per:5.1f} s  {what}"

    def places(looks: Counter[Stack]) -> Counter[tuple[str, str]]:
        out: Counter[tuple[str, str]] = Counter()
        for (codes, line), n in looks.items():
            out[_place(codes, line)] += n
        return out

    own = places(r.own)
    seen = sum(own.values())
    lines = [f"  its own work seen {seen * per:.1f} s of it, in {r.looks} looks; the deepest of our own code:"]
    top = own.most_common(TOP)
    lines += [row(n, path + (f" [in {inner}]" if inner else "")) for (path, inner), n in top]
    rest = seen - sum(n for _k, n in top)
    if rest:
        lines.append(row(rest, "elsewhere"))
    # What each function took, with what it calls: the ones that weren't on (nearly) every look that took most.
    within: Counter[str] = Counter()
    for (codes, _line), n in r.own.items():
        for name in {f"{_short(c.co_filename)} {c.co_name}" for c in codes if _own(c)}:
            within[name] += n
    parts = [(name, n) for name, n in within.most_common() if n < 0.9 * seen][:TOP]
    if parts:
        lines.append("  counting what they call:")
        lines += [row(n, name) for name, n in parts]
    shared = places(r.shared)
    if shared:
        lines.append(
            f"  the service's own thread busy {sum(shared.values()) * per:.1f} s meanwhile (shared by every request"
            " under way: reading them, turning answers into JSON):"
        )
        lines += [row(n, path + (f" [in {inner}]" if inner else "")) for (path, inner), n in shared.most_common(3)]
    waiting = r.looks - seen
    if waiting > 0.2 * r.looks:
        lines.append(row(waiting, "not seen working: waiting (on the disk, another process, a lock) or not started"))
    if r.others:
        lines.append(
            "  other requests working at the same time: "
            + ", ".join(f"{name} {n * per:.1f} s" for name, n in r.others.most_common(TOP))
        )
    return "\n".join(lines)
