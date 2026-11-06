"""What OAK box keeps is never lost to the way it's saved: changes to a project made at once each count, and a
settings file that can't be read whole keeps what can be read (above all, where the projects are)."""

import json
import threading
import time

from helpers import NEW

from oakbox import appsettings, projects


def test_changes_made_at_once_each_count(client, monkeypatch):
    """The page can send two changes at once (a wizard step shown while a field is set). Each loads the project,
    changes it and saves it: without the project's lock, the second save undoes the first."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    load = projects.load

    def slow_load(project_id):
        project = load(project_id)
        time.sleep(0.05)  # widen the gap between loading and saving, so a missing lock fails every time
        return project

    monkeypatch.setattr(projects, "load", slow_load)
    names = [f"Set {i}" for i in range(4)]  # a new project has one set; six at most
    url = f"/api/projects/{pid}/wizard/value-sets"
    codes: list[int] = []
    threads = [
        threading.Thread(target=lambda n=n: codes.append(client.post(url, json={"name": n}).status_code)) for n in names
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes == [200] * len(names)
    saved = {v.name for v in load(pid).wizard.value_sets or []}
    assert saved >= set(names), f"lost: {sorted(set(names) - saved)}"


def test_a_change_that_fails_saves_nothing(client):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    before = (projects.project_dir(pid) / "oakbox.json").read_text(encoding="utf-8")
    r = client.patch(f"/api/projects/{pid}/locale", json={"units": "metric", "currency": "XXX"})
    assert r.status_code == 422
    assert (projects.project_dir(pid) / "oakbox.json").read_text(encoding="utf-8") == before


def _write_settings(data) -> None:
    path = appsettings.config_dir() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def test_one_bad_setting_leaves_the_others_and_keeps_a_copy(oakbox_home):
    bad = {"projects": {"a": "/somewhere/A", "b": None}, "zoom": None, "census_api_key": "KEY"}
    _write_settings(bad)
    s = appsettings.load()  # a zoom of null used to stop every request
    assert s.projects == {"a": "/somewhere/A"} and s.census_api_key == "KEY" and s.zoom == 100
    copy = appsettings.config_dir() / appsettings.DAMAGED
    assert json.loads(copy.read_text(encoding="utf-8")) == bad


def test_an_unreadable_settings_file_is_kept_before_anything_writes_over_it(oakbox_home):
    _write_settings("{not json")
    assert appsettings.load() == appsettings.AppSettings()
    appsettings.save(appsettings.load())
    assert (appsettings.config_dir() / appsettings.DAMAGED).read_text(encoding="utf-8") == "{not json"


def test_a_project_kept_elsewhere_is_still_listed_after_a_bad_setting(client, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    assert (
        client.put("/api/app-settings/storage-location", json={"storage_location": str(elsewhere)}).status_code == 200
    )
    pid = client.post("/api/projects", json=NEW).json()["id"]
    assert client.put("/api/app-settings/storage-location", json={"storage_location": None}).status_code == 200
    path = appsettings.config_dir() / "settings.json"
    _write_settings({**json.loads(path.read_text(encoding="utf-8")), "zoom": "very big"})
    assert pid in [p["id"] for p in client.get("/api/projects").json()]


def test_the_street_map_is_openfreemaps_unless_the_settings_name_another(client):
    assert client.get("/api/app-settings").json()["map_style"] == appsettings.MAP_STYLE
    assert appsettings.MAP_STYLE.startswith("https://tiles.openfreemap.org/")
    own = "https://tiles.example.org/styles/ours.json"
    appsettings.save(appsettings.load().model_copy(update={"map_style": own}))
    assert client.get("/api/app-settings").json()["map_style"] == own
