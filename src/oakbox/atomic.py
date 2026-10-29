"""Writing a file so a reader never sees half of it, and two writers never trip over each other."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

_lock = threading.Lock()


def save_text(path: Path, text: str) -> None:
    """Write UTF-8 text to a temporary file beside the target, then put it in place in one step. Each write has its
    own temporary file (two saves at once used to share one, and the second found it gone); on Windows, replacing
    a file another process has open fails for a moment, so it's tried again briefly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        with _lock:
            for attempt in range(10):
                try:
                    os.replace(tmp, path)
                    return
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(0.05)
    finally:
        tmp.unlink(missing_ok=True)
