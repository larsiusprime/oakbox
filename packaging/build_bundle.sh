#!/usr/bin/env bash
# Build the Oakbox portable bundle for one platform (M0 spike). Runs on Linux.
#
# Usage: packaging/build_bundle.sh <windows|linux>
#
# Output: dist/oakbox-<plat>/ plus a .zip (Windows) or .tar.gz (Linux)
#   python/        standalone CPython 3.11 (python-build-standalone)
#   site-packages  every dependency for that platform, from uv.lock
#   app/           Oakbox source and spike scripts
#   smoke.cmd|sh   offline end-to-end smoke test on a 2k synthetic county
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
    # manylinux_2_28 = glibc 2.28+: Ubuntu 20.04+, Debian 10+, RHEL/Rocky 8+.
    UV_PLATFORM=x86_64-manylinux_2_28
    NAME=oakbox-linux-x86_64
    SITE=python/lib/python3.11/site-packages ;;
  *) echo "unknown platform: $PLATFORM" >&2; exit 2 ;;
esac

OUT=dist/$NAME
rm -rf "$OUT" "dist/$NAME.zip" "dist/$NAME.tar.gz"
mkdir -p "$OUT/app" build

[ -f "build/cpython-$PLATFORM.tar.gz" ] || curl -sSfL "$PBS/$PY_ASSET" -o "build/cpython-$PLATFORM.tar.gz"
tar -xzf "build/cpython-$PLATFORM.tar.gz" -C "$OUT"   # unpacks to $OUT/python

# Exact dependency set from the lockfile. openavmkit is pure Python and is built
# here from its pinned commit (CI checks the engine branch out into build/engine).
ENGINE_REV=$(grep -o 'rev = "[0-9a-f]*"' pyproject.toml | cut -d'"' -f2)
if [ ! -d build/engine ]; then
  git clone -q https://github.com/larsiusprime/oakbox build/engine
fi
git -C build/engine fetch -q origin "$ENGINE_REV" && git -C build/engine checkout -q "$ENGINE_REV"
rm -rf build/wheels && uv build -q --wheel --out-dir build/wheels build/engine

uv export --frozen --no-dev --no-emit-project --format requirements.txt \
  | grep -v '^openavmkit @' > build/requirements.txt
uv pip install -q \
  --python-platform "$UV_PLATFORM" --python-version 3.11 \
  --no-deps \
  --target "$OUT/$SITE" \
  -r build/requirements.txt build/wheels/openavmkit-*.whl

cp -r src/oakbox "$OUT/app/oakbox"
mkdir -p "$OUT/app/spikes"
cp -r spikes/m0 "$OUT/app/spikes/m0"

if [ "$PLATFORM" = windows ]; then
  cat > "$OUT/smoke.cmd" <<'CMD'
@echo off
rem Oakbox M0 smoke test: build a 2k-parcel synthetic county and run every step offline.
setlocal
set HERE=%~dp0
set PY=%HERE%python\python.exe
set WORK=%HERE%work
if not exist "%WORK%" mkdir "%WORK%"
"%PY%" "%HERE%app\spikes\m0\make_synthetic.py" 2000 "%WORK%" || exit /b 1
"%PY%" "%HERE%app\spikes\m0\bench.py" "%WORK%" us-zz-synth2k quick || exit /b 1
echo SMOKE OK
CMD
  (cd dist && zip -qr "$NAME.zip" "$NAME")
  du -sh "$OUT" "dist/$NAME.zip"
else
  cat > "$OUT/smoke.sh" <<'SH'
#!/bin/sh
# Oakbox M0 smoke test: build a 2k-parcel synthetic county and run every step offline.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PY="$HERE/python/bin/python3"
WORK="$HERE/work"
mkdir -p "$WORK"
"$PY" "$HERE/app/spikes/m0/make_synthetic.py" 2000 "$WORK"
"$PY" "$HERE/app/spikes/m0/bench.py" "$WORK" us-zz-synth2k quick
echo SMOKE OK
SH
  chmod +x "$OUT/smoke.sh"
  tar -czf "dist/$NAME.tar.gz" -C dist "$NAME"
  du -sh "$OUT" "dist/$NAME.tar.gz"
fi
