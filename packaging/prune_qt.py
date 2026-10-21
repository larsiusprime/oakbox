"""Strip the parts of Qt (PySide6) that OAK box never loads from a Linux bundle.

Usage: python packaging/prune_qt.py <site-packages>

OAK box's window is pywebview on Qt: widgets plus Qt WebEngine. The PySide6 wheels carry
all of Qt (QML, 3D, multimedia with FFmpeg, Designer, the developer tools), most of the
bundle's size. What's kept is worked out from the files themselves: the Python modules
pywebview imports, Qt WebEngine's helper process and the display plugins, plus every
library those link to (read from each file's ELF dynamic section), repeated until
nothing new turns up. A Python module stays whenever its Qt library does, since PySide6
modules import the modules their API mentions. Everything else under PySide6/ goes.
"""

from __future__ import annotations

import shutil
import struct
import sys
from pathlib import Path

# What pywebview's Qt backend imports (webview/platforms/qt.py), and OAK box's menus.
MODULES = ["QtCore", "QtGui", "QtWidgets", "QtNetwork", "QtWebChannel", "QtWebEngineCore", "QtWebEngineWidgets"]
# Plugin folders Qt loads by itself for a window on X11 or Wayland: display, input,
# OpenGL, icons and images, TLS, desktop look.
PLUGINS = [
    "platforms",
    "platformthemes",
    "platforminputcontexts",
    "xcbglintegrations",
    "wayland-decoration-client",
    "wayland-graphics-integration-client",
    "wayland-shell-integration",
    "generic",
    "iconengines",
    "imageformats",
    "networkinformation",
    "tls",
]
# Plugins in those folders a desktop window doesn't use, and the libraries they'd pull in:
# kiosk and framebuffer displays (EGLFS, linuxfb, VNC, Vulkan display), the on-screen
# keyboard (QML), PDF as an image format (Qt PDF).
SKIP_PLUGINS = {
    "libqeglfs.so",
    "libqminimalegl.so",
    "libqlinuxfb.so",
    "libqvnc.so",
    "libqvkkhrdisplay.so",
    "libqtvirtualkeyboardplugin.so",
    "libqpdf.so",
}
# Data Qt WebEngine reads at run time.
KEEP_DIRS = ["Qt/resources", "Qt/translations/qtwebengine_locales"]
# Python files PySide6 itself needs (its __init__, signatures support).
KEEP_PY = ["__init__.py", "_config.py", "_git_pyside_version.py", "py.typed", "support", "__pycache__"]


def needed(path: Path) -> list[str]:
    """The DT_NEEDED entries of a 64-bit little-endian ELF file (what `readelf -d` lists)."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return []
    shoff, shentsize, shnum = struct.unpack_from("<Q", data, 0x28)[0], *struct.unpack_from("<HH", data, 0x3A)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    out: list[str] = []
    for _name, kind, _flags, _addr, offset, size, link, *_ in sections:
        if kind != 6:  # SHT_DYNAMIC
            continue
        strtab = sections[link][4]
        for pos in range(offset, offset + size, 16):
            tag, value = struct.unpack_from("<qQ", data, pos)
            if tag == 0:
                break
            if tag == 1:  # DT_NEEDED
                end = data.index(b"\0", strtab + value)
                out.append(data[strtab + value : end].decode())
    return out


def prune(site: Path) -> None:
    pyside = site / "PySide6"
    lib = pyside / "Qt" / "lib"
    libs = {p.name: p for p in [*lib.iterdir(), *pyside.glob("lib*.so*")] if p.is_file()}

    keep: set[Path] = set()
    todo = [pyside / f"{m}.abi3.so" for m in MODULES]
    todo += [pyside / "Qt" / "libexec" / "QtWebEngineProcess"]
    for folder in PLUGINS:
        todo += [p for p in (pyside / "Qt" / "plugins" / folder).glob("*.so") if p.name not in SKIP_PLUGINS]
    while todo:
        path = todo.pop()
        if path in keep or not path.exists():
            continue
        keep.add(path)
        for name in needed(path):
            if name in libs:
                todo.append(libs[name])
            if name.startswith("libQt6") and name.endswith(".so.6"):  # libQt6Foo.so.6 -> PySide6.QtFoo
                todo.append(pyside / f"Qt{name[len('libQt6') : -len('.so.6')]}.abi3.so")

    modules = {p.name.split(".")[0] for p in keep if p.parent == pyside and p.name.endswith(".abi3.so")}
    kept_dirs = [pyside / d for d in KEEP_DIRS]
    before = _size(pyside)
    for path in sorted(pyside.rglob("*"), reverse=True):  # files before their folders
        rel = path.relative_to(pyside)
        if (
            path in keep
            or rel.parts[0] in KEEP_PY
            or (path.suffix == ".pyi" and path.stem in modules)
            or any(path == d or d in path.parents for d in kept_dirs)
            or any(path in d.parents for d in [*keep, *kept_dirs])  # a folder holding something kept
        ):
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    print(f"Qt: kept {', '.join(sorted(modules))}; PySide6 {before // 2**20} MB -> {_size(pyside) // 2**20} MB")


def _size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


if __name__ == "__main__":
    prune(Path(sys.argv[1]))
