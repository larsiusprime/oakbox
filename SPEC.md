# Oakbox — OpenAVMKit in a Box

**Status:** Draft 0.2. Built through dialogue; nothing here is final until marked **Decided**.

## 1. Purpose

A desktop app that lets a non-technical assessor run OpenAVMKit on their own parcels, with no command line and no hand-edited config. Download, double-click, work.

**Primary user:** a 50-year-old, tech-averse assessor at a small, underfunded office, on an old Windows PC, often without admin rights.

**Success test:** that user can go from "downloaded" to "a PDF ratio study of my current values" with no outside help.

## 2. Decisions so far

| # | Topic | Decision |
|---|-------|----------|
| D1 | Scope | **Decided.** Both checking values and producing values. Checking values ships first. |
| D2 | Configuration | **Decided.** A wizard builds `settings.json`. Users never see JSON. |
| D3 | Jurisdictions | **Decided.** Generic, not Texas-specific. Test with OpenAVMKit's public sample localities first. Non-disclosure states come later. |
| D4 | Data model | **Decided.** GIS-first. A parcel geometry layer is required. |
| D5 | Scale | **Decided.** Must handle 500k+ parcels (subject to the hardware tiers in §5). |
| D6 | Platform | **Decided.** Windows 10 64-bit minimum. Installs per user, with no admin rights. |
| D7 | Network | **Decided.** Works offline. Internet is only needed for the optional enrichment steps. |
| D8 | Updates | **Decided.** The user approves each update. IT-managed deployment comes later. |
| D9 | Input/output | **Decided.** Shapefile, CSV and Excel in and out, effortlessly. Polished PDF reports. Custom reports. |
| D10 | Upstream | **Decided.** OpenAVMKit changes live on an `oakbox` branch of `larsiusprime/openavmkit`. |
| D11 | Licensing | **Decided.** Free and open-source tech only. Oakbox is AGPL-3.0, to match OpenAVMKit. |
| D12 | Privacy | **Decided.** No parcel data leaves the machine. No telemetry. |
| D13 | Localization | **Decided.** Deferred, but all UI strings go in a string table from day one. |
| D14 | Code signing | **Decided.** Deferred; the maintainer will handle it. |
| D15 | UI tech | **Decided.** Web tech (HTML/JS) in a native window on a Python backend. Must keep a later macOS target possible (§6.1). |
| D16 | Checking values | **Decided.** The user must name the value field(s) to check. Current appraised values are not required, but whatever is checked has to be named. |
| D17 | Enrichment | **Decided.** Every online step says exactly what it sends, every time, before it sends it. The wizard walks users through getting a Census API key. |
| D18 | CAMA export | **Decided.** v1 is a generic CSV/Excel file: parcel ID plus new columns. Vendor-specific layouts come later. |
| D19 | Sample county | **Decided.** `us-va-petersburgcity`, because it runs fast. |
| D20 | Model choice | **Decided.** The assessor picks a model, or "Choose for me", which means LightGBM. |
| D21 | Name | **Decided.** "Oakbox" for now. |

## 3. What the user sees

### 3.1 Home screen
- **My projects**, shown as cards: county name, last opened, and how far along the steps it is.
- **New project** opens the wizard (§3.2).
- **Try a sample county** downloads the public OpenAVMKit locality `us-va-petersburgcity` and opens it. This is the first-run experience and also the training mode.

### 3.2 New-project wizard
One question per screen, in plain words. **Back** always works. Progress is saved after every screen.

1. **Name and place.** County name, state. The app picks the folder, units and map center.
2. **Parcels.** The user drags in a file (`.shp`/`.zip`, `.gpkg`, `.geojson`) and sees it on a map straight away.
3. **Parcel details** (optional). CSV or Excel files joined to the parcels by parcel ID. The app guesses the ID column; the user confirms it.
4. **Sales.** A CSV or Excel file with parcel ID, date and price.
5. **Match columns.** The app auto-maps the user's columns to OpenAVMKit fields: "We think `SQFT_LIV` is *Living area*. Correct?" The user only has to confirm the uncertain ones.
6. **Values to check.** "Which value(s) do you want to check against sales?" The user picks one or more columns, for example the current appraised value or last year's value. At least one is required to run step 3. If none exists yet, the user can skip and check model values after step 4.
7. **Enrichment.** Optional, online only. Plain-language checkboxes, for example: "Add building footprints (Overture)", "Add census tracts and income", "Add distances to roads, water and parks (OpenStreetMap)", "Add elevation (USGS)". Each one says what is sent: only the county's bounding box, never parcel data. The Census option includes a short guided walkthrough for getting a free API key, then pasting it in; Oakbox checks that the key works. With no key, the Census step is skipped.
8. **Valuation date** and which years of sales to use.
9. **Review.** A summary of the setup, then **Create project**.

### 3.3 Project screen: a checklist of steps
Each step has a **Run** button, a progress bar, a plain-language status and a **See results** link. If a later step is run before an earlier one, the app runs the earlier ones first.

| Step | OpenAVMKit stage | Internet? |
|------|------------------|-----------|
| 1. Bring in data | assemble + enrichment | Only if enrichment is on |
| 2. Check sales | clean, sales scrutiny | No |
| 3. Check my values | ratio study, horizontal and vertical equity on the value field(s) named in the wizard | No |
| 4. Build model values | model, finalize, ratio study on model values. The user picks a model or "Choose for me" (LightGBM). Each option has a one-line plain description | No |
| 5. Reports and export | PDF reports, CSV/Excel/shapefile export | No |

**Results views:**
- a map colored by ratio, value or flag
- sortable tables
- a few charts
- "things to look at" lists, such as suspicious sales and outlier parcels

Every number has a "What does this mean?" explainer.

### 3.4 Plain-language rules
- No jargon without an explainer. "COD 14.2 — *your values are fairly uniform; IAAO target is under 15*."
- Errors say what happened, why, and what to click next. They never show a stack trace; that goes to a log file instead.
- Long jobs show time remaining, can be cancelled, and survive the app being closed (they resume from checkpoints).

## 4. Inputs, outputs, reports

- **Import:** Shapefile (loose files or zipped), GeoPackage, GeoJSON, CSV, Excel (`.xlsx`/`.xls`). Oakbox converts everything to GeoParquet in the project's `in/` folder. OpenAVMKit only reads CSV/Parquet today.
- **Export:** values, flags and ratios per parcel as CSV, Excel and Shapefile/GeoPackage, laid out for re-import into appraisal (CAMA) software. Saved export layouts ("profiles") come later.
- **PDF reports:**
  - ratio study
  - equity studies
  - sales scrutiny
  - model summary

  They should be clean, printable and suitable for a review board.
- **Custom reports:** the user picks sections and filters (neighborhood, class) and adds a logo or header text. Saved as a template per project. Jurisdiction packs (for example Texas) ship as templates later.

## 5. Hardware targets

These are hypotheses, to be confirmed by the M0 benchmark.

**Decided:** the low-end floor is acceptable for small jurisdictions. Large jurisdictions get a clear warning that they need a stronger machine.

| Tier | Machine | Parcel capacity (target) |
|------|---------|--------------------------|
| Floor | Win10 x64, 4 cores, **8 GB RAM**, 25 GB free disk | ~150k parcels, all steps |
| Recommended | 4+ cores, **16 GB RAM**, SSD | ~150k–500k parcels |
| Large | 8+ cores, **32 GB RAM**, SSD | 500k+ parcels |
| Below floor | 4 GB RAM | Sample counties and small counties (<25k) only. The app warns but doesn't block. |

The large-tier numbers are a guess until M0. When parcels are imported, Oakbox compares the parcel count with the machine. If the machine is under-specified, it shows a plain warning, for example: "This county has 520,000 parcels. This computer has 8 GB of memory; we recommend 32 GB. Steps may be very slow or fail." The user can continue anyway.

What the floor is based on:
- Windows 10 is still about 26% of Windows PCs ([StatCounter, May 2026](https://tech.yahoo.com/computing/articles/microsoft-giving-windows-10-users-180152418.html)), and its paid security updates run to Oct 2027.
- 16 GB is the most common RAM size in consumer surveys, but around 10% of machines have 8 GB ([PassMark](https://www.memorybenchmark.net/amount-of-ram-installed.html)), and office PCs skew lower.

On start, the app checks RAM, cores and free disk, and scales down parallelism and memory-hungry steps to fit (for example, it turns off the street-network enrichment below 16 GB).

## 6. Architecture (proposed)

```
┌──────────── Oakbox.exe (per-user install) ─────────────┐
│ UI: local web UI in a native window (pywebview →       │
│     Edge WebView2; falls back to the default browser)  │
│        │  localhost HTTP + server-sent progress events │
│ App service (Python): projects, wizard, file import,   │
│     map tiles, reports, update check                   │
│        │  spawn / cancel                                │
│ Engine worker (separate Python process): OpenAVMKit    │
│     stage runner, one per job; streams progress events │
└────────────────────────────────────────────────────────┘
  Bundled: CPython 3.11 (standalone build) + locked wheels
```

- **One language (Python) plus a thin HTML/JS front end.** That suits a small team and reuses the OpenAVMKit stack. A web UI makes maps, tables and report previews much easier than Qt does. Win10 machines get WebView2 through Windows Update. Libraries: MapLibre or Leaflet for maps, a lightweight table component, and no build-heavy framework.
- **The engine runs in a worker process.** OpenAVMKit uses `os.chdir` and paths relative to the current folder, and it can run out of memory or crash. A separate process isolates it, makes cancelling clean, and lets the UI stay responsive.
- **Large maps.** The app service builds vector tiles on the fly from the project's GeoParquet, so the browser never loads 500k polygons at once.
- **Packaging:**
  - a standalone CPython build plus pre-installed, hash-locked wheels (via `uv`), with no freezing. PyInstaller-style freezing struggles with GDAL, PROJ and numba.
  - shipped as a **per-user installer** (Inno Setup or NSIS, both open source) that unpacks to `%LOCALAPPDATA%\Oakbox` with no admin rights and adds Start-menu and desktop shortcuts.
  - a plain portable `.zip` as a fallback.

  Expected size: about 1.2 GB installed, about 400 MB to download.
- **Projects** are ordinary folders (an OpenAVMKit locality layout plus `oakbox.json`) under `Documents\Oakbox\`. You can copy, zip or back them up.
- **Reproducibility.** Each project records the Oakbox and OpenAVMKit versions it last ran with. Installs sit side by side, so an old version can be kept to re-run a past year exactly.
- **Updates.** A **Check for updates** button, plus an optional reminder the user agrees to on first run, reads GitHub Releases. The only thing sent is a plain version request. Updates install side by side and the old version is kept until the user removes it.
- **Privacy.** No telemetry and no crash upload. Enrichment calls send geographic extents only. A "Send log to support" button builds a zip the user emails themselves.

### 6.1 Keeping a macOS target possible
The stack is cross-platform already:
- pywebview uses WKWebView on macOS.
- The scientific wheels exist for Apple Silicon.
- Standalone CPython builds exist for macOS.

Rules to keep it that way:
- No Windows-only APIs outside one small `platform/` module (paths, installer hooks, RAM/CPU probe).
- `pathlib` everywhere; no hard-coded drive letters or `\` separators.
- CI builds and smoke-tests the bundle on macOS from M1, even before we ship there.

Known macOS costs, deferred:
- **Signing and notarization.** Apple requires a paid developer account to avoid Gatekeeper warnings.
- **OpenMP runtime.** LightGBM and XGBoost need it, and `libomp` must be bundled inside the app.
- **Format.** A `.dmg`/`.app` package instead of an installer.

## 7. Upstream OpenAVMKit work (`oakbox` branch)

1. **Headless stage API.**

   ```python
   run_stage(project_dir, stage, on_progress, cancel)
   ```

   It shouldn't use `os.chdir` or require IPython. `ipython`, `pytest` and `pipreqs` move out of the runtime dependencies.
2. **Structured progress events** (stage, step, fraction, message) instead of `print`. Warnings get routed into the same channel.
3. **Settings schema and validation**, with field-level, human-readable errors. The wizard uses it too.
4. **Replace wkhtmltopdf**, which is archived and needs a separate install. Candidate: **Typst**, an open-source typesetter whose Python wheel has no system dependencies. It also gives us templated custom reports.
5. **Native GIS and Excel loaders** (Shapefile, GPKG, GeoJSON, XLSX), or keep these in Oakbox. TBD.
6. **Ratio and equity studies on an existing value column** as a first-class step that doesn't need modeling first.
7. **Low-memory mode:** smaller number types, a cap on parallel workers, chunked enrichment.
8. **Versioned releases** (git tags), so Oakbox can pin an exact OpenAVMKit version.

## 8. Milestones

- **M0 — Spike.**
  - Portable build runs the `us-va-petersburgcity` sample end to end on a clean Win10 VM with 8 GB RAM, with no internet after install.
  - Benchmark RAM and time on a synthetic city at 50k, 150k and 500k parcels.
  - Confirm §5.
- **M1 — "Check my values."**
  - Installer, home screen, sample county, minimal wizard (parcels, sales, current value)
  - steps 1–3, map and tables, ratio study PDF, CSV/Excel export
- **M2 — Full wizard and enrichment.** All wizard screens, enrichment, sales scrutiny views, custom report builder (v1).
- **M3 — "Build model values."** Step 4, export back to CAMA, model summary report.
- **M4 — Hardening.**
  - IT-friendly install (MSI, silent install, admin-managed updates), code signing
  - localization
  - jurisdiction packs (Texas first)

## 9. Open questions

See the current round in the conversation; answers are folded into §2 as they're decided.
