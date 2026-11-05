"""Run every profile on every size, smallest first, one run at a time: the performance matrix.

Usage: python perf/matrix.py <work_dir> [--profiles vdi,floor,potato,current] [--sizes 5000,20000,50000]

Makes each county under <work_dir>/data/<n> (once), then runs perf/drive.py --ui for each pair into
<work_dir>/results/<profile>-<n>.json, skipping any already there, so a stopped matrix picks up where it was. A run
that fails is recorded (its steps up to the failure) and the matrix goes on. Linux, as root (perf/profiles.py).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("work", type=Path)
    ap.add_argument("--profiles", default="vdi,floor,potato,current")
    ap.add_argument("--sizes", default="5000,20000,50000")
    ap.add_argument("--port", type=int, default=8790)
    a = ap.parse_args()
    sizes = [int(x) for x in a.sizes.split(",")]
    profs = a.profiles.split(",")
    (a.work / "results").mkdir(parents=True, exist_ok=True)
    for n in sizes:
        data = a.work / "data" / str(n)
        if not (data / "sales.csv").is_file():
            subprocess.run([sys.executable, str(HERE / "make_county.py"), str(data), str(n)], check=True)
        for p in profs:
            out = a.work / "results" / f"{p}-{n}.json"
            if out.is_file():
                continue
            t = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {p} {n:,} ...", flush=True)
            subprocess.run(
                [
                    sys.executable,
                    str(HERE / "drive.py"),
                    str(data),
                    "--out",
                    str(out),
                    "--profile",
                    p,
                    "--port",
                    str(a.port),
                    "--ui",
                ],
                check=False,
            )
            print(f"[{time.strftime('%H:%M:%S')}] {p} {n:,} done in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
