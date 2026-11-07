"""Where a run's time goes (timing.py, SPEC §5): each step's run leaves its record in out/oakbox/timing/<step>/,
however it ends; Help › Save a performance report zips the records with the receipts and logs, no data."""

import json
import zipfile

from oakbox import steps, timing


def test_a_run_leaves_its_timeline_trials_and_how_it_ended(tmp_path, monkeypatch):
    monkeypatch.delenv(timing.TRIAL_LOG_ENV, raising=False)
    r = timing.start(tmp_path, "model")
    assert r is not None
    steps.emit(step="load", fraction=0.0, message="Reading")
    steps.emit(beat=True)  # heartbeats aren't kept
    steps.emit(step="models", fraction=0.5, message="Single-family: training CatBoost")
    # OpenAVMKit's trial log goes where the run's workers will find it (they inherit the variable).
    trials = tmp_path / "out" / "oakbox" / "timing" / "model" / "trials.jsonl"
    import os

    assert os.environ[timing.TRIAL_LOG_ENV] == str(trials)
    lines = [
        {"model": "CatBoost", "seconds": 12.5, "state": "COMPLETE", "rows": 284, "features": 29, "cat_features": 6},
        {"model": "CatBoost", "seconds": 3.0, "state": "PRUNED", "rows": 284, "features": 29, "cat_features": 6},
        {"model": "LightGBM", "seconds": 0.1, "state": "COMPLETE", "rows": 284, "features": 29, "cat_features": 6},
    ]
    trials.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    r.finish(error="ValueError: stopped")
    timing._current = None

    rec = json.loads((trials.parent / "timing.json").read_text(encoding="utf-8"))
    assert rec["step"] == "model" and rec["ended"] == "error" and rec["error"] == "ValueError: stopped"
    assert [x.get("message") for x in rec["timeline"]] == ["Reading", "Single-family: training CatBoost"]
    cat = next(x for x in rec["trials"] if x["model"] == "CatBoost")
    assert (cat["trials"], cat["seconds"], cat["slowest"], cat["pruned"]) == (2, 15.5, 12.5, 1)
    assert cat["searched_on"] == [{"rows": 284, "features": 29, "cat_features": 6, "folds": None}]
    assert rec["openavmkit"] and rec["cpu_logical"] and "process" in rec


def test_the_report_holds_the_records_receipts_and_logs_not_data(tmp_path):
    base = tmp_path / "out" / "oakbox"
    (base / "timing" / "model").mkdir(parents=True)
    (base / "timing" / "model" / "timing.json").write_text("{}", encoding="utf-8")
    (base / "model").mkdir()
    (base / "model" / "receipt.json").write_text("{}", encoding="utf-8")
    (base / "model" / "values.parquet").write_bytes(b"data")  # not sent
    (base / "model.log").write_text("x" * (timing.LOG_TAIL + 10), encoding="utf-8")
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "settings.json").write_text("{}", encoding="utf-8")
    out = timing.report(tmp_path)
    assert out.parent == tmp_path and out.name.startswith("performance-report-")
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert {"about.json", "timing/model/timing.json", "runs/model/receipt.json", "logs/model.log"} <= names
        assert "settings.json" in names and not any(n.endswith(".parquet") for n in names)
        assert len(z.read("logs/model.log")) == timing.LOG_TAIL  # its end
