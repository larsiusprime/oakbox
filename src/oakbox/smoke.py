"""End-to-end smoke test through the real app service (used by CI on each platform).

Usage: python -m oakbox.smoke [--sample us-va-petersburgcity]

Starts the app server without a window, creates the sample project over HTTP,
runs steps 1-4 and checks that the value study came back. Uses a throwaway
OAKBOX_HOME unless one is set. Needs internet for the sample download.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

STEPS = ("bring_in_data", "model_groups", "check_sales", "check_values")


def _call(base: str, method: str, path: str) -> dict:
    req = urllib.request.Request(base + path, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _follow(base: str, job_id: str, label: str) -> str:
    """Stream a job's events to stdout; return its final state."""
    last = ""
    with urllib.request.urlopen(f"{base}/api/jobs/{job_id}/events", timeout=3600) as resp:
        event_name = "message"
        for raw in resp:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                if event_name == "end":
                    return data["state"]
                msg = data.get("message", "")
                if msg != last:
                    print(f"  [{label}] {msg}", flush=True)
                    last = msg
                if data.get("type") == "error":
                    print(data.get("detail", ""), flush=True)
            elif line == "":
                event_name = "message"
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(prog="oakbox.smoke")
    parser.add_argument("--sample", default="us-va-petersburgcity")
    parser.add_argument("--port", type=int, default=8799)
    args = parser.parse_args()

    env = dict(os.environ)
    env.setdefault("OAKBOX_HOME", tempfile.mkdtemp(prefix="oakbox-smoke-"))
    base = f"http://127.0.0.1:{args.port}"
    server = subprocess.Popen([sys.executable, "-m", "oakbox", "--no-window", "--port", str(args.port)], env=env)
    try:
        for _ in range(240):
            try:
                _call(base, "GET", "/api/version")
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise SystemExit("App server did not start")

        t0 = time.time()
        job = _call(base, "POST", f"/api/samples/{args.sample}")
        project = job["project_id"]
        if _follow(base, job["id"], "download") != "done":
            raise SystemExit("Sample download failed")
        for step in STEPS:
            job = _call(base, "POST", f"/api/projects/{project}/steps/{step}/run")
            state = _follow(base, job["id"], step)
            if state != "done":
                raise SystemExit(f"Step {step} ended as {state}")
        studies = _call(base, "GET", f"/api/projects/{project}/results/value-studies")
        overall = studies[0]["overall"]["ratio"]
        assert overall["count"] > 0, "value study has no sales"
        print(
            f"SMOKE OK in {time.time() - t0:.0f}s: median ratio {overall['median_ratio']['value']:.3f}, "
            f"COD {overall['cod']['value']:.1f}, {overall['count']} sales",
            flush=True,
        )
    finally:
        server.terminate()
        server.wait(timeout=30)


if __name__ == "__main__":
    main()
