"""Optional model engines (oakbox/engines.py): installing from engines.json, checking, activating, removing."""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from oakbox import engines


def _wheel(path: Path, files: dict[str, str]) -> dict:
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    data = path.read_bytes()
    return {"filename": path.name, "url": path.as_uri(), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """A manifest for "xgboost" naming one made-up wheel whose module is `oakbox_fake_engine`."""
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path / "home"))
    monkeypatch.setitem(engines.OPTIONAL, "xgboost", ("XGBoost", "oakbox_fake_engine"))
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    w = _wheel(
        wheels / "oakbox_fake_engine-1.0-py3-none-any.whl",
        {
            "oakbox_fake_engine/__init__.py": "ANSWER = 42\n",
            "oakbox_fake_engine-1.0.data/purelib/oakbox_fake_extra.py": "X = 1\n",
            "oakbox_fake_engine-1.0.data/scripts/tool": "#!/bin/sh\n",
            "oakbox_fake_engine-1.0.dist-info/METADATA": "Name: oakbox-fake-engine\n",
        },
    )
    manifest = tmp_path / "engines.json"
    manifest.write_text(
        json.dumps({"platform": "test", "engines": {"xgboost": {"wheels": [w], "disk": 100}}}), encoding="utf-8"
    )
    monkeypatch.setattr(engines, "manifest_path", lambda: manifest)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delenv("PYTHONPATH", raising=False)
    yield {"manifest": manifest, "wheel": w}
    sys.modules.pop("oakbox_fake_engine", None)


def test_not_installed_until_installed(fake):
    state = {s.key: s for s in engines.states()}["xgboost"]
    assert not state.installed and state.can_install and state.download == fake["wheel"]["size"]
    assert engines.missing({"xgboost", "lightgbm"}) == ["XGBoost"]

    seen = []
    engines.install("xgboost", lambda done, total: seen.append(done))
    assert engines.installed("xgboost") and engines.missing({"xgboost"}) == []
    import oakbox_fake_engine  # type: ignore[import-not-found]

    assert oakbox_fake_engine.ANSWER == 42
    site = engines.engines_dir() / "xgboost" / "site"
    assert (site / "oakbox_fake_extra.py").is_file(), ".data/purelib goes in beside the package"
    assert not (site / "tool").exists() and not any(site.glob("*.data")), "scripts are left out"
    assert not list(engines.engines_dir().glob(".*")), "no leftovers"
    assert seen[-1] == -1 and fake["wheel"]["size"] in seen
    # what a run's process gets
    assert str(site) in engines.os.environ["PYTHONPATH"]


def test_a_wheel_that_doesnt_match_is_refused(fake):
    m = json.loads(fake["manifest"].read_text(encoding="utf-8"))
    m["engines"]["xgboost"]["wheels"][0]["sha256"] = "0" * 64
    fake["manifest"].write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(RuntimeError, match="checksum"):
        engines.install("xgboost")
    assert not engines.installed("xgboost")
    assert not (engines.engines_dir() / "xgboost").exists() and not list(engines.engines_dir().glob(".*"))


def test_stopping_leaves_nothing(fake):
    stop = threading.Event()
    stop.set()
    with pytest.raises(engines.Stopped):
        engines.install("xgboost", stop=stop)
    assert not (engines.engines_dir() / "xgboost").exists() and not list(engines.engines_dir().glob(".*"))


def test_a_folder_for_other_wheels_is_left_off(fake):
    """An older OAK box's download (other wheels) reads as not installed, so it's fetched again."""
    engines.install("xgboost")
    sys.path.remove(str(engines.engines_dir() / "xgboost" / "site"))
    sys.modules.pop("oakbox_fake_engine", None)
    marker = engines.engines_dir() / "xgboost" / engines.MARKER
    marker.write_text(json.dumps({"wheels": ["oakbox_fake_engine-0.9-py3-none-any.whl"]}), encoding="utf-8")
    engines.activate()
    assert not engines.installed("xgboost")
    engines.install("xgboost")  # replaces it
    assert engines.installed("xgboost")


def test_remove(fake):
    engines.install("xgboost")
    engines.remove("xgboost")
    sys.modules.pop("oakbox_fake_engine", None)
    assert not engines.installed("xgboost") and not (engines.engines_dir() / "xgboost").exists()


def test_a_checkout_has_no_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(engines, "manifest_path", lambda: tmp_path / "none.json")
    s = {x.key: x for x in engines.states()}
    assert not s["xgboost"].can_install and s["xgboost"].download is None
    with pytest.raises(ValueError, match="uv sync --extra xgboost"):
        engines.start("xgboost")


def test_the_app_installs_in_the_background(fake, client):
    r = client.get("/api/engines")
    assert {e["key"]: e["installed"] for e in r.json()} == {"xgboost": False, "catboost": engines.installed("catboost")}
    client.post("/api/engines/xgboost/install").raise_for_status()
    x: dict = {}
    for _ in range(200):
        x = {e["key"]: e for e in client.get("/api/engines").json()}["xgboost"]
        if x["install"]["status"] != "running":
            break
        threading.Event().wait(0.05)
    assert x["install"]["status"] == "done" and x["installed"]
    client.post("/api/engines/xgboost/seen").raise_for_status()
    assert {e["key"]: e for e in client.get("/api/engines").json()}["xgboost"]["install"] is None
    client.delete("/api/engines/xgboost").raise_for_status()


def test_a_run_needs_its_engines(monkeypatch):
    """Try them and Finalize refuse models whose engine isn't installed, and say how to get it."""
    from oakbox import model

    monkeypatch.setattr(engines, "installed", lambda key: key != "xgboost")
    assert model.not_installed({"lightgbm", "xgboost", "catboost"}) == [
        "XGBoost isn't installed: install it (Help › Model engines), or remove its models."
    ]
    assert model.not_installed({"lightgbm", "mra"}) == []
