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
