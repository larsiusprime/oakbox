"""Which model groups are modeled (Model groups › Check them): proposed from their sales, ticked or unticked by the
user; a group not modeled has every model skipped (OpenAVMKit instructions.main.skip)."""

from helpers import NEW

from oakbox import assemble, groups, model, projects
from oakbox.projects import ModelGroup


def test_proposed_from_the_sales_then_as_chosen():
    g = ModelGroup(id="sf", name="Single-family", color="#000")
    assert groups.is_modeled(g, 15) and not groups.is_modeled(g, 14)
    assert groups.is_modeled(g, None)  # not counted yet: modeled until the counts say otherwise
    assert groups.is_modeled(g.model_copy(update={"modeled": True}), 3)
    assert not groups.is_modeled(g.model_copy(update={"modeled": False}), 900)


def test_a_group_not_modeled_skips_every_model(client, monkeypatch):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    project = projects.load(pid)
    project.groups = [
        ModelGroup(id="sf", name="Single-family", color="#000"),
        ModelGroup(id="ex", name="Exempt", color="#111", modeled=False),
    ]
    project.model.groups = {
        "sf": [
            model.ModelEntry(key="lightgbm", name="LightGBM", engine="lightgbm"),
            model.ModelEntry(key="mra", name="MRA", engine="mra"),
        ]
    }
    monkeypatch.setattr(
        model,
        "variables",
        lambda p, d: [
            model.Variable(field="x", name="x", kind="building", numeric=True, parcels=3, blanks=0, trees_only=False)
        ],
    )
    monkeypatch.setattr(model, "_universe_fields", lambda d: [])
    monkeypatch.setattr(model, "_has_roll", lambda d: True)
    pdir = projects.project_dir(pid)
    assert assemble.modeled(project, pdir) == {"sf"}
    main = model.settings(project, pdir)["modeling"]["instructions"]["main"]
    assert main["skip"] == {"ex": ["lightgbm", "mra", "assessor"]}
