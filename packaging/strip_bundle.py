"""Strip what a bundle carries but never runs (SPEC §6, Packaging): libraries' own test suites, C headers, static
libraries and type stubs, pip and setuptools, and Python's Tk GUI toolkit, IDLE and ensurepip.

    python3 packaging/strip_bundle.py <bundle dir> <windows|linux>

Kept on purpose:
- a library's `testing` module (numpy.testing, pandas._testing…): some import it at run time; only folders named
  `tests` or `test` go
- C sources (.c, .cpp): headers go, but a library could in principle compile its own sources at run time
- every .dist-info: importlib.metadata reads them (OAK box's own version, for one)
Nothing imports tkinter at run time (matplotlib falls back to a non-GUI backend without it); nothing imports
pkg_resources but pytz, which tries importlib.resources first. CI's smoke tests run the stripped bundle end to end.
"""

import shutil
import sys
from pathlib import Path

TEST_DIRS = {"tests", "test"}
JUNK_SUFFIXES = {".h", ".hpp", ".pxd", ".pyx", ".pyi", ".lib", ".a"}
TOOLS = ("pip", "setuptools", "_distutils_hack", "pkg_resources")


def size(p: Path) -> int:
    if p.is_file() or p.is_symlink():
        return p.lstat().st_size
    return sum(f.lstat().st_size for f in p.rglob("*") if f.is_file() or f.is_symlink())


def main() -> None:
    root, platform = Path(sys.argv[1]), sys.argv[2]
    py = root / "python"
    if platform == "windows":
        lib, site = py / "Lib", py / "Lib" / "site-packages"
        gone = [py / "tcl", py / "include", py / "libs", py / "Scripts"]
        gone += [py / "DLLs" / n for n in ("_tkinter.pyd", "tcl86t.dll", "tk86t.dll")]
    elif platform == "linux":
        lib, site = py / "lib" / "python3.11", py / "lib" / "python3.11" / "site-packages"
        gone = [py / "include"]
        gone += [p for p in (py / "lib").iterdir() if p.name.startswith(("tcl", "tk", "itcl", "libtcl", "libtk"))]
        gone += list((lib / "lib-dynload").glob("_tkinter*"))
    else:
        sys.exit(f"unknown platform: {platform}")
    gone += [lib / n for n in ("tkinter", "idlelib", "turtledemo", "ensurepip")]
    # pip and setuptools: nothing installs into a bundle once it's built.
    for name in TOOLS:
        gone.append(site / name)
        gone += list(site.glob(f"{name}-*.dist-info"))
    gone.append(site / "distutils-precedence.pth")

    removed: dict[str, int] = {}

    def drop(p: Path, why: str) -> None:
        if not (p.exists() or p.is_symlink()):
            return
        removed[why] = removed.get(why, 0) + size(p)
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()

    for p in gone:
        drop(p, "Python's Tk, IDLE, ensurepip, headers; pip, setuptools")
    # Libraries' test suites: folders named tests/test inside a package (not their `testing` modules).
    for d in sorted(site.rglob("*"), key=lambda p: len(p.parts)):
        if d.is_dir() and d.name in TEST_DIRS and d.parent != site and d.exists():
            drop(d, "libraries' test suites")
    for f in site.rglob("*"):
        if f.is_file() and f.suffix in JUNK_SUFFIXES:
            drop(f, "headers, static libraries, type stubs")
    for d in sorted(site.rglob("include"), key=lambda p: -len(p.parts)):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    total = sum(removed.values())
    for why, n in sorted(removed.items(), key=lambda x: -x[1]):
        print(f"  stripped {n / 1e6:6.0f} MB  {why}")
    print(f"  stripped {total / 1e6:6.0f} MB in all")


if __name__ == "__main__":
    main()
