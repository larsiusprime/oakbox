"""Write engines.json for a bundle: the wheels each optional model engine needs on this platform, from uv.lock, with
their sha256 and size, and how much disk they take unpacked (oakbox/engines.py downloads them; SPEC §6).

    uv run --no-project --with packaging python packaging/engines_manifest.py <windows|linux> <out.json>

An engine's wheels are what OpenAVMKit's extra for it pulls in that the bundle doesn't already have: for CatBoost,
catboost itself plus plotly, narwhals and graphviz. Measuring the unpacked size means downloading them once
(kept in build/engine-wheels, checked against uv.lock's hashes).
"""

import hashlib
import json
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

from packaging.markers import Marker
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

ENGINES = ("xgboost", "catboost")
# NVIDIA's NCCL: xgboost loads it only to train across several GPUs (build_bundle.sh leaves it out of the base too).
LEFT_OUT = {"nvidia-nccl-cu12"}

PLATFORMS = {
    "windows": {
        "env": {"sys_platform": "win32", "platform_system": "Windows", "os_name": "nt", "platform_machine": "AMD64"},
        "platforms": ["win_amd64"],
    },
    "linux": {
        "env": {"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix", "platform_machine": "x86_64"},
        # The bundle's floor is glibc 2.34 (build_bundle.sh); newest first.
        "platforms": [f"manylinux_2_{m}_x86_64" for m in range(34, 4, -1)]
        + ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"],
    },
}
PY = {"python_version": "3.11", "python_full_version": "3.11.15", "implementation_name": "cpython"}
PY |= {"platform_python_implementation": "CPython", "extra": ""}


def closure(lock: dict, start: list[dict], env: dict) -> set[str]:
    by_name = {p["name"]: p for p in lock["package"]}
    seen: set[str] = set()
    todo = list(start)
    while todo:
        dep = todo.pop()
        name = dep["name"]
        if name in seen or name in LEFT_OUT:
            continue
        if "marker" in dep and not Marker(dep["marker"]).evaluate(env):
            continue
        seen.add(name)
        pkg = by_name[name]
        todo += pkg.get("dependencies", [])
        for extra in dep.get("extra", []):
            todo += pkg.get("optional-dependencies", {}).get(extra, [])
    return seen


def pick_wheel(pkg: dict, platforms: list[str]) -> dict:
    """The most specific wheel that installs on this platform with CPython 3.11, as pip would choose."""
    tags = list(cpython_tags((3, 11), platforms=platforms))
    tags += list(compatible_tags((3, 11), "cp311", platforms))
    rank = {t: i for i, t in enumerate(tags)}
    best: tuple[int, dict] | None = None
    for w in pkg.get("wheels", []):
        filename = w["url"].rsplit("/", 1)[1]
        _, _, _, wtags = parse_wheel_filename(filename)
        r = min((rank[t] for t in wtags if t in rank), default=None)
        if r is not None and (best is None or r < best[0]):
            best = (r, {**w, "filename": filename})
    if best is None:
        sys.exit(f"{pkg['name']} {pkg['version']}: no wheel for this platform in uv.lock")
    return best[1]


def unpacked_size(path: Path) -> int:
    with zipfile.ZipFile(path) as z:
        return sum(
            i.file_size
            for i in z.infolist()
            if not i.filename.split("/")[0].endswith(".data") or i.filename.split("/")[1] in ("purelib", "platlib")
        )


def fetch(w: dict, cache: Path) -> Path:
    path = cache / w["filename"]
    want = w["hash"].removeprefix("sha256:")
    if not (path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == want):
        cache.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(w["url"], path)  # noqa: S310 - a URL from uv.lock
        if hashlib.sha256(path.read_bytes()).hexdigest() != want:
            sys.exit(f"{w['filename']}: sha256 doesn't match uv.lock")
    return path


def main() -> None:
    platform, out = sys.argv[1], Path(sys.argv[2])
    spec = PLATFORMS[platform]
    env = {**PY, **spec["env"]}
    root = Path(__file__).resolve().parent.parent
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    by_name = {p["name"]: p for p in lock["package"]}
    oakbox = by_name["oakbox"]
    base = closure(lock, oakbox["dependencies"], env)
    engines = {}
    for key in ENGINES:
        wanted = closure(lock, oakbox["optional-dependencies"][key], env) - base
        if canonicalize_name(key) not in wanted:
            sys.exit(f"{key} is in the bundle already: is OpenAVMKit pinned to a commit where it's optional?")
        wheels = [pick_wheel(by_name[n], spec["platforms"]) for n in sorted(wanted)]
        disk = sum(unpacked_size(fetch(w, root / "build" / "engine-wheels")) for w in wheels)
        engines[key] = {
            "wheels": [
                {
                    "filename": w["filename"],
                    "url": w["url"],
                    "sha256": w["hash"].removeprefix("sha256:"),
                    "size": w["size"],
                }
                for w in wheels
            ],
            "disk": disk,
        }
        print(
            f"  {key}: {', '.join(sorted(wanted))}: {sum(w['size'] for w in wheels) / 1e6:.0f} MB download, "
            f"{disk / 1e6:.0f} MB on disk"
        )
    out.write_text(json.dumps({"platform": platform, "engines": engines}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
