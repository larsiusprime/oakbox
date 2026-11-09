# Platform: hardware, architecture, stack

How it's built as it stands is in [docs/ARCHITECTURE.md](../ARCHITECTURE.md); this is the spec's side: targets,
decisions and plans.

## 5. Hardware targets

**Measured** (2026-11-05/06, `perf/`): the whole pipeline on synthetic counties of 5,000, 20,000 and 50,000 parcels,
under four machine profiles made with cgroup limits (cores, slower cores, memory for OAK box, disk reads), the pages
timed in a slowed headless Chromium. At 50,000 parcels with two fold workers, the three profiles with 2–2.5 GB for
OAK box ran out of memory in Models or Finalize; Finalize needed 2.65 GB, of which about 1.2 GB was two idle fold
workers. One fold at a time brought it to 1.51 GB in about the same time. The Model groups map froze the page for
12–20 s at 50,000 parcel shapes without graphics hardware; 20,000 dots, 2.1 s at most. Earlier, M0
([`docs/m0/REPORT.md`](../m0/REPORT.md)): 500,000 parcels, Thorough model step, about 36 min end to end and 9.2 GB
peak memory on 4 cores.

**Folds at once give the same values.** Measured: four Models runs from scratch (two with two workers, two with one)
wrote bit-identical files, predictions included; Finalize too. Tuning trials are fitted single-threaded and
deterministic, picked in fixed batches and recorded in the order asked, so threads change only the time. So the
setting is speed against memory, and no part of any step's key.

**The computer check** (built 2026-11-06, `oakbox/machine.py`, `screens/MachineCheck.tsx`). On first run, before the
projects page, OAK box checks the computer (about 15 seconds; Cancel takes the safest settings, Light):

| Check | How |
|---|---|
| Memory | Installed, and free right now |
| Processor | Its name, physical and logical cores |
| Speed | A fixed piece of pandas and NumPy work like OAK box's own, in a process of its own; the test machine (a 2.1 GHz cloud Xeon) = 100 |
| Disk | Writing 128 MB in the projects folder, flushed to disk (on Windows, the antivirus included) |
| Graphics | In the page: WebGL's renderer (software: SwiftShader, llvmpipe, Microsoft Basic Render Driver, or none) and 20,000 parcels drawn and timed |
| Remote session | Remote Desktop or Citrix, noted |

It shows what it found, the tier, why, and the settings it recommends: Use these settings, or Change them… (Settings).
It checks again on its own when the memory or core count changes, and shows the result again only if the tier
changed. Settings › Performance › Check again does the same any time.

**Tiers.** Memory decides, because memory is what failed:

| Setting | Light | Standard | Strong | Graphics in software |
|---|---|---|---|---|
| Computer | under 12 GB, or 2 cores, or speed under 60 | 12 to 24 GB | 24 GB or more and 6 cores or more | any tier |
| Model training | One fold at a time | Two at a time | As many as the cores allow (logical − 2, OpenAVMKit's default; at most 5, its folds, as it never runs more) | — |
| Maps | When Show map is clicked | Right away | Right away | When clicked |
| Map detail | Dots | Dots above 20,000 parcels | Shapes | Dots |
| Street map | Off | On | On | Off |

**Settings** (a gear on the plate, File › Settings…, Ctrl+,): Performance first (what the check found, Check again,
and
each setting as **Recommended** (what the tier chose, which follows a new check) or the user's own choice, which
stays); then Display (density, zoom), Projects (where they're kept) and Data keys (the Census API key). Kept in OAK
box's settings on the computer, never in a project. Models and Finalize set OpenAVMKit's `cv_max_workers` from it in
memory only, and shut the fold workers down once the models are trained. With one fold at a time, the tuning
trials run one at a time too (`OPENAVMKIT_TUNE_WORKERS=1`, 2026-11-06): OpenAVMKit otherwise runs them on a thread
pool in the one process, and two LightGBM trials at once crashed it now and then (a segmentation fault or a
floating-point exception, never memory: 7 runs in 11 on two slow cores, 1 in 3 on four; none in 11 one at a time, in
the same time).

**Maps.** Where maps wait, each starts as a panel the map's size (its name, Show map, and a link to Settings). Drawn
as dots, the Model groups map shows each parcel's centre in its group's colour, clickable; zoomed in to 5,000 parcels
or fewer in view, their shapes are drawn instead. Some parcel files hold only a small square at each parcel's point
(Manassas Park: a 20-foot square each); when the shapes are such scattered specks (covering under a tenth of the ground
they're spread over) and smaller than 3 pixels on screen, a whole-county view can't show them: with Parcel shapes chosen
each is drawn at least 3 pixels across, otherwise as a dot. Every other parcel map already draws points. A street map that's
off isn't fetched.

**Where a run's time goes** (built 2026-11-07, `timing.py`). Every step's run leaves a record in
`out/oakbox/timing/<step>/`, the last run of each step, kept however it ended (an error, Stop):
- `timing.json`: OAK box's and OpenAVMKit's versions; this computer (the check's record, logical and physical cores,
  memory) and the performance settings in force; the run's timeline (each progress line and its seconds from the
  start); its seconds; the CPU seconds of its process and its workers, the peak memory of them together (sampled every
  2 s), the most workers at once; how it ended; and a summary of the tuning trials per model (how many, their
  seconds, the slowest, pruned, the rows, features, categorical features and folds searched on).
- `trials.jsonl`: OpenAVMKit's trial log (`OPENAVMKIT_TRIAL_LOG`, upstream): each tuning trial as it finishes, the
  model, its own seconds, state, score and params, the search's size (CatBoost: its threads). Worker processes
  inherit the variable, so folds tuned in parallel are in it; written as it goes, so a stopped run leaves its trials.

**Help › Save a performance report** (in a project) zips those records with each step's receipt and fingerprint, the
end of each run's log (400 KB) and the project's settings for OpenAVMKit (file and field names; no data) into
`performance-report-<date>.zip` in the project folder, shows it in the file manager, and says where it is and what's
in it.

**A large county is said before the long steps.** Bring in data's plan works out about how much memory the county
needs (0.5 GB, plus 1 GB per 50,000 parcels, plus 0.6 GB per 50,000 for each extra fold worker: the test runs'
figures) against what the computer leaves OAK box (its memory less 5.5 GB for Windows and the usual programs), and
says so when it's short: a warning, never a block.

**A CSV gets a quick-read copy** (`readcache.py`, 2026-11-07). The Data steps read a file a column at a time (previews,
ID checks, Sales record fields), and from a big CSV each read is about a second (Guilford, NC's 220 MB parcels.csv: 0.99 s).
So each CSV is converted once into Parquet, `out/oakbox/cache/<name>-<size>-<mtime>.parquet`, every column as text
exactly as the CSV is read (blanks as "", "NA" kept as written): a column then reads in 0.04 s. The conversion starts
in the background when the file is added (Guilford's parcels: about 8 s, 46 MB), its entry on the step shows how far
it is, about how long to go, and Stop (the file is read as it is until **Make it** starts it again). Nothing waits on
it: a read before it's done reads the CSV. A changed file gets a new copy and the old one is removed. Only OAK box's
own reads use it; OpenAVMKit reads the files themselves.

- **Why this floor:**
  - Windows 10 is still about 26% of Windows PCs ([StatCounter via Yahoo, May
    2026](https://tech.yahoo.com/computing/articles/microsoft-giving-windows-10-users-180152418.html)), with paid
    security updates to Oct 2027.
  - About 10% of machines have 8 GB RAM ([PassMark](https://www.memorybenchmark.net/amount-of-ram-installed.html)),
    and office PCs skew lower.
- **Disk per project.** Outputs are roughly 100× the input size (3.9 GB for 500k, M0). Not checked yet.
- **Still to measure:** a real county office PC (run `perf/drive.py` there without a profile), real extracts with
  many columns (they need more memory than the synthetic counties), and paging on Windows instead of a kill.

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
  arrays, not GeoJSON (`shapes.bin`: each parcel's polygons, rings and corners in millionths of a degree; a quarter
  of GeoJSON's size and nothing to parse), which deck.gl draws as its binary features. **Planned if that proves too heavy:** vector tiles built on the fly from GeoParquet, so the browser never
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

### 6.7 Project files across versions (planned)

**Not built, on purpose.** While the format changes every week, a project that no longer loads is simply hidden (and
re-made). This is the plan for when that stops being acceptable: **turn it on before the first release whose users are
told their projects carry over to the next one** (open item 5, §10). From then on, a project made by one OAK box opens
in every later one, and nothing a user decided is ever lost silently.

**What's kept, and how each kind is treated:**

| File | Whose | Across versions |
|---|---|---|
| `oakbox.json` | the user's: every choice | versioned and upgraded (below) |
| `in/oakbox/*` (sales kept and excluded, time adjustment files) | the user's | versioned with `oakbox.json`: its schema covers them |
| `in/settings.json` | derived from `oakbox.json` | not versioned: rewritten on opening (`projects.refresh_settings`, as today) |
| `out/oakbox/<step>/` (receipts) | derived from runs | not versioned: one this OAK box can't read is no receipt, and the step asks to run again (as today) |
| OAK box's own `settings.json` | the user's, per computer | versioned the same way; one that doesn't read keeps what does and a copy (as today) |

**`oakbox.json`:**
- **A version:** `"schema": N`, written on every save, with the OAK box version that saved it (`saved_by`). A file
  without one is schema 1, the format the first release ships.
- **Every change to the `Project` model raises it**, an added field too: an older OAK box drops fields it doesn't know
  when it saves, so it mustn't save a newer project at all. CI enforces this: the model's JSON schema is fingerprinted
  in the repository per version, and a change without a raised version fails the build.
- **Upgrades:** one function per step (`2: upgrade_from_1(raw) -> raw`), on the raw JSON before the model reads it,
  applied in order from the file's version to this one. The first save after an upgrade keeps the file it replaced as
  `oakbox.json.v<N>.bak` (once per version), so a user can go back by hand.
- **A newer project** (its schema above this OAK box's) is listed but not opened: "Made by OAK box 1.4: update OAK box
  to open it". It's never saved by this one, so nothing is dropped.
- **A damaged project** (it doesn't read, even after upgrading) is listed with why ("Damaged: `groups[2].rule` isn't a
  rule") and **Show folder**, not hidden, and never written over. Repairing one is for later.
- **Tests:** a project file of every schema there has been, kept in `tests/data/projects/`, each upgraded to the
  current one and checked; plus a newer one (listed, untouched) and a damaged one (listed, with its reason).
- **AGENTS.md** then says: a change to `Project` raises its schema, adds the upgrade, and adds a test file.

**Open questions, for then:**
- OpenAVMKit's own changes: a step that ran on an older OpenAVMKit (its receipt records which) is up to date by its
  settings, but might come out differently now. Say so beside its receipt, or put it out of date?
- Read-only opening of a newer project, if users share project folders between offices on different versions.
