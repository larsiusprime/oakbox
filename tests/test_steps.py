"""The machinery every step shares (steps.py): its output folder put in place, its receipt read, and whether it's
out of date or accepted."""

from types import SimpleNamespace

from pydantic import BaseModel

from oakbox import steps


class R(BaseModel):
    ran_at: str


def test_publish_replaces_the_last_runs_folder(tmp_path):
    final = tmp_path / "out" / "step"
    final.mkdir(parents=True)
    (final / "old.txt").write_text("last run", encoding="utf-8")
    tmp = steps.workdir(final)
    (tmp / "new.txt").write_text("this run", encoding="utf-8")
    steps.publish(tmp, final)
    assert [p.name for p in final.iterdir()] == ["new.txt"]
    assert not tmp.exists() and not final.with_suffix(".old").exists()


def test_a_run_that_fails_before_publishing_leaves_the_last_one(tmp_path):
    final = tmp_path / "step"
    final.mkdir()
    (final / "receipt.json").write_text('{"ran_at": "then"}', encoding="utf-8")
    tmp = steps.workdir(final)
    (tmp / "half.txt").write_text("…", encoding="utf-8")  # and then it fails: no publish
    assert steps.read(final, R)[0] == R(ran_at="then")


def test_a_receipt_this_oak_box_cant_read_is_no_receipt(tmp_path):
    (tmp_path / "receipt.json").write_text('{"something": "else"}', encoding="utf-8")
    assert steps.read(tmp_path, R) == (None, None)
    assert steps.read(tmp_path / "never", R) == (None, None)


def test_out_of_date_and_accepted(tmp_path):
    depends = {"x": 1}
    step = steps.Step("demo", "Demo", R, key=lambda project, pdir: depends)
    project = SimpleNamespace(id="p1", accepted={})
    pdir = tmp_path
    out = step.out_dir(pdir)
    out.mkdir(parents=True)
    (out / "receipt.json").write_text('{"ran_at": "now"}', encoding="utf-8")
    (out / "settings.json").write_text(f'{{"hash": "{steps.key_hash(depends)}"}}', encoding="utf-8")

    s = step.state(project, pdir)
    assert s.status == "done" and not s.stale and not s.accepted
    step.accept(project, pdir)
    assert step.accepted(project, pdir)

    depends["x"] = 2  # what it depends on changed: out of date, no longer accepted, and can't be accepted
    s = step.state(project, pdir)
    assert s.stale and not s.accepted
    try:
        step.accept(project, pdir)
        raise AssertionError("accepted an out-of-date run")
    except ValueError as e:
        assert str(e) == step.again
    # Blocked: what it depends on can't be worked out, so it isn't called out of date.
    assert not step.state(project, pdir, check=False).stale


def _ran(step, pdir, ran_at, key):
    out = step.out_dir(pdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "receipt.json").write_text(f'{{"ran_at": "{ran_at}"}}', encoding="utf-8")
    (out / "settings.json").write_text(f'{{"hash": "{steps.key_hash(key)}"}}', encoding="utf-8")


def test_a_step_follows_the_run_before_and_waits_for_any_step_before_it(tmp_path):
    calls = {"first": 1}
    first = steps.Step("first", "First", R, key=lambda project, pdir: dict(calls))
    second = steps.Step("second", "Second", R, key=lambda project, pdir: {"first": first.ran_at(pdir)}, after=first)
    third = steps.Step("third", "Third", R, key=lambda project, pdir: {"second": second.ran_at(pdir)}, after=second)
    project = SimpleNamespace(id="p2", accepted={})
    _ran(first, tmp_path, "t1", calls)
    _ran(second, tmp_path, "t2", {"first": "t1"})
    _ran(third, tmp_path, "t3", {"second": "t2"})
    for s in (first, second, third):
        s.accept(project, tmp_path)
    assert third.accepted(project, tmp_path)

    # A call changes on the first step: it's out of date; the ones after it aren't, but wait for it.
    calls["first"] = 2
    assert first.state(project, tmp_path).stale
    s3 = third.state(project, tmp_path)
    assert not s3.stale and not s3.accepted
    assert s3.waiting == "Run First again first: something it depends on changed since it ran."

    # The first runs again and is accepted: the second is out of date (its run is replaced), the third waits.
    _ran(first, tmp_path, "t4", calls)
    first.accept(project, tmp_path)
    assert second.state(project, tmp_path).stale
    assert (third.state(project, tmp_path).waiting or "").startswith("Run Second again first")


def test_bring_in_says_what_changed_even_when_oak_box_wrote_it():
    """A change no line names (a newer OAK box writing the step's settings differently) is still said, never an empty
    list beside "out of date"."""
    from oakbox.bring_in import changes

    old = {"data": {"load": {}, "process": {"enrich": {}}}}
    new = {"data": {"load": {}, "process": {"enrich": {"calc": {"universe": {"x": ["set", 1]}}}}}}
    assert changes(old, new) == ["fields worked out after the files join"]
    odd = {"data": {"load": {}, "process": {"enrich": {}, "something_new": 1}}}
    assert changes(old, odd) == ["how OAK box writes this step's settings (a newer OAK box)"]
    # Check sales' own calls aren't Bring in data's.
    assert changes(old, {"data": {"load": {}, "process": {"enrich": {}, "collapse_sparse_categories": {}}}}) == []


def test_opening_a_project_refreshes_its_settings(client):
    """Settings a newer OAK box would write differently are rewritten when the project is opened, so what that
    changes shows then, not at the next unrelated click."""
    import json

    from helpers import NEW

    from oakbox import projects

    pid = client.post("/api/projects", json=NEW).json()["id"]
    path = projects.project_dir(pid) / "in" / "settings.json"
    assert not projects.refresh_settings(projects.load(pid))
    s = json.loads(path.read_text(encoding="utf-8"))
    s["stale_by_an_older_oak_box"] = True
    path.write_text(json.dumps(s), encoding="utf-8")
    client.get(f"/api/projects/{pid}")
    assert "stale_by_an_older_oak_box" not in json.loads(path.read_text(encoding="utf-8"))
