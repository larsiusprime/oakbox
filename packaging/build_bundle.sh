#!/usr/bin/env bash
# Build the Oakbox portable bundle for one platform. Runs on Linux.
#
# Usage: packaging/build_bundle.sh <windows|linux>
#
# Output: dist/oakbox-<plat>/ plus a .zip (Windows) or .tar.gz (Linux)
#   python/        standalone CPython 3.11 (python-build-standalone)
#   site-packages  every dependency for that platform, from uv.lock
#   Oakbox.cmd     (Windows) / oakbox.sh (Linux) launcher
#   smoke.cmd|sh   end-to-end test through the app service on the sample county
#
# No freezing: the interpreter and wheels are shipped as-is (see SPEC §6).
set -euo pipefail
cd "$(dirname "$0")/.."

PLATFORM=${1:?usage: build_bundle.sh <windows|linux>}
PBS="https://github.com/astral-sh/python-build-standalone/releases/download/20260718"
case "$PLATFORM" in
  windows)
    PY_ASSET="cpython-3.11.15%2B20260718-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
    UV_PLATFORM=x86_64-pc-windows-msvc
    NAME=oakbox-win64
    SITE=python/Lib/site-packages ;;
  linux)
    PY_ASSET="cpython-3.11.15%2B20260718-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
    # manylinux_2_34 = glibc 2.34+: Ubuntu 22.04+, Debian 12+, RHEL/Rocky 9+, Fedora 35+.
    # (Qt's PySide6 wheels, for the native window, need 2.34.)
    UV_PLATFORM=x86_64-manylinux_2_34
    NAME=oakbox-linux-x86_64
    SITE=python/lib/python3.11/site-packages ;;
  *) echo "unknown platform: $PLATFORM" >&2; exit 2 ;;
esac

OUT=dist/$NAME
rm -rf "$OUT" "dist/$NAME.zip" "dist/$NAME.tar.gz"
mkdir -p "$OUT" build

[ -f "build/cpython-$PLATFORM.tar.gz" ] || curl -sSfL "$PBS/$PY_ASSET" -o "build/cpython-$PLATFORM.tar.gz"
tar -xzf "build/cpython-$PLATFORM.tar.gz" -C "$OUT"   # unpacks to $OUT/python

# Exact dependency set from the lockfile. openavmkit is pure Python and is built
# here from its pinned commit (pyproject.toml's [tool.uv.sources]: OpenAVMKit's repo and commit).
ENGINE_URL=$(grep -o '^openavmkit = { git = "[^"]*"' pyproject.toml | cut -d'"' -f2)
ENGINE_REV=$(grep -o 'rev = "[0-9a-f]*"' pyproject.toml | cut -d'"' -f2)
if [ ! -d build/engine/.git ] || [ "$(git -C build/engine remote get-url origin)" != "$ENGINE_URL" ]; then
  rm -rf build/engine && git clone -q "$ENGINE_URL" build/engine
fi
git -C build/engine fetch -q origin "$ENGINE_REV" && git -C build/engine checkout -q "$ENGINE_REV"
rm -rf build/wheels && uv build -q --wheel --out-dir build/wheels build/engine

# The UI is built once (it's platform-independent) into src/oakbox/web, then shipped
# inside the oakbox wheel.
(cd web && npm ci --silent && npm run -s build)
uv build -q --wheel --out-dir build/wheels .

# No extras: XGBoost and CatBoost aren't in the bundle (about 560 MB); engines.json lists what OAK box downloads
# for them when asked (oakbox/engines.py, packaging/engines_manifest.py).
uv export --frozen --no-dev --no-emit-project --format requirements.txt \
  | grep -v '^openavmkit @' > build/requirements.txt
if grep -qiE '^(xgboost|catboost)==' build/requirements.txt; then
  echo "xgboost or catboost is a dependency of the bundle: they should only be OpenAVMKit extras" >&2; exit 1
fi
uv pip install -q \
  --python-platform "$UV_PLATFORM" --python-version 3.11 \
  --no-deps \
  --target "$OUT/$SITE" \
  -r build/requirements.txt build/wheels/openavmkit-*.whl build/wheels/oakbox-*.whl
uv run -q --no-project --with packaging python packaging/engines_manifest.py "$PLATFORM" "$OUT/$SITE/oakbox/engines.json"

# Sample counties to try it on (sample/README.md).
cp -r sample "$OUT/sample"
rm -rf "$OUT"/sample/*/.cache  # the downloads make.py keeps; what it made is in in/

# Linux: keep only the parts of Qt the window loads (about 270 MB less).
[ "$PLATFORM" = linux ] && python3 packaging/prune_qt.py "$OUT/$SITE"

# What the bundle never runs: libraries' test suites, headers, static libraries, stubs, pip and setuptools,
# Python's Tk, IDLE and ensurepip (about 140 MB; packaging/strip_bundle.py says what it keeps and why).
python3 packaging/strip_bundle.py "$OUT" "$PLATFORM"

if [ "$PLATFORM" = windows ]; then
  cat > "$OUT/Oakbox.cmd" <<'CMD'
@echo off
rem Start Oakbox. pythonw.exe runs it without a console window; -X utf8: text is UTF-8, not the code page.
start "" "%~dp0python\pythonw.exe" -X utf8 -m oakbox
CMD
  cat > "$OUT/smoke.cmd" <<'CMD'
@echo off
rem End-to-end test through the app service: download the sample county and run steps 1-4.
"%~dp0python\python.exe" -X utf8 -m oakbox.smoke || exit /b 1
CMD
  (cd dist && zip -qr "$NAME.zip" "$NAME")
  du -sh "$OUT" "dist/$NAME.zip"
else
  cat > "$OUT/oakbox.sh" <<'SH'
#!/bin/sh
# Start OAK box: a native Qt window, or a browser window if Qt can't open one here
# (it needs the desktop's usual display libraries, e.g. libEGL and libxcb-cursor on X11).
HERE=$(cd "$(dirname "$0")" && pwd)
exec "$HERE/python/bin/python3" -X utf8 -m oakbox "$@"
SH
  cat > "$OUT/smoke.sh" <<'SH'
#!/bin/sh
# End-to-end test through the app service: download the sample county and run steps 1-4.
HERE=$(cd "$(dirname "$0")" && pwd)
exec "$HERE/python/bin/python3" -X utf8 -m oakbox.smoke
SH
  chmod +x "$OUT/oakbox.sh" "$OUT/smoke.sh"
  tar -czf "dist/$NAME.tar.gz" -C dist "$NAME"
  du -sh "$OUT" "dist/$NAME.tar.gz"
fi
