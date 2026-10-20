"""Projects: one jurisdiction x one tax year, stored as an ordinary folder.

Layout (SPEC §3.7, §6)::

    <home>/<project-id>/
        oakbox.json        project metadata, the guided build's decisions, stage and step status
        in/                the user's imported copies (sources/), stitched tables, settings.json
        out/               OpenAVMKit outputs; out/oakbox/ holds OAK box's checks and receipts
        cache/             enrichment cache

The project folder is itself an OpenAVMKit locality, so the engine runs on it
directly. ``<home>`` defaults to ~/Documents/Oakbox and can be overridden with
the OAKBOX_HOME environment variable.

Every stage and step is done only after the user says **Looks right** (SPEC §3.2).
Changing a decision re-opens that stage and marks everything after it out of date.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

from oakbox.settings_gen import generate
from oakbox.setup import STAGE_ORDER, Setup, StageId

StepId = Literal["bring_in_data", "model_groups", "check_sales", "check_values"]
STEP_ORDER: tuple[StepId, ...] = ("bring_in_data", "model_groups", "check_sales", "check_values")
StepState = Literal["not_run", "running", "done", "failed", "stale"]
StageState = Literal["todo", "done", "stale"]


class BaseModel(_PydanticBase):
    # Fields with defaults are always present in responses; say so in the schema so
    # the generated TypeScript types are exact (no spurious optionals).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class StepStatus(BaseModel):
    state: StepState = "not_run"
    finished_at: dt.datetime | None = None
    message: str = ""


class StageStatus(BaseModel):
    state: StageState = "todo"
    confirmed_at: dt.datetime | None = None
    reason: str = Field(default="", description="Why it is out of date.")


class Project(BaseModel):
    id: str
    name: str
    created_at: dt.datetime
    sample: str | None = None
    notes: dict[StageId, str] = Field(default_factory=dict, description="Walkthrough notes (samples).")
    setup: Setup = Field(default_factory=Setup)
    stages: dict[StageId, StageStatus] = Field(default_factory=lambda: {s: StageStatus() for s in STAGE_ORDER})
    steps: dict[StepId, StepStatus] = Field(default_factory=lambda: {s: StepStatus() for s in STEP_ORDER})

    @property
    def tax_year(self) -> int | None:
        return self.setup.basics.tax_year


def home() -> Path:
    env = os.environ.get("OAKBOX_HOME")
    return Path(env) if env else Path.home() / "Documents" / "Oakbox"


def project_dir(project_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", project_id):
        raise ValueError(f"Invalid project id: {project_id!r}")
    return home() / project_id


def checks_dir(project_id: str) -> Path:
    return project_dir(project_id) / "out" / "oakbox"


def list_projects() -> list[Project]:
    root = home()
    if not root.exists():
        return []
    projects = []
    for meta in sorted(root.glob("*/oakbox.json")):
        try:
            projects.append(Project.model_validate_json(meta.read_text()))
        except ValueError:
            continue  # an older or damaged project file
    return sorted(projects, key=lambda p: p.created_at, reverse=True)


def load(project_id: str) -> Project:
    return Project.model_validate_json((project_dir(project_id) / "oakbox.json").read_text())


def save(project: Project) -> None:
    project.name = project.setup.basics.name or project.name
    path = project_dir(project.id) / "oakbox.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2))
    tmp.replace(path)


def _new_id(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
    pid, n = base, 2
    while project_dir(pid).exists():
        pid, n = f"{base}-{n}", n + 1
    return pid


def create(name: str) -> Project:
    """A new, empty project at its first setup stage."""
    project = Project(id=_new_id(name), name=name, created_at=dt.datetime.now(dt.UTC))
    project.setup.basics.name = name
    save(project)
    return project


def create_from_sample(sample_id: str) -> Project:
    """A project pre-filled from a sample. Every stage still waits for the user's Looks right."""
    from oakbox.samples import SAMPLES

    sample = SAMPLES[sample_id]
    setup = sample.setup()
    year = setup.basics.tax_year
    project = Project(
        id=_new_id(f"{setup.slug()}-{year}"),
        name=setup.basics.name,
        created_at=dt.datetime.now(dt.UTC),
        sample=sample_id,
        notes=sample.notes(),
        setup=setup,
    )
    save(project)
    return project


# ---------- Decisions, staleness and confirmation ----------


def stage_decisions(setup: Setup, stage: StageId) -> Any:
    """What a stage's decisions are, for detecting changes. Measurements are not decisions."""
    if stage == "basics":
        return setup.basics.model_dump(mode="json")
    if stage == "files":
        return [f.model_dump(mode="json", exclude={"profile", "imported", "size_bytes"}) for f in setup.files]
    if stage == "stitch":
        return setup.stitch.model_dump(mode="json")
    if stage == "columns":
        return setup.columns.model_dump(mode="json")
    return {
        "sales": setup.sales_basics.model_dump(mode="json") if setup.sales_basics else None,
        "groups": [g.model_dump(mode="json") for g in setup.model_groups],
    }


def decisions_hash(setup: Setup, upto: StageId) -> str:
    """Hash of this stage's decisions and every earlier stage's. Checks are tied to it."""
    stages = STAGE_ORDER[: STAGE_ORDER.index(upto) + 1]
    blob = json.dumps([stage_decisions(setup, s) for s in stages], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def change_setup(project: Project, new: Setup, reason: str) -> Project:
    """Apply edited decisions. A changed stage re-opens; later stages and all steps go stale."""
    changed = [s for s in STAGE_ORDER if stage_decisions(project.setup, s) != stage_decisions(new, s)]
    project.setup = new
    if changed:
        first = STAGE_ORDER.index(changed[0])
        for s in STAGE_ORDER[first:]:
            st = project.stages[s]
            if s in changed:
                project.stages[s] = StageStatus(state="todo")
            elif st.state == "done":
                project.stages[s] = StageStatus(state="stale", reason=reason)
        for step in STEP_ORDER:
            if project.steps[step].state == "done":
                project.steps[step] = StepStatus(state="stale", message=reason)
    save(project)
    return project


def blocking_stage(project: Project, before: StageId | None = None) -> StageId | None:
    """The first stage (before ``before``, or overall) that isn't confirmed."""
    stages = STAGE_ORDER if before is None else STAGE_ORDER[: STAGE_ORDER.index(before)]
    return next((s for s in stages if project.stages[s].state != "done"), None)


def confirm_stage(project: Project, stage: StageId) -> Project:
    project.stages[stage] = StageStatus(state="done", confirmed_at=dt.datetime.now(dt.UTC))
    save(project)
    return project


def write_settings(project: Project) -> Path:
    path = project_dir(project.id) / "in" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(generate(project.setup), indent=2))
    return path


def mark_step(project: Project, step: StepId, state: StepState, message: str = "") -> Project:
    """Record a step's outcome. A finished step makes every later step stale."""
    project.steps[step] = StepStatus(
        state=state,
        message=message,
        finished_at=dt.datetime.now(dt.UTC) if state in ("done", "failed") else None,
    )
    if state == "done":
        for later in STEP_ORDER[STEP_ORDER.index(step) + 1 :]:
            if project.steps[later].state == "done":
                project.steps[later] = StepStatus(state="stale", message="An earlier step was re-run.")
    save(project)
    return project


# ---------- Saved checks and receipts ----------


def save_check(project_id: str, name: str, data: dict) -> None:
    d = checks_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{name}.json.tmp"
    tmp.write_text(json.dumps(data, default=str, indent=1))
    tmp.replace(d / f"{name}.json")


def read_check(project_id: str, name: str) -> dict | None:
    path = checks_dir(project_id) / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None
