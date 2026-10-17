# Oakbox — OpenAVMKit in a Box

**Status:** Draft 0.4. Built through dialogue; nothing here is final until marked **Decided**.

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
| D22 | Model groups | **Decided.** A dedicated, detailed builder: define groups, see the result on a map at once, inspect parcels, adjust, refresh (§3.5). |
| D23 | Sale validity | **Decided.** Use both the office's own validity codes and OpenAVMKit's scrutiny. The assessor can overrule any sale, the same way the settings and notebook workflow allows (§3.6). |
| D24 | Years | **Decided.** One project per jurisdiction per tax year. A new year starts as a copy of the previous one (§3.7). |
| D25 | Users | **Decided.** Single user, one PC, for now. Multi-user comes later. |
| D26 | Help | **Decided.** Built-in help pages plus a link to the Discord. An AI helper comes later (§3.8). |
| D27 | Bad input data | **Decided.** A Data health screen after import, with plain-language problems and safe one-click fixes. Every fix is logged and reported (§3.9). |
| D28 | Ratio study report | **Decided.** IAAO statistics by default, building on OpenAVMKit's existing report and exports. openratiostudy.com is a reference. Targets come from configurable local-standards profiles (§4.1). |
| D29 | Enrichment v1 | **Decided.** Building footprints, census, distances and elevation. The street network is deferred (too memory-heavy). |
| D30 | Variables | **Decided.** Two paths: "Plow forward" (defaults) or "Test variables first" (an explicit significance review). Neither path is required (§3.10). |

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
4. **Sales.** A CSV or Excel file with parcel ID, date and price, plus the office's validity code if there is one. The user maps which codes mean "valid". With no code, all sales start as valid and scrutiny in step 3 flags the doubtful ones. OpenAVMKit requires a `valid_sale` column, so Oakbox always produces one.
5. **Match columns.** The app auto-maps the user's columns to OpenAVMKit fields: "We think `SQFT_LIV` is *Living area*. Correct?" The user only has to confirm the uncertain ones.
6. **Values to check.** "Which value(s) do you want to check against sales?" The user picks one or more columns, for example the current appraised value or last year's value. At least one is required to run step 4. If none exists yet, the user can skip and check model values after step 5.
7. **Enrichment.** Optional, online only. Plain-language checkboxes, for example: "Add building footprints (Overture)", "Add census tracts and income", "Add distances to roads, water and parks (OpenStreetMap)", "Add elevation (USGS)". The street-network enrichment is not offered in v1. Each one says what is sent: only the county's bounding box, never parcel data. The Census option includes a short guided walkthrough for getting a free API key, then pasting it in; Oakbox checks that the key works. With no key, the Census step is skipped.
8. **Valuation date** and which years of sales to use.
9. **Review.** A summary of the setup, then **Create project**.

Property groups are *not* set up in the wizard. They need the assembled and enriched data, so they get their own step (§3.5). The wizard creates one default group, "All properties", so step 1 can run.

### 3.3 Project screen: a checklist of steps
Each step has a **Run** button, a progress bar, a plain-language status and a **See results** link. If a later step is run before an earlier one, the app runs the earlier ones first.

| Step | OpenAVMKit stage | Internet? |
|------|------------------|-----------|
| 1. Bring in data | assemble + enrichment, then Data health (§3.9) | Only if enrichment is on |
| 2. Define property groups | model group tagging (§3.5) | No |
| 3. Check sales | clean, sales scrutiny, assessor overrides (§3.6) | No |
| 4. Check my values | ratio study, horizontal and vertical equity on the value field(s) named in the wizard, overall and by group | No |
| 5. Build model values | optional variable testing (§3.10), then model, finalize, ratio study on model values. The user picks a model or "Choose for me" (LightGBM). Each option has a one-line plain description | No |
| 6. Reports and export | PDF reports, CSV/Excel/shapefile export | No |

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

### 3.5 Property group builder
Groups are parcels that are valued together, for example single-family, condos, commercial, vacant land. Getting them right is iterative, so the screen is built around a tight edit → see → fix loop.

**Layout:**
- **Left:** the ordered list of groups, each with its name, color, parcel count and sale count. An "Unassigned" row is always shown in grey.
- **Center:** a map colored by group. Clicking a parcel shows its attributes and *why* it landed in its group ("matched rule 2 of Commercial"). A table toggle shows the same parcels as rows.
- **Right:** the rule editor for the selected group.

**Ways to define a group, from easiest to hardest:**
1. **From a field.** Pick a field such as land-use code. Oakbox lists its distinct values with counts, and the user drags or assigns each value to a group. This covers the "prefilled field" case in a minute.
2. **Rule builder.** Conditions of the form *field / operator / value*: equals, not equals, in list, greater/less than, between, is empty, contains. They combine with AND/OR and can nest. This maps one-to-one onto OpenAVMKit's filter lists (`filters.py`), so anything the notebooks can express, the builder can express.
3. **Hand edits.** Lasso or click parcels on the map and move them to a group. These are saved as an explicit key list. They're the last resort, and reports list them.

**Behavior:**
- **Order matters.** A parcel goes to the *first* group whose rules it matches, which is how OpenAVMKit works. Groups can be dragged to reorder, and the map updates.
- **Live preview.** Every edit re-evaluates instantly against the cached parcel table in the app service, without re-running the pipeline. The target is under 2 seconds at 500k parcels. **Apply** writes the settings and re-tags.
- **Health checks per group,** in plain words: "Only 12 sales — too few to model reliably", "3,104 parcels unassigned", "This rule matches nothing".
- **Advanced options:** common-area handling, condo rules. These sit behind an "Advanced" toggle.
- **Undo/redo** works throughout. Group definitions are saved per project and can be exported or imported, to reuse across years or share with a neighbouring county.

### 3.6 Sales review and overrides
- Every sale shows two verdicts: the **office code** (from import) and **OpenAVMKit scrutiny** flags, with the reason (for example "price far below similar sales nearby").
- The final status is **Valid** or **Invalid**, plus **who decided**: office code, scrutiny, or assessor.
- The assessor can **Keep** or **Exclude** any sale, with an optional note. Overrides win over both automatic sources and survive re-runs.
- Overrides are stored in the project and written into the settings/override files OpenAVMKit already reads (for example `analysis.sales_scrutiny.invalid_key_file`). Notebook users and Oakbox users see the same result.
- Reports include an overrides appendix (sale, decision, note, date), so the process is defensible.
- Views: a map of sales coloured by status, a sortable list, and filters such as "only flagged", "only overridden", "by group".

### 3.7 Tax years
- A project is **one jurisdiction × one tax year**, stored as `Documents\Oakbox\<Jurisdiction>\<Year>\`.
- **Start next year** copies settings, groups, column mappings, overrides (optional, defaulting to off for sales older than the window) and report templates into a new year. The user then imports the new data files, and the wizard only asks about columns that changed.
- Past years are read-only by default and keep the engine version they ran with (§6), so a past result can be reproduced for an appeal.

### 3.8 Help
- **"?" on every screen** opens a built-in help page for that screen. The pages ship with the app and work offline.
- **Glossary pop-ups** explain terms such as COD, PRD, PRB and model group wherever they appear.
- **Error screens** link to the matching help page and to the **Discord**. The Discord link is the only community channel in v1.
- **Later: AI helper.** Two options, both strictly opt-in:
  - (a) a small local language model with access to the help pages, which stays fully offline and keeps the D12 privacy promise.
  - (b) the user's own frontier-model API key. Before the first use, the app clearly discloses what is sent; this is an explicit exception to D12 that the user agrees to.

### 3.9 Data health
Shown automatically after step 1, and again whenever data is re-imported. Each problem is one card: what's wrong, how many rows, an example, and what to do.

| Problem | Safe one-click fix | Otherwise |
|---------|--------------------|-----------|
| Duplicate parcel IDs | Keep first / keep newest | Export the list to fix in CAMA |
| Sales that match no parcel | Exclude them from the study | Export the list |
| Invalid or empty geometry | Repair geometry / drop the parcel | Export the list |
| Parcels outside the jurisdiction | Drop them | Show on the map |
| Impossible values (negative area, year built 2099, $0 sale) | Treat as missing | Export the list |
| Wrong units or coordinate system | Reproject (with confirmation) | — |
| Sales outside the study window | Nothing to fix (informational) | — |

- Fixes are **never silent**. Each one is logged with a count and appears in a "Data corrections" appendix in every report.
- A **"Download problem list"** button exports Excel, so the office can fix the source data in its CAMA system.
- Problems are rated **blocking** or **warning**. Only blocking ones stop the next step; the user can always continue past warnings.

### 3.10 Variables: plow forward or test first
At the start of step 5, the user chooses one of two paths. The choice can be changed later.

- **"Plow forward" (default).** Oakbox uses OpenAVMKit's default variable handling and goes straight to modeling.
- **"Test variables first."** This runs OpenAVMKit's variable analysis (`try_variables`) per group and shows a review screen:
  - One row per variable, with a plain verdict: *Drives value*, *Redundant with ___*, *Weak*, or *Counter-intuitive* (for example "bigger homes sell for less").
  - Behind an "Details" expander: the underlying statistics (correlation, VIF, p-value, SHAP importance). The wording comes from the existing `variables.md` report.
  - A toggle per variable to include or exclude it, defaulting to OpenAVMKit's recommendation. Exclusions are saved to the project and listed in the model report.
  - **"Try models with these variables"** runs a quick comparison and shows the ratio statistics side by side, before the user commits to a full run.

Both paths produce the same Variables report, so the documentation is consistent either way.

## 4. Inputs, outputs, reports

- **Import:** Shapefile (loose files or zipped), GeoPackage, GeoJSON, CSV, Excel (`.xlsx`/`.xls`). Oakbox converts everything to GeoParquet in the project's `in/` folder. OpenAVMKit only reads CSV/Parquet today.
- **Export:** values, flags and ratios per parcel as CSV, Excel and Shapefile/GeoPackage, laid out for re-import into appraisal (CAMA) software. Saved export layouts ("profiles") come later.
- **PDF reports:**
  - ratio study
  - equity studies
  - sales scrutiny
  - model summary

  They should be clean, printable and suitable for a review board.
### 4.1 Ratio study report and local standards
Build on OpenAVMKit's existing `ratio_study.md` report rather than starting over. It already compares the jurisdiction's values with model values, includes a sales-chasing check, and breaks results down by price decile. It also already writes openratiostudy.com exports. Oakbox adds:

- **IAAO core statistics** for every group and breakdown, each with confidence intervals and sale counts:
  - median ratio
  - COD
  - PRD
  - PRB

  The IAAO draft revision adds VEI and MKI; include them so the report doesn't need a structural change when the standard is adopted.
- **Pass/fail badges** against a **standards profile**. A profile is a small file: target ranges per statistic, per property class, minimum sample size, look-back period, required breakdowns.
  - It ships with an **IAAO default** profile.
  - State profiles (for example Texas PVS) come later, as part of jurisdiction packs.
  - Users can copy a profile and edit the targets in a form.

  OpenAVMKit currently has no thresholds, so this is new.
- **Breakdowns** by group, neighborhood, price decile and any user-chosen field, such as age bracket or school district.
- **Charts:** ratio vs. sale price (scatter), ratio distribution (histogram), and a map of ratios by neighborhood.
- **A plain-language summary** on the first page, readable by a board member: "Residential values meet IAAO standards for uniformity (COD 11.8, target ≤15) but show mild regressivity (PRD 1.04, target ≤1.03)."
- **Appendices:** data corrections (§3.9), sale overrides (§3.6), and methodology.

**Reference wanted:** openratiostudy.com couldn't be reached from the build environment. A screenshot or a sample export would help pin down the layout.

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

**Where the work lives until access is granted (proposed).** A branch `openavmkit-oakbox` in the Oakbox repo, carrying OpenAVMKit's full history plus our commits.

**How Oakbox uses it:** as a normal pinned Python dependency, not a git submodule and not monkey patches. The lockfile names an exact commit:

```
openavmkit @ git+https://github.com/larsiusprime/oakbox@<commit>
```

`uv` hashes it, so every build is reproducible.

**Later:**
1. When access to the OpenAVMKit repo is granted, the branch is pushed there as `oakbox` unchanged and merged by a normal PR, with no rebasing or patch juggling. The dependency URL moves to the OpenAVMKit repo.
2. Once the changes are in an OpenAVMKit release, Oakbox pins that released version instead.

Oakbox never patches OpenAVMKit at runtime. Any change to OpenAVMKit is a real commit on that branch.

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
9. **Sale overrides both ways.** OpenAVMKit has an invalid-key file today. Add a matching "force valid" list, and record the reason for each override so reports can show it.
10. **Explain group assignment.** A helper that returns which group, and which rule, matched a parcel. `resolve_filter` already does the evaluation.
11. **Standards profiles and pass/fail thresholds** in the ratio study, plus VEI and MKI statistics.
12. **Data health checks** as a library function that returns structured problems. This keeps the checks reusable from notebooks.

## 8. Milestones

- **M0 — Spike.**
  - Portable build runs the `us-va-petersburgcity` sample end to end on a clean Win10 VM with 8 GB RAM, with no internet after install.
  - Benchmark RAM and time on a synthetic city at 50k, 150k and 500k parcels.
  - Confirm §5.
- **M1 — "Check my values."**
  - Installer, home screen, sample county, minimal wizard (parcels, sales, value field to check)
  - steps 1–4, with the group builder limited to the "From a field" mode
  - map and tables, ratio study PDF, CSV/Excel export, built-in help
- **M2 — Full wizard, groups and sales.**
  - All wizard screens and enrichment
  - the full group builder (rules, hand edits, health checks)
  - sales review with overrides
  - "Start next year"
  - custom report builder (v1)
- **M3 — "Build model values."** Step 5, export back to CAMA, model summary report.
- **M4 — Hardening.**
  - IT-friendly install (MSI, silent install, admin-managed updates), code signing
  - localization
  - jurisdiction packs (Texas first)

## 9. Open questions

See the current round in the conversation; answers are folded into §2 as they're decided.
