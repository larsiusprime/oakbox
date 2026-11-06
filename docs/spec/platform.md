# Platform: hardware, architecture, stack

How it's built as it stands is in [docs/ARCHITECTURE.md](../ARCHITECTURE.md); this is the spec's side: targets,
decisions and plans.

## 5. Hardware targets
**Provisional, from M0 benchmarks** ([`docs/m0/REPORT.md`](../m0/REPORT.md)). These came from synthetic data with
about 10 fields per parcel, on 4 cores. Real extracts and a real low-end PC still need to confirm them.

| Tier | Machine | Model step setting | Parcels (target) |
|------|---------|--------------------|------------------|
| Below floor | 4 GB RAM | 1 fold worker | Samples and jurisdictions under 25k; warns |
| Floor | Win10 x64, 4 cores, 8 GB RAM, 25 GB free disk | 1 fold worker (`cv_max_workers=1`) | up to ~150k |
| Recommended | 4+ cores, 16 GB RAM, SSD | 2 fold workers | up to ~500k |
| Large | 8+ cores, 32 GB RAM, SSD | `cores − 2` workers | 500k+, or real data with many columns |

**Measured** at 500k parcels, Thorough model step: about 36 min end to end, 9.2 GB peak memory, 3.9 GB of project
outputs.

- **Memory has a fixed base.** About 0.7 GB per process (the OpenAVMKit import), plus about 0.7 GB per cross-validation
  fold worker. The data-proportional part grows with column count, so real extracts will raise it.
- **Plain warning, never a block.** "This county has 520,000 parcels. This computer has 8 GB of memory; we recommend 16
  GB. Steps may be very slow or fail." The user can continue.
- **Automatic scaling.** Oakbox reads RAM, cores and disk, then sets fold workers and enrichment defaults to fit.
- **Disk per project.** Outputs are roughly 100× the input size (3.9 GB for 500k). Oakbox prunes intermediate outputs
  after each step, and the disk check counts the project's expected size.
- **Why this floor:**
  - Windows 10 is still about 26% of Windows PCs ([StatCounter via Yahoo, May
    2026](https://tech.yahoo.com/computing/articles/microsoft-giving-windows-10-users-180152418.html)), with paid
    security updates to Oct 2027.
  - About 10% of machines have 8 GB RAM ([PassMark](https://www.memorybenchmark.net/amount-of-ram-installed.html)), and
    office PCs skew lower.

## 6. Architecture

```
┌──────────── OAK box (per-user install) ────────────────┐
│ UI: React + TypeScript in a native window (pywebview:  │
│     WebView2 on Windows, Qt on Linux; else a browser)  │
│        │  localhost HTTP (JSON); progress is polled    │
│ App service (Python, FastAPI): projects, the Data      │
│     wizard, checks, model group preview, staleness,    │
│     report and export                                  │
│        │  spawn / stop                                 │
│ A run (a process of its own, one per run): a step's    │
│     part of OpenAVMKit; prints a JSON line per part    │
└────────────────────────────────────────────────────────┘
  Bundled: standalone CPython 3.11 + hash-locked wheels (uv)
```

As built in detail (the modules, a run from button to receipt, a project on disk):
[docs/ARCHITECTURE.md](../ARCHITECTURE.md).

- **Python backend, TypeScript frontend** (§6.5). WebView2 ships with Windows 10 through Windows Update; on Linux the
  window is Qt, or a browser app window (§6.1).
- **Each run is a process of its own.** OpenAVMKit changes the working folder, uses relative paths, and can crash or run
  out of memory. A run is given its project and environment (UTF-8 mode, API keys); a crash fails that run, not the app.
- **Large maps.** MapLibre and deck.gl (WebGL) draw the parcels on the page (§6.5); the service sends their shapes as
  GeoJSON. **Planned if that proves too heavy:** vector tiles built on the fly from GeoParquet, so the browser never
  loads 500k polygons.
- **Packaging:**
  - a standalone CPython build plus pre-installed wheels, with no freezing (PyInstaller struggles with GDAL, PROJ and
    numba)
  - **Windows:** a per-user Inno Setup installer (built 2026-11-04: `packaging/oakbox.iss`) into
    `%LOCALAPPDATA%\Programs\OAK box`, with no admin rights, a Start menu entry and an uninstaller, plus a portable
    `.zip` fallback. Unsigned until D14. A version tag (`v<pyproject.toml's version>`) publishes both as a GitHub
    pre-release; CI installs, starts and uninstalls the installer on a clean machine first. A newer installer replaces
    the runtime wholesale, so nothing dropped lingers. **Size today (2026-11-04):** 705 MB installed, 232 MB zipped, a
    152 MB installer, without XGBoost and CatBoost (OpenAVMKit #420; Optional engines, below). Before them: 1.25 GB and
    458 MB (OpenAVMKit #419 had made the cloud SDKs and NGBoost optional extras, 23 packages fewer; before it 1.30 GB
    and 471 MB). Polars went with OpenAVMKit #418 (it was 1.62 GB and 562 MB); then `packaging/strip_bundle.py` (run by
    the build) drops what the bundle never runs: libraries' test suites (85 MB), headers, static libraries and stubs (20
    MB), pip, setuptools and Python's Tk, IDLE and ensurepip (36 MB). It keeps libraries' `testing` modules, C sources
    and every `.dist-info`. XGBoost and CatBoost left the bundle with OpenAVMKit #420 (about 545 MB installed). What's
    left, largest first: llvmlite and numba 114 MB (numba, SHAP), scipy 97, pyarrow 71, rasterio 70 (only the elevation
    enrichment; kept in the bundle, decided 2026-11-04: about 26 MB of the installer isn't worth another optional
    download), pyogrio 70, numpy 33, pandas 26, pyproj 25, scikit-learn 20, matplotlib 18. (IPython, jedi, debugpy and
    the rest of a Jupyter kernel came in through `layeredcompmodel` 0.3.0's `ipykernel`; 0.3.1 dropped it, OpenAVMKit
    #417, OAK box pins `abdd817`). The longest path in the bundle is 141 characters from its root, so the install folder
    stays under Windows' 260. Measured in M0: 1.7 GB installed, 544 MB zipped; roughly 350 MB after upstream A13
  - **Linux:** a portable `.tar.gz`, run where it's unpacked (`oakbox.sh`), with no root. **Planned:** installing per
    user into `~/.local/share/oakbox` with a desktop-menu entry (`.desktop` file); an AppImage may follow. Measured in
    M0: 2.5 GB installed, 974 MB compressed. 469 MB of that was NVIDIA's NCCL library, which XGBoost's Linux wheel pulls
    in to train one model across several GPUs. The bundle leaves it out (CPU and single-GPU training don't use it); Qt
    for the native window adds about 385 MB once trimmed (`packaging/prune_qt.py`). **Revisit with modelling:** an
    optional download for multi-GPU training (NCCL), offered in the app rather than shipped to everyone (upstream A13)
  - **Optional engines (built 2026-11-04):** XGBoost and CatBoost aren't in the bundle: together they'd add about 560 MB
    installed (XGBoost 144 MB on Windows, CatBoost with plotly, narwhals and graphviz 407 MB) for engines LightGBM
    already covers. OpenAVMKit has them as extras (`openavmkit[xgboost]`, `[catboost]`, #420); OAK box's own extras of
    the same names pull them in for a checkout (the dev group has both, so the tests try every engine).
    - **What's fetched is fixed at build time.** `packaging/engines_manifest.py` writes `engines.json` into the bundle:
      each engine's wheels for that platform from `uv.lock` (what its extra adds that the bundle doesn't already have),
      with sha256, size, and the disk they take unpacked. Nothing else is downloaded, and a wheel that doesn't match is
      refused.
    - **Where:** per user, outside the install folder (`%LOCALAPPDATA%\OAK box\engines\<engine>`,
      `~/.local/share/oakbox/engines/<engine>`), one folder per engine, unpacked from the wheels as a `--target` install
      would. `oakbox/engines.py` puts installed ones after the bundle's own site-packages on `sys.path`, and on
      `PYTHONPATH` for the processes a run starts. A folder written for other wheels (an older OAK box's) is left off,
      so the engine reads as not installed and is fetched again. Installs go to a temporary folder and are renamed into
      place; a failure or Stop leaves nothing.
    - **In the app:** the engine list says "not installed · 102 MB"; choosing one asks then and there (Install XGBoost?
      sizes, from the Python Package Index, for this user only, no admin), and the model is added once it's in, with a
      bar and Stop in its row meanwhile. A model whose engine is missing (a project from another computer) says so in
      its row. **Try them** and **Finalize** refuse such models and say how to get the engine. **Help › Model engines**
      installs or removes either.
    - **In the installer:** a components page offers both, unticked, with their download sizes; ticked, they're fetched
      at the end of the install by the same code (`python -m oakbox.engines install …`). A failed download doesn't fail
      the install: the app offers it again. Uninstalling removes the engines folder. A checkout has no `engines.json`:
      it says to run `uv sync --extra <engine>`.
    - **CI:** the Linux bundle must not import either, then downloads both through `python -m oakbox.engines` and trains
      with them; the Windows installer is installed with XGBoost ticked (CatBoost not) and checked, then uninstalled.
  - **Both bundles are built on Linux** from one script (`packaging/build_bundle.sh`) and one lockfile. CI smoke-tests
    each on a clean machine of its platform
- **Projects** are ordinary folders: an OpenAVMKit locality plus `oakbox.json`. Easy to copy, zip and back up.
- **Reproducibility.** Each run's receipt records the OpenAVMKit version it ran with. **Planned:** the project recording
  OAK box's version and the seed; versions installed side by side (today a newer installer replaces the older).
- **Updates (planned).** **Check for updates** reads GitHub Releases, sending only a plain version request. The user
  approves each install, and the old version is kept. Today: download the newer installer and run it.
- **Privacy.** No telemetry and no crash upload. **Planned:** **Send log to support** builds a zip the user emails
  themselves.

### 6.1 Cross-platform: Linux now, macOS possible
**Windows text is UTF-8, always.** Most users are on Windows, where Python reads and writes text in the code page
(cp1252) unless told otherwise, so a "−" or an "é" can stop a run there and nowhere else. Every text read and write
names `encoding="utf-8"` (`tests/test_encoding.py` checks the source). Every Python process OAK box starts, the
launchers included, runs in UTF-8 mode (`-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`), so OpenAVMKit's own I/O is
UTF-8 too. The app's console output is reconfigured to UTF-8. CI runs the whole suite a second time with a non-UTF-8
default encoding. AGENTS.md has the rules for contributors and coding agents.

**Linux (supported).** It's the development environment as well as a target. Many contributors and most CI already run
on it, and the engine runs there unchanged.
- **Window:** a native Qt window (pywebview on PySide6, which the bundle includes). Qt still needs the desktop's usual
  display libraries (libEGL, and libxcb-cursor on X11), which some minimal installs lack. Before opening the window, OAK
  box tries Qt in a short-lived process (a missing library makes Qt abort rather than fail cleanly). If that fails, it
  opens the UI in the user's browser instead: Chromium/Chrome "app" mode (a chromeless window) when one is installed,
  else a normal tab.

  The UI is identical either way; only the native menus (§3.14) are missing in a browser.
- Chromium's sandbox inside Qt WebEngine is off: the window only shows OAK box's own UI from 127.0.0.1, and the sandbox
  can't start on some systems (as root, or under Ubuntu 24.04's user-namespace restriction).
- **Baseline:** glibc 2.34+ (the `manylinux_2_34` wheels, which Qt needs): Ubuntu 22.04+, Debian 12+, RHEL/Rocky 9+.
  x86_64. ARM64 Linux is later; its wheels mostly exist.
- **Shipped as** a per-user `.tar.gz`. It needs no root, Python or package manager (§6). There are no distro packages
  (.deb/.rpm) in v1.
- **Tested in CI:** the full test suite, the native window's menus, and the bundle's smoke test on a clean
  `ubuntu-latest`.
- **Platform differences** are kept small:
  - default project folder: `Documents/OAK box`, wherever the desktop keeps Documents (`xdg-user-dir`; Windows' known
    folder, OneDrive included); the first builds' `Documents/Oakbox` is still searched
  - the native window and its menus (`winmenu.py`, `qtmenu.py`)
  - where settings and downloaded engines live (`appsettings.py`, `engines.py`)

**macOS (later).**
- **The stack already runs on macOS:** pywebview uses WKWebView, the scientific wheels exist for Apple Silicon, and
  standalone CPython builds exist.
- **OS-specific code stays contained** in the few places above. `pathlib` is used everywhere.
- **CI smoke-tests a macOS build** once there is one (not yet).
- **Deferred macOS costs:**
  - Apple signing and notarization
  - bundling `libomp` for LightGBM/XGBoost
  - a `.dmg` package

### 6.2 Licensing
- **Oakbox code: MIT.** It is permissive, AGPL-compatible, and familiar to government IT.
- **The engine stays dual-licensed.** OpenAVMKit, including `openavmkit-oakbox`, remains AGPL-3.0 or commercial.
  Contributions there go through its CLA.
- **The installer is AGPL-governed** because it contains OpenAVMKit. **Planned:** the About screen and installer link to
  the exact OpenAVMKit source commit, and a `THIRD-PARTY-LICENSES` file lists every bundled package.
- **CI licence check (planned)** fails the build on a non-free or AGPL-incompatible dependency.

### 6.3 Engine facts that shape the design
These were verified in the OpenAVMKit code at `f35b089`. Where the docs differ, the code wins.

| Fact | Consequence for Oakbox |
|---|---|
| `valid_sale` **and** `vacant_sale` are required; `key_sale` and `data.process.merge` are required | Sales basics always produces them (§3.2) |
| Without a `dupes` setting, a geometry file is de-duplicated on an *arbitrary* column; the column order comes from a `set` and varies between runs. In M0 this silently dropped up to 99.8% of parcels | Oakbox always writes `dupes` explicitly (`subset: [key]`). Upstream A11 |
| Importing OpenAVMKit pulls in IPython and costs about 0.7 GB per process; the first Windows import takes about 17 s | Each run imports it in its own process; the app service imports it once, in the background, at start-up (`app._warm_engine`). Upstream A1 |
| Office-invalid sales are deleted at the end of the load and merge step; scrutiny drops outliers by default | Kept as-is: invalid sales never touch modeling. Oakbox reviews them in its own register outside the pipeline (§3.6) |
| Model groups are tagged at the end of assemble, and sales take their parcel's model group | Step 1 stops before tagging; step 2 tags. Unmatched parcels become `UNKNOWN` and are not modeled |
| Fills, equity clusters, time adjustment and scrutiny are per model group | Any model group change re-runs steps 3–5 |
| Blank finished area → 0 → vacant, with building fields erased, in step 1 | Kept as the stated default with an opt-out (§3.9); building-field estimates need a filter |
| Estimation runs before lookup tables, formulas and the vacancy rule | Those outputs can't be predictors |
| The only spatial-join rule is "centroid inside" | No "overlaps" in v1 (upstream B3) |
| Enrichments and each distance feature default to **off** | Oakbox writes `enabled: true` explicitly |
| Census key comes from the environment; `.env` isn't found outside notebooks | Each run's environment carries the key (`steps.child_env`) |
| Checkpoints only check that the file exists | Oakbox owns staleness (§6.4) |
| The ratio-study report needs a finalized model and hard-codes `assr_market_value`; the field-agnostic study functions exist but don't persist | Step 4 needs upstream A3 |
| `try_variables` needs an explicit candidate list and runs only correlation and R² | Oakbox supplies candidates; verdicts need A5 |
| Models need explicit `ind_vars`; there's no default run list | Oakbox ships per-model-group defaults (§3.10) |
| `cloud_sync` syncs both ways | The sample is fetched download-only |
| The streets enrichment is always called in notebook 1 | Explicitly disabled |
| Since 0.7.0: nested CV by default, raw-price ratio study, `benchmark` renamed `model_runner` (shim removed in 0.8) | Benchmarks and the headless API target 0.7+ behaviour |

### 6.4 Staleness and re-runs
Oakbox keeps a hash of what each step depends on: its own calls, and the run of the step it starts from (settled
2026-10-30: "follow the run before"). A step is **out of date** when one of its calls changed or the step before it has
run again since; nothing further back. A change further back shows only where it was made: every step after that one
**waits** for it ("Run Bring in data again first: something it depends on changed since it ran"), and can't start or be
accepted until each step before it is accepted (Looks right) on an up-to-date run. So a re-run with nothing changed
still puts the steps after it out of date. Check sales deletes notebook 2's OpenAVMKit checkpoints before it runs. How
this is built: [docs/ARCHITECTURE.md](../ARCHITECTURE.md), "Out of date, waits, accepted".

| Change | Re-runs from |
|---|---|
| Files, stitch plan, ID fixes, column mapping, transforms, sales basics, condo rules, enrichment settings, keeping an office-invalid sale | Step 1. Unchanged enrichments reuse their cache |
| Model groups | Step 2 |
| Validity rules, time adjustment, sales windows, scrutiny settings, keeping or excluding a sale | Step 3 |
| Value fields to check | Step 4 only |
| The study's calls: window, price, trimming, standards, classes, region | Step 4, and Finalize (step 6), which judges the model values the same way |
| Fills, rare categories | Step 5 (Prepare the fields) |
| Variable lists, models, small groups | Step 6. Planned: speed tiers, model-outlier exclusions, tuning reused unless Re-tune |
| The report's title and what it judges on, the export format | Step 7 only (nothing runs) |

Step 4 depends on steps 2–3 but not on step 5, so checking values never waits for modeling.

### 6.5 Frontend and build stack
**Priorities:** great UI, a stable codebase, good performance. Most code will be AI-written, so a type checker that
catches mistakes matters more than developer convenience.

**UI library: React 19,** client-side only (an SPA), with the React Compiler enabled. Decided after comparing it with
Preact, Lit, plain Web Components, Solid, Svelte and htmx.
- **Why React:**
  - **Accessible complex widgets.** **React Aria Components** (Adobe, Apache-2.0) covers the widgets that make up most
    of Oakbox's UI, with best-in-class accessibility:
    - comboboxes for column matching
    - date pickers
    - drag-to-reorder model groups
    - tree and rule-builder structures
    - dialogs, tabs and tooltips
  - **AI writes React most reliably.** Preact's near-identical API invites subtle React-isms.
  - **Stability.** The largest user base, long deprecation cycles, and governance under the React Foundation.
  - **Type checking.** TSX is fully type-checked by `tsc`, the same as Preact.
- **Costs accepted:**
  - About 45 KB of runtime, irrelevant for a desktop app loading from local disk.
  - Coarser re-rendering, mitigated by the React Compiler's automatic memoisation. Heavy work isn't in React anyway:
    MapLibre and deck.gl draw maps, and Python does the number-crunching.
- **Guardrails** against React's usual problems:
  - **No framework.** No Next.js, no server components, no SSR: Vite builds a static SPA.
  - **Lint rules** enforce the rules of hooks and effect dependencies.
  - **Few effects.** Prefer derived state and event handlers over `useEffect`.
  - **Data:** server state lives in a typed query layer (TanStack Query over the generated API client). UI state uses
    plain React state/context, and a small store library only if one proves necessary.
  - **No component kit** beyond React Aria. Styling is our own.
- **Other UI pieces:**
  - **One map for every map** (settled 2026-11-01, replacing Leaflet): MapLibre GL JS draws the street map
    (OpenFreeMap's vector tiles, §3.11; a **Street map** box takes it away, remembered on the computer) and deck.gl
    (WebGL, `@deck.gl/mapbox`'s overlay) draws what's on it, so half a million parcels draw as smoothly as a few hundred
    sales. One component, `components/MapView.tsx` (fit to a box, resize, hover text, a hook for markers such as
    Location's pin); MapLibre's worker is bundled (`?worker&url`, ES format) as the bundle doesn't keep it beside
    MapLibre. Used by Model groups' parcel shapes, Location's dots and pin, a map layer over the parcels, Check my
    values' ratio map and Model values' map. Parcels as dots for now; shapes for every parcel on the value maps are a
    later choice (deck.gl draws them; at county size, likely as vector tiles made on the computer).
  - Charts are SVG drawn by our own components (`screens/ValueCharts.tsx`, `TimeChart.tsx`…), at their width in pixels
  - Tables are plain `<table>`s, sorted in `DataTable` and `ValueTable`; TanStack Virtual if one ever needs virtualising

**Build stack** (all dev-time only; nothing here ships to users, who get static files):

| Piece | Choice | Why | Not chosen |
|---|---|---|---|
| Type checker | `tsc --noEmit`, `strict` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` | The only full TypeScript checker. Bundlers *strip* types without checking them, so this runs separately in the editor, the build and CI | — |
| Dev server and bundler | **Vite** (React plugin) | Hot reload in a normal browser while the Python backend runs. Proxies API calls to the backend with one line of config. Production build is a static bundle. Uses esbuild internally, so it's fast | *esbuild alone:* no hot reload or dev proxy. *Webpack:* slow and config-heavy. *Next.js / Turbopack:* server-oriented, not needed for a local SPA |
| Backend API → TS types | **FastAPI** (pydantic) → OpenAPI → **`openapi-typescript`** + **`openapi-fetch`** | FastAPI emits OpenAPI from the same pydantic models the backend validates with. The generated types and a ~6 KB typed client mean a backend change that breaks the UI fails `tsc` | Hand-written client types, which drift |
| Lint + format | **Biome** for formatting and general lint, plus **ESLint** limited to `eslint-plugin-react-hooks` and the React Compiler rules | Biome is fast with few dependencies. The hooks rules are React's main bug guard and only ship as ESLint plugins | Full ESLint + Prettier stack: more packages for little gain |
| Unit tests | **Vitest** | Shares Vite's config and TS handling | Jest, which needs separate TS setup |
| End-to-end tests | **Playwright** (planned; Chromium is already in the build environment). Today the Python suite drives the real backend through its HTTP API, and CI opens the real window to check its menus | Drives the real UI against the real backend | — |
| Packages | **npm** with a committed lockfile, `npm ci` in CI; Node LTS, dev only | Ships with Node, one less tool | pnpm (fine too; not worth the extra tool yet) |
| Python side | **uv**, **ruff**, **pyright** (standard mode) | Same "type checker first" rule for the backend | mypy (slower; pyright matches the editor) |

**Styling and strings:**
- plain CSS with design tokens (custom properties) for density and zoom
- a typed string table (D13), so a missing translation key is a type error: the wording catalog, §6.6

### 6.6 Wording: the catalog and live editing

**Why:** the wording needs a big clean-up (about 15,100 words in the UI, half of it in 246 paragraph-length entries),
done fastest by editing it in the running app and reviewing the result in git. The same move readies the copy for
translation (D13).

**The catalog.** The UI's wording (its copy) is in a data file, `web/src/wording/en.json`, imported as `t`. Each value
is an **ICU MessageFormat** message (the format translation tools read): `"Add field"`; `"{first} + {n, plural, one {#
other field} other {# other fields}}"`; `"{mode, select, move {Moving…} other {Copying…}}"`; numbers as `{n, number}`
(in the user's locale, as `toLocaleString` did). Lists stay JSON lists.
- **Runtime:** `intl-messageformat` (FormatJS) formats each message, compiled once and cached.
- **Types:** a generator reads `en.json` and writes `wording.gen.ts`: a message with no arguments is a `string`; one
  with arguments is a function of a named-argument object, typed from its placeholders (`plural` and `number` arguments
  are numbers, `select` a union of its cases, others strings). So `t.wizard.custom.title` stays a string and
  `t.x.plusOthers({ first, n })` is type-checked. CI checks the generated file is up to date, as it does for the API
  types.
- **Lookup tables** (`checkNames`, `checkWhy`…: keys are ids from the backend) stay objects keyed by id; only their
  values are copy.
- **What stays in code:** logic that isn't wording. About 20 of today's functions join lists, change case or do
  arithmetic; the code does that and passes the result in as an argument. A message never computes.
- **History:** it moved out of `strings.ts` on 2026-11-03, checked by rendering every old function against the new
  catalog with sample arguments, and comparing screenshots of every step of every tab.
- **Python's wording** (about 5,600 words: receipt notes, check wording, errors, the report) is the next bite, not this
  one.

**Live editing (developer builds only).** `npm run dev:wording` runs the Vite dev server in `wordingedit` mode. Only
that mode compiles the editor in (`__WORDING_EDIT__`); every other build has none of it (CI checks the shipped bundle).
- **Finding the text:** in this mode each message carries an invisible marker (zero-width characters) naming its key;
  **Alt+click** any text to edit the message it came from. Text that isn't clickable (tooltips, placeholders, labels for
  screen readers, the window title, text on maps and charts) is reached from a panel listing the messages on the screen,
  with a search over the whole catalog.
- **The editor:** the message's key, its text with its arguments as fixed chips (moved, not added or removed), each
  plural or select case as a line of its own, the values it was last shown with, and how many places use it. Saving
  updates the screen at once, with no reload (nothing open is lost).
- **Writing back:** a dev-server plugin writes the change into `en.json` (that key only, re-reading the file first, so
  an edit made in an editor meanwhile is kept), checks the message parses as ICU, and regenerates the types. `git diff`
  shows every change, for review.
- **Markers never leave the page:** stripped from every request to the backend (copy can be saved into projects, e.g. a
  default name), from the clipboard, and from the window title.
- **As built (2026-11-03):** `wording/marks.ts` (the markers: a number per message and the arguments it was shown with),
  `wording/edit/install.ts` (first on the page: takes markers out of requests, the clipboard and the title, then loads
  the editor), `wording/edit/editor.tsx` (Alt+click, the editor, the ✎ Wording panel, putting new words on the screen),
  `scripts/wording-edit-plugin.mjs` (the dev server's writer; a message must keep the same arguments, the same types,
  and isn't overwritten if it was changed in the file since it was opened). **Line breaks and paragraphs:** Enter in the
  editor is a line break and a blank line starts a new paragraph, kept in `en.json` as `\n` and `\n\n`; text elements
  (`p`, `li`, `dd`, tooltips, ledes) show them (`white-space: pre-line`, at zero specificity), so a blank line reads as
  a paragraph gap wherever the message is shown, with no change to the screens. The editor shows apostrophes single
  (ICU's `''`) and each plural or select case on its own line, and writes them back as ICU. Text that isn't copy (the
  user's data) says so when Alt+clicked. A click on a message inside another (a tab's name in "Model groups waits for
  Bring in data") edits the inner one and offers the outer. "Named in N places" counts the code that names the key's end
  (approximate: code often reaches a message through a shorter name). Not done: the arguments as chips (the editor
  checks instead that they're unchanged). **In the app window:** `edit-wording.bat` (repository root) starts the dev
  server and the app with `--ui-url http://127.0.0.1:5173`: the window shows the dev server's page (its /api goes on to
  the app service on port 8765), so the native menus, pickers and title bar are there as users have them; closing the
  window stops both. `--ui-url` takes only a local address. Alt+click there doesn't open the Windows menu bar: Alt with
  a click isn't Alt alone (`AppMenus`), as in Windows. `npm run build` fails if the bundle has any of it
  (`scripts/no-wording-edit.mjs`). In this mode only, code that compares or slices a message's text sees the markers;
  the `say` helpers allow for them. **Formatting (2026-11-04):** `**bold**` and `*italic*` in a message (`\*` is an
  asterisk; `wording/rich.ts`). A message with any unescaped asterisk renders as React nodes and is typed `ReactNode` in
  `wording.gen.ts`, so the build refuses it anywhere only text goes (a title, a placeholder, an attribute); an
  argument's own asterisks are text. In the editor, the preview shows the formatting; each piece of a formatted message
  carries the markers, so a click on bold text finds it; and when a formatted message changes (or gains or loses
  formatting), the app is drawn again on the same page (`WordingRoot`), since formatting can't be written into text
  already on the screen.
- **Not editable here:** OpenAVMKit's own messages (shown as "from OpenAVMKit"), the user's data, and the native menus'
  labels (`menus.py`, few and short).
