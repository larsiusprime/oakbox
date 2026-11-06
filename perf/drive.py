"""Drive OAK box through a whole valuation over its HTTP API, timing each step: the performance run's driver.

Usage:
  python perf/drive.py <data_dir> --out results.json [--profile potato] [--port 8790] [--home DIR]

<data_dir> holds parcels.parquet and sales.csv (perf/make_county.py). The driver starts OAK box itself (no window)
under the profile's limits (Linux, as root: perf/profiles.py), sets the project up as a user would (the files, their
fields, no downloads), then runs Bring in data, Model groups, Check sales, Prepare, Check my values, the variable
tests, the models and Finalize, accepting each, and fetches the report. Each step's wall time is recorded, and under a
profile its CPU time, peak memory, disk reads and writes and any out-of-memory kill. With no profile it runs
unconstrained, on any OS: the same numbers, less the ones a cgroup gives.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import profiles  # noqa: E402

STEP_TIMEOUT = 4 * 3600


class Api:
    def __init__(self, base: str):
        self.base = base

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 600):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            self.base + path, data=data, method=method, headers={"content-type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                return (
                    json.loads(raw) if raw and r.headers.get("content-type", "").startswith("application/json") else raw
                )
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path}: {e.code} {e.read().decode(errors='replace')[:500]}") from e

    def get(self, path: str):
        return self.call("GET", path)

    def post(self, path: str, body: dict | None = None):
        return self.call("POST", path, body)

    def put(self, path: str, body: dict | None = None):
        return self.call("PUT", path, body)


def wait(api: Api, path: str) -> dict:
    """A run's view once it's no longer running."""
    start = time.time()
    while True:
        view = api.get(path)
        if view.get("status") != "running":
            return view
        if time.time() - start > STEP_TIMEOUT:
            raise TimeoutError(f"{path} still running after {STEP_TIMEOUT}s")
        time.sleep(1.0)


def setup(api: Api, data: Path) -> str:
    """A project as a user would set it up: the two files, their fields, a rule for valid and vacant sales, and no
    downloads (OpenStreetMap, footprints, census and elevation are off: the run is offline)."""
    pid = api.post(
        "/api/projects",
        {
            "name": f"Perf {data.name}",
            "country": "US",
            "region": "VA",
            "jurisdiction": "Perf County",
            "tax_year": 2026,
            "valuation_date": "2026-01-01",
            "units": "imperial",
        },
    )["id"]
    p = f"/api/projects/{pid}"
    for name, file in (("parcels", "parcels.parquet"), ("sales", "sales.csv")):
        api.post(f"{p}/files", {"path": str(data / file), "mode": "copy", "name": name})
    api.put(f"{p}/wizard/files/parcels", {"universe": True, "id_column": "PARCEL_ID"})
    api.put(f"{p}/wizard/files/sales", {"holds": "sales", "id_column": "PARCEL_ID"})
    api.put(f"{p}/wizard/sale-id", {"column": None, "make": True})
    api.put(f"{p}/wizard/enrich", {"distances": False, "footprints": False, "census": False, "elevation": False})
    f = f"{p}/wizard/fields"
    api.put(f"{f}/sale_price", {"file": "sales", "column": "SALE_PRICE"})
    api.put(f"{f}/sale_date", {"file": "sales", "column": "SALE_DATE", "date_format": "%m/%d/%Y"})
    api.put(f"{f}/valid_sale", {"file": "sales", "column": "QUALIFIED"})
    api.put(
        f"{f}/valid_sale/rule",
        {
            "join": "all",
            "conditions": [
                {"column": "QUALIFIED", "op": "isin", "values": ["Q"]},
                {"column": "SALE_PRICE", "op": ">=", "values": ["1000"]},
            ],
        },
    )
    api.put(f"{f}/vacant_sale", {"file": "sales", "column": "VACANT_AT_SALE"})
    api.put(
        f"{f}/vacant_sale/rule",
        {"join": "all", "conditions": [{"column": "VACANT_AT_SALE", "op": "isin", "values": ["Y"]}]},
    )
    higher = {"kind": "higher", "fraction": False, "low": None, "high": None, "tiers": {}}
    for key, column, extra in (
        ("bldg_area_finished_sqft", "LIVING_AREA", {"area_unit": "sqft"}),
        ("bldg_year_built", "YR_BUILT", {}),
        ("bldg_quality_num", "QUALITY", {"scale": higher}),
        ("bldg_condition_num", "CONDITION", {"scale": higher}),
        ("land_class", "LANDUSE", {}),
        ("bldg_type", "BLDGTYPE", {}),
        ("bldg_stories", "STORIES", {}),
        ("assr_market_value", "ASSESSED", {}),
    ):
        api.put(f"{f}/{key}", {"file": "geo_parcels", "column": column, **extra})
    api.put(f"{p}/wizard/locations/neighborhood", {"file": "geo_parcels", "column": "NBHD"})
    return pid


def run_step(api: Api, path: str, accept: bool = True) -> dict:
    """Run a step, wait for it, and say Looks right when it has finished well."""
    try:
        api.get(f"{path}/setup")  # the page shows the step's setup before Run is pressed
    except RuntimeError:
        pass
    api.post(f"{path}/run")
    view = wait(api, path)
    if view.get("status") != "done":
        job = view.get("job") or {}
        last = (job.get("steps") or [{}])[-1].get("message")
        raise RuntimeError(f"{path}: {view.get('status')} at '{last}': {job.get('error')}")
    if accept:
        # As the page does before Looks right can be pressed: read the step's setup (some steps settle their
        # choices from the run's output there), then the step again.
        try:
            api.get(f"{path}/setup")
        except RuntimeError:
            pass
        api.get(path)
        done = api.post(f"{path}/accept")
        if isinstance(done, dict) and done.get("accepted") is False:
            raise RuntimeError(f"{path}: not accepted: {json.dumps(done.get('blocked'))[:400]}")
    return view


def make_lists(api: Api, p: str) -> None:
    """A variable list of each type for every modeled group: the variables the tests recommend for it, as a user
    taking the recommendations would."""
    vl = api.get(f"{p}/varlists")
    groups = [g["id"] for g in vl["groups"] if g.get("modeled")]
    lists = []
    for kind, name in (("ml", "Trees"), ("regression", "Regression")):
        chosen = sorted(
            {v for g in groups for v, why in vl["recommend"].get(g, {}).get(kind, {}).items() if why is None}
        )
        if not chosen:
            chosen = [v["field"] for v in vl["variables"]][:12]
        lists.append({"id": "", "name": name, "kind": kind, "groups": groups, "variables": chosen})
    api.put(f"{p}/varlists", {"lists": lists})


STEPS = [
    "setup",
    "bring_in",
    "model_groups",
    "check_sales",
    "prepare",
    "check_values",
    "variable_tests",
    "models",
    "finalize",
    "report",
]


def stand_in(api: Api, prof: profiles.Profile | None) -> dict:
    """The computer check, as the profile's machine (SPEC §5): its memory (what it leaves OAK box, plus what Windows
    and the usual programs take), its cores, its speed measured under its limits, and graphics in software (headless
    Chromium has no GPU). Without a profile, this machine as it is. Its tier then picks every Recommended setting,
    as on first run."""
    from oakbox.machine import OTHERS_GB

    basics = api.post("/api/machine/basics")
    if prof:
        basics |= {
            "memory_gb": round(prof.memory_mb / 1024 + OTHERS_GB, 1),
            "memory_free_gb": round(prof.memory_mb / 1024, 1),
            "cores": prof.cores,
            "threads": prof.cores,
        }
    speed = api.post("/api/machine/speed")["speed"]
    disk = api.post("/api/machine/disk")["disk_mb_s"]
    found = {**basics, "speed": speed, "disk_mb_s": disk, "graphics": "Google SwiftShader", "cancelled": False}
    return api.put("/api/machine", found)


def drive(api: Api, data: Path, meter: profiles.Meter | None, log) -> dict:
    out: dict = {"steps": {}}
    pid = None

    def step(name: str, fn):
        if meter:
            meter.start()
        t = time.time()
        err = None
        try:
            fn()
        except Exception as e:  # recorded, and the run stops: a later step needs this one
            err = f"{type(e).__name__}: {e}"
        row = {"wall_s": round(time.time() - t, 2), "error": err}
        if meter:
            row |= meter.stop()
        out["steps"][name] = row
        log(f"{name}: {row}")
        if err:
            raise RuntimeError(err)

    try:

        def do_setup():
            nonlocal pid
            pid = setup(api, data)

        step("setup", do_setup)
        p = f"/api/projects/{pid}"
        step("bring_in", lambda: run_step(api, f"{p}/bring-in"))

        def groups():
            gs = api.post(f"{p}/groups/start", {"how": "suggested"})["groups"]
            api.put(f"{p}/groups", {"groups": gs})
            run_step(api, f"{p}/assemble")

        step("model_groups", groups)
        step("check_sales", lambda: run_step(api, f"{p}/clean"))
        step("prepare", lambda: run_step(api, f"{p}/prepare"))
        step("check_values", lambda: run_step(api, f"{p}/ratio"))
        step("variable_tests", lambda: run_step(api, f"{p}/vartest", accept=False))

        def models():
            make_lists(api, p)
            run_step(api, f"{p}/model")

        step("models", models)
        step("finalize", lambda: run_step(api, f"{p}/final"))
        step("report", lambda: (api.get(f"{p}/report"), api.get(f"{p}/report/html")))
    except RuntimeError:
        pass
    out["project"] = pid
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--profile", default=None, help=f"one of {', '.join(profiles.PROFILES)}; none: unconstrained")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--home", type=Path, default=None, help="OAKBOX_HOME for the run (default: a new temp folder)")
    ap.add_argument("--ui", action="store_true", help="also time the pages, in a throttled headless Chromium")
    ap.add_argument(
        "--ui-only", default=None, metavar="PROJECT", help="time the pages of a project already in --home; no steps"
    )
    a = ap.parse_args()

    home = a.home or Path(tempfile.mkdtemp(prefix="oakbox-perf-"))
    home.mkdir(parents=True, exist_ok=True)
    log_path = a.out.with_suffix(".log")
    logf = log_path.open("w", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    prof = profiles.PROFILES.get(a.profile) if a.profile else None
    meter = None
    slower = None
    cmd = [sys.executable, "-X", "utf8", "-m", "oakbox", "--no-window", "--port", str(a.port)]
    # The machine the check records is the profile's, not this one: kept as set (machine.changed).
    env = os.environ | {"OAKBOX_HOME": str(home), "OAKBOX_KEEP_MACHINE": "1"}
    if prof:
        group = profiles.make_group(prof, f"oakbox-perf-{a.port}")
        cmd = profiles.wrap(group, cmd)
        slower = profiles.Slower(prof, group)
        meter = profiles.Meter(group)
    server_log = a.out.with_suffix(".server.log").open("w", encoding="utf-8")
    server = subprocess.Popen(cmd, env=env, stdout=server_log, stderr=subprocess.STDOUT)
    api = Api(f"http://127.0.0.1:{a.port}")
    try:
        for _ in range(120):
            try:
                api.get("/api/projects")
                break
            except Exception:
                time.sleep(1)
        if prof:
            # A cold start: nothing of the data in the file cache, as on a machine that's been doing other work.
            subprocess.run(["sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"], check=False)
        log(f"server up; profile {a.profile or 'none'}; data {a.data}")
        machine = stand_in(api, prof)
        log(f"machine: {machine['machine']['tier']}; {machine['resolved']}")
        idle = meter.snapshot() if meter else {}
        result = {"project": a.ui_only, "steps": {}} if a.ui_only else drive(api, a.data, meter, log)
        if (a.ui or a.ui_only) and result.get("project"):
            # The pages, timed in a throttled headless Chromium (perf/ui.js, Node's Playwright).
            slowdown = prof.ui_slowdown if prof else 1
            ui_out = a.out.with_suffix(".ui.json")
            ui = subprocess.run(
                ["node", str(Path(__file__).parent / "ui.js"), api.base, result["project"], str(slowdown), str(ui_out)],
                capture_output=True,
                text=True,
            )
            for line in ui.stdout.splitlines():
                log(line)
            result["ui"] = json.loads(ui_out.read_text()) if ui_out.is_file() else {"error": ui.stderr[-800:]}
            result["ui_slowdown"] = slowdown
        result |= {
            "machine": machine,
            "profile": a.profile,
            "limits": prof.__dict__ if prof else None,
            "data": str(a.data),
            "parcels": int(a.data.name) if a.data.name.isdigit() else None,
            "idle": idle,
            "host": {"cpus": os.cpu_count(), "platform": platform.platform(), "python": platform.python_version()},
            "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        a.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
        log(f"wrote {a.out}")
    finally:
        if slower:
            slower.stop()
        server.terminate()
        try:
            server.wait(30)
        except subprocess.TimeoutExpired:
            server.kill()
        if prof:
            profiles.drop_group(f"oakbox-perf-{a.port}")
        if not a.home:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
