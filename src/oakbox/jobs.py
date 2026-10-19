"""Background jobs: one engine worker process per running step.

The app service starts ``python -m oakbox.worker <project> <step>``, reads its
JSON event stream, keeps every event (so a page that reconnects can replay
them) and records the outcome in the project's step status.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from oakbox import projects
from oakbox.worker import CANCEL_FILE

JobState = str  # "running" | "done" | "failed" | "cancelled"


@dataclass
class Job:
    id: str
    project_id: str
    step: str
    state: JobState = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    proc: subprocess.Popen | None = None
    changed: threading.Condition = field(default_factory=threading.Condition)

    def add(self, event: dict[str, Any]) -> None:
        with self.changed:
            self.events.append(event)
            self.changed.notify_all()

    def wait_for(self, n_seen: int, timeout: float) -> None:
        with self.changed:
            if len(self.events) <= n_seen and self.state == "running":
                self.changed.wait(timeout)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def running_for(self, project_id: str) -> Job | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j.project_id == project_id and j.state == "running"), None)

    def start(self, project_id: str, step: str) -> Job:
        with self._lock:
            busy = next((j for j in self._jobs.values() if j.project_id == project_id and j.state == "running"), None)
            if busy is not None:
                raise RuntimeError(f"'{busy.step}' is still running for this project.")
            job = Job(id=uuid.uuid4().hex[:12], project_id=project_id, step=step)
            self._jobs[job.id] = job
        pdir = projects.project_dir(project_id)
        (pdir / "out").mkdir(parents=True, exist_ok=True)
        (pdir / "out" / CANCEL_FILE).unlink(missing_ok=True)
        if step in projects.STEP_ORDER:
            projects.mark_step(projects.load(project_id), step, "running")  # type: ignore[arg-type]
        log = (pdir / "out" / f"oakbox-{step}.log").open("w", encoding="utf-8")
        job.proc = subprocess.Popen(
            [sys.executable, "-m", "oakbox.worker", project_id, step],
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            encoding="utf-8",
            env=_worker_env(),
        )
        threading.Thread(target=self._pump, args=(job, log), daemon=True).start()
        return job

    def cancel(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.state != "running":
            return
        (projects.project_dir(job.project_id) / "out" / CANCEL_FILE).touch()

        def _hard_stop() -> None:
            time.sleep(15)
            if job.state == "running" and job.proc and job.proc.poll() is None:
                job.proc.kill()

        threading.Thread(target=_hard_stop, daemon=True).start()

    def _pump(self, job: Job, log) -> None:
        assert job.proc and job.proc.stdout
        final: dict[str, Any] | None = None
        for line in job.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") in ("done", "error", "cancelled"):
                final = event
            job.add(event)
        code = job.proc.wait()
        log.close()
        if final is None:
            final = {
                "type": "error",
                "message": f"The engine stopped unexpectedly (exit code {code}).",
                "detail": "See the log in the project's out/ folder.",
            }
            job.add(final)
        state = {"done": "done", "error": "failed", "cancelled": "cancelled"}[final["type"]]
        if job.step in projects.STEP_ORDER:
            step_state = "not_run" if state == "cancelled" else state
            projects.mark_step(projects.load(job.project_id), job.step, step_state, final.get("message", ""))  # type: ignore[arg-type]
        with job.changed:
            job.state = state
            job.changed.notify_all()


def _worker_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # joblib/loky otherwise shells out to wmic (gone from new Windows) to count cores.
    env.setdefault("LOKY_MAX_CPU_COUNT", str(max(1, (os.cpu_count() or 2) - 1)))
    return env
