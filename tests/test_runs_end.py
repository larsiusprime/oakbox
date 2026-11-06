"""No process of OAK box's outlives what it was for: a run stopped, or the app closed or gone, takes every process
the run started with it (steps.end, steps.stop_all, steps.die_with_app)."""

import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from oakbox import steps

# A stand-in for a run: it starts a worker (as OpenAVMKit's model training does), says both their numbers, and waits.
RUN = """
import os, pathlib, subprocess, sys, time
worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
pathlib.Path(sys.argv[1]).write_text(f"{os.getpid()} {worker.pid}", encoding="utf-8")
time.sleep(120)
"""


def _pids(path: Path, seconds: float = 20) -> list[int]:
    end = time.time() + seconds
    while time.time() < end:
        if path.is_file() and len(text := path.read_text(encoding="utf-8").split()) == 2:
            return [int(x) for x in text]
        time.sleep(0.05)
    raise AssertionError("the run never started its worker")


def _gone(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def _all_gone(pids: list[int], seconds: float = 10) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if all(_gone(p) for p in pids):
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def fake_runs(tmp_path, monkeypatch):
    """steps.start starts the stand-in run instead of a step's module; whatever a failed test leaves is killed."""
    monkeypatch.setattr(
        steps, "command", lambda module, project_id: [sys.executable, "-c", RUN, str(tmp_path / module)]
    )
    seen: list[int] = []
    yield seen
    for pid in seen:
        try:
            psutil.Process(pid).kill()
        except psutil.NoSuchProcess:
            pass


def test_stopping_a_run_ends_the_processes_it_started(tmp_path, fake_runs):
    steps.start("p1", tmp_path, "one")
    pids = _pids(tmp_path / "one")
    fake_runs.extend(pids)
    steps.stop("p1", "one")
    assert _all_gone(pids), "a worker outlived its stopped run"
    job = steps.job("p1", "one")
    assert job is not None and job.status == "stopped"


def test_closing_the_app_ends_every_run_and_their_workers(tmp_path, fake_runs):
    steps.start("p1", tmp_path, "one")
    steps.start("p2", tmp_path, "two")
    pids = _pids(tmp_path / "one") + _pids(tmp_path / "two")
    fake_runs.extend(pids)
    steps.stop_all()  # waits until they've gone
    assert all(_gone(p) for p in pids)
    assert steps.running_projects() == []


# A stand-in for the app: it starts a run (which follows it, as steps.main does), says the run's number, and waits.
APP = """
import os, pathlib, subprocess, sys, time
run = '''
import sys, time
from oakbox import steps
steps.die_with_app(every=0.1)
exec(sys.argv[2])
'''
env = {**os.environ, "OAKBOX_APP_PID": str(os.getpid())}
subprocess.Popen([sys.executable, "-c", run, sys.argv[1], sys.argv[2]], env=env)
time.sleep(120)
"""


def test_a_run_ends_with_its_workers_when_the_app_is_gone(tmp_path):
    """The app killed outright (a crash, Task Manager): nothing runs its code as it goes, so the run notices and
    ends itself and its workers."""
    app = subprocess.Popen([sys.executable, "-c", APP, str(tmp_path / "pids"), RUN])
    try:
        pids = _pids(tmp_path / "pids")
        app.kill()
        app.wait()
        assert _all_gone(pids), "the run or its worker outlived the app"
    finally:
        written = (tmp_path / "pids").read_text(encoding="utf-8").split() if (tmp_path / "pids").is_file() else []
        for pid in [app.pid, *map(int, written)]:
            try:
                psutil.Process(pid).kill()
            except psutil.NoSuchProcess:
                pass


def test_a_run_started_by_hand_follows_no_app(monkeypatch):
    """python -m oakbox.<step> by hand: no app to follow, so no watch is started."""
    monkeypatch.delenv(steps.APP_PID, raising=False)
    before = threading.active_count()
    steps.die_with_app()
    assert threading.active_count() == before
