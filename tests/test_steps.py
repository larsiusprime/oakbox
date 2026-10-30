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
    step = steps.Step("demo", R, key=lambda project, pdir: depends)
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
