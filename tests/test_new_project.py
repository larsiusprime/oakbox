"""F1 New project and F1b project actions (SPEC §3.0)."""

import json

import pytest
from fastapi.testclient import TestClient

from oakbox import appsettings, projects
from oakbox.app import create_app

TRAVIS = {
    "name": "Travis County 2026",
    "country": "US",
    "region": "TX",
    "jurisdiction": "Travis County",
    "tax_year": 2026,
    "valuation_date": "2026-01-01",
    "units": "imperial",
}


@pytest.fixture(autouse=True)
def oakbox_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OAKBOX_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def client():
    return TestClient(create_app())


def test_new_project_writes_only_the_locality_and_valuation_date(client, oakbox_home):
    r = client.post("/api/projects", json=TRAVIS)
    assert r.status_code == 200, r.text
    p = r.json()
    folder = oakbox_home / "Travis County 2026"
    assert (folder / "in").is_dir() and (folder / "out").is_dir()
    settings = json.loads((folder / "in" / "settings.json").read_text())
    assert settings["locality"] == {
        "name": "Travis County",
        "state": "TX",
        "units": "imperial",
        "slug": "us-tx-traviscounty",
    }
    assert settings["modeling"] == {"metadata": {"valuation_date": "2026-01-01"}}
    assert "data" not in settings and "center" not in settings["locality"]
    assert client.get(f"/api/projects/{p['id']}").json()["project"]["jurisdiction"] == "Travis County"


def test_new_project_checks_what_the_user_entered(client):
    assert client.post("/api/projects", json=TRAVIS | {"region": "Texas"}).status_code == 422  # US: pick a state
    assert client.post("/api/projects", json=TRAVIS | {"country": "XX"}).status_code == 422
    assert client.post("/api/projects", json=TRAVIS | {"jurisdiction": " "}).status_code == 422
    other = TRAVIS | {"country": "CA", "region": "Ontario", "jurisdiction": "City of Ottawa", "units": "metric"}
    assert client.post("/api/projects", json=other).status_code == 200  # elsewhere the region is free text


def test_regions_list_countries_and_us_states(client):
    r = client.get("/api/regions").json()
    assert {"code": "US", "name": "United States"} in r["countries"]
    assert len(r["subdivisions"]["US"]) == 51  # 50 states and DC


def test_storage_location_applies_to_new_projects_only(client, tmp_path):
    first = client.post("/api/projects", json=TRAVIS).json()
    elsewhere = tmp_path / "elsewhere"
    view = client.put("/api/app-settings/storage-location", json={"storage_location": str(elsewhere)}).json()
    assert view["storage_location"] == str(elsewhere)
    second = client.post("/api/projects", json=TRAVIS | {"name": "Travis 2027"}).json()
    assert projects.project_dir(second["id"]) == elsewhere / "Travis 2027"
    assert {p["id"] for p in client.get("/api/projects").json()} == {first["id"], second["id"]}  # both still listed
    reset = client.put("/api/app-settings/storage-location", json={"storage_location": None}).json()
    assert reset["storage_location"] == reset["default_storage_location"]


def test_projects_from_the_first_builds_are_still_found(tmp_path, monkeypatch):
    legacy = tmp_path / "Documents" / "Oakbox" / "us-va-cityofpetersburg-2026"
    legacy.mkdir(parents=True)
    old = {
        "id": "us-va-cityofpetersburg-2026",
        "name": "City of Petersburg",
        "tax_year": 2026,
        "created_at": "2026-10-01T00:00:00Z",
        "sample": None,
    }
    (legacy / "oakbox.json").write_text(json.dumps(old))
    monkeypatch.setattr(appsettings, "legacy_storage", lambda: legacy.parent)
    assert [p.id for p in projects.list_projects()] == ["us-va-cityofpetersburg-2026"]
    assert projects.project_dir("us-va-cityofpetersburg-2026") == legacy


def test_delete_sends_the_folder_to_the_trash(client, tmp_path):
    p = client.post("/api/projects", json=TRAVIS).json()
    folder = projects.project_dir(p["id"])
    disk = client.get(f"/api/projects/{p['id']}/disk").json()
    assert disk["files"] >= 2 and disk["folder"] == str(folder)
    assert client.delete(f"/api/projects/{p['id']}").status_code == 200
    assert not folder.exists()
    assert any((tmp_path / "xdg" / "Trash" / "files").iterdir())  # recoverable from the trash
    assert client.get(f"/api/projects/{p['id']}").status_code == 404
    assert client.get("/api/projects").json() == []


def test_show_in_folder_opens_the_file_manager(client, monkeypatch):
    p = client.post("/api/projects", json=TRAVIS).json()
    opened = []
    monkeypatch.setattr(projects.subprocess, "Popen", lambda args: opened.append(args))
    monkeypatch.setattr(projects.shutil, "which", lambda _: "/usr/bin/xdg-open")
    assert client.post(f"/api/projects/{p['id']}/show-in-folder").status_code == 200
    assert opened == [["xdg-open", str(projects.project_dir(p["id"]))]]


def test_currency_number_style_and_units_come_from_the_country_and_can_be_changed(client, oakbox_home):
    regions = client.get("/api/regions").json()
    assert regions["defaults"]["US"] == {"currency": "USD", "numbers": "1,234.56", "units": "imperial"}
    assert regions["defaults"]["DE"] == {"currency": "EUR", "numbers": "1.234,56", "units": "metric"}
    assert regions["defaults"]["CH"]["numbers"] == "1'234.56"
    assert {"code": "EUR", "name": "Euro", "symbol": "€"} in regions["currencies"]

    berlin = {**TRAVIS, "name": "Berlin", "country": "DE", "region": "Berlin", "jurisdiction": "Berlin"}
    del berlin["units"]
    p = client.post("/api/projects", json=berlin).json()
    assert (p["currency"], p["numbers"], p["units"]) == ("EUR", "1.234,56", "metric")
    # Chosen at creation: kept, whatever the country says.
    p2 = client.post(
        "/api/projects", json={**berlin, "name": "Berlin 2", "currency": "USD", "units": "imperial"}
    ).json()
    assert (p2["currency"], p2["numbers"], p2["units"]) == ("USD", "1.234,56", "imperial")
    assert client.post("/api/projects", json={**berlin, "name": "B3", "currency": "XYZ"}).status_code == 422

    # Changed later, under Metadata: units reach OpenAVMKit's settings.
    r = client.patch(f"/api/projects/{p['id']}/locale", json={"numbers": "1 234,56", "units": "imperial"})
    assert (r.json()["currency"], r.json()["numbers"], r.json()["units"]) == ("EUR", "1 234,56", "imperial")
    settings = json.loads((oakbox_home / "Berlin" / "in" / "settings.json").read_text())
    assert settings["locality"]["units"] == "imperial"
    assert client.patch(f"/api/projects/{p['id']}/locale", json={"currency": "nope"}).status_code == 422

    # A project saved before these existed takes its country's.
    path = oakbox_home / "Berlin" / "oakbox.json"
    old = json.loads(path.read_text())
    del old["currency"], old["numbers"]
    path.write_text(json.dumps(old))
    assert projects.load(p["id"]).currency == "EUR"
