"""OAK box starts as the installed app starts it: under pythonw (OAK box.exe), with no console, so sys.stdout and
sys.stderr are None. uvicorn's logging asked sys.stdout.isatty() and ended the app before it served a page."""

import json
import os
import subprocess
import sys
import time
import urllib.request

START = """
import runpy, sys
sys.stdout = None
sys.stderr = None  # as under pythonw
sys.argv = ["oakbox", "--no-window", "--port", sys.argv[1]]
runpy.run_module("oakbox", run_name="__main__")
"""


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_it_starts_with_no_console(tmp_path):
    port = _free_port()
    env = {**os.environ, "OAKBOX_HOME": str(tmp_path)}
    p = subprocess.Popen([sys.executable, "-X", "utf8", "-c", START, str(port)], env=env)
    try:
        answer = None
        for _ in range(120):
            if p.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1) as r:
                    answer = json.loads(r.read())
                break
            except OSError:
                time.sleep(0.5)
        log = tmp_path / ".oakbox" / "logs" / "oakbox.log"
        said = log.read_text(encoding="utf-8")[-3000:] if log.exists() else "(no log)"
        assert answer is not None and "version" in answer, f"it didn't start; its log ends:\n{said}"
    finally:
        p.kill()
        p.wait()
