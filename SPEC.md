# Oakbox — OpenAVMKit in a Box

**Status:** v1.10 draft. Project setup is being redesigned one feature at a time to mirror OpenAVMKit (D41, §3.0); agreed features go in §3.0 before any code. Earlier revisions followed a full read of the OpenAVMKit docs, checked against its code (§6.3). Decisions are in §2; open items are in §10.

## 1. Purpose

A desktop app that lets a non-technical assessor run OpenAVMKit on their own parcels, with no command line and no hand-edited config. Download, double-click, work.

**Primary user:** a 50-year-old, tech-averse assessor at a small, underfunded office, on an old Windows PC, often without admin rights.

**Success test:** that user can go from "downloaded" to "a PDF ratio study of my current values" with no outside help.

## 2. Decisions

| # | Topic | Decision |
|---|-------|----------|
| D1 | Scope | Both checking values and producing values. Checking values ships first. |
| D2 | Configuration | The guided build and builders write fully resolved `settings.json`. Users never have to edit JSON; Under the hood shows it read-only (§3.2). Hand-made settings, including `$$` references and `!`/`+` keys, can be imported. |
| D3 | Jurisdictions | Generic, not Texas-specific. Test with OpenAVMKit's public sample localities. Non-disclosure states come later. |
| D4 | Data model | GIS-first. A parcel geometry layer is required. |
| D5 | Scale | 500k+ parcels supported on suitable hardware. Small jurisdictions run on the low-end floor (§5). |
| D6 | Platform | Windows 10 64-bit minimum is the primary target. **Linux x86_64 is also supported** (glibc 2.28+: Ubuntu 20.04+, Debian 10+, RHEL/Rocky 8+), from the same codebase and CI. Installs per user, with no admin rights. A later macOS version must stay possible (§6.1). |
| D7 | Network | Works offline. Internet is only needed for optional enrichment, the map background, update checks and the sample download. |
| D8 | Updates | The user approves each update. IT-managed deployment comes later. |
| D9 | Input/output | In: Shapefile, GeoPackage, GeoJSON, (Geo)Parquet, CSV, Excel, fixed-width text with a layout (PACS exports). Out: (Geo)Parquet, GeoPackage, Shapefile, CSV, Excel. Polished PDF reports. Custom reports. |
| D10 | Engine | OpenAVMKit changes are real commits on the `openavmkit-oakbox` branch, pinned by commit, later upstreamed (§7). |
| D11 | Licensing | Oakbox's own code is MIT. OpenAVMKit, including our `openavmkit-oakbox` commits, stays AGPL-3.0/commercial. The installer ships OpenAVMKit under AGPL with a source link. Every other dependency must be free/open-source and AGPL-compatible (§6.2). |
| D12 | Privacy | No parcel data leaves the machine. No telemetry. |
| D13 | Localization | Deferred. All UI strings go in a string table from day one. |
| D14 | Code signing | Deferred; the maintainer will handle it. |
| D15 | UI tech | Strict TypeScript + React 19 (SPA, React Compiler, React Aria Components), built with Vite. No Next.js/SSR. Runs in a native window on a FastAPI backend whose API types are generated into TypeScript, so the whole stack type-checks (§6.5). |
| D16 | Checking values | The user names the total-value field(s) to check. No particular field is required. Land values are out of scope: a separate land-value tool is planned. |
| D17 | Online notices | Anything that goes online says what it sends, in a calm one-time notice (§3.11). |
| D18 | CAMA export | v1 is a generic CSV/Excel file: parcel ID plus new columns. It carries total value only. Land values are left out; a separate land-value tool is planned. Vendor layouts come later. |
| D19 | Sample county | **Removed for now** (F3). It may be rebuilt on the new flow later. CI still runs OpenAVMKit end to end on `us-va-petersburgcity`, outside the app (§8 smoke test). |
| D20 | Model choice | The assessor picks a model, or "Choose for me": LightGBM with Oakbox's default variables and a small-sample fallback (§3.10). |
| D21 | Name and look | "OAK box" (written "Oakbox" in code and folder names). An oak-grain titlebar is the one decorative element; everything else is flat and edged, and only pressable things look raised. Type is IBM Plex Sans and Plex Mono (OFL), bundled, with Noto Sans as the fallback for other scripts. |
| D22 | Model groups | A dedicated builder with live map feedback (§3.5). |
| D23 | Sale validity | Office codes and OpenAVMKit scrutiny together. The assessor can overrule any sale. **A sale flagged invalid never enters the modeling pipeline.** Review happens in Oakbox's separate sales register (§3.6). |
| D24 | Years | One project per jurisdiction per tax year (§3.7). |
| D25 | Users | Single user, one PC, for now. |
| D26 | Help | Built-in help pages plus a link to the Discord. An AI helper comes later (§3.8). |
| D27 | Bad input data | Data health and a Field profile, with plain-language problems and safe one-click fixes (§3.9). |
| D28 | Ratio study | IAAO statistics with pass/fail against editable standards profiles (§4.2). |
| D29 | Enrichment | A dedicated Enrichment screen exposing OpenAVMKit's real options, with cost estimates, small-area trial runs and coverage results (§3.12). v1 covers map-layer joins, footprints, census (configurable variables), distances (OpenAVMKit's defaults plus the user's own layers), elevation, permits and missing-value estimation. The street network is deferred. |
| D30 | Variables | "Plow forward" or "Test variables first" (§3.10). |
| D31 | Map background | Offline: parcels only. Online: an OpenStreetMap-based background. The user's own imagery comes later (§3.11). |
| D32 | Custom reports | Sections and branding for everyone; editable Typst templates for power users (§4.3). |
| D33 | Staleness | Oakbox tracks which settings feed which step and re-runs exactly what changed. OpenAVMKit's checkpoints don't self-invalidate (§6.4). |
| D34 | Derived fields | Typed "transforms" in Match columns, plus an Advanced formula builder, compile to OpenAVMKit `calc`. Per-parcel corrections compile to `tweak` (§3.13). |
| D35 | Vacancy | Default: a blank finished area means vacant land (OpenAVMKit's rule), stated clearly. Users opt out per project and supply an explicit vacancy signal instead (§3.9). |
| D36 | Vacant land | Main (total-value) models only. No separate vacant-stage run within a model group (`run_vacant=False`). Vacant sales are still flagged correctly (`vacant_sale`), and vacant land is not a model group of its own. May be revisited. |
| D37 | Guided build | No up-front wizard. The project screen is the guide: setup stages, then steps, each with Decide → Check → Run → Receipt, and done only after **Looks right** (§3.2). |
| D38 | Datasets | Any number of input files, each declared as one of seven kinds, stitched by an explicit, user-confirmed plan with match rates and ID fixes (§3.2). |
| D39 | Show the work | Every stage shows what it will do and what it did, with counts and reasons. **Under the hood** (collapsed, open to everyone) shows the settings it wrote. |
| D40 | Sample | Superseded by D19: no sample in the app for now. |
| D41 | Mirror OpenAVMKit | OAK box is a GUI for OpenAVMKit, not logic on top of it. Every screen maps to something OpenAVMKit does or a setting it reads, and the user's choices are written as OpenAVMKit settings. When OpenAVMKit can't do something a user needs, the change goes upstream (§7), not into OAK box. OAK box's own logic is limited to presentation: previews, explanations, defaults and checks that read data without changing it. |
| D42 | Help on hover | Explanations go in hover tooltips (also shown on keyboard focus), not in lines of text on the screen. Screens carry only labels and what the user needs to act. Applies to new screens and to screens as they are revised. |

## 3. What the user sees

### 3.0 Project setup, feature by feature
Agreed one small feature at a time, each mapped to OpenAVMKit's own onboarding steps (its tutorial, "Build a jurisdiction from scratch", part B). Where this section and §3.2 differ, this section wins.

#### F1. New project
OpenAVMKit: creating a locality folder (`in/`, `out/`) and the `locality` block of `settings.json`, plus `modeling.metadata.valuation_date`.

**The user enters:**
- **Project name**: free text, e.g. "Travis County 2026". It names the folder and appears in OAK box. It is not the OpenAVMKit slug.
- **Country**, from the ISO 3166-1 list (two-letter codes).
- **State, province or region.** For the United States, picked from the ISO 3166-2 list of states and DC. For other countries, free text.
- **Jurisdiction**: what the office calls itself, e.g. "Travis County". Becomes `locality.name`, which OpenAVMKit prints on reports.
- **Tax year.** OpenAVMKit has no tax-year setting; it is OAK box's project identity (one project per jurisdiction per year, D24) and sets the valuation date's default.
- **Valuation date**: defaults to 1 January of the tax year. A one-line note: it should match the roll being checked.
- **Units**: imperial or metric, defaulting from the country. Becomes `locality.units`.

**OAK box creates:**
- The project folder `<storage location>/<project name>/`, with OpenAVMKit's `in/` and `out/`.
- `in/settings.json` with only:
  - `locality`: `name`, `state`, `units` and `slug`.
    - The slug is internal and never shown: `<country>-<region>-<jurisdiction>`, lowercase, no dashes inside a part (e.g. `us-tx-traviscounty`).
    - `center` is left out until the map step. OpenAVMKit falls back to the centroid of the parcel geometry when it is missing.
  - `modeling.metadata.valuation_date`.
- `oakbox.json`: OAK box's own state (project name, country and region codes, tax year, stage status).

**Storage location:** a Settings item, "Where projects are kept". It defaults to a folder named `OAK box` in the user's Documents (on Windows, `C:\Users\<name>\Documents\OAK box`). Changing it affects new projects only.

**Not in F1:** the center (from the map step, after a parcel map is loaded), data files, `data.load`.

**Open (F1):** editing core settings after creation. Name, units and the valuation date must stay editable, but changing units or the valuation date affects everything downstream, which must be shown as out of date ("dirty") before anything re-runs. How that is indicated is to be designed.

#### F1b. Project actions on the home screen
- **Show in folder** opens the project folder in the system file manager (Explorer on Windows).
- **Delete** sends the whole project folder to the system's Recycle Bin (or the desktop trash on Linux), so it can be recovered there. A confirmation names the project and its size on disk first. A project with a step running can't be deleted.

#### F2. Add a data file
OpenAVMKit: raw files live in the locality's `in/`, and each one is declared as an entry under `data.load` with its `filename`.

- **Formats:** exactly what OpenAVMKit's `data.load` reads: CSV, Parquet/GeoParquet, GeoPackage and shapefile. GeoPackage and shapefile reading was added on the engine branch for this (§7 B10). Any other format (Excel, zipped shapefile, FileGDB, GeoJSON, PACS fixed-width) is added upstream first, then offered here.
- **Move or copy.** Everything belongs in one place, the project's `in/`. When adding a file, the user chooses:
  - **Move**: the file leaves its original location.
  - **Copy**: the original stays where it was.

  A shapefile moves or copies with its sidecar files (`.shx`, `.dbf`, `.prj`, …). If a file of that name is already in `in/`, the user picks a new name or cancels.
- **Entry name.** OAK box suggests the `data.load` key from the file name (lowercase letters, digits and underscores, e.g. `parcels_2026`). The user can change it. The workflow around names will evolve with use.
- **GeoPackage layers.** If the file has several layers, the user picks one, and it is written as `"layer"`.
- **What gets written:** `data.load.<name> = {"filename": ...}` (plus `layer`). Nothing else. OpenAVMKit only loads columns an entry maps, so a new entry contributes nothing until later features map its columns.

- **Built:** Copy is pre-selected, as the choice that can't lose anything. A file already in `in/` is only declared, not moved. A shapefile missing its `.shx` or `.dbf` is refused before anything moves.

- **The add flow** *(revised after F3).* The file picker drives it:
  - **Add a file** opens the system file picker straight away. Cancelling the picker changes nothing.
  - Picking a file checks it at once (exists, supported format, shapefile companions, layers, size). There is no Check button.
  - The path is shown, not typed. **Browse…** picks another file; **Cancel** closes the form.
  - Format and size are pills on the File label's line, right-aligned to the path field's edge. A shapefile's companions are a third pill. The path field has a fixed width, so the buttons never move. A long path is cut short with "…", and the full path is in a tooltip.
  - A file that can't be used shows the reason in red under the path, and **Add file** stays disabled.
  - The file name isn't repeated below the path.
  - The name's explanation is a hover tooltip on the field (D42).
  - Outside the OAK box window (browser mode) there is no file picker, so **Add a file** is disabled, with a tooltip saying why.

  ```
  File                               (CSV) (11 MB)
  [ L:\git\...\us-va-petersburg\cama.csv   ]  [Browse…] [Cancel]

  Name            How to import
  [ cama      ]   (•) Copy it (a new copy is made for the project)
                  ( ) Move it (the original moves into the project)

  [ + Add file ]
  ```

  Other cases fit into that layout:
  - **GeoPackage with several layers:** a **Layer** column (a drop-down) between Name and How to import.
  - **Shapefile:** pills `(Shapefile) (2 MB) (+ .shx .dbf .prj)`.
  - **Filename already taken in `in/`:** a **New file name** field under Name, with the reason in its tooltip.
  - **File already in `in/`:** How to import reads "Already in the project folder", with no copy/move choice.
  - **Unusable file:** for example "Shapefile is missing its .dbf" in red under the path.
  - The path field and the buttons share one centreline.

**Not in F2:** looking inside the file, its ID, column mapping, joins, and removing a file (F3b).

#### F3. The project view: one tabbed panel

Under the project's name and tax year, everything about a project lives in one tabbed panel. Each later feature becomes a tab; a tab's own design always assumes this frame.

```
  < Projects
  Travis County 2026   Tax year 2026

 +-------------+-----------------+ - - - - + - - - - + - - - - +
 | [⚙] Metadata| [🗃] Input files |  · · ·  |  · · ·  |  · · ·  |
 +-------------+                 +---------+---------+---------+------------+
 |                                                         [ + Add a file ] |
 |   parcels        parcels.geoparquet               GeoParquet · 4 MB      |
 |   cama_2026      petersburg-dbo-cama-fix.parquet  Parquet · 3 MB         |
 |   county         county.gpkg (layer: parcels)     GeoPackage · 388 KB    |
 +--------------------------------------------------------------------------+
```

- **Tabs:**
  - **Metadata**, with a gear (⚙).
  - **Input files**, with a card file box (🗃). This is F2's "Data files", renamed.
  - Three placeholder tabs, shown as `· · ·`. They are greyed out and do nothing.
- **Tab icons** are the Noto Color Emoji images: the SVG files from Google's `noto-emoji` repository (Apache 2.0), bundled with the app. They are never the system's emoji font. They are placeholders for OAK box's own imagery later.
- **Look:** the selected tab joins the panel below it, like a folder tab. Other tabs sit behind it.
- **Which tab opens:** Input files when the project has no input files yet, otherwise Metadata.
- **Addresses:** each tab has one (`#/projects/<id>/metadata`, `#/projects/<id>/files`), so back and forward, and reopening a project, land on the same tab. The desktop window doesn't show addresses; this mostly matters in browser mode.
- **Text:** as little as possible. No explanatory sentences unless the maintainer asks for one.

**Metadata tab:** the F1 facts, read-only (editing is still open under F1), plus the project folder.

```
 |   Jurisdiction     Travis County                                         |
 |   Region           TX, United States                                     |
 |   Tax year         2026                                                  |
 |   Valuation date   2026-01-01                                            |
 |   Units            Imperial (square feet, acres)                         |
 |   Project folder   C:\Users\lars\Documents\OAK box\Travis County 2026    |
 |                    [ Show in folder ]                                    |
```

**Input files tab:** F2, unchanged in what it does. One line per file (its columns are in F3b). **Add a file** sits at the top right; the add flow opens inline at the top of the tab, above the list. Empty state: "No input files yet." with **Add a file**.

**The sample county is removed** (D19): the home screen's sample, the old steps screen (Run, Stop, results), and the code and API behind them, including the M1a settings generator. Projects made from the sample by earlier builds are no longer listed. The CI smoke test changes with it (§8).

#### F3b. The input file list: show, rename, remove

OpenAVMKit: each input file is one `data.load` entry, keyed by its name, with its `filename` (and `layer`).

```
                                                          [ + Add a file ]
                      Name         Type         Size     Geometry
  [📁] [✏️] [🗑️]      parcels      Parquet      4 MB     Yes
  [📁] [✏️] [🗑️]      cama         CSV          11 MB    No
  [📁] [✏️] [🗑️]      county       GeoPackage   388 KB   Yes
  [📁] [✏️] [🗑️]      old_sales    CSV          —        Missing
```

- **Columns:** Name, Type, Size, Geometry. There is no Source column.
- **Row buttons:** show (📁), rename (✏️) and remove (🗑️) sit to the left of the name, always shown (revised from hover-only after review). The folder button It shows the file in the system's file manager (Explorer selects it; elsewhere its folder opens). Its tooltip is the file name, and the layer for a GeoPackage, e.g. "county.gpkg, layer parcels" (D42). For a missing file it opens `in/`.
- **Type** comes from the extension: CSV, Parquet (`.parquet` and `.geoparquet` alike), GeoPackage, Shapefile.
- **Size** includes a shapefile's companions.
- **Geometry** is checked in the file itself, the way OpenAVMKit does it: the file has a column named `geometry` (`data._snoop_column_names`: the Parquet schema, or pyogrio's layer info). Only column names are read, never the data.
- **A missing file** has "—" for size and "Missing" (red) for geometry.
- Rename and Remove have the tooltips "Rename" and "Remove". The icons are Noto Color Emoji SVGs, like the tabs.

**Rename** edits the row in place:

```
                      [ cama_2026     ] [ Save ] [ Cancel ]   CSV   11 MB   No
```

- Enter saves and Esc cancels.
- It renames the `data.load` key only. The file keeps its name.
- The new name follows the suggested-name rules (lowercase letters, digits and underscores) and must not clash with another entry. A problem shows in red under the field, and Save stays disabled.
- Rule for later features: anything that refers to an entry by name (column mapping, joins) is updated by a rename.

**Remove** asks first:

```
  +-----------------------------------------------------+
  |  Remove cama from the project?                      |
  |                                                     |
  |  [ ] Also move cama.csv to the Recycle Bin          |
  |                                                     |
  |                          [ Cancel ]  [ Remove ]     |
  +-----------------------------------------------------+
```

- **Remove** deletes the `data.load` entry.
- The box is not ticked by default. Unticked, the file stays in `in/`. Ticked, it goes to the Recycle Bin (send2trash), with a shapefile's companions.
- For a missing file, there is no box.
- **Built:** if another entry uses the same file (e.g. two layers of one GeoPackage), the file is not sent to the Recycle Bin; the dialog says why and nothing is removed.
- A removed file left in `in/` can be added again later. Its add form shows "Already in the project folder" instead of the copy/move choice (F2).

#### F4 onwards: building the joins (intent; to be designed feature by feature)
A stage where the user builds the joins between their files in real time: inspect what is in each file and in the joined result as it grows, so they can make informed decisions about how to build it up. Everything it does maps to OpenAVMKit's own settings (`data.load` mappings, `dupes`, `data.process.merge`).

### 3.1 Home screen
- **Projects**: name and tax year.
- **New project** (§3.0 F1), and **Show in folder** and **Delete** on each project (F1b).
- *(The sample county is removed for now, D19.)*

### 3.2 The guided build
*Being redesigned feature by feature in §3.0. The text below is the earlier draft, kept for reference until each part is re-agreed.*

There is no up-front wizard. **New project** asks for a name and opens the project, and the project screen *is* the guide. The user works down one ordered list: five **setup stages**, which describe the data, then the six **steps** of §3.3, which run the engine. Each one is a single screen.

**Every stage and step has the same four parts:**
1. **Decide.** Choices are made against the user's real data: real column names, real distinct values with counts, previews. Every default is shown as a pre-filled choice with a one-line "why". Nothing is applied silently.
2. **Check.** Fast diagnostics before anything heavy: match rates, duplicates, what would be dropped and why. These run in the app service and read only the columns they need, so they take seconds even at 500k parcels. They never run the engine.
3. **Run.** Only steps run the engine. A setup stage just saves its decisions.
4. **Receipt.** What happened, in plain words: rows in and out, every drop with its reason, warnings. Each number opens the rows behind it. For runs, the receipt compares the engine's counts (upstream A14) with what Check predicted, and flags any difference.

A stage or step is done only when the user clicks **Looks right** on its receipt. **Back** always works, and every decision is saved as soon as it's made. Changing an earlier decision marks later stages out of date, with the reason (§6.4).

**Under the hood** is a collapsed panel on every stage and step, open to everyone. It shows the exact `settings.json` fragment this stage wrote and which engine stage it runs. Settings can also be exported whole, for notebook users.

#### Setup stages
1. **Basics.** Name, place, tax year, valuation date.
   - Oakbox derives the locality slug (no dashes inside the name), map centre and county FIPS.
   - It proposes **units** (imperial or metric) from the place, and the user confirms. Units decide every field name (`*_sqft` vs `*_sqm`).
   - **Valuation date.** Everything is valued as of this date; it also drives ages and time adjustment. *When checking an existing roll, it must match that roll's valuation date, or the comparison isn't like-for-like.*
2. **Your files.** The user adds any number of files, one at a time, in any format from §4.1. For each file Oakbox shows a preview of the rows, the column types and the row count, and the user says what it is:

   | Kind | Example | Becomes |
   |---|---|---|
   | **Parcel map** | Parcel polygons | The spine everything attaches to (`geo_parcels`) |
   | **One row per parcel** | Main CAMA table | Attached by ID |
   | **Several rows per parcel** | Buildings, land segments, improvement details | Collapsed to one row per parcel (Stitch) |
   | **Sales** | One or more sales files | The sales table; several files are stacked |
   | **Points** | Permits or addresses with latitude and longitude | Attached by position (`lat_long` merge) |
   | **Map layer** | Neighbourhoods, zoning, school districts | Attached by overlay (§3.12.1) |
   | **Not sure** | — | Oakbox suggests a kind from the columns and the ID check |

   - **ID column.** The user picks the parcel ID column, which is always read as **text** so leading zeros are kept. Oakbox checks uniqueness straight away: "12,431 rows but 11,902 IDs. Does this file have several rows per parcel?" A file can need several columns to identify a row (property + improvement + detail), and can belong to a parent file rather than to the parcel directly.
   - **Fixed-width text** (such as PACS appraisal exports) needs a layout: the user picks a known layout (Oakbox ships the PACS ones it has been tested on) or supplies one. A recognised export is added as a whole: Oakbox lists its files with sizes and a plain description, and preselects the ones modeling uses (for PACS: property, improvements, improvement details, land). Oakbox converts each file to Parquet in `in/`, keeping only the fields the user keeps (§4.1).
3. **Stitch.** How the files become one table of parcels and one table of sales. Oakbox drafts the plan and the user confirms each part:
   - **The spine.** The parcel map. Without a map (allowed only with a warning, D4), a one-row-per-parcel table.
   - **How each file attaches:** by ID, by position or by overlay; sales files stacked (`append`). A nested file rolls up through its parent: improvement details → improvements → parcel, collapsing at each level.
   - **Matching.** Each attachment shows its match rate both ways: "11,640 of 11,902 IDs match the map (97.8%). See the 262 that don't." When IDs nearly match, Oakbox suggests a fix and shows how many more would match: "IDs here have dashes and the map's don't. Remove dashes? +247 matches." Fixes are trim, remove characters, pad with zeros, change case and keep only part. They compile to `calc` on that file (§3.13), so Check and the engine apply the same rule.
   - **Rows without an ID** are dropped with a named reason, counted in the receipt.
   - **Several rows per parcel.** Per field: **sum**, **largest**, **smallest** or **first**, with sensible defaults (areas sum; year built takes the earliest; codes take the row with the largest area). This becomes that file's `dupes` setting.
     - In the parcel table itself, duplicates usually mean versions or owners (PACS: supplement number, one row per owner). Oakbox proposes "latest version, primary owner" and shows how many rows that removes.
     - In the parcel map, several polygons for one ID are merged into one shape.
   - **On the roll, not on the map.** Parcels without a polygon are listed by type, because some are expected: condo units that share a polygon (handled by condo rules, §3.5), and accounts newer than the map.
   - **Column clashes.** When two files have a column of the same name, the user picks which one wins (`reconcile`); the other is kept with the file's name as a suffix.
   - **Context data starting point:** **None (offline)**, **Recommended**, or **Custom**, which opens the Enrichment screen (§3.12). Nothing heavy runs without a cost estimate first.
   - **Preview:** the stitched parcel table, with each column's source file, and the parcels each file left blank.
4. **Columns.** Oakbox maps the stitched columns onto OpenAVMKit's data dictionary (163 standard fields): "We think `SQFT_LIV` is *Finished building area*. Correct?" The user only confirms uncertain matches. Check shows each standard field after its transform: blanks, range and examples.
   - **Transforms** fix columns that don't match as-is: unit conversion, code→number tables, date formats, combining columns (§3.13).
   - **Year built, not age.** Age is derived from the valuation date.
   - **Other columns** the user wants to keep are classified automatically as land/building/other × number/category/yes-no, shown for review. OpenAVMKit's fills and models ignore unclassified fields.
   - **Location fields** (neighbourhood, market area…) are marked as locations, so they can drive breakdowns, equity studies and estimation.
   - **Values to check.** "Which value(s) do you want to check against sales?" One or more **total value** columns, such as the current or last year's appraised value. Step 4 needs at least one. Land values are not checked in v1.
5. **Sales basics.** Decided before step 1, because OpenAVMKit applies them while loading.
   - **Required columns:** parcel ID, sale date and price.
   - **Sale ID:** OpenAVMKit needs a unique `key_sale`. If the file has none, Oakbox builds one from parcel ID + date (+ a counter).
   - **Date format** is detected and confirmed with examples ("We read `03/04/2023` as 4 March 2023. Correct?"). Unparseable dates are a blocking Data health problem.
   - **Validity:** the user ticks which office codes mean "valid", from the codes actually in the file, with counts. With no code column, all sales start valid.
   - **Vacant at sale:** which codes or rules mean "the land was vacant when sold". Default: same as the parcel's current vacancy.
   - Oakbox always produces `valid_sale` and `vacant_sale`; OpenAVMKit refuses to run without both.
   - **Check** starts the **sales funnel**: all sales → not matched to a parcel → invalid by office code → remaining. Step 3 completes it (§3.3).

After Sales basics, the project has one model group, "All properties", with a match-all rule. Real model groups are built in step 2 (§3.5).

**The sample county is a walkthrough.** It goes through the same stages and steps, with Petersburg's answers pre-filled and annotated ("Petersburg's sales file marks valid sales with code Q"). The user confirms each one. There is no "run everything" button in the app; CI's smoke test drives the same API end to end (D40).

### 3.3 Project screen: the steps
The setup stages are followed by the steps that run the engine. Each step follows the four parts of §3.2. Its Run has a progress bar, time remaining and **Stop**, and its receipt has **See results**.

Before running, a step shows what's stale and why ("Model groups changed: steps 3–5 will re-run"). Jobs resume after the app is closed where OpenAVMKit supports it (checkpoints, tuning journals).

| Step | What runs (OpenAVMKit stage boundaries) | Internet? |
|------|------------------------------------------|-----------|
| 1. Bring in data | Load, merge, condo handling, enrichment (§3.12). The street enrichment is explicitly off. Ends before model group tagging. Then Data health and Field profile (§3.9) | Only for online enrichments |
| 2. Define model groups | Model group tagging (§3.5). Writes the 1-assemble hand-off | No |
| 3. Check sales | Clean, in OpenAVMKit's order: default fills (§3.12.2), equity clusters, sale processing (validity rules, **time adjustment**, sales window), scrutiny in flag-only mode, overrides (§3.6), collapse of rare categories. Writes the 2-clean hand-off | No |
| 4. Check my values | Ratio, vertical-equity and horizontal-equity studies on the named value fields, per model group and overall (§4.2). Reads the 2-clean hand-off explicitly, never stale step-5 output | No |
| 5. Build model values | Splits, spatial lag, area stats, optional variable testing (§3.10), **Try** models (repeatable) → outlier review → **Finalize** → ratio study on model values. Main models only (`run_vacant=False`) | No |
| 6. Reports and export | PDF reports; Parquet, GeoPackage, Shapefile, CSV, Excel (§4) | No |

**What each step's receipt shows:**
- **Step 1:** rows read from each file; each attachment's match rate, against the Stitch prediction; rows collapsed by several-rows rules; sales removed as office-invalid. Then Data health and Field profile (§3.9).
- **Step 2:** parcels and sales per model group, split improved/vacant; parcels left unassigned.
- **Step 3:** the full **sales funnel**, continuing from Sales basics: outside the sales window → flagged by scrutiny → overridden (§3.6) → used. Plus the time adjustment found per model group, as a chart.
- **Step 4:** the study tables (§4.2), with the funnel's final count beside each.
- **Steps 5–6:** as §3.10 and §4.

**Results views:**
- a map coloured by ratio, value, model group or flag
- sortable tables
- charts
- "things to look at" lists: flagged sales, model outliers, sparse model groups

### 3.4 Plain-language rules
- **No jargon without an explainer.** "COD 14.2: your values are fairly uniform. The IAAO target is under 15."
- **Errors** say what happened, why, and what to click next. OpenAVMKit's fatal and warning messages, such as variable validation, are mapped to plain text. Stack traces go only to the log.
- **Large text and high contrast** are available. Nothing important is shown only by colour.

### 3.5 Model group builder
Model groups are parcels valued together, for example single-family, condos, commercial and agricultural. **Vacant land is not a model group of its own.** Vacant parcels stay in their model group and are valued by its main model. Vacant sales are flagged (`vacant_sale`), so reports can break results out by improved/vacant. The builder shows improved/vacant counts per model group.

**Layout:**
- **Left:** the ordered model group list, with colour, parcel count, and sale count split improved/vacant. "Unassigned" is always shown in grey.
- **Center:** a map coloured by model group. Clicking a parcel shows its attributes and *why* it landed in its model group ("matched rule 2 of Commercial"). A table toggle shows the same parcels as rows.
- **Right:** the rule editor for the selected model group.

**Ways to define a model group:**
1. **From a field.** Pick a field, such as land-use code. Oakbox lists the distinct values with counts, and the user assigns each value to a model group.
2. **Rule builder.** Conditions of the form *field / operator / value*, with AND/OR and nesting. It compiles to OpenAVMKit's filter lists.
   - On fields with blanks, it uses in-list/not-in-list, because `==`/`!=` silently send blank rows to Unassigned.
3. **Hand edits.** Lasso or click parcels on the map. These are saved as an explicit parcel list, and reports list them.

**Behavior:**
- **First match wins,** as in OpenAVMKit. Model groups can be dragged to reorder.
- **Unassigned parcels are not modeled.** OpenAVMKit labels them `UNKNOWN`. The health panel makes this loud.
- **Sales follow their parcel's model group.**
- **Live preview.** Each edit is re-evaluated against a cached parcel table, reproducing first-match-wins, common-area reassignment and the `UNKNOWN` fallback exactly. The target is under 2 seconds at 500k parcels.
- **Apply** writes the settings and warns that steps 3–5 will re-run, because fills, clusters, time adjustment, scrutiny and models are all per model group.
- **Health checks per model group:**
  - "Only 12 sales — too few to model reliably" (model warning under 15 sales)
  - "Too few sales for a vertical-equity test" (under 20)
  - "3,104 parcels unassigned"
  - "This rule matches nothing"
- **Advanced:** common areas.
  - Condo handling is *not* here. It runs at the start of step 1 and changes the row set, so it lives in the step 1 settings.
- **Undo/redo.** Definitions can be exported and imported, to reuse across years or share with a neighbouring jurisdiction.

### 3.6 Sales review and overrides
**Rule: a sale flagged invalid never touches the modeling pipeline.** The flag can come from the office code, a validity rule, scrutiny, a model outlier or the assessor. OpenAVMKit already removes such sales as it goes, and Oakbox keeps it that way.

Review happens **outside** the pipeline, in Oakbox's own **sales register**. The register is a separate record of every imported sale, with every verdict it received:
- office code (step 1)
- validity rules and scrutiny (step 3)
- model outlier (step 5)

Each verdict comes with reasons in plain words.

- **Final status:** **Valid** or **Invalid**, plus who decided.
- **Overrides:**
  - **Exclude** a valid sale. A note is optional. Excluding a model outlier requires a reason from a checklist (bad data, non-market, partial interest, …).
  - **Keep** a flagged sale. A note is required. The sale re-enters the pipeline only through a re-run, and only because it is no longer flagged invalid:
    - Office-code invalid → re-run from step 1. Oakbox rewrites that sale's `valid_sale` at load.
    - Scrutiny or rule → re-run from step 3, through a keep-list (upstream A6).
    - Excluding → re-run from step 3, through `invalid_key_file`.
  - Overrides survive re-runs and are written into files OpenAVMKit reads, so notebook users see the same result.
  - Before applying, Oakbox says which steps will re-run.
- **Rule templates** (Advanced). Relative rules such as "price under 50% of current value" compile to `invalid_sales` filters.
- **Views:** a map, a list, and filters ("only flagged", "only overridden", "by model group", "model outliers").
- **Reported.** Reports list every override, with its note.

### 3.7 Tax years
- **Storage.** A project is one jurisdiction × one tax year: `Documents\Oakbox\<Jurisdiction>\<Year>\`, which holds a standard OpenAVMKit locality.
- **Shared cache.** Downloaded enrichment data (`cache/`) is shared per jurisdiction, so a new year doesn't re-download gigabytes.
- **Start next year** copies settings, model groups, column mappings, transforms, standards profile and report templates. It can optionally copy overrides still inside the sales window.
  - It does *not* copy model outputs or tuned parameters, and offers a fresh tune.
  - The user then imports new files, and the setup stages only ask about what changed: new or missing files, columns and codes.
- **Read-only past years.** Past years are read-only by default. Each records its engine version and random seed, so results can be reproduced for an appeal.

### 3.8 Help
- **"?" on every screen** opens an offline help page for that screen.
- **Glossary pop-ups** wherever a technical term appears.
- **Error screens** link to the matching help page and to the Discord.
- **Later, opt-in AI helper:**
  - (a) a small local model over the help pages, fully offline.
  - (b) the user's own frontier-model API key. This is an explicit, disclosed exception to D12.

### 3.9 Data health and Field profile
Shown after step 1 and after any re-import.

**Data health** (integrity problems). Each problem gets one card: what's wrong, how many rows, an example, and what to do.

| Problem | Safe one-click fix | Otherwise |
|---------|--------------------|-----------|
| Duplicate parcel IDs | Combine per field (sum/largest/smallest/first, §3.2) | Export the list |
| Sales that match no parcel | Exclude them | Export the list |
| Sale dates that can't be read | — (blocking) | Fix the date format |
| Invalid or empty geometry | Repair / drop (dropped parcels listed) | Export the list |
| Parcels outside the jurisdiction | Drop | Show on map |
| Impossible values (negative area, year built 2099, $0 sale) | Treat as missing | Export the list |
| Wrong coordinate system | Reproject (with confirmation) | — |

**Field profile** (does the data mean what it says?). This reflects the QA the OpenAVMKit tutorial insists on before model groups are defined.
- **Per field:** % filled, % zero, distinct values, top values. Mostly-empty fields are flagged.
- **Cross-checks on code labels:**
  - "412 parcels coded LAND have a building area"
  - "88 single-family parcels have no building area"
- **The blank-building-area rule (default, stated plainly).** OpenAVMKit treats a blank finished area as **0, which makes the parcel vacant** and erases its building fields. Oakbox shows a card: "1,240 parcels have no finished area. **By default they're treated as vacant land.**" A map and list of them are shown.
  - The user accepts with no action needed.
  - **To opt out** (project setting): "Don't treat blank finished area as vacant". The user then names an explicit vacancy signal, such as a land-use code or a vacant flag. The remaining blanks become candidates for an estimate (§3.12.2) or a fix at source. This needs upstream A9.

Rules for both screens:
- **Blocking or warning.** Only blocking problems stop the next step.
- **No silent fixes.** Every fix is logged and listed in each report's "Data corrections" appendix.
- **Originals are kept.** Oakbox keeps the originally imported values, so exports can always return the office's own data.
- **Download problem list (Excel),** so the office can fix the source in its appraisal (CAMA) system.

### 3.10 Building model values (step 5)
**Variables.** At the start of step 5, the user picks a path. They can switch later.
- **Plow forward** (default). OpenAVMKit has no built-in default variable list, so Oakbox ships one, using whichever of these fields are mapped or enriched:
  - **The "big five":** building size (finished area), land size, building age (effective age if available, otherwise age), building quality, building condition.
  - **Location:** latitude, longitude, and neighbourhood characteristics. These are the neighbourhood or other location fields, plus their spatial-lag and area-statistic features from step 5.

  Missing ones are skipped with a note. Tree models such as LightGBM get this list plus any other well-covered fields.
- **Test variables first.** Oakbox runs variable analysis per model group on the candidate list and shows a review:
  - One row per variable with a plain verdict: *Drives value*, *Weak*, *Redundant with ___* or *Counter-intuitive*. Today `try_variables` only runs correlation and R²; the last two verdicts need VIF and coefficient-sign tests (upstream A5).
  - A **Details** expander shows the statistics, worded from the existing `variables.md`.
  - An include/exclude toggle per variable. Per the OpenAVMKit tutorial, the pruned list is applied to **linear** models only; tree models keep the broad list.

**Models.**
- **Picker.** Pick model(s), or **Choose for me**: LightGBM.
- **Small model groups.** Under 15 sales, "Choose for me" falls back to a simpler model (log-price linear regression or local-area) or suggests merging model groups.
- **Ensemble.** With several models, it's an explicit list that never includes the office's own value fields.
- **Speed tier.** **Quick** or **Thorough** (OpenAVMKit's default, 5-fold nested cross-validation), pre-selected by machine tier.
  - M0 found that 1-fold is *slower* than 5-fold at 150k+ parcels, so Quick must not be built on `cv_folds`. Quick will use fewer tuning trials and reuse saved tuning; to be measured in M1.
  - Parallel fold workers are capped by memory (`cv_max_workers`).

**Try, review, finalize.**
1. **Try** runs the chosen models and shows ratio statistics side by side. It's repeatable and cheap to re-run.
2. **Review outliers.** Model outliers appear in Sales review (§3.6) with likely causes.
3. **Finalize** commits the values and writes the model-value ratio study.
- **Re-tune.** Oakbox reuses saved tuning by default. A **Re-tune** toggle discards it, and is suggested after big data or model group changes. Cancelling never deletes tuning journals, so a cancelled tune can resume.

**Total value only.** Oakbox runs main models only (`run_vacant=False` on try and finalize). There is no vacant-stage run, and no land values are shown, reported or exported. A separate land-value tool is planned.

### 3.11 Online features and the map background
**Map background:**
- Offline, maps show parcels only.
- Online, the user can turn on a street background built from OpenStreetMap data.
  - **Default provider:** a free, no-key service intended for third-party apps, such as OpenFreeMap. The tile URL lives in config, so the provider can change without a software update.
  - **Fallback:** OSMF's own `tile.openstreetmap.org`. Its [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) allows it, but it has no service guarantee and may block heavy use without notice. If used, Oakbox must send an identifying User-Agent, show attribution, and not prefetch or cache tiles for offline use.
- The user's own aerial imagery (GeoTIFF/MBTiles) comes later.

**Online notices.**
- **Shown once, calmly, never recurring.** The notice appears the first time any online feature is switched on, and lists each service and what it receives. For example: "To draw the street map, Oakbox asks OpenFreeMap for map pictures of the area you're viewing, like any web map does. Your parcel data never leaves this computer."
- **Services covered:**
  - the map tile service
  - Overture
  - Census
  - OpenStreetMap Overpass
  - USGS
  - Azure, for the sample
  - GitHub, for updates
- **Settings → Online features** lists every service and lets the user switch each one off.

### 3.12 Enrichment
Enrichment adds context the office's data lacks. Some of it is cheap and local; some downloads gigabytes and runs for hours on a large county. The screen treats it as a set of configurable jobs, not checkboxes.

**Screen layout:**
- **One card per enrichment,** showing:
  - what it adds
  - its settings (common ones visible, the rest under **Advanced**)
  - what it sends online
  - a cost estimate
  - its cache state
  - after running, a results summary
- **Map preview** of the selected card: downloaded features, or the new column coloured on parcels.
- **Run all**, **Run selected**, or **Try on a small area** per card.

**Cost estimate before every run:**
- **Inputs:** parcel count, bounding-box area, the enrichment's own drivers, and this machine's tier (§5).
- **Shown as:** download size, time range and peak memory, as a green, amber or red light.
- **On red:** the cheapest fix is named: "Lower elevation detail to 30 m: about 9× less data", "Cap distance to 2 km".
- **Coefficients** come from the M0 benchmarks.

**Try on a small area.** The user draws a box or picks a neighbourhood. Oakbox runs the enrichment on just those parcels, with the same settings, into a scratch cache, never the project.

**Caching is visible.** Each card says "Up to date", "Will reuse downloaded data" or "Settings changed: will re-download ~1.2 GB". **Clear cache** is per card. Oakbox clears OpenAVMKit's enrichment cache automatically when columns change; otherwise OpenAVMKit stops with an error.

**Results summary.**
- **Coverage:** % of parcels that got a value.
- **New columns,** with a histogram and a map layer.
- **Plain warnings,** such as "No buildings found in 312 parcels — mostly vacant land, as expected".
- New columns become available everywhere downstream.

**Failure handling.** A failed online enrichment never fails step 1. The card turns amber with the reason and offers **Retry** or **Skip**. Skipped enrichments are listed in the report methodology.

**Oakbox writes every enrichment explicitly.**
- Each enrichment block and each distance feature needs `enabled: true`. OpenAVMKit's per-feature default is *off*, which contradicts its docs.
- The Census API key is written to the engine's environment. It is not a settings value, and OpenAVMKit's `.env` lookup fails outside notebooks.

#### 3.12.1 The enrichments
Run order inside step 1:
1. map layers
2. footprints
3. basic geometry
4. census
5. distances
6. elevation
7. permits
8. **estimation**
9. lookup tables, formulas and per-parcel corrections
10. the vacancy rule

| Enrichment | User decisions (Advanced in italics) | Online: what is sent | Main cost driver | Adds |
|---|---|---|---|---|
| **Map layers** (spatial join, key `geometry`) | Which layers; which fields. Match rule is "parcel centre inside" (the only one OpenAVMKit has; "overlaps" is upstream B3) | Nothing | Parcels × layer complexity | `neighborhood`, `zoning`, … for model groups, breakdowns, equity |
| **Basic geometry** | Always on; lat/lon locked on. *Shape and polar toggles* | Nothing | Shape metrics per parcel | Lat/lon, GIS area, shape regularity. Lat/lon is required by distances, spatial lag and modeling |
| **Building footprints** (Overture) | On/off; *units* | Bounding box, to Overture's public S3 | Downloaded area; parcel × building intersection | Footprint area, height, stories |
| **Census** (ACS 5-year) | Year; county FIPS (from the place); API key (guided signup); variables from a plain-language list, defaulting to the current four. *Block group or tract; any ACS variable by code* | State and county codes and variable codes, to the Census API and TIGERweb | Small | Chosen variables; tract and block-group IDs (usable as locations) |
| **Distances** | **Defaults:** OpenAVMKit's feature set (water bodies, rivers, water, rail, airport, schools, parks, golf, coastline), written out explicitly. **Custom:** the user's own GIS layers (downtown, landfill, highway…) or *a custom OSM tag query*. Per feature: *max distance, unit, minimum size (default 10,000 m²), nearest-N named* | Bounding box, to OSM Overpass. Own layers: nothing | Features × parcels. **Max distance is the main speed lever** | `dist_to_*`, `within_*`, `proximity_to_*` |
| **Elevation** (USGS 3DEP) | 10 m, 30 m or 60 m; Oakbox recommends one by area | Bounding box, to USGS | Area ÷ resolution² | Mean elevation, variation, slope |
| **Permits** | Permit file(s); a **"classify permit types"** step mapping the office's permit codes to teardown / renovation / major-minor (OpenAVMKit needs `is_teardown`, `is_renovation`, `renovation_num`). *Effective age; teardown window* | Nothing | Small | Renovation/teardown flags, effective year built |
| **Estimate missing values** (`enrich.infer`) | Field; **which parcels** (required for building fields: see below); predictors; location field. *Substitute fields to copy first; method ("Choose for me" = LightGBM, ratio, random forest, XGBoost, ensemble); rounding* | Nothing | Parcels × predictors, per field | Estimated field plus an `inferred_*` flag |
| **Street frontage** | Deferred; too heavy and has open bugs (§7 C4) | — | — | — |

#### 3.12.2 Two different ways of filling blanks
OpenAVMKit has two separate features, and Oakbox keeps them apart, with different names, screens and labels.

| | **Estimate missing values** (`enrich.infer`) | **Default fills** (`data.process.fill`) |
|---|---|---|
| What it does | Predicts a value from similar nearby parcels with a model | Puts in a stand-in: model group median/mean/mode, zero, min/max, "UNKNOWN", or a fixed value. *Can be limited to improved or vacant parcels* |
| When | Step 1, after the other enrichments but **before** lookup tables, formulas and the vacancy rule | Step 3 (clean), per model group |
| Screen | Its card on the Enrichment screen | **"Fill blanks"** panel in step 3 |
| Typical use | Important characteristics with sizable gaps | Making every model input complete. Linear models crash on any blank; tree models tolerate them |
| Cost | Model training per field | Negligible |
| Label in UI | **"Estimate"** | **"Default"** |

**Shared rules.** Both are offered to everyone and always explained. The card or panel and a first-use dialog say, in plain words:

> "This fills gaps so the model can run. A filled value is an **educated guess** (Estimate) or a **simple stand-in** (Default). It is **not a fact** about the property. It is used **for modeling only** and is never written back to your records."

- **Always marked.** Filled values have a distinct style and label in tables and pop-ups. Estimates carry `inferred_*`. Default fills need a new flag (upstream A9).
- **Never exported as data.** Exports return the office's original value from Oakbox's kept copy (§3.9). Optional, clearly named "estimated"/"default" columns can go alongside.
- **Reported.** Reports state how many values of each field were filled, and how.

**Specific to Estimate missing values:**
- **Building fields need a "which parcels" filter.** Without one, OpenAVMKit estimates every blank, including true vacant land. The vacancy rule then marks those parcels improved. Oakbox pre-fills the filter from the Field profile answer (§3.9).
- **Predictors** can't use lookup-table or formula outputs, because those run later.
- **Preview before committing:** how many values are missing, and a validation score from OpenAVMKit's experiment mode, e.g. "guesses are typically within ±18% of the real value".

**Specific to Default fills:**
- **Suggested automatically.** Before step 5, Oakbox lists every model input that still has blanks and proposes a fill (median for numbers, "UNKNOWN" for categories).
  - Accepting means re-running step 3, since fills live in clean.
  - Partial-coverage enrichment fields, such as census and elevation, are the usual cases.
- **Automatic steps are shown.** OpenAVMKit's automatic tidy-ups (year-built/age reconciliation, categorical "UNKNOWN") appear as read-only rules.
- **Blank finished area is not handled here.** It is already 0 (vacant) after step 1, so it's decided in the Field profile instead.

#### 3.12.3 Modeling-time context (step 5)
**Spatial lag** (nearby sale prices and characteristics) and **area statistics** (neighbourhood means and medians) run in step 5. They depend on model groups and train/test splits.
- **Defaults:**
  - Spatial lag: each model group samples from itself. OpenAVMKit requires this entry per model group, and Oakbox always writes it.
  - Area stats: the chosen location fields × price and size medians.
- **Advanced:** locations, fields, statistics, minimum count, cross-group sampling.

### 3.13 Transforms and corrections (`calc` / `tweak`)
Real extracts rarely match OpenAVMKit's fields as-is. There's no free-form editor in v1.
- **Transforms in Match columns.** These are typed, previewed on real rows, and compiled to `calc`:
  - **Unit converter** (acres → sq ft, …)
  - **Code → number table** (grade "B+" → 7), with an editable map and a list of unmapped values
  - **Date format**
  - **Combine columns into an ID**
  - **Trim / strip leading zeros**
- **Where they go.** Transforms referencing only the source file go into `data.load.<file>.calc`. Ones that reference enriched fields go into `data.process.enrich.calc`. Scratch columns are removed with `drop_fields`.
- **Advanced → Formula builder.** An operator picker over OpenAVMKit's calc reference, with a row preview. Safe defaults: divide-by-zero gives blank, empty → fill.
- **"Correct this parcel's value"** in the parcel pop-up. Stored as `tweak`, and listed in the Data corrections appendix.

## 4. Inputs, outputs and reports

### 4.1 Import and export
- **Import:** Shapefile (loose or zipped), GeoPackage, GeoJSON, Parquet/GeoParquet, CSV, Excel, and fixed-width text with a layout. Oakbox ships layouts for the PACS appraisal export versions it has been tested on (Travis CAD first); other layouts can be supplied as a simple field/start/width table. Zipped exports are opened in place, without unpacking by hand. Large exports are read straight from the zip as a stream, never unpacked to disk: the Travis CAD export is 0.5 GB zipped and 17.8 GB unpacked. Quick checks read only the columns they need (Travis: IDs from the 4.9 GB property file in 20 s). Oakbox stores everything as GeoParquet in the project's `in/` folder; OpenAVMKit itself only reads CSV/Parquet. The parcel layer is loaded as OpenAVMKit's `geo_parcels`.
- **Export:** per-parcel values, flags and ratios as Parquet/GeoParquet, GeoPackage, Shapefile, CSV and Excel.
  - **Default format:** GeoPackage for GIS users, CSV for everyone else.
  - **Shapefile limits:** field names are cut to 10 characters, and files are capped at 2 GB. Oakbox warns and writes a field-name key.
  - **Excel limit:** about 1,048,576 rows. Larger exports are split across sheets, or CSV is suggested.

### 4.2 Ratio study report and standards profiles
**What exists upstream today:**
- Field-agnostic study functions: `run_ratio_study`, `run_vertical_equity_study`, `run_horizontal_equity_study`, already used on assessor values without modeling in the `assessment_quality` notebook. They display results but write nothing, take one model group per call, and have no breakdowns.
- A ratio-study **report** that reads only a finalized model, with the checked value hard-coded to `assr_market_value`. It shows count, median ratio, COD with a bootstrap CI, and trimmed COD.
- **Bootstrap confidence intervals.**
- PRD computed with a CI, but not printed.
- **PRB** and **VEI** in the vertical-equity study.
- Breakdowns by any field (`analysis.ratio_study.breakdowns`).
- A sales-chasing check (assessor vs model).
- openratiostudy.com exports. These are model-only today: key, sale key, prediction, sale price, time-adjusted price, lat/lon, locations.
- Since 0.7.0, the formal ratio study scores **raw** sale price, not time-adjusted.

**Oakbox needs (mostly upstream A3–A4):**
- **One report path for any value field,** with or without a model. Per model group, overall, by breakdown, written to disk.
- **IAAO statistics in the report:** median ratio, COD, PRD, PRB, with CIs and sale counts. Also VEI (exists) and MKI (new), so the report survives the IAAO draft revision.
- **Pass/fail badges against a standards profile.** A small file with targets per statistic and property class, trimming, minimum sample size and windows. It ships with an IAAO default; state profiles come later; users copy and edit in a form.
  - The minimum sample size must match OpenAVMKit's pooling of cells with 15 or fewer sales.
- **An exact ratio-study window** (date bounds, post-valuation sales excluded). Today the cut is by calendar year with no upper bound.
- **Charts:** ratio vs sale price, ratio distribution, and a map of ratios by location.
- **A first page a board member can read:** "Residential values meet IAAO uniformity standards (COD 11.8, target ≤15) but show mild regressivity (PRD 1.04, target ≤1.03)."
- **Appendices:** data corrections, sale overrides, filled values, excluded variables, skipped enrichments, methodology.
- **openratiostudy export** that also carries the checked value field and model group.

**openratiostudy.com is the reference.** Its source is `larsiusprime/openratiostudy` (a static single-page app). It defines what the assessor sees, and Oakbox matches it:
- **Statistics** (per its `spec.md`):
  - median ratio with a **90%** bootstrap CI (10,000 resamples, seeded)
  - COD
  - PRD (mean ratio ÷ sale-weighted mean)
  - PRB (OLS of ratio on ln(sale price), HC3 robust standard errors, slope and p-value)
  - **VEI** and **VEI significance**, from market-value-proxy strata (2/4/10 strata by sample size, none under 10), with per-stratum median and CI
- **Views:**
  - results table with exclusion notes
  - VEI strata box plot
  - ratio map (lat/lon)
  - **neighbourhood price-level stats**: deciles of region price level vs median ratio, which separates real vertical inequity from invalid-sale artifacts
  - a **black-and-white print mode**, which Oakbox adopts for offices that print in greyscale
- **Parity tests.** Its test suite uses **Table 1 of the IAAO Ratio Studies Exposure Draft** (Sept 2025; 54 observations) as a fixture. OpenAVMKit's study functions must reproduce openratiostudy's results on the same fixtures, within tolerance. This runs in Oakbox's CI. Any definition mismatch is fixed upstream (A4), for example VEI strata rules or the CI level. OpenAVMKit's report uses 95% CIs; the standards profile sets the level, defaulting to 90% to match.

### 4.3 Reports and customization
- **Standard PDF reports:**
  - ratio study
  - equity studies
  - sales scrutiny
  - variables
  - model summary
- **Rendering:** Typst, replacing wkhtmltopdf, which OpenAVMKit still uses. Typst is open source, and its Python wheel needs no system install.
- **For everyone:** pick sections, filter by location or class, add a logo and header text, choose a standards profile. Saved as a per-project report preset.
- **For power users and consultants:** the reports are plain Typst template files. **Open template folder** copies them into the project. Edited templates are validated, with a fallback to the stock template on error. Jurisdiction packs ship as template sets.

## 5. Hardware targets
**Provisional, from M0 benchmarks** ([`docs/m0/REPORT.md`](docs/m0/REPORT.md)). These came from synthetic data with about 10 fields per parcel, on 4 cores. Real extracts and a real low-end PC still need to confirm them.

| Tier | Machine | Model step setting | Parcels (target) |
|------|---------|--------------------|------------------|
| Below floor | 4 GB RAM | 1 fold worker | Samples and jurisdictions under 25k; warns |
| Floor | Win10 x64, 4 cores, 8 GB RAM, 25 GB free disk | 1 fold worker (`cv_max_workers=1`) | up to ~150k |
| Recommended | 4+ cores, 16 GB RAM, SSD | 2 fold workers | up to ~500k |
| Large | 8+ cores, 32 GB RAM, SSD | `cores − 2` workers | 500k+, or real data with many columns |

**Measured** at 500k parcels, Thorough model step: about 36 min end to end, 9.2 GB peak memory, 3.9 GB of project outputs.

- **Memory has a fixed base.** About 0.7 GB per process (the OpenAVMKit import), plus about 0.7 GB per cross-validation fold worker. The data-proportional part grows with column count, so real extracts will raise it.
- **Plain warning, never a block.** "This county has 520,000 parcels. This computer has 8 GB of memory; we recommend 16 GB. Steps may be very slow or fail." The user can continue.
- **Automatic scaling.** Oakbox reads RAM, cores and disk, then sets fold workers and enrichment defaults to fit.
- **Disk per project.** Outputs are roughly 100× the input size (3.9 GB for 500k). Oakbox prunes intermediate outputs after each step, and the disk check counts the project's expected size.
- **Why this floor:**
  - Windows 10 is still about 26% of Windows PCs ([StatCounter via Yahoo, May 2026](https://tech.yahoo.com/computing/articles/microsoft-giving-windows-10-users-180152418.html)), with paid security updates to Oct 2027.
  - About 10% of machines have 8 GB RAM ([PassMark](https://www.memorybenchmark.net/amount-of-ram-installed.html)), and office PCs skew lower.

## 6. Architecture

```
┌──────────── Oakbox (per-user install) ─────────────────┐
│ UI: TypeScript web UI in a native window (pywebview →  │
│     Edge WebView2; falls back to the default browser)  │
│        │  localhost HTTP + server-sent progress events │
│ App service (Python): projects, guide, import, checks, │
│     health, sales register, model group preview,       │
│     staleness, map tiles, reports, updates             │
│        │  spawn / cancel                               │
│ Engine worker (separate process): OpenAVMKit stage     │
│     runner, one per job; streams progress events       │
└────────────────────────────────────────────────────────┘
  Bundled: standalone CPython 3.11 + hash-locked wheels (uv)
```

- **Python backend, TypeScript frontend** (§6.5). WebView2 ships with Windows 10 through Windows Update; on Linux the window is WebKitGTK or a browser app window (§6.1).
- **The engine runs in a worker process.** OpenAVMKit changes the working folder, uses relative paths, and can crash or run out of memory. The worker is given an explicit project directory and environment (API keys).
- **Large maps.** The app service builds vector tiles on the fly from GeoParquet, so the browser never loads 500k polygons.
- **Packaging:**
  - a standalone CPython build plus pre-installed wheels, with no freezing (PyInstaller struggles with GDAL, PROJ and numba)
  - **Windows:** a per-user Inno Setup installer into `%LOCALAPPDATA%\Oakbox`, with no admin rights, plus a portable `.zip` fallback. Measured in M0: 1.7 GB installed, 544 MB zipped; roughly 350 MB after upstream A13
  - **Linux:** a portable `.tar.gz`. Its launcher installs per user into `~/.local/share/oakbox` and adds a desktop-menu entry (`.desktop` file), with no root. An AppImage may follow. Measured in M0: 2.5 GB installed, 974 MB compressed. 469 MB of that is NVIDIA's NCCL library, which XGBoost's Linux wheel pulls in and a CPU-only app never needs (upstream A13)
  - **Both bundles are built on Linux** from one script (`packaging/build_bundle.sh`) and one lockfile. CI smoke-tests each on a clean machine of its platform
- **Projects** are ordinary folders: an OpenAVMKit locality plus `oakbox.json`. Easy to copy, zip and back up.
- **Reproducibility.** Each project records the Oakbox and OpenAVMKit versions and the seed. Versions install side by side.
- **Updates.** **Check for updates** reads GitHub Releases, sending only a plain version request. The user approves each install, and the old version is kept.
- **Privacy.** No telemetry and no crash upload. **Send log to support** builds a zip the user emails themselves.

### 6.1 Cross-platform: Linux now, macOS possible
**Linux (supported).** It's the development environment as well as a target. Many contributors and most CI already run on it, and the engine runs there unchanged.
- **Window:** pywebview's Linux backends need system libraries (WebKitGTK through PyGObject, or Qt WebEngine). These can't be relied on across distributions. So on Linux, Oakbox:
  - uses a native window when WebKitGTK is present;
  - otherwise opens the UI in the user's browser, in Chromium/Chrome "app" mode (a chromeless window) when one is installed, else in a normal tab.

  The UI is identical either way.
- **Baseline:** glibc 2.28+ (the `manylinux_2_28` wheels), x86_64. ARM64 Linux is later; its wheels mostly exist.
- **Shipped as** a per-user `.tar.gz`. It needs no root, Python or package manager (§6). There are no distro packages (.deb/.rpm) in v1.
- **Tested in CI:** an empty-environment smoke test on `ubuntu-latest` (passes in M0), plus the full test suite.
- **Platform differences** are kept small:
  - default project folder: `~/Documents/Oakbox` or `XDG_DOCUMENTS_DIR`
  - hardware probe from `/proc`
  - `LOKY_MAX_CPU_COUNT` set the same way on every platform

**macOS (later).**
- **The stack already runs on macOS:** pywebview uses WKWebView, the scientific wheels exist for Apple Silicon, and standalone CPython builds exist.
- **OS-specific code stays contained** in one `platform/` module (Windows, Linux, later macOS). `pathlib` is used everywhere.
- **CI smoke-tests a macOS build** from M1.
- **Deferred macOS costs:**
  - Apple signing and notarization
  - bundling `libomp` for LightGBM/XGBoost
  - a `.dmg` package

### 6.2 Licensing
- **Oakbox code: MIT.** It is permissive, AGPL-compatible, and familiar to government IT.
- **The engine stays dual-licensed.** OpenAVMKit, including `openavmkit-oakbox`, remains AGPL-3.0 or commercial. Contributions there go through its CLA.
- **The installer is AGPL-governed** because it contains OpenAVMKit. The About screen and installer link to the exact OpenAVMKit source commit, and a `THIRD-PARTY-LICENSES` file lists every bundled package.
- **CI licence check** fails the build on a non-free or AGPL-incompatible dependency.

### 6.3 Engine facts that shape the design
These were verified in the OpenAVMKit code at `f35b089`. Where the docs differ, the code wins.

| Fact | Consequence for Oakbox |
|---|---|
| `valid_sale` **and** `vacant_sale` are required; `key_sale` and `data.process.merge` are required | Sales basics always produces them (§3.2) |
| Without a `dupes` setting, a geometry file is de-duplicated on an *arbitrary* column; the column order comes from a `set` and varies between runs. In M0 this silently dropped up to 99.8% of parcels | Oakbox always writes `dupes` explicitly (`subset: [key]`). Upstream A11 |
| Importing OpenAVMKit pulls in IPython and costs about 0.7 GB per process; the first Windows import takes about 17 s | The engine worker starts once and shows a splash screen. Upstream A1 |
| Office-invalid sales are deleted at the end of the load and merge step; scrutiny drops outliers by default | Kept as-is: invalid sales never touch modeling. Oakbox reviews them in its own register outside the pipeline (§3.6) |
| Model groups are tagged at the end of assemble, and sales take their parcel's model group | Step 1 stops before tagging; step 2 tags. Unmatched parcels become `UNKNOWN` and are not modeled |
| Fills, equity clusters, time adjustment and scrutiny are per model group | Any model group change re-runs steps 3–5 |
| Blank finished area → 0 → vacant, with building fields erased, in step 1 | Kept as the stated default with an opt-out (§3.9); building-field estimates need a filter |
| Estimation runs before lookup tables, formulas and the vacancy rule | Those outputs can't be predictors |
| The only spatial-join rule is "centroid inside" | No "overlaps" in v1 (upstream B3) |
| Enrichments and each distance feature default to **off** | Oakbox writes `enabled: true` explicitly |
| Census key comes from the environment; `.env` isn't found outside notebooks | The worker sets the environment |
| Checkpoints only check that the file exists | Oakbox owns staleness (§6.4) |
| The ratio-study report needs a finalized model and hard-codes `assr_market_value`; the field-agnostic study functions exist but don't persist | Step 4 needs upstream A3 |
| `try_variables` needs an explicit candidate list and runs only correlation and R² | Oakbox supplies candidates; verdicts need A5 |
| Models need explicit `ind_vars`; there's no default run list | Oakbox ships per-model-group defaults (§3.10) |
| `cloud_sync` syncs both ways | The sample is fetched download-only |
| The streets enrichment is always called in notebook 1 | Explicitly disabled |
| Since 0.7.0: nested CV by default, raw-price ratio study, `benchmark` renamed `model_runner` (shim removed in 0.8) | Benchmarks and the headless API target 0.7+ behaviour |

### 6.4 Staleness and re-runs
Oakbox keeps a hash of the decisions, settings and inputs that feed each stage and step. When one changes, every later step is marked stale, and its OpenAVMKit checkpoints are deleted before the re-run.

| Change | Re-runs from |
|---|---|
| Files, stitch plan, ID fixes, column mapping, transforms, sales basics, condo rules, enrichment settings, keeping an office-invalid sale | Step 1. Unchanged enrichments reuse their cache |
| Model groups | Step 2 |
| Fills, validity rules, time adjustment, sales windows, scrutiny settings, excluding a sale | Step 3 |
| Value fields to check, standards profile | Step 4 only |
| Variables, models, speed tier, model-outlier exclusions | Step 5 (tuning reused unless Re-tune) |
| Report presets, export formats | Step 6 only |

Step 4 depends on steps 2–3 but not on step 5, so checking values never waits for modeling.

### 6.5 Frontend and build stack
**Priorities:** great UI, a stable codebase, good performance. Most code will be AI-written, so a type checker that catches mistakes matters more than developer convenience.

**UI library: React 19,** client-side only (an SPA), with the React Compiler enabled. Decided after comparing it with Preact, Lit, plain Web Components, Solid, Svelte and htmx.
- **Why React:**
  - **Accessible complex widgets.** **React Aria Components** (Adobe, Apache-2.0) covers the widgets that make up most of Oakbox's UI, with best-in-class accessibility:
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
  - Coarser re-rendering, mitigated by the React Compiler's automatic memoisation. Heavy work isn't in React anyway: MapLibre draws maps, tables are virtualised, and Python does the number-crunching.
- **Guardrails** against React's usual problems:
  - **No framework.** No Next.js, no server components, no SSR: Vite builds a static SPA.
  - **Lint rules** enforce the rules of hooks and effect dependencies.
  - **Few effects.** Prefer derived state and event handlers over `useEffect`.
  - **Data:** server state lives in a typed query layer (TanStack Query over the generated API client). UI state uses plain React state/context, and a small store library only if one proves necessary.
  - **No component kit** beyond React Aria. Styling is our own.
- **Other UI pieces:**
  - MapLibre GL JS for maps, used directly through a thin component wrapper
  - TanStack Virtual for large tables
  - Observable Plot or uPlot for charts

**Build stack** (all dev-time only; nothing here ships to users, who get static files):

| Piece | Choice | Why | Not chosen |
|---|---|---|---|
| Type checker | `tsc --noEmit`, `strict` + `noUncheckedIndexedAccess` | The only full TypeScript checker. Bundlers *strip* types without checking them, so this runs separately in the editor, a pre-commit hook and CI | — |
| Dev server and bundler | **Vite** (React plugin) | Hot reload in a normal browser while the Python backend runs. Proxies API calls to the backend with one line of config. Production build is a static bundle. Uses esbuild internally, so it's fast | *esbuild alone:* no hot reload or dev proxy. *Webpack:* slow and config-heavy. *Next.js / Turbopack:* server-oriented, not needed for a local SPA |
| Backend API → TS types | **FastAPI** (pydantic) → OpenAPI → **`openapi-typescript`** + **`openapi-fetch`** | FastAPI emits OpenAPI from the same pydantic models the backend validates with. The generated types and a ~6 KB typed client mean a backend change that breaks the UI fails `tsc` | Hand-written client types, which drift |
| Lint + format | **Biome** for formatting and general lint, plus **ESLint** limited to `eslint-plugin-react-hooks` and the React Compiler rules | Biome is fast with few dependencies. The hooks rules are React's main bug guard and only ship as ESLint plugins | Full ESLint + Prettier stack: more packages for little gain |
| Unit tests | **Vitest** | Shares Vite's config and TS handling | Jest, which needs separate TS setup |
| End-to-end tests | **Playwright** (Chromium already in the build environment) | Drives the real UI against the real backend | — |
| Packages | **npm** with a committed lockfile, `npm ci` in CI; Node LTS, dev only | Ships with Node, one less tool | pnpm (fine too; not worth the extra tool yet) |
| Python side | **uv**, **ruff**, **pyright** (strict on Oakbox code) | Same "type checker first" rule for the backend | mypy (slower; pyright matches the editor) |

**Styling and strings:**
- plain CSS with design tokens (custom properties) for large-text and high-contrast modes
- a typed string table (D13), so a missing translation key is a type error

## 7. Engine: OpenAVMKit changes

**Where the work lives.** The branch [`openavmkit-oakbox`](https://github.com/larsiusprime/oakbox/tree/openavmkit-oakbox) in the Oakbox repo carries OpenAVMKit's full history from `master` (`f35b089`, after v0.7.0). Our changes go on top as ordinary commits.

**How Oakbox uses it.** As a dependency pinned to one commit in the `uv` lockfile, e.g. `openavmkit @ git+https://github.com/larsiusprime/oakbox@<commit>`. There are no submodules and no runtime patches.

**Moving it later** means changing one dependency URL:
1. push the branch to OpenAVMKit as `oakbox` and merge it by PR;
2. then pin the released version.

### A. Needed for M1 ("Check my values")
1. **Headless stage API:** `run_stage(project_dir, stage, on_progress, cancel)`. No `os.chdir`, no IPython (including in `try_variables`). The environment is passed in. `ipython`, `pytest` and `pipreqs` leave the runtime dependencies.
2. **Structured progress events** replace `print`; warnings go through the same channel.
3. **Value-field studies that persist.** Ratio, vertical and horizontal studies on any named field, for all model groups plus overall, with breakdowns, written to disk, with no model required. Remove the hard-coded `assr_market_value`.
4. **Report statistics** (parity with openratiostudy, §4.2).
   - Print PRD, PRB and VEI in the report; add MKI.
   - Standards profiles with pass/fail.
   - An exact ratio-study date window.
   - Honour the bootstrap `iterations` argument (it's ignored today, and fixed at 10,000).
   - Fix the trimmed table showing the untrimmed median.
   - **VEI definition mismatch with openratiostudy.** OpenAVMKit's market-value proxy is `0.5 × sale + value ÷ median ratio`; openratiostudy's spec uses `0.5 × sale + 0.5 × (value ÷ median ratio)`. OpenAVMKit also needs 20 sales for VEI, where openratiostudy needs 10 (2 strata for 10–50). Agree on one definition and test both against the IAAO exposure-draft fixture.
5. **Typst report rendering** replaces wkhtmltopdf.
6. **Scrutiny outputs for review:**
   - write every flagged or dropped sale, with its reason, to a machine-readable file;
   - a **keep-list** that exempts named sales from scrutiny drops;
   - drop behaviour as a setting, not a function argument.

   Flagged sales still never reach modeling.
7. **Settings schema and validation** with field-level, plain-language errors.
8. **Settings-hashed checkpoints,** or at least a documented stage-to-settings map.
9. **Provenance flags** for default fills, and for the step 1 rule that turns blank finished area into 0. Also a setting to **opt out** of that rule, with vacancy taken from an explicit field instead.
10. **Tagged releases.** The version already comes from tags, but Oakbox must pin tagged commits.
11. **Safe `dupes` default** for geometry files: de-duplicate on `key`, or raise an error. Never use an arbitrary column.
12. **Performance hotspots from M0:**
    - the horizontal-equity study (473 s at 500k)
    - equity clusters plus scrutiny (about 220 s at 500k)
    - `finalize_models` when `cv_folds=1` (1,395 s at 500k)
13. **Leaner runtime dependencies.** Drop IPython from module-level imports. Make CatBoost and XGBoost optional extras; XGBoost's Linux wheel also pulls in NCCL (469 MB). Together these cut the Windows download from 544 MB to roughly 350 MB, and the Linux download by more.
14. **Stage receipts.** Each stage reports structured counts through the progress channel (A2): rows in and out per file and per merge, rows collapsed by `dupes`, and sales removed with the reason (office code, outside window, scrutiny rule, override). Today these are only printed, if at all. Oakbox's receipts and the sales funnel depend on it.

### B. Needed for M2 (enrichment, model groups, sales)
1. **Enrichment plumbing:** progress per enrichment, a cost-estimate helper, and running an enrichment on a subset of parcels.
2. **Per-enrichment cache signatures.** Today the Overture signature covers the whole `enrich` block, and the estimation cache has no settings signature.
3. **"Overlaps" / area-weighted** spatial-join rule.
4. **Census:** configurable variables and geography; key via parameter; multi-county FIPS.
5. *(Dropped: invalid sales must never enter the pipeline. Oakbox handles office-code keeps by rewriting `valid_sale` at load.)*
6. **Explain model group assignment:** which model group and which rule matched a parcel.
7. **Data health checks** as a library function returning structured problems.
8. **Machine-readable model outliers** for the sales register.
9. **Vectorise the Overture parcel × building intersection.**
10. **GIS and Excel loaders** in OpenAVMKit itself. GeoPackage and shapefile: **done** on topic branch `engine/gis-loaders` (also case-insensitive extensions and a GeoPackage `layer` option), merged into `openavmkit-oakbox`. Still to do: GeoJSON, zipped shapefile, FileGDB, Excel, and a fixed-width loader for PACS exports.

### C. Needed for M3 (model values) and later
1. **Headless `try_variables`** with a configurable test list (VIF, p-value, coefficient sign).
2. **Default per-group model configuration** and a "choose for me" policy with a small-sample fallback.
3. **Ensemble exclusion** of pass-through value fields.
4. **Streets fixes** before it's offered:
   - the hard-coded `frontage_ft_1` breaks metric localities
   - a KeyError when no roads are found
   - expose the ray and buffer parameters
5. *(Moved to the separate land-value tool: land/improvement allocation.)*
6. **Low-memory mode:** smaller dtypes, capped workers, chunked enrichment.

### D. Documentation fixes found during review
- **Spatial-join key name.** The real key is `geometry`. `advanced_settings` §4.2 calls it `spatial_joins`.
- **Unsupported file formats.** `advanced_settings` §4.5 and `tutorial` L102 claim `.shp`/GeoPackage loading, which the loader doesn't support.
- **Distances.** The per-feature `enabled` default is documented as true; it is false. `config.md` shows an obsolete distances schema and enrich keys without the `data.` prefix.
- **Wrong stage for spatial lag.** `advanced_settings` §4.8 lists it as a step 1 enrichment and omits the required per-model-group `model_groups` entries.
- **Run order.** `ref_tables` is documented as running before estimation; it runs after.
- **Checkpoints.** They're documented as "self-invalidating" (`advanced_settings` L1502, `tutorial` L575); they aren't.
- **Re-run point after a model group change.** The tutorial says to re-run from notebook 3; it must start at tagging.
- **Recipe.** `recipe.md` lists `process_sales` in assemble.
- **infer's `fill` key** is described backwards (the code copies *into* the target).
- **`time_adjustment` docstring** says it feeds ratio studies; it hasn't since 0.7.0.
- **Missing model.** `lcomp` is absent from `models_reference.md`.
- **Naming.** Consider renaming one of the three different "fill" concepts.

## 8. Milestones

- **M0 — Spike.** Prove the packaging and the hardware assumptions. **Done**, including a real-data run on Petersburg. See [`docs/m0/REPORT.md`](docs/m0/REPORT.md).
  - A portable build runs Petersburg end to end on a clean Windows 10 VM with 8 GB RAM. The only online step is the prompted sample download.
  - Benchmark under 0.7 defaults (§5) on synthetic cities of 50k, 150k and 500k parcels.
  - Rewrite §5 and the enrichment cost coefficients with measured numbers.
- **M1 — "Check my values."** Built as four slices, each one runnable:
  - **CI smoke test, after F3** (replacing the sample walk-through). On each platform, using only the bundled Python:
    1. **Engine:** download `us-va-petersburgcity` (download-only) and run OpenAVMKit's own stages (assemble, clean, value studies) on it with a checked-in `settings.json`, outside the app. This proves a bundle can run the engine.
    2. **App:** start the app service, load the UI (its script must be served as JavaScript), create a project and add one of the downloaded files to it.

    When the app's own flow can run steps again, the smoke test goes back to driving it.
  - **M1a, walking skeleton (done).** Real app shell: home screen, sample county download, steps 1–4 with live progress and Stop, and the results table with IAAO default targets. Engine changes: A1, A2, A3, A11, A12 (horizontal equity), plus a CatBoost Windows fix found by a user run. Bundles ship the app, and CI smoke-tests it end to end on Windows and Linux.
  - **M1b, own data.** The guided build's frame (four-part stages, Looks right, Under the hood, staleness of decisions) and the first three setup stages: Basics, Your files and Stitch, with their quick checks. Fixed-width import with the PACS layout, tested on the Travis CAD export. Step 1's receipt (upstream A14 for its counts). The sample becomes a walkthrough of the stages built so far.
  - **M1c, trust the data.** Setup stages Columns and Sales basics; the sales funnel and the receipts for steps 2–4; Data health, Field profile, the "From a field" model group builder, the read-only sales register.
  - **M1d, hand it over.** PDF report, exports, help.

  Full M1 scope:
  - Windows installer and Linux `.tar.gz`, both smoke-tested in CI; home screen; sample county
  - The guided build: all five setup stages, receipts and the sales funnel, including sale ID, vacant-at-sale, date format, dupes, ID fixes, units and transforms
  - Steps 1–4; the model group builder in "From a field" mode only; enrichment limited to map layers and basic geometry, so M1 runs offline
  - Data health, Field profile, a read-only sales register
  - Staleness tracking
  - Ratio study PDF with the IAAO profile; CSV/Excel export; offline help
  - Usability test with 3 real assessors before calling M1 done
  - Upstream: A1–A14
- **M2 — Enrichment, full model groups and sales.**
  - Enrichment screen (all of §3.12.1 except Street frontage)
  - Full model group builder
  - Sales review with overrides and rule templates
  - Formula builder and per-parcel corrections
  - Map background
  - Start next year
  - Report presets and editable templates
  - Upstream: B1–B10
- **M3 — "Build model values."**
  - Step 5: both variable paths, the model picker, Try/Finalize, outlier review, speed tiers
  - CAMA export
  - Model summary report
  - Upstream: C1–C3
- **M4 — Hardening.**
  - IT-friendly install
  - Code signing
  - Localization
  - Jurisdiction packs (Texas first)
  - macOS build
  - Upstream: C4–C6

## 9. Out of scope for v1
- Multi-user or shared-drive projects
- Non-disclosure-state workflows
- Vendor-specific CAMA formats
- Street-network enrichment
- Own aerial imagery
- The AI helper
- macOS release
- Land values of any kind: checking, reporting or exporting. A separate tool is planned

## 10. Open items
**Resolved:**
- GIS and Excel loaders go upstream into OpenAVMKit (B10).
- OpenFreeMap is the map tile service.
- Typst renders reports.
- The default variables are the big five plus location.
- The IAAO default profile is accepted, to be revised later.
- The frontend is React (§6.5).
- The openratiostudy.com reference is settled: read from its source repo (§4.2).

**Open:**
1. **M0 follow-ups:**
   - Is a Census API key actually needed? Petersburg's Census enrichment worked with none set. If the anonymous quota covers a county, the key becomes optional on the Enrichment screen.
   - Fail fast on unreachable services. Petersburg spent minutes retrying a blocked OpenStreetMap server; Oakbox needs a short timeout and a plain "skipped" card.
   - timing on a real low-end PC
   - memory on real extracts
   - why `cv_folds=1` is slow
   - the enrichment cost coefficients, which need an M2 run with enrichment on
2. **Real extracts.** The maintainer has several. They'll be shared, anonymised if needed, for guided-build and Data health testing. The first is a full Travis CAD PACS export (fixed-width text, 391 MB zipped).
3. **Land-value tool:** how, if at all, should Oakbox hand off to it later (shared project folder, export format)?
4. **Usability test:** after M1, with assessors the maintainer recruits.
