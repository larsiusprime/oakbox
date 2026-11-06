"""Machine profiles for performance runs, and the Linux cgroup (v1) limits and meters that stand them up.

A profile caps what OAK box and every process it starts may use: how many cores (cpuset), how fast they run (the
group frozen part of the time: a crude stand-in for a slower chip), how much memory (a hard limit, with out-of-memory
kills counted), and how fast the disk reads (blkio bandwidth; seek time isn't modelled). Needs root and cgroup v1
controllers mounted at /sys/fs/cgroup/<controller>; elsewhere use no profile and the driver runs unconstrained.

The profiles (see perf/README.md for where each comes from):
- vdi:      a virtual desktop session on a shared county host: 2 cores at 60%, 2 GB, ~50 MB/s storage.
- floor:    a 2018-19 budget machine (Pentium Gold, old i3): 2 cores at 75%, 2 GB, HDD-like ~100 MB/s.
- potato:   the main target, a 2018-20 OptiPlex (i3-8100/i5-8500, 8 GB): 4 cores, 2.5 GB for OAK box, SSD.
- current:  a 2025-26 purchase (i5/Ultra 5, 16 GB): 4 cores, 8 GB, SSD.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path("/sys/fs/cgroup")
CONTROLLERS = ("cpu", "cpuacct", "cpuset", "memory", "blkio", "freezer")


@dataclass
class Profile:
    name: str
    cores: int
    speed: float  # share of each core's time it may use (1.0: all of it)
    memory_mb: int
    disk_mb_s: int | None  # read and write bandwidth; None: unlimited
    ui_slowdown: float  # Chrome's CPU throttle for the UI timings


PROFILES = {
    "vdi": Profile("vdi", cores=2, speed=0.6, memory_mb=2048, disk_mb_s=50, ui_slowdown=6),
    "floor": Profile("floor", cores=2, speed=0.75, memory_mb=2048, disk_mb_s=100, ui_slowdown=6),
    "potato": Profile("potato", cores=4, speed=1.0, memory_mb=2560, disk_mb_s=None, ui_slowdown=4),
    "current": Profile("current", cores=4, speed=1.0, memory_mb=8192, disk_mb_s=None, ui_slowdown=1),
}


def _w(path: Path, value: str) -> None:
    path.write_text(value)


def _r(path: Path) -> str:
    return path.read_text().strip()


def _block_devices() -> list[str]:
    """major:minor of each real disk (virtio, SCSI, NVMe), for the bandwidth limits."""
    out = []
    for d in Path("/sys/block").iterdir():
        if d.name.startswith(("vd", "sd", "nvme", "xvd")):
            out.append(_r(d / "dev"))
    return out


def make_group(p: Profile, name: str) -> str:
    """The cgroup for a run, made under each controller with the profile's limits; its name."""
    drop_group(name)
    for c in CONTROLLERS:
        (ROOT / c / name).mkdir(exist_ok=True)
    g = {c: ROOT / c / name for c in CONTROLLERS}
    cpus = os.cpu_count() or 1
    if p.cores > cpus:
        raise ValueError(f"profile {p.name} wants {p.cores} cores; this machine has {cpus}")
    _w(g["cpuset"] / "cpuset.cpus", f"0-{p.cores - 1}" if p.cores > 1 else "0")
    _w(g["cpuset"] / "cpuset.mems", _r(ROOT / "cpuset" / "cpuset.mems") or "0")
    # Slower cores: Slower, below.
    _w(g["memory"] / "memory.limit_in_bytes", str(p.memory_mb * 2**20))
    if p.disk_mb_s:
        bps = p.disk_mb_s * 2**20
        for dev in _block_devices():
            _w(g["blkio"] / "blkio.throttle.read_bps_device", f"{dev} {bps}")
            _w(g["blkio"] / "blkio.throttle.write_bps_device", f"{dev} {bps}")
    return name


class Slower:
    """Slower cores: the run's group frozen (cgroup freezer) for (1 - speed) of every 100 ms. Every thread loses the
    same share of its time, single-threaded steps included, which a CFS quota or a rival process can't do (a quota
    caps the group's total, so one busy thread still gets a whole core; cgroup v1 spreads a rival's shares over the
    cores it runs on). Measured on a Python loop: 0.75 gives 72% of full speed, 0.6 gives 55%. Waits on the disk or
    the network stretch too, as they would on a machine that's busy with other things. Nothing when speed is 1."""

    PERIOD = 0.1

    def __init__(self, p: Profile, name: str):
        self.state = ROOT / "freezer" / name / "freezer.state"
        self.speed = p.speed
        self.stopped = threading.Event()
        self.thread = None
        if p.speed < 1:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _run(self) -> None:
        while not self.stopped.is_set():
            time.sleep(self.PERIOD * self.speed)
            _w(self.state, "FROZEN")
            time.sleep(self.PERIOD * (1 - self.speed))
            _w(self.state, "THAWED")

    def stop(self) -> None:
        self.stopped.set()
        if self.thread:
            self.thread.join()
        if self.state.exists():
            _w(self.state, "THAWED")


def drop_group(name: str) -> None:
    """Remove a run's cgroup (its processes gone first: the server is stopped before)."""
    for c in CONTROLLERS:
        d = ROOT / c / name
        if d.exists():
            for _ in range(20):
                try:
                    d.rmdir()
                    break
                except OSError:
                    for pid in _r(d / "cgroup.procs").split():
                        try:
                            os.kill(int(pid), 9)
                        except OSError:
                            pass
                    time.sleep(0.5)


def wrap(name: str, cmd: list[str]) -> list[str]:
    """A command that joins the run's cgroup (every controller), then becomes `cmd`: its children are in it too."""
    joins = "; ".join(f"echo $$ > {ROOT / c / name / 'cgroup.procs'}" for c in CONTROLLERS)
    return ["sh", "-c", f'{joins}; exec "$@"', "sh", *cmd]


class Meter:
    """What a step used, from the run's cgroup: CPU seconds, peak memory, disk bytes, out-of-memory kills.

    Disk bytes come from each process's /proc/<pid>/io, sampled twice a second: cgroup v1 charges buffered writes
    to the system, not the group, so its own counters miss them (and its bandwidth limit doesn't hold them back:
    only reads from disk are slowed). A process that starts and ends between samples is missed."""

    def __init__(self, name: str):
        self.g = {c: ROOT / c / name for c in CONTROLLERS}
        self.base: dict = {}
        self.seen: dict[int, tuple[int, int]] = {}
        self.lock = threading.Lock()
        threading.Thread(target=self._sample, daemon=True).start()

    def _sample(self) -> None:
        while True:
            try:
                pids = [int(x) for x in _r(self.g["memory"] / "cgroup.procs").split()]
            except OSError:
                return
            for pid in pids:
                try:
                    io = dict(line.split(": ") for line in Path(f"/proc/{pid}/io").read_text().splitlines())
                except OSError:
                    continue
                with self.lock:
                    self.seen[pid] = (int(io["read_bytes"]), int(io["write_bytes"]))
            time.sleep(0.5)

    def _io(self) -> tuple[int, int]:
        with self.lock:
            return sum(v[0] for v in self.seen.values()), sum(v[1] for v in self.seen.values())

    def _ooms(self) -> int:
        for line in _r(self.g["memory"] / "memory.oom_control").splitlines():
            if line.startswith("oom_kill "):
                return int(line.split()[1])
        return int(_r(self.g["memory"] / "memory.failcnt"))

    def snapshot(self) -> dict:
        return {"memory_mb": round(int(_r(self.g["memory"] / "memory.usage_in_bytes")) / 2**20)}

    def start(self) -> None:
        time.sleep(0.6)  # one more sample of what came before
        _w(self.g["memory"] / "memory.max_usage_in_bytes", "0")
        self.base = {
            "cpu": int(_r(self.g["cpuacct"] / "cpuacct.usage")),
            "io": self._io(),
            "oom": self._ooms(),
            "throttled": self._throttled(),
        }

    def _throttled(self) -> int:
        for line in _r(self.g["cpu"] / "cpu.stat").splitlines():
            if line.startswith("throttled_time "):
                return int(line.split()[1])
        return 0

    def stop(self) -> dict:
        time.sleep(0.6)
        read, write = self._io()
        return {
            "cpu_s": round((int(_r(self.g["cpuacct"] / "cpuacct.usage")) - self.base["cpu"]) / 1e9, 2),
            "peak_mb": round(int(_r(self.g["memory"] / "memory.max_usage_in_bytes")) / 2**20),
            "read_mb": round((read - self.base["io"][0]) / 2**20, 1),
            "write_mb": round((write - self.base["io"][1]) / 2**20, 1),
            "oom_kills": self._ooms() - self.base["oom"],
            "throttled_s": round((self._throttled() - self.base["throttled"]) / 1e9, 1),
        }
