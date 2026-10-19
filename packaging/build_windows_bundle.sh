#!/usr/bin/env bash
# Cross-build the Oakbox portable Windows bundle from Linux (M0 spike).
#
# Output: dist/oakbox-win64/ and dist/oakbox-win64.zip
#   python/            standalone CPython 3.11 (python-build-standalone, MSVC build)
#   python/Lib/site-packages/  every dependency as a win_amd64 wheel, from uv.lock
#   app/               Oakbox source and spike scripts
#   smoke.cmd          offline end-to-end smoke test on a 2k synthetic county
#
# No freezing: the interpreter and wheels are shipped as-is (see SPEC §6).
set -euo pipefail
cd "$(dirname "$0")/.."

PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20260718/cpython-3.11.15%2B20260718-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
OUT=dist/oakbox-win64
rm -rf "$OUT" dist/oakbox-win64.zip
mkdir -p "$OUT/app" build

[ -f build/cpython-win64.tar.gz ] || curl -sSfL "$PY_URL" -o build/cpython-win64.tar.gz
tar -xzf build/cpython-win64.tar.gz -C "$OUT"   # unpacks to $OUT/python

# Exact dependency set from the lockfile. Everything must be a prebuilt win_amd64 wheel,
# except openavmkit, which is pure Python and built here from its pinned commit.
ENGINE_REV=$(grep -o 'rev = "[0-9a-f]*"' pyproject.toml | cut -d'"' -f2)
if [ ! -d build/engine ]; then
  git clone -q https://github.com/larsiusprime/oakbox build/engine
fi
git -C build/engine fetch -q origin "$ENGINE_REV" && git -C build/engine checkout -q "$ENGINE_REV"
rm -rf build/wheels && uv build -q --wheel --out-dir build/wheels build/engine

uv export --frozen --no-dev --no-emit-project --format requirements.txt \
  | grep -v '^openavmkit @' > build/requirements-win.txt
uv pip install -q \
  --python-platform x86_64-pc-windows-msvc --python-version 3.11 \
  --no-deps \
  --target "$OUT/python/Lib/site-packages" \
  -r build/requirements-win.txt build/wheels/openavmkit-*.whl

cp -r src/oakbox "$OUT/app/oakbox"
mkdir -p "$OUT/app/spikes"
cp -r spikes/m0 "$OUT/app/spikes/m0"

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

(cd dist && zip -qr oakbox-win64.zip oakbox-win64)
du -sh "$OUT" dist/oakbox-win64.zip
