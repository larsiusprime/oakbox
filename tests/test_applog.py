"""OAK box's own log (applog): a request that fails with a bug is written there with its traceback, and the page is
told its reference, to copy; the performance report carries the log's end."""

from fastapi.testclient import TestClient

from oakbox import applog, timing
from oakbox.app import create_app


def _failing_client() -> TestClient:
    app = create_app()

    def boom() -> None:
        raise KeyError("no_such_column")

    app.add_api_route("/api/boom", boom)
    app.router.routes.insert(0, app.router.routes.pop())  # before the page's catch-all

    # The 500's answer, as the page gets it (TestClient would raise it otherwise).
    return TestClient(app, raise_server_exceptions=False)


def test_a_failed_request_is_logged_with_its_traceback_and_a_reference(oakbox_home):
    r = _failing_client().get("/api/boom")
    assert r.status_code == 500
    failure = r.json()["failure"]
    assert failure["request"] == "GET /api/boom"
    assert failure["what"] == "KeyError: 'no_such_column'"
    log = applog.log_file()
    assert failure["log"] == str(log) and log.is_relative_to(oakbox_home)
    text = log.read_text(encoding="utf-8")
    assert f"[{failure['ref']}] GET /api/boom failed: KeyError" in text
    assert "Traceback (most recent call last)" in text and 'raise KeyError("no_such_column")' in text


def test_expected_refusals_are_not_logged_as_failures(client):
    assert client.get("/api/projects/nope").status_code == 404
    assert "failed:" not in (applog.log_file().read_text(encoding="utf-8") if applog.log_file().exists() else "")


def test_where_the_log_is(client, oakbox_home):
    info = client.get("/api/log").json()
    assert info["file"] == str(applog.log_file()) and info["folder"] == str(oakbox_home / ".oakbox" / "logs")


def test_the_performance_report_carries_the_logs_end(tmp_path):
    _failing_client().get("/api/boom")
    import zipfile

    project = tmp_path / "p"
    project.mkdir()
    with zipfile.ZipFile(timing.report(project)) as z:
        assert "KeyError" in z.read("logs/oakbox.log").decode("utf-8")


def test_a_native_crash_is_in_the_log_on_the_next_start(tmp_path):
    """A crash below Python leaves every thread's stack; the next start puts it in the log, once."""
    import os
    import subprocess
    import sys

    env = {**os.environ, "OAKBOX_HOME": str(tmp_path)}
    crash = "from oakbox import applog; import faulthandler; applog.watch_for_crashes(); faulthandler._sigsegv()"
    start = "from oakbox import applog; applog.watch_for_crashes()"
    assert subprocess.run([sys.executable, "-c", crash], env=env, capture_output=True).returncode != 0
    for _ in range(2):
        subprocess.run([sys.executable, "-c", start], env=env, check=True)
    text = (tmp_path / ".oakbox" / "logs" / "oakbox.log").read_text(encoding="utf-8")
    assert text.count("The last run crashed") == 1 and "Segmentation fault" in text
    assert text.rstrip().endswith("OAK box stopped (closed normally)")
