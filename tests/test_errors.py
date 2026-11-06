"""What the app answers when a request can't be done: what it names isn't there (404), or an earlier step has to run
first (409), said in words; never a 500, which is kept for bugs (oakbox/errors.py)."""

from helpers import NEW


def test_an_unknown_file_is_not_found(client):
    pid = client.post("/api/projects", json=NEW).json()["id"]
    url = f"/api/projects/{pid}/wizard/files/nope"
    for path, body in (("/permits", {"guess": True}), ("/reconcile", {})):
        r = client.put(url + path, json=body)
        assert r.status_code == 404, (path, r.text)  # was a 500: StopIteration


def test_an_earlier_step_to_run_first_says_so_wherever_it_comes_from(client):
    """Looking at a parcel before Bring in data ran: the route only expects an unknown parcel, but the answer is the
    step to run first, not "No parcel 0"."""
    pid = client.post("/api/projects", json=NEW).json()["id"]
    r = client.post(f"/api/projects/{pid}/groups/inspect", json={"groups": [], "index": 0})
    assert r.status_code == 409
    assert r.json()["detail"].startswith("Bring in data first")
