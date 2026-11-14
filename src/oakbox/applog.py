"""OAK box's own log: every request that failed with a bug (a 500), with its traceback, kept in a file so it's
there to send even when OAK box runs with no console (the installed app starts with pythonw).

The file is ``logs/oakbox.log`` in OAK box's settings folder (``%APPDATA%\\OAK box\\logs`` on Windows,
``~/.config/oakbox/logs`` on Linux; ``<OAKBOX_HOME>/.oakbox/logs`` with OAKBOX_HOME), kept to its last few
megabytes. Help › Open the log folder shows it; Help › Save a performance report includes its end.
"""

from __future__ import annotations

import logging
import secrets
import threading
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from oakbox import appsettings

NAME = "oakbox.log"
SIZE = 1_000_000  # bytes per file; three old ones kept besides
TAIL = 200_000  # bytes of it in a performance report

_LOCK = threading.Lock()
_logger: logging.Logger | None = None
_dir: Path | None = None


def log_dir() -> Path:
    return appsettings.config_dir() / "logs"


def log_file() -> Path:
    return log_dir() / NAME


def logger() -> logging.Logger:
    """The log, set up once (again if the settings folder moved: tests give each their own OAKBOX_HOME)."""
    global _logger, _dir
    with _LOCK:
        here = log_dir()
        if _logger is None or _dir != here:
            log = logging.getLogger("oakbox.app")
            log.setLevel(logging.INFO)
            log.propagate = False
            for h in list(log.handlers):
                log.removeHandler(h)
                h.close()
            try:
                here.mkdir(parents=True, exist_ok=True)
                handler: logging.Handler = RotatingFileHandler(
                    here / NAME, maxBytes=SIZE, backupCount=3, encoding="utf-8", delay=True
                )
            except OSError:  # the folder can't be written: nowhere to keep it, but never a second failure
                handler = logging.NullHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            log.addHandler(handler)
            _logger, _dir = log, here
        return _logger


def failure(method: str, path: str, error: BaseException) -> dict:
    """Write a request's failure to the log with its traceback; what the page is told about it, to copy."""
    ref = secrets.token_hex(3)
    at = datetime.now().astimezone().isoformat(timespec="seconds")
    what = f"{type(error).__name__}: {error}"
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    logger().error("[%s] %s %s failed: %s\n%s", ref, method, path, what, tb.rstrip())
    return {"ref": ref, "at": at, "request": f"{method} {path}", "what": what[:500], "log": str(log_file())}


CRASH = "crash.log"
_crash_file = None


def watch_for_crashes() -> None:
    """Make a crash leave a record. A crash below Python (a native library, or the window's browser engine taking
    the process down) writes every thread's Python stack to logs/crash.log (faulthandler), and the next start copies
    it into this log; an error no one caught on a background thread is logged; a normal close says so ("stopped"),
    so a log that ends without it ended in a crash."""
    import atexit
    import faulthandler
    import sys

    global _crash_file
    log = logger()
    here = log_dir()
    crash = here / CRASH
    try:
        before = crash.read_text(encoding="utf-8", errors="replace") if crash.is_file() else ""
    except OSError:
        before = ""
    # On Windows faulthandler also writes exceptions native code catches and carries on from (WebView2 does): only a
    # run that didn't close normally crashed.
    closed = tail(4000).rstrip().endswith(b"(closed normally)")
    if not closed and ("Fatal Python error" in before or "Windows fatal exception" in before):
        log.error("The last run crashed (a native crash: below Python). Its threads then:\n%s", before.strip()[-20000:])
    try:
        here.mkdir(parents=True, exist_ok=True)
        _crash_file = open(crash, "w", encoding="utf-8")  # noqa: SIM115 - open for the life of the process
        faulthandler.enable(file=_crash_file, all_threads=True)
    except OSError:
        pass

    def uncaught(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit:
            return
        tb = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        name = args.thread.name if args.thread else "?"
        log.error("Uncaught error on thread %s:\n%s", name, tb.rstrip())

    threading.excepthook = uncaught
    previous = sys.excepthook

    def uncaught_main(t: type[BaseException], e: BaseException, tb: object) -> None:
        log.error("Uncaught error:\n%s", "".join(traceback.format_exception(t, e, tb)).rstrip())  # type: ignore[arg-type]
        previous(t, e, tb)  # type: ignore[arg-type]

    sys.excepthook = uncaught_main
    atexit.register(lambda: log.info("OAK box stopped (closed normally)"))


def tail(limit: int = TAIL) -> bytes:
    """The end of the log (the newest of its files), for a report."""
    f = log_file()
    try:
        return f.read_bytes()[-limit:]
    except OSError:
        return b""


def open_folder() -> None:
    from oakbox.projects import _open_in_file_manager

    here = log_dir()
    here.mkdir(parents=True, exist_ok=True)
    _open_in_file_manager(here)
