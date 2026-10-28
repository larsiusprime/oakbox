# Guidance for coding agents (OAK box)

OAK box is a desktop app, and **most of its users are on Windows**. Develop and test on Linux, but write for
Windows first. SPEC.md is the product spec: keep it in step with what's built.

## Windows: text is always UTF-8 (non-negotiable)

Windows Python reads and writes text in the system code page (cp1252, "charmap") unless told otherwise. A "−", "é",
"²" or "✓" then stops a run on Windows that passes everywhere else (`UnicodeEncodeError: 'charmap' codec can't
encode character…`). Every time you touch I/O:

- **Every text read and write says `encoding="utf-8"`:** `open()`, `Path.read_text()` / `write_text()` / `.open()`,
  `importlib.resources` `read_text()`, `io.TextIOWrapper`, text-mode temp files, `subprocess` with `text=True`
  (also give `errors="replace"` when reading another program's output). Never rely on the default.
  `tests/test_encoding.py` fails on any that doesn't.
- **CSVs and other files the user brings** may not be UTF-8 (Excel writes cp1252, sometimes with a BOM). Read them
  as their files are, never as the computer's default; `utf-8-sig` drops a BOM.
- **Every Python process OAK box starts runs in UTF-8 mode** (`-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`:
  `bring_in.child_env()`), so OpenAVMKit's own reads, writes and prints are UTF-8 too. The launchers
  (`Oakbox.cmd`, `oakbox.sh`, `run.bat`) start it with `-X utf8`. A new launcher or subprocess does the same.
- **Printing:** `pythonw` has no console (`sys.stdout` is `None`); a console may not be UTF-8. The app reconfigures
  its streams to UTF-8; don't print where it can fail a run.
- **Also Windows:** paths with spaces and non-ASCII letters (`C:\Users\José\Documents\OAK box`), `\` separators
  (use `pathlib`, never string paths), a file open in Excel can't be replaced (say so, don't crash), names are
  case-insensitive, `os.rename` onto an existing file fails (use `os.replace`), CRLF line endings in files users
  bring.
- **Check it:** CI runs the whole suite a second time with a non-UTF-8 default encoding (ASCII, stricter than
  cp1252). Do the same before pushing:
  `PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 LC_ALL=C LANG=C uv run pytest -q tests`

## Going online

- Downloads check certificates as the computer does: every process OAK box starts calls
  `oakbox.net.use_system_certificates()` first (a new entry point does too).
- Say who's asking: `oakbox.net.USER_AGENT`. Public services are shared (OpenStreetMap's Overpass is run by
  volunteers): keep rate limits on, cache and reuse, never retry in a loop, and send nothing to a service that
  didn't answer. Credit data as its licence asks ("© OpenStreetMap contributors", ODbL).

## Before pushing: what CI runs

Run all of it, not only the tests; CI fails on any of these.

```sh
uv run ruff check src tests && uv run ruff format --check src tests && uv run pyright && uv run pytest -q tests
PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 LC_ALL=C LANG=C uv run pytest -q tests
(cd web && npx biome check src && npx eslint src && npx tsc --noEmit)
# API types: regenerate and check nothing changed
uv run python -c "import json; from oakbox.app import create_app; print(json.dumps(create_app().openapi(), indent=1))" > web/openapi.json
(cd web && npm run -s api) && git diff --exit-code web/openapi.json web/src/api/schema.d.ts
```

A change to what the user sees is also checked in the real app (`run.bat`, or `uv run python -X utf8 -m oakbox`),
not only by tests.
