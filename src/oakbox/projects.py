"""Projects: one jurisdiction x one tax year, stored as an ordinary folder.

Layout (SPEC §3.7, §6)::

    <home>/<project-id>/
        oakbox.json        project metadata, wizard answers, step status
        in/                imported data + generated settings.json
        out/               OpenAVMKit outputs
        cache/             enrichment cache

The project folder is itself an OpenAVMKit locality, so the engine runs on it
directly. ``<home>`` defaults to ~/Documents/Oakbox and can be overridden with
the OAKBOX_HOME environment variable.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field

from oakbox.answers import WizardAnswers
from oakbox.settings_gen import generate

StepId = Literal["bring_in_data", "model_groups", "check_sales", "check_values"]
STEP_ORDER: tuple[StepId, ...] = ("bring_in_data", "model_groups", "check_sales", "check_values")
StepState = Literal["not_run", "running", "done", "failed", "stale"]


class BaseModel(_PydanticBase):
    # Fields with defaults are always present in responses; say so in the schema so
    # the generated TypeScript types are exact (no spurious optionals).
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class StepStatus(BaseModel):
    state: StepState = "not_run"
    finished_at: dt.datetime | None = None
    message: str = ""


class Project(BaseModel):
    id: str
    name: str
    tax_year: int
    created_at: dt.datetime
    sample: str | None = None
    answers: WizardAnswers
    steps: dict[StepId, StepStatus] = Field(default_factory=lambda: {s: StepStatus() for s in STEP_ORDER})


def home() -> Path:
    env = os.environ.get("OAKBOX_HOME")
    return Path(env) if env else Path.home() / "Documents" / "Oakbox"


def project_dir(project_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", project_id):
        raise ValueError(f"Invalid project id: {project_id!r}")
    return home() / project_id


def list_projects() -> list[Project]:
    root = home()
    if not root.exists():
        return []
    projects = []
    for meta in sorted(root.glob("*/oakbox.json")):
        try:
            projects.append(Project.model_validate_json(meta.read_text()))
        except ValueError:
            continue
    return sorted(projects, key=lambda p: p.created_at, reverse=True)


def load(project_id: str) -> Project:
    return Project.model_validate_json((project_dir(project_id) / "oakbox.json").read_text())


def save(project: Project) -> None:
    path = project_dir(project.id) / "oakbox.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2))
    tmp.replace(path)


def create(answers: WizardAnswers, sample: str | None = None) -> Project:
    """Create the project folder, write oakbox.json and the generated settings."""
    base = f"{answers.slug()}-{answers.place.tax_year}"
    pid, n = base, 2
    while project_dir(pid).exists():
        pid, n = f"{base}-{n}", n + 1
    project = Project(
        id=pid,
        name=answers.place.name,
        tax_year=answers.place.tax_year,
        created_at=dt.datetime.now(dt.UTC),
        sample=sample,
        answers=answers,
    )
    save(project)
    write_settings(project)
    return project


def write_settings(project: Project) -> Path:
    path = project_dir(project.id) / "in" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(generate(project.answers), indent=2))
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
