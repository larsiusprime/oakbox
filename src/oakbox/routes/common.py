"""What several routers share: a project loaded or a 404, an input file entry, and the views a step's
routes and its own routes both answer with."""

from __future__ import annotations

from fastapi import HTTPException

from oakbox import assemble, bring_in, clean, datafiles, projects, wizard


def load_project(project_id: str) -> projects.Project:
    try:
        return projects.load(project_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Project not found") from None


def file_entry(project: projects.Project, name: str) -> datafiles.DataFile:
    entry = next((f for f in project.files if f.name == name), None)
    if entry is None:
        raise HTTPException(404, "No such input file")
    return entry


def wizard_view(project: projects.Project) -> wizard.Wizard:
    return wizard.view(project, projects.project_dir(project.id) / "in")


def bring_in_view(project: projects.Project) -> bring_in.View:
    return bring_in.view(project, projects.project_dir(project.id), wizard_view(project).problems)


def assemble_view(project: projects.Project) -> assemble.AssembleView:
    return assemble.view(project, projects.project_dir(project.id))


def clean_view(project: projects.Project) -> clean.CleanView:
    return clean.view(project, projects.project_dir(project.id))
