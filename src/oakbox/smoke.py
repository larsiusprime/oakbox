"""End-to-end smoke test, run by CI on each platform with the bundled Python (SPEC §8).

Usage: python -m oakbox.smoke [--port N]

1. Engine: download Petersburg's public sample (download-only) into a throwaway
   locality, write a checked-in settings.json, and run OpenAVMKit's own stages on it
   (assemble, clean, value-field studies). This proves a bundle can run the engine.
2. App: start the app service without a window, check the UI's script is served as
   JavaScript, create a project and add one of the downloaded files to it.

Uses a throwaway OAKBOX_HOME unless one is set. Needs internet for the download.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from importlib import resources
from pathlib import Path
from urllib.parse import quote

CONTAINER = "https://landeconomics.blob.core.windows.net/localities-public"
PREFIX = "us/va/petersburgcity/"
FILES = ("parcels.geoparquet", "petersburg-dbo-cama-fix.parquet")


def download(in_dir: Path) -> None:
    """Fetch the sample's data files, download-only (never cloud_sync, which can upload)."""
    in_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = in_dir / name
        with urllib.request.urlopen(f"{CONTAINER}/{quote(PREFIX + name)}", timeout=120) as resp, dest.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
        print(f"  [download] {name}: {dest.stat().st_size // 2**10:,} KB", flush=True)


def engine(locality: Path) -> None:
    from openavmkit.headless import run_stage
    from openavmkit.pipeline import load_settings, read_pickle
    from openavmkit.value_studies import run_value_field_studies

    settings = resources.files("oakbox.smokedata").joinpath("us-va-petersburgcity-settings.json").read_text()
    (locality / "in" / "settings.json").write_text(settings)
    last = ""

    def on_progress(event) -> None:
        nonlocal last
        if event.message != last:
            print(f"  [{event.step}] {event.message}", flush=True)
            last = event.message

    run_stage(locality, "assemble", on_progress, lambda: False)
    run_stage(locality, "clean", on_progress, lambda: False)
    previous = os.getcwd()
    os.chdir(locality)
    try:
        results = run_value_field_studies(
            read_pickle("out/2-clean-sup"),
            load_settings(),
            ["assr_market_value"],
            location="neighborhood",
            outpath="out/studies",
        )
    finally:
        os.chdir(previous)
    ratio = results["assr_market_value"]["overall"]["ratio"]
    assert ratio["count"] > 0, "the ratio study has no sales"
    print(
        f"ENGINE OK: median ratio {ratio['median_ratio']['value']:.3f}, "
        f"COD {ratio['cod']['value']:.1f}, {ratio['count']} sales",
        flush=True,
    )


def _call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, method=method, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _check_ui(base: str) -> None:
    """The UI page loads and its module script is served as JavaScript (blank window otherwise)."""
    with urllib.request.urlopen(base + "/", timeout=30) as resp:
        html = resp.read().decode("utf-8")
    match = re.search(r'<script[^>]+src="([^"]+\.js)"', html)
    if match is None:
        raise SystemExit("UI page has no script tag; was the UI built into the bundle?")
    with urllib.request.urlopen(base + match.group(1), timeout=30) as resp:
        content_type = resp.headers.get("content-type", "")
    if not content_type.startswith(("text/javascript", "application/javascript")):
        raise SystemExit(f"UI script served as {content_type!r}; browsers will refuse it")
    print(f"UI OK: {match.group(1)} served as {content_type}", flush=True)


def app(port: int, data_file: Path) -> None:
    env = dict(os.environ)
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen([sys.executable, "-m", "oakbox", "--no-window", "--port", str(port)], env=env)
    try:
        for _ in range(240):
            try:
                _call(base, "GET", "/api/version")
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit("App server did not start")
        _check_ui(base)
        project = _call(
            base,
            "POST",
            "/api/projects",
            {
                "name": "Smoke test",
                "country": "US",
                "region": "VA",
                "jurisdiction": "City of Petersburg",
                "tax_year": 2026,
                "valuation_date": "2026-01-01",
                "units": "imperial",
            },
        )
        pid = project["id"]
        found = _call(base, "POST", f"/api/projects/{pid}/files/check", {"path": str(data_file)})
        if found["problem"]:
            raise SystemExit(f"Checking the file failed: {found['problem']}")
        body = {"path": str(data_file), "mode": "copy", "name": found["suggested_name"]}
        _call(base, "POST", f"/api/projects/{pid}/files", body)
        detail = _call(base, "GET", f"/api/projects/{pid}")
        files = detail["files"]
        assert files and files[0]["size_bytes"] > 0, "the added file isn't in the project"
        settings = json.loads((Path(detail["folder"]) / "in" / "settings.json").read_text())
        assert settings["data"]["load"][files[0]["name"]] == {"filename": data_file.name}
        print(f"APP OK: project created, {data_file.name} added as {files[0]['name']}", flush=True)
    finally:
        server.terminate()
        server.wait(timeout=30)


def main() -> None:
    parser = argparse.ArgumentParser(prog="oakbox.smoke")
    parser.add_argument("--port", type=int, default=8799)
    args = parser.parse_args()
    os.environ.setdefault("OAKBOX_HOME", tempfile.mkdtemp(prefix="oakbox-smoke-"))
    # joblib/loky otherwise shells out to wmic (gone from new Windows) to count cores.
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(max(1, (os.cpu_count() or 2) - 1)))
    t0 = time.time()
    locality = Path(tempfile.mkdtemp(prefix="oakbox-smoke-engine-"))
    download(locality / "in")
    engine(locality)
    app(args.port, locality / "in" / FILES[0])
    print(f"SMOKE OK in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
