# Oakbox — OpenAVMKit in a Box

**Status:** v1.0 draft for review. Decisions are in §2; open items are in §10.

## 1. Purpose

A desktop app that lets a non-technical assessor run OpenAVMKit on their own parcels, with no command line and no hand-edited config. Download, double-click, work.

**Primary user:** a 50-year-old, tech-averse assessor at a small, underfunded office, on an old Windows PC, often without admin rights.

**Success test:** that user can go from "downloaded" to "a PDF ratio study of my current values" with no outside help.

## 2. Decisions

| # | Topic | Decision |
|---|-------|----------|
| D1 | Scope | Both checking values and producing values. Checking values ships first. |
| D2 | Configuration | Wizards and builders write `settings.json`. Users never see JSON. |
| D3 | Jurisdictions | Generic, not Texas-specific. Test with OpenAVMKit's public sample localities. Non-disclosure states come later. |
| D4 | Data model | GIS-first. A parcel geometry layer is required. |
| D5 | Scale | 500k+ parcels supported on suitable hardware. Small jurisdictions run on the low-end floor (§5). |
| D6 | Platform | Windows 10 64-bit minimum. Installs per user, with no admin rights. A later macOS version must stay possible (§6.1). |
| D7 | Network | Works offline. Internet is only needed for optional enrichment, the map background and update checks. |
| D8 | Updates | The user approves each update. IT-managed deployment comes later. |
| D9 | Input/output | In: Shapefile, GeoPackage, GeoJSON, (Geo)Parquet, CSV, Excel. Out: (Geo)Parquet, GeoPackage, Shapefile, CSV, Excel. Polished PDF reports. Custom reports. |
| D10 | Engine | OpenAVMKit changes are real commits on the `openavmkit-oakbox` branch, pinned by commit, later upstreamed (§7). |
| D11 | Licensing | Oakbox's own code is MIT. OpenAVMKit, including our `openavmkit-oakbox` commits, stays AGPL-3.0/commercial. The installer bundle ships OpenAVMKit under AGPL with a source link. All other dependencies must be free and open-source and AGPL-compatible (§6.2). |
| D12 | Privacy | No parcel data leaves the machine. No telemetry. |
| D13 | Localization | Deferred. All UI strings go in a string table from day one. |
| D14 | Code signing | Deferred; the maintainer will handle it. |
| D15 | UI tech | Web tech (HTML/JS) in a native window on a Python backend. |
| D16 | Checking values | The user must name the value field(s) to check. No particular field is required. |
| D17 | Online notices | Anything that goes online says what it sends, in a calm one-time notice (§3.11). |
| D18 | CAMA export | v1 is a generic CSV/Excel file: parcel ID plus new columns. Vendor-specific layouts come later. |
| D19 | Sample county | `us-va-petersburgcity`, because it runs fast. |
| D20 | Model choice | The assessor picks a model, or "Choose for me", which means LightGBM. |
| D21 | Name | "Oakbox" for now. |
| D22 | Model groups | A dedicated builder with live map feedback (§3.5). |
| D23 | Sale validity | Office codes and OpenAVMKit scrutiny together. The assessor can overrule any sale (§3.6). |
| D24 | Years | One project per jurisdiction per tax year (§3.7). |
| D25 | Users | Single user, one PC, for now. |
| D26 | Help | Built-in help pages plus a link to the Discord. An AI helper comes later (§3.8). |
| D27 | Bad input data | A Data health screen with plain-language problems and safe one-click fixes (§3.9). |
| D28 | Ratio study | IAAO statistics with pass/fail against editable standards profiles (§4.2). |
| D29 | Enrichment | A dedicated Enrichment screen exposes OpenAVMKit's real options. It shows per-enrichment cost estimates, a small-area trial run and coverage results (§3.12). v1 covers map-layer joins, footprints, census (configurable variables), distances (OpenAVMKit's default features plus the user's own layers), elevation, permits and missing-value inference (explained as a modeling-only guess). The street network is deferred. |
| D30 | Variables | "Plow forward" or "Test variables first" (§3.10). |
| D31 | Map background | Offline: parcels only. Online: an OpenStreetMap-based background. The user's own imagery comes later (§3.11). |
| D32 | Custom reports | Sections and branding for everyone; editable Typst templates for power users (§4.3). |

## 3. What the user sees

### 3.1 Home screen
- **My projects**, shown as cards: jurisdiction, tax year, last opened, and how far along the steps it is.
- **New project** opens the wizard.
- **Try a sample county** downloads `us-va-petersburgcity` and opens it. This is the first-run experience and also the training mode.

### 3.2 New-project wizard
One question per screen, in plain words. **Back** always works. Progress is saved after every screen.

1. **Name, place, tax year.** The app picks the folder, units and map center.
2. **Parcels.** The user drags in a GIS file (`.shp`, a zipped shapefile, `.gpkg`, `.geojson`, GeoParquet `.parquet`) and sees it on a map straight away.
3. **Parcel details** (optional). CSV, Excel or Parquet files joined to the parcels by parcel ID. The app guesses the ID column; the user confirms it.
4. **Sales.** A CSV, Excel or Parquet file with parcel ID, date, price and the office's validity code if there is one.
   - The user marks which codes mean "valid".
   - With no code, all sales start as valid and step 3 flags the doubtful ones.
   - Oakbox always produces the `valid_sale` column that OpenAVMKit requires.
5. **Match columns.** The app auto-maps the user's columns to OpenAVMKit fields: "We think `SQFT_LIV` is *Living area*. Correct?" The user only has to confirm the uncertain ones.
6. **Values to check.** "Which value(s) do you want to check against sales?" The user picks one or more columns. Step 4 needs at least one; the user can skip this and check model values after step 5.
7. **Other map layers** (optional, local). Neighbourhoods, zoning, school districts and similar. The user drops in a file and picks which fields to attach (§3.12.1).
8. **Context data starting point:**
   - **None (offline)**
   - **Recommended:** census, standard distances, and elevation at a resolution suited to the area size. Footprints are included when the cost estimate allows.
   - **Custom:** opens the full Enrichment screen after the wizard.

   This is only a starting point. Everything is configured on the Enrichment screen (§3.12), and nothing heavy runs without a cost estimate first.
9. **Valuation date** and which years of sales to use.
10. **Review**, then **Create project**.

Property groups are not set up here, because they need the assembled data (§3.5). The wizard creates one default group, "All properties".

### 3.3 Project screen: a checklist of steps
Each step has **Run**, a progress bar with time remaining, **Cancel**, a plain-language status and **See results**. Running a later step runs any stale earlier steps first. Jobs resume from checkpoints if the app is closed.

| Step | What runs (OpenAVMKit) | Internet? |
|------|------------------------|-----------|
| 1. Bring in data | assemble + enrichment (§3.12), then Data health (§3.9) | Only for online enrichments |
| 2. Define property groups | model group tagging (§3.5) | No |
| 3. Check sales | clean (including Fill blanks, §3.12.2), sales scrutiny, assessor overrides (§3.6) | No |
| 4. Check my values | ratio study, horizontal and vertical equity on the named value fields, overall and by group | No |
| 5. Build model values | optional variable testing (§3.10), model, finalize, ratio study on model values. Model picker with "Choose for me" | No |
| 6. Reports and export | PDF reports; Parquet, GeoPackage, Shapefile, CSV and Excel export (§4) | No |

**Results views:**
- a map coloured by ratio, value, group or flag
- sortable tables
- a few charts
- "things to look at" lists, such as suspicious sales and outlier parcels

### 3.4 Plain-language rules
- **No jargon without an explainer.** Every statistic has a "What does this mean?" pop-up, for example: "COD 14.2: your values are fairly uniform. The IAAO target is under 15."
- **Errors** say what happened, why, and what to click next. Stack traces only go to the log file.
- **Large text and high contrast** are available. Nothing important is shown only by colour.

### 3.5 Property group builder
Groups are parcels valued together, for example single-family, condos, commercial and vacant land. The screen is built around a tight edit → see → fix loop.

**Layout:**
- **Left:** the ordered group list, each with its colour, parcel count and sale count. "Unassigned" is always shown in grey.
- **Center:** a map coloured by group. Clicking a parcel shows its attributes and *why* it landed in its group ("matched rule 2 of Commercial"). A table toggle shows the same parcels as rows.
- **Right:** the rule editor for the selected group.

**Ways to define a group:**
1. **From a field.** Pick a field, such as land-use code. Oakbox lists the distinct values with counts, and the user assigns each value to a group.
2. **Rule builder.** Conditions of the form *field / operator / value*, with AND/OR and nesting. It maps one-to-one onto OpenAVMKit's filter lists (`filters.py`), so the builder can express anything the notebooks can.
3. **Hand edits.** Lasso or click parcels on the map. These are saved as an explicit parcel list, and reports list them.

**Behavior:**
- **First match wins,** as in OpenAVMKit. Groups can be dragged to reorder.
- **Live preview.** Every edit is re-evaluated against a cached parcel table without re-running the pipeline. The target is under 2 seconds at 500k parcels. **Apply** writes the settings.
- **Health checks per group:** "Only 12 sales — too few to model reliably", "3,104 parcels unassigned", "This rule matches nothing".
- **Advanced toggle:** common areas and condo rules.
- **Undo/redo.** Group definitions can be exported and imported, to reuse across years or share with a neighbouring jurisdiction.

### 3.6 Sales review and overrides
- **Two verdicts per sale:** the office code and OpenAVMKit's scrutiny flags, with reasons in plain words.
- **Final status:** **Valid** or **Invalid**, plus who decided (office code, scrutiny or assessor).
- **Overrides:** the assessor can **Keep** or **Exclude** any sale, with an optional note. Overrides win over both automatic sources and survive re-runs. They're written into the override files OpenAVMKit reads, so notebook users see the same result.
- **Views:** a map, a list, and filters ("only flagged", "only overridden", "by group").

### 3.7 Tax years
- A project is one jurisdiction × one tax year, stored at `Documents\Oakbox\<Jurisdiction>\<Year>\`.
- **Start next year** copies settings, groups, column mappings, standards profile and report templates. It can optionally copy overrides that still fall inside the sales window. The user then imports the new files, and the wizard only asks about columns that changed.
- Past years are read-only by default and record the engine version they ran with, so results can be reproduced for an appeal.

### 3.8 Help
- **"?" on every screen** opens an offline help page for that screen.
- **Glossary pop-ups** wherever a technical term appears.
- **Error screens** link to the matching help page and to the Discord.
- **Later, opt-in AI helper:**
  - (a) a small local model over the help pages, fully offline.
  - (b) the user's own frontier-model API key. This is an explicit, disclosed exception to D12.

### 3.9 Data health
Shown after step 1 and after any re-import. Each problem gets one card: what's wrong, how many rows, an example, and what to do.

| Problem | Safe one-click fix | Otherwise |
|---------|--------------------|-----------|
| Duplicate parcel IDs | Keep first / keep newest | Export the list |
| Sales that match no parcel | Exclude them | Export the list |
| Invalid or empty geometry | Repair / drop | Export the list |
| Parcels outside the jurisdiction | Drop | Show on map |
| Impossible values (negative area, year built 2099, $0 sale) | Treat as missing | Export the list |
| Wrong coordinate system | Reproject (with confirmation) | — |

- **Blocking or warning.** Only blocking problems stop the next step.
- **No silent fixes.** Every fix is logged and listed in each report's "Data corrections" appendix.
- **Download problem list (Excel),** so the office can fix the source in its appraisal (CAMA) system.

### 3.10 Variables: plow forward or test first
At the start of step 5, the user picks a path. They can switch later.

- **Plow forward** (default): OpenAVMKit's default variable handling, straight to modeling.
- **Test variables first:** runs `try_variables` per group and shows a review:
  - One row per variable with a plain verdict: *Drives value*, *Redundant with ___*, *Weak*, or *Counter-intuitive*.
  - A **Details** expander shows correlation, VIF, p-value and SHAP. The wording comes from the existing `variables.md`.
  - An include/exclude toggle per variable, defaulting to OpenAVMKit's recommendation.
  - **Try models with these variables:** a quick side-by-side comparison of the ratio statistics before the full run.

Both paths produce the same Variables report.

### 3.11 Online features and the map background
**Map background:**
- Offline, maps show parcels only.
- Online, the user can turn on a street background built from OpenStreetMap data.
- **Default provider:** a free, no-key service intended for third-party apps, such as OpenFreeMap. The tile URL lives in config, so the provider can be changed without a software update.
- **Fallback:** OSMF's own `tile.openstreetmap.org` is allowed under its [tile usage policy](https://operations.osmfoundation.org/policies/tiles/), but it has no service guarantee and may block heavy use without notice. If used, Oakbox must:
  - send an identifying User-Agent
  - show attribution
  - not prefetch or cache tiles for offline use
- The user's own aerial imagery file (GeoTIFF/MBTiles) comes later.

**Online notices.** The notice is calm, shown once, and never recurring. It appears the first time any online feature is switched on, and lists each service and what it receives. For example: "To draw the street map, Oakbox asks OpenFreeMap for map pictures of the area you're viewing, like any web map does. Your parcel data never leaves this computer." A **Settings → Online features** page lists every service and lets the user switch each one off. Nothing is re-asked unless a new service is added.

### 3.12 Enrichment
Enrichment adds context the office's data lacks. Some of it is cheap and local; some downloads gigabytes and runs for hours on a large county. The screen treats it as a set of configurable jobs, not checkboxes.

**Screen layout:**
- **One card per enrichment.** Each card shows:
  - what it adds, in plain words
  - its settings (common ones visible, the rest under **Advanced**)
  - what it sends online
  - a cost estimate
  - its cache state
  - after running, a results summary
- **Map preview** of whichever card is selected: downloaded features, or the new column coloured on parcels.
- **Run all**, **Run selected**, or **Try on a small area** for each card (below).

**Cost estimate before every run.** Oakbox computes it from:
- parcel count
- the bounding box area
- the enrichment's own drivers (resolution, number of features, distance caps)
- this machine's tier (§5)

It shows expected download size, time range and peak memory as a green, amber or red light. Red explains the cheapest lever, for example "Lower elevation detail to 30 m: about 9× less data" or "Cap distance to 2 km". The estimator's coefficients come from the M0 benchmarks and are refined over time.

**Try on a small area.** The user draws a box, or picks a neighbourhood. Oakbox runs the selected enrichment on just those parcels in seconds, using the same settings, and shows the result. This is how users tune settings before committing to a county-wide run. Results land in a scratch cache, never in the project.

**Caching is visible.** Each card says "Up to date", "Will reuse downloaded data" or "Settings changed: will re-download ~1.2 GB". Re-running only redoes what changed. **Clear cache** is per card.

**Results summary per card:**
- coverage: "% of parcels that got a value"
- new columns, with a histogram and a map layer
- warnings in plain words: "No buildings found in 312 parcels — mostly vacant land, as expected"

New columns automatically become available in the group builder, sales review, breakdowns and variable testing.

**Failure handling.** A failed online enrichment never fails step 1. The card turns amber with the reason (service down, bad key, area outside the US) and offers **Retry** or **Skip**. Skipped enrichments are listed in the report methodology.

#### 3.12.1 The enrichments
| Enrichment | User decisions (Advanced in italics) | Online: what is sent | Main cost driver | Adds |
|---|---|---|---|---|
| **Map layers** (spatial join) | Which layers; which fields; *match rule: "parcel centre inside" (default) or "overlaps"* | Nothing | Parcels × layer complexity | `neighborhood`, `zoning`, … Used by groups, breakdowns, equity studies |
| **Basic geometry** | None (always on). *Toggles for lat/lon, area, shape, polar* | Nothing | Shape metrics on every parcel | Lat/lon, GIS area, shape regularity. Required by distances, spatial lag and modeling, so these can't be turned off |
| **Building footprints** (Overture) | On/off; *units* | Bounding box, to Overture's public S3 | Downloaded area; parcel × building intersection (slow on big counties) | Footprint area, height, stories |
| **Census** (ACS 5-year) | Survey year; county FIPS (filled in from the place); API key; variables picked from a curated plain-language list (income, population, rent, home value, vacancy, tenure, …), defaulting to the current four. *Geography: block group (default) or tract; any ACS variable by table code* | State and county code and the chosen variable codes, to the Census API and TIGERweb | Small | Chosen variables; tract and block-group IDs (usable as locations) |
| **Distances** | **Defaults:** OpenAVMKit's built-in OSM feature set (water bodies, rivers, water, rail/transportation, airport, educational, parks, golf courses, coastline), kept exactly as maintained upstream. **Custom:** the assessor adds their own targets. Either a shapefile or other GIS layer (for example downtown, a landfill, a highway corridor), or *a custom OSM tag query*. Per feature: *max distance, unit, minimum size, nearest-N named features* | Bounding box, to the OpenStreetMap Overpass API. Custom shapefiles: nothing | Features × parcels. **Max distance is the main speed lever** | `dist_to_*`, `within_*`, `proximity_to_*` |
| **Elevation** (USGS 3DEP) | Detail: 10 m, 30 m or 60 m. Oakbox recommends one by area | Bounding box, to USGS | Area ÷ resolution². 10 m on a large county is gigabytes | Mean elevation, its variation, mean slope |
| **Permits** | Permit file(s) and column mapping; *effective-age calculation; teardown window* | Nothing | Small | Renovation and teardown flags, effective year built |
| **Estimate missing values** (spatial inference, `enrich.infer`) | Field to estimate; predictors (suggested: footprint, land area); location field; *substitute fields to copy from first (infer's `fill` key); method: "Choose for me" (LightGBM), ratio, random forest, XGBoost, ensemble; filters; rounding* | Nothing | Parcels × predictors, for each field | The estimated field plus an `inferred_*` flag |
| **Street frontage** | Deferred. Too heavy for v1 | — | — | — |

#### 3.12.2 Two different ways of filling blanks
OpenAVMKit has two separate features, and Oakbox keeps them separate, with different names, screens and labels:

| | **Estimate missing values** (`enrich.infer`) | **Default fills** (`data.process.fill`) |
|---|---|---|
| What it does | Predicts a value from nearby similar parcels with a model | Puts in a simple stand-in: group median/mean/mode, zero, min/max, "UNKNOWN", or a fixed value. *Can be limited to improved or vacant parcels* |
| When | Step 1, last enrichment | Step 3 (clean), per property group |
| Screen | Its card on the Enrichment screen | **"Fill blanks"** panel in step 3 |
| Typical use | Important characteristics with sizable gaps, such as finished area | Making every model input complete. Linear models crash on any blank; tree models tolerate blanks |
| Cost | Model training per field | Negligible |
| Label in UI | **"Estimate"** | **"Default"** |

**Shared rules (both features).** Each one is offered to everyone and always explained. The card or panel and a first-use dialog say, in plain words:

> "This fills gaps so the model can run. A filled value is an **educated guess** (Estimate) or a **simple stand-in** (Default). It is **not a fact** about the property. It is used **for modeling only** and is never written back to your records."

- **Always marked.** Filled values appear in a distinct style with their label in tables and parcel pop-ups. Estimates carry OpenAVMKit's `inferred_*` flag. Default fills need a new flag (upstream item 19).
- **Never exported as data.** CAMA exports keep the office's original (empty) value. Optional, clearly named "estimated"/"default" columns can go alongside.
- **Reported.** Reports state how many values of each field were filled, and how.
- **Order.** If both apply to a field, the estimate runs first (step 1). Default fills only touch what is still blank in step 3.

**Specific to Estimate missing values:**
- It runs last in step 1, so it can use every other enrichment as a predictor.
- **Preview before committing:** how many values are missing, and a plain validation score from OpenAVMKit's experiment mode, e.g. "guesses are typically within ±18% of the real value".

**Specific to Default fills:**
- **Suggested automatically.** Before step 5, Oakbox lists every model input that still has blanks and proposes a fill (median for numbers, "UNKNOWN" for categories). This replaces the manual rule in OpenAVMKit's docs: "whenever you add an enrichment numeric, add it to `data.process.fill`". Enrichment fields with partial coverage, such as census or elevation, are the usual culprits.
- **Automatic tidy-ups are shown, not hidden.** OpenAVMKit's automatic steps (year-built/age reconciliation, categorical "UNKNOWN") are listed in the panel as read-only rules.

#### 3.12.3 Modeling-time context (step 5)
**Spatial lag** (nearby sale prices and characteristics) and **area statistics** (neighbourhood means and medians) are computed in step 5, not step 1. They depend on groups and train/test splits.

- **Defaults:**
  - spatial lag: each group samples from itself
  - area stats: neighbourhood and census-tract medians of price and size
- **Advanced:** which locations, fields and statistics; minimum count; which groups a group samples from.
- **Cost:** cheap compared with step 1.

## 4. Inputs, outputs and reports

### 4.1 Import and export
- **Import:** Shapefile (loose or zipped), GeoPackage, GeoJSON, Parquet/GeoParquet, CSV and Excel. Oakbox stores everything as GeoParquet in the project's `in/` folder. Parquet is copied as-is after a schema check. OpenAVMKit itself only reads CSV/Parquet today.
- **Export:** per-parcel values, flags and ratios as Parquet/GeoParquet, GeoPackage, Shapefile, CSV and Excel, ready to re-import into appraisal software. Saved export layouts come later.
  - **Default:** GeoPackage for GIS users and CSV for everyone else.
  - **Shapefile caveats:** the format truncates field names to 10 characters and caps files at 2 GB. When either applies, Oakbox warns and writes a field-name key alongside the file.
  - **Excel cap:** about 1,048,576 rows. Larger exports are split across sheets, or Oakbox suggests CSV.

### 4.2 Ratio study report and standards profiles
Built on OpenAVMKit's existing `ratio_study.md` report and exports, which already include:
- the jurisdiction-vs-model comparison
- a sales-chasing check
- price-decile breakdowns
- openratiostudy.com exports

Oakbox adds:
- **IAAO statistics** for every group and breakdown: median ratio, COD, PRD and PRB, each with confidence intervals and sale counts. VEI and MKI from the IAAO draft revision are included, so the report survives the new standard.
- **Pass/fail badges against a standards profile.** A profile is a small file holding targets per statistic and property class, minimum sample size, look-back period and required breakdowns.
  - It ships with an IAAO default.
  - State profiles come with jurisdiction packs later.
  - Users can copy a profile and edit it in a form.
- **Breakdowns** by group, neighbourhood, price decile and any user-chosen field.
- **Charts:** ratio vs. sale price, ratio distribution, and a map of ratios by neighbourhood.
- **A first page a board member can read:** "Residential values meet IAAO uniformity standards (COD 11.8, target ≤15) but show mild regressivity (PRD 1.04, target ≤1.03)."
- **Appendices:** data corrections, sale overrides, excluded variables and methodology.

### 4.3 Reports and customization
- **Standard PDF reports:**
  - ratio study
  - equity studies
  - sales scrutiny
  - variables
  - model summary
- **Rendering:** Typst, replacing wkhtmltopdf. Typst is open source, and its Python wheel needs no system install.
- **For everyone:** pick sections, filter by neighbourhood or class, add a logo and header text, choose a standards profile. These choices are saved as a per-project report preset.
- **For power users and consultants:** the reports are plain Typst template files. **Open template folder** copies them into the project so they can be edited. Oakbox validates an edited template before using it and falls back to the stock template on error. Jurisdiction packs ship as template sets.

## 5. Hardware targets

| Tier | Machine | Parcels (target) |
|------|---------|------------------|
| Below floor | 4 GB RAM | Samples and jurisdictions under 25k; warns |
| Floor | Win10 x64, 4 cores, 8 GB RAM, 25 GB free disk | up to ~150k |
| Recommended | 4+ cores, 16 GB RAM, SSD | ~150k–500k |
| Large | 8+ cores, 32 GB RAM, SSD | 500k+ |

- **The parcel limits are hypotheses** until the M0 benchmark confirms them.
- **Plain warning, never a block.** When parcels are imported, Oakbox compares the parcel count with this machine. For example: "This county has 520,000 parcels. This computer has 8 GB of memory; we recommend 32 GB. Steps may be very slow or fail." The user can continue.
- **Automatic scaling.** On start, Oakbox reads RAM, cores and free disk, then scales parallelism and memory-heavy settings to fit.
- **Why this floor:**
  - Windows 10 is still about 26% of Windows PCs ([StatCounter via Yahoo, May 2026](https://tech.yahoo.com/computing/articles/microsoft-giving-windows-10-users-180152418.html)), with paid security updates to Oct 2027.
  - 16 GB is the most common RAM size in consumer surveys, but about 10% of machines have 8 GB ([PassMark](https://www.memorybenchmark.net/amount-of-ram-installed.html)), and office PCs skew lower.

## 6. Architecture

```
┌──────────── Oakbox (per-user install) ─────────────────┐
│ UI: local web UI in a native window (pywebview →       │
│     Edge WebView2; falls back to the default browser)  │
│        │  localhost HTTP + server-sent progress events │
│ App service (Python): projects, wizard, import, data   │
│     health, group preview, map tiles, reports, updates │
│        │  spawn / cancel                                │
│ Engine worker (separate process): OpenAVMKit stage     │
│     runner, one per job; streams progress events       │
└────────────────────────────────────────────────────────┘
  Bundled: standalone CPython 3.11 + hash-locked wheels (uv)
```

- **Python plus a thin HTML/JS front end,** with no heavy build framework. MapLibre draws the maps; the table component is lightweight. WebView2 ships with Windows 10 through Windows Update.
- **The engine runs in a worker process.** OpenAVMKit uses `os.chdir`, paths relative to the current folder, and can crash or run out of memory. A separate process isolates it, makes cancelling clean, and keeps the UI responsive.
- **Large maps.** The app service builds vector tiles on the fly from GeoParquet, so the browser never loads 500k polygons at once.
- **Packaging:**
  - A standalone CPython build plus pre-installed wheels. No freezing: PyInstaller struggles with GDAL, PROJ and numba.
  - A per-user installer (Inno Setup) into `%LOCALAPPDATA%\Oakbox`, with no admin rights, plus Start-menu and desktop shortcuts.
  - A portable `.zip` as a fallback.
  - Roughly 1.2 GB installed and 400 MB to download.
- **Projects** are ordinary folders: an OpenAVMKit locality layout plus `oakbox.json`. They're easy to copy, zip and back up.
- **Reproducibility.** Each project records the Oakbox and OpenAVMKit versions it ran with. Versions install side by side, so an old one can be kept to re-run a past year exactly.
- **Updates.** **Check for updates** reads GitHub Releases. The only thing sent is a plain version request. The user approves each install, and the old version is kept until they remove it.
- **Privacy.** No telemetry and no crash upload. **Send log to support** builds a zip the user emails themselves.

### 6.1 Keeping macOS possible
- **The stack already runs on macOS:** pywebview uses WKWebView there, the scientific wheels exist for Apple Silicon, and standalone CPython builds exist.
- **Windows-only code stays contained.** OS-specific code lives in one `platform/` module (paths, installer hooks, hardware probe). `pathlib` is used everywhere.
- **CI smoke-tests a macOS build** from M1.
- **Deferred macOS costs:**
  - Apple signing and notarization (a paid account)
  - bundling `libomp` for LightGBM and XGBoost
  - a `.dmg` package

### 6.2 Licensing
- **Oakbox code: MIT.** It is the simplest permissive licence, compatible with the AGPL, and familiar to government IT and procurement.
- **The engine stays dual-licensed.** OpenAVMKit, including everything on `openavmkit-oakbox`, remains AGPL-3.0 or commercial. Contributions there go through OpenAVMKit's CLA.
- **The installer is AGPL-governed.** It contains OpenAVMKit, so it is distributed under the AGPL's terms. The About screen and installer link to the exact OpenAVMKit source commit, and a `THIRD-PARTY-LICENSES` file lists every bundled package.
- **Effect:** anyone may reuse or rebrand the Oakbox wrapper. Shipping it with OpenAVMKit still requires AGPL compliance or a commercial OpenAVMKit licence. The engine keeps its protection; the wrapper is friction-free.
- **CI licence check** fails the build if a dependency is not free/open-source or not AGPL-compatible.

## 7. Engine: OpenAVMKit changes

**Where the work lives.** The branch [`openavmkit-oakbox`](https://github.com/larsiusprime/oakbox/tree/openavmkit-oakbox) in the Oakbox repo carries OpenAVMKit's full history. It currently starts at OpenAVMKit `master` (`f35b089`, after v0.7.0). Our changes go on top as ordinary commits.

**How Oakbox uses it.** As a normal dependency pinned to one commit in the `uv` lockfile, for example `openavmkit @ git+https://github.com/larsiusprime/oakbox@<commit>`. There are no submodules and no runtime monkey patches.

**Easy to change later.** Moving it means changing one dependency URL:
1. With push access to OpenAVMKit, push the branch there as `oakbox` and merge it by PR. The dependency URL then points there.
2. Once the changes are released, pin the OpenAVMKit release instead.

**Planned changes:**
1. **Headless stage API:** `run_stage(project_dir, stage, on_progress, cancel)`, with no `os.chdir` and no IPython. `ipython`, `pytest` and `pipreqs` move out of the runtime dependencies.
2. **Structured progress events** (stage, step, fraction, message) replace `print`. Warnings go through the same channel.
3. **Settings schema and validation** with field-level, plain-language errors.
4. **Typst report rendering** replaces wkhtmltopdf.
5. **Ratio and equity studies on an existing value field,** without modeling first.
6. **Standards profiles,** pass/fail thresholds, and VEI/MKI.
7. **Sale overrides both ways:** add a "force valid" list next to the existing invalid-key file, with reasons.
8. **Explain group assignment:** which group and which rule matched a parcel.
9. **Data health checks** as a library function that returns structured problems.
10. **Low-memory mode:** smaller dtypes, capped workers, chunked enrichment.
11. **GIS and Excel loaders** (or keep them in Oakbox; see §10).
12. **Tagged releases,** so `__version__` is never `0+unknown`.
13. **Enrichment plumbing:**
    - a progress event per enrichment
    - a cost-estimate helper (inputs: bbox, parcel count, settings)
    - run any enrichment on a subset of parcels (for "Try on a small area")
14. **Per-enrichment cache signatures.**
    - Today, the Overture signature covers the whole `enrich` block, so editing any enrichment invalidates it.
    - The inference cache has no settings signature, so its results can go stale.
15. **Census (needed for v1):** honour a configurable variable list and geography level (block group or tract). Variables are hard-coded to four today, and the documented `fields` key is ignored.
16. **Performance:** vectorise the Overture parcel × building intersection, which is currently a row-wise `apply` marked TODO.
17. **Streets fixes before it is offered:**
    - the hard-coded `frontage_ft_1` breaks metric localities
    - the empty-result KeyError
    - expose ray and buffer parameters in settings
18. **Docs:** `config.md` shows an obsolete distances schema; the spatial-join key is `geometry`, not `spatial_joins`; the spatial-lag docs omit `model_groups`. Docs describe infer's `fill` key as "follow-up fields to fill from the inferred values", but the code copies *into* the target field from those substitute fields.
19. **Provenance flag for default fills.** `data.process.fill` currently overwrites blanks without recording which rows were filled, so the UI can't mark them or keep them out of exports.

## 8. Milestones

- **M0 — Spike.** Prove the packaging and the hardware assumptions.
  - A portable build runs Petersburg end to end on a clean Windows 10 VM with 8 GB RAM, offline after install.
  - Benchmark RAM and time on synthetic cities of 50k, 150k and 500k parcels.
  - Rewrite §5 with the measured numbers.
- **M1 — "Check my values."**
  - Installer, home screen, sample county, minimal wizard
  - Steps 1–4, with the group builder in "From a field" mode only
  - Enrichment limited to map layers and basic geometry, so M1 runs offline
  - Data health (blocking checks), map and tables
  - Ratio study PDF with the IAAO profile, CSV/Excel export, offline help
  - Usability test with 3 real assessors before calling M1 done
- **M2 — Full wizard, groups and sales.**
  - Enrichment screen: all §3.12.1 enrichments except Street frontage, with cost estimates, small-area trial runs, cache states and the one-time online notice
  - Full group builder, sales review and overrides
  - Map background
  - Start next year
  - Report presets and editable templates
- **M3 — "Build model values."**
  - Step 5 with both variable paths and the model picker
  - CAMA export
  - Model summary report
- **M4 — Hardening.**
  - IT-friendly install (MSI, silent install, managed updates)
  - Code signing
  - Localization
  - Jurisdiction packs (Texas first)
  - macOS build

## 9. Out of scope for v1
- Multi-user or shared-drive projects
- Non-disclosure-state workflows
- Vendor-specific CAMA formats
- Street-network enrichment
- Own aerial imagery
- The AI helper
- macOS release

## 10. Open items
1. **openratiostudy.com layout.** The site is blocked by this environment's network policy. Unblock it, or share a screenshot or sample export, to align the report layout.
2. **M0 results** will set the hardware tiers in §5 and the enrichment cost-estimate coefficients in §3.12.
3. **GIS and Excel loaders:** upstream in OpenAVMKit, or in Oakbox only? I lean upstream, so notebook users benefit too.
4. **Tile service:** confirm OpenFreeMap, or choose another free provider that allows app use.
5. **Typst** as the report engine: confirm before M1.
