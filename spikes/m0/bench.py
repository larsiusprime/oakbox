"""Time each Oakbox step and sample peak memory of its whole process tree.

Usage: python bench.py <base_dir> <slug> <quick|thorough> [steps...]

Appends one JSON line per step to <base_dir>/bench.jsonl. Peak memory is the max
over 0.25 s samples of summed RSS across the step process and its children
(loky/joblib workers), so shared pages may be counted more than once.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

STAGE = Path(__file__).with_name("stage.py")


def tree_rss(proc: psutil.Process) -> int:
    total = 0
    for p in [proc, *proc.children(recursive=True)]:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


def run(base: Path, slug: str, step: str, tier: str) -> dict:
    log = base / f"{slug}.{tier}.{step}.log"
    t0 = time.time()
    with log.open("w") as fh:
        child = subprocess.Popen(
            [sys.executable, str(STAGE), str(base), slug, step, tier], stdout=fh, stderr=subprocess.STDOUT
        )
        proc = psutil.Process(child.pid)
        peak = 0
        while child.poll() is None:
            peak = max(peak, tree_rss(proc))
            time.sleep(0.25)
    marks = [json.loads(line.split("@@OAKBOX ", 1)[1]) for line in log.read_text().splitlines() if "@@OAKBOX " in line]
    for m in marks:
        m.pop("summary", None)
        m.pop("columns", None)
    return {
        "slug": slug, "tier": tier, "step": step, "ok": child.returncode == 0,
        "seconds": round(time.time() - t0, 1), "peak_rss_gb": round(peak / 2**30, 2), "marks": marks,
    }


def main() -> None:
    base, slug, tier = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    steps = sys.argv[4:] or ["assemble", "clean", "check_values", "model"]
    for step in steps:
        result = run(base, slug, step, tier)
        with (base / "bench.jsonl").open("a") as fh:
            fh.write(json.dumps(result) + "\n")
        print(f"{slug} {tier} {step}: ok={result['ok']} {result['seconds']}s peak={result['peak_rss_gb']} GB", flush=True)
        if not result["ok"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
