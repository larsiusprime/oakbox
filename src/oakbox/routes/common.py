"""What several routers share: a project loaded or a 404, a project to change, an input file entry, and the views a
step's routes and its own routes both answer with."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from oakbox import assemble, bring_in, clean, datafiles, projects, wizard


def load_project(project_id: str) -> projects.Project:
    try:
        return projects.load(project_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Project not found") from None


@contextmanager
def editing(project_id: str, settings: bool = False) -> Iterator[projects.Project]:
    """The project, to change in the block: loaded, then saved when the block ends (and its settings.json written,
    with `settings`), with no other change to it in between (projects.lock). An exception in the block saves
    nothing. Every route that changes a project changes it here, or holds projects.lock itself."""
    with projects.lock(project_id):
        project = load_project(project_id)
        before = project.model_dump_json()
        yield project
        # Nothing changed (the option already chosen, pressed again): nothing written, so nothing worked out again.
        if project.model_dump_json() == before:
            return
        project.revision += 1
        projects.save(project)
        if settings:
            projects.write_settings(project)


def file_entry(project: projects.Project, name: str) -> datafiles.DataFile:
    entry = project.file(name)
    if entry is None:
        raise HTTPException(404, "No such input file")
    return entry


def wizard_view(project: projects.Project) -> wizard.Wizard:
    return wizard.view(project, projects.inputs_dir(project.id))


def bring_in_view(project: projects.Project) -> bring_in.View:
    return bring_in.view(project, projects.project_dir(project.id), wizard_view(project).problems)


def assemble_view(project: projects.Project) -> assemble.AssembleView:
    return assemble.view(project, projects.project_dir(project.id))


def clean_view(project: projects.Project) -> clean.CleanView:
    return clean.view(project, projects.project_dir(project.id))
