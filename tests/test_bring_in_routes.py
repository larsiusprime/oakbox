"""Bring in data's routes for a run under way and for what it brought in: skipping one part of a run (an
enrichment), and one field of the parcel universe or the sales record in detail."""

import time

import pytest
from helpers import NEW

from oakbox import bring_in, projects, steps

# ---------- Skipping a part of the run ----------


def test_skipping_asks_the_running_run_to_leave_that_part_out(client, monkeypatch):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    url = f"/api/projects/{pid}/bring-in/skip"
    # Nothing running yet: nothing to skip.
    r = client.post(f"{url}/census")
    assert r.status_code == 409 and "Nothing is running" in r.json()["detail"]

    # A run under way (as steps.start leaves it, without its process).
    key = f"{bring_in.MODULE}:{pid}"
    monkeypatch.setitem(steps._jobs, key, steps.Job(status="running", started=time.time(), part="census"))
    r = client.post(f"{url}/census")
    assert r.status_code == 200
    assert r.json()["job"]["skipping"] == ["census"]
    # The run reads its parts to skip from a file, one a line, at each checkpoint.
    asked = steps.skip_path(projects.project_dir(pid), bring_in.MODULE).read_text(encoding="utf-8")
    assert asked.splitlines() == ["census"]
    # Asked again: said once.
    assert client.post(f"{url}/census").json()["job"]["skipping"] == ["census"]


def test_only_an_enrichment_can_be_skipped(client, monkeypatch):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    key = f"{bring_in.MODULE}:{pid}"
    monkeypatch.setitem(steps._jobs, key, steps.Job(status="running", started=time.time()))
    r = client.post(f"/api/projects/{pid}/bring-in/skip/load")
    assert r.status_code == 409 and "can't be skipped" in r.json()["detail"]
    assert not steps.skip_path(projects.project_dir(pid), bring_in.MODULE).exists()


# ---------- One field in detail ----------


@pytest.fixture
def field_url(brought_in_client, brought_in):
    pid = brought_in[1]
    return brought_in_client, f"/api/projects/{pid}/bring-in/fields"


def test_a_number_field_has_its_statistics_and_spread(field_url):
    client, url = field_url
    r = client.get(f"{url}/sales/sale_price")
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["kind"] == "number" and p["field"] == "sale_price"
    assert p["rows"] > 0 and p["blank"] == 0
    assert p["stats"] and p["histogram"]


def test_a_category_field_has_its_values_most_common_first(field_url):
    client, url = field_url
    p = client.get(f"{url}/universe/subdivision").json()
    assert p["kind"] == "category"
    assert sorted(v["value"] for v in p["values"]) == ["OAKS", "PINES"]
    assert p["distinct"] == 2 and p["rows"] == 40
    counts = [v["count"] for v in p["values"]]
    assert counts == sorted(counts, reverse=True)


def test_a_fields_values_can_be_searched_and_sorted(field_url):
    client, url = field_url
    found = client.get(f"{url}/universe/subdivision", params={"search": "oak"}).json()["values"]
    assert [v["value"] for v in found] == ["OAKS"]
    by_value = client.get(f"{url}/universe/subdivision", params={"sort": "value", "desc": False}).json()["values"]
    assert [v["value"] for v in by_value] == ["OAKS", "PINES"]


@pytest.mark.parametrize(
    "path",
    ["universe/no_such_field", "sales/no_such_field", "rows/subdivision"],
    ids=["a field the universe hasn't", "a field the sales haven't", "neither the universe nor the sales"],
)
def test_a_field_that_isnt_there_is_404(field_url, path):
    client, url = field_url
    r = client.get(f"{url}/{path}")
    assert r.status_code == 404
    assert "bring in data first" in r.json()["detail"]
