"""Where a slow request spent its time (profiler), and a slow click as the window saw it: both written to OAK box's
log, so a slow click can be diagnosed from the log alone."""

import time

from fastapi.testclient import TestClient

from oakbox import app as app_module
from oakbox import applog, profiler
from oakbox.app import create_app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(app_module, "SLOW", 0.2)
    app = create_app()

    def busy() -> None:  # our own code at work for a while: profiler._library, over and over
        start = time.perf_counter()
        while time.perf_counter() - start < 0.5:
            profiler._library("/venv/lib/site-packages/pandas/core/frame.py")

    app.add_api_route("/api/busy", busy)
    app.router.routes.insert(0, app.router.routes.pop())  # before the page's catch-all
    return TestClient(app)


def test_a_slow_request_is_logged_with_where_its_time_went(oakbox_home, monkeypatch):
    assert _client(monkeypatch).get("/api/busy").status_code == 200
    text = applog.log_file().read_text(encoding="utf-8")
    assert "slow: GET /api/busy took" in text
    seen = next(line for line in text.splitlines() if "its own work seen" in line)
    assert not seen.strip().startswith("its own work seen 0.0 s")  # the worker thread was known to be its
    assert "oakbox/profiler.py:" in text and "_library" in text


def test_a_quick_request_is_not_logged(oakbox_home, monkeypatch):
    assert _client(monkeypatch).get("/api/version").status_code == 200
    assert "slow:" not in (applog.log_file().read_text(encoding="utf-8") if applog.log_file().exists() else "")


def test_a_slow_click_is_logged_with_its_requests(oakbox_home, monkeypatch):
    click = {
        "what": "Date",
        "page": "/#/projects/x/fields/sale_date",
        "took": 22.1,
        "requests": [
            {
                "method": "PUT",
                "path": "/api/projects/…/wizard/fields/sale_date",
                "at": 0.1,
                "took": 18.4,
                "status": 200,
            },
            {"method": "GET", "path": "/api/projects/…/wizard", "at": 18.6, "took": 2.1, "status": 200},
        ],
        "busy": 0.7,
        "neither": 0.9,
    }
    assert _client(monkeypatch).post("/api/log/slow-click", json=click).status_code == 200
    text = applog.log_file().read_text(encoding="utf-8")
    assert "slow click: 'Date' on /#/projects/x/fields/sale_date took 22.1 s to settle" in text
    assert "2 requests, the service answering 20.5 s of it, the window busy 0.7 s, 0.9 s neither" in text
    assert "+  0.1 s   18.4 s  PUT /api/projects/…/wizard/fields/sale_date 200" in text
