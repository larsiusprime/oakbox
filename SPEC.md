# Oakbox — OpenAVMKit in a Box

**Status:** v1.11 draft. Project setup is being redesigned one feature at a time to mirror OpenAVMKit (D41, §3.0); agreed features go in §3.0 before any code. Earlier revisions followed a full read of the OpenAVMKit docs, checked against its code (§6.3). Decisions are in §2; open items are in §10.

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
| D6 | Platform | Windows 10 64-bit minimum is the primary target. **Linux x86_64 is also supported** (glibc 2.34+: Ubuntu 22.04+, Debian 12+, RHEL/Rocky 9+), from the same codebase and CI. Installs per user, with no admin rights. A later macOS version must stay possible (§6.1). |
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
| D20 | Model choice | Each model group has its own models (LightGBM, MRA and Multi-MRA to start), each taking a named variable list (F9; revised 2026-10-31 from "Choose for me"). |
| D21 | Name and look | "OAK box" (written "Oakbox" in code and folder names). The look is a dense desktop tool (D43). The top of every screen (revised 2026-11-01, `OakBand`) is an oak band (the procedural flat-sawn grain, varnished) with the brass plate on it. **No text sits on the bare wood: what's said is on the plate**, and the plate says where you are: "OAK box | Projects" at home, "OAK box | New project", "OAK box | G2 · Tax year 2026" in a project; it takes you home (there is no separate back link). Inside a project the folder tabs stand on the band's bottom edge, paper on wood, and the open one runs into the page; a tab that waits on an earlier step says so at the top of the page, under the tabs. High contrast: the band black, the plate black and white. Print leaves the band out. Type is IBM Plex Sans and Plex Mono (OFL), bundled, with Noto Sans as the fallback for other scripts. |
| D22 | Model groups | A dedicated builder with live map feedback (§3.5). |
| D23 | Sale validity | Office codes and OpenAVMKit scrutiny together. The assessor can overrule any sale. **A sale flagged invalid never enters the modeling pipeline.** Review happens in Oakbox's separate sales register (§3.6). |
| D24 | Years | One project per jurisdiction per tax year (§3.7). |
| D25 | Users | Single user, one PC, for now. |
| D26 | Help | Built-in help pages plus a link to the Discord. An AI helper comes later (§3.8). |
| D27 | Bad input data | Data health and a Field profile, with plain-language problems and safe one-click fixes (§3.9). |
| D28 | Ratio study | IAAO statistics with pass/fail against editable standards profiles (§4.2). |
| D29 | Enrichment | A dedicated Enrichment screen exposing OpenAVMKit's real options, with cost estimates, small-area trial runs and coverage results (§3.12). v1 covers map-layer joins, footprints, census (configurable variables), distances (OpenAVMKit's defaults plus the user's own layers), elevation, permits and missing-value estimation. The street network is deferred. |
| D30 | Variables | "Plow forward" or "Test variables first" (§3.10). |
| D31 | Map background | Offline: parcels only. Online: an OpenStreetMap-based background. Every map has a **Street map** box in its corner to take the background away (a plain one, to see only the colours); the choice carries to every map and is remembered on the computer. The user's own imagery comes later (§3.11). |
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
| D43 | Dense by default | Compact, information-dense presentation, after mid-2000s desktop software (Mac OS X Tiger): 14 px text, about 24 px controls and table rows, a light grey window, softly rounded panels and tabs, buttons with a classic two-step bevel (two rings of light and shadow, swapped when pressed; grey, blue for the main action, red for danger; hovered icon buttons share it); every dropdown, pick-list or searchable, is a classic combo box: a sunken white field with a bevelled arrow button inside its right edge, folder tabs that touch, the first flush with the panel, slightly rounded inputs, little padding. Tables keep full outlines: an outer border, a gradient header bar, column lines and row lines, with a blue alternate-row tint. **Comfortable** density (about 36 px controls and rows, same text size) is used automatically on touch screens and can be chosen under View → Density (with the menus, D44); the choice is kept in OAK box's settings. **Built:** touch screens get it automatically (`pointer: coarse`); the setting itself arrives with the menus. Large text scales everything up. |
| D44 | Native window | The app's name and place are in the native title bar ("Travis County 2026 – OAK box"; "OAK box" on the home screen), not on the page. Menus are native (pywebview) and hold only what exists (§3.9). Browser mode has no menus; everything in them is also reachable on the page. |
| D45 | Fields wizard | Fields are chosen in a guided wizard over all of a project's files, one small question at a time (F3d), (the per-file table, F3c, was the Advanced view until it was removed on 2026-10-31). Guesses are preselected only on a name match that passes the field's check. |
| D46 | Tables use the width | Tables, charts and other non-text elements use all the width there is (a minimum width, never a maximum); only running text is capped for reading. Every table has faint cell lines and alternate gray rows, and a numbers column's header lines up with its numbers. A cell says a short phrase; the fuller explanation is in a tooltip on an ⓘ (D42), and a column's header isn't repeated in its cells. |

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

**Input files tab** (removed 2026-10-31, see F3b): F2, unchanged in what it does. One line per file (its columns are in F3b). **Add a file** sits at the top right; the add flow opens inline at the top of the tab, above the list. Empty state: "No input files yet." with **Add a file**.

**The sample county is removed** (D19): the home screen's sample, the old steps screen (Run, Stop, results), and the code and API behind them, including the M1a settings generator. Projects made from the sample by earlier builds are no longer listed. The CI smoke test changes with it (§8).

#### F3b. The input file list: show, rename, remove

> **Removed 2026-10-31:** the Input files tab, its list (F3b) and the per-file field view (F3c) are gone, with the API only they used (rename, remove, show a file; a file's columns, load, the dictionary, date formats). Files are added and described in the Data wizard (F3d), which keeps F2's add flow.

OpenAVMKit: each input file is one `data.load` entry, keyed by its name, with its `filename` (and `layer`).

```
                                                          [ + Add a file ]
                      Name         Type         Size     Geometry
  [📁] [✏️] [🗑️]      parcels      Parquet      4 MB     Yes
  [📁] [✏️] [🗑️]      cama         CSV          11 MB    No
  [📁] [✏️] [🗑️]      county       GeoPackage   388 KB   Yes
  [📁] [✏️] [🗑️]      old_sales    CSV          —        Missing
```

- **Columns:** Name, Type, Size, Geometry, and Fields (F3c). There is no Source column.
- **Row buttons:** show (📁), rename (✏️) and remove (🗑️) sit to the left of the name, always shown (revised from hover-only after review). The folder button shows the file in the system's file manager (Explorer selects it; elsewhere its folder opens). Its tooltip is the file name, and the layer for a GeoPackage, e.g. "county.gpkg, layer parcels" (D42). For a missing file it opens `in/`.
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

#### F3c. Choosing a file's fields

> **Removed 2026-10-31** with the Input files tab (see F3b).

OpenAVMKit: an entry loads only the columns listed in its `load`, each renamed to a field and optionally cast:

```json
"load": {
  "key":        "PIN",
  "sale_price": ["PRICE", "float"],
  "sale_date":  ["SALEDT", "datetime", "%m/%d/%Y"],
  "is_vacant":  ["VAC", "bool", "na_false"]
}
```

**From the list (F3b):** a Fields column with the count and a **Choose fields** button on every row.

```
              Name        Type      Size    Geometry   Fields
  📁 ✏️ 🗑️   parcels     Parquet   4 MB    Yes        3 of 12      [ Choose fields ]
  📁 ✏️ 🗑️   cama        CSV       11 MB   No         None yet     [ Choose fields ]
  📁 ✏️ 🗑️   old_sales   CSV       —       Missing    —            [ Choose fields ]  (disabled)
```

- The count is loaded columns out of the file's columns. "None yet" when nothing is loaded.
- A missing file shows "—", and its button is disabled with a tooltip.
- The button looks the same on every row. Adding a file returns to the list; it does not open this view.

**The field view** replaces the list inside the Input files tab, at `#/projects/<id>/files/<name>`, with "‹ Input files" to go back.

```
  ‹ Input files

  cama   cama.csv · CSV · 11 MB · 48,210 rows

  [ Filter columns…        ]   Show: (•) All 52  ( ) Loaded 4

  Load  Column       In file   Sample values                  Field                              Type
  [x]   PIN          text      0012-001, 0012-002, 0013-…     [ Primary key (key)          ▾ ]   [ Text     ▾ ]
  [x]   PRICE        number    185000, 92500, 240000          [ Sale price (sale_price)    ▾ ]   [ Number   ▾ ]
  [x]   SALEDT       text      03/14/2025, 11/02/2024         [ Sale date (sale_date)      ▾ ]   [ Date     ▾ ]  [ %m/%d/%Y  ▾ ]  ✓ 2025-03-14
  [x]   VAC          text      Y, N                           [ Custom… → is_vacant_lot      ]   [ Yes/No   ▾ ]  [ Blank = No ▾ ]
  [ ]   OWNER_NAME   text      SMITH JOHN, …                  ( greyed )                         ( greyed )
        geometry     geometry                                 always loaded
```

- **Column, In file, Sample values:**
  - These are read from the file without changing it: the column list (as for Geometry, F3b), and a few distinct non-blank values from its first rows.
  - "In file" is the column's own type: Text, Number, Yes/No, Date or Geometry.
  - The row count is shown when it's cheap to get (Parquet and GeoPackage metadata). For CSV it's left out rather than read.
- **Load** puts the column in `load`, or takes it out.
- **Field and Type on an unticked row** are shown greyed out. They hold what ticking would choose, so you can see that before ticking.
- **Field** is a searchable dropdown of OpenAVMKit's data dictionary:
  - It offers the `input` and `either` fields (§7 B11), except `dist_to_*` (computed when a distance is configured), grouped by the dictionary's groups.
  - **A loaded field OpenAVMKit computes is flagged**, whether picked or typed under Custom…: `derived` ("OpenAVMKit computes it, so it will overwrite this column") or `reserved` ("kept for a value it computes; load this column under another name"). The row is still saved. `either` fields aren't flagged: your column is used.
  - Each option shows the readable name with the key in brackets; the description is a tooltip (D42).
  - Where OpenAVMKit's dictionary says `{jurisdiction}` (assessed values, land-area checks), the project's jurisdiction is filled in: "Travis County land value". The wizard (F3d) shows the same names.
  - **Custom…**, at the top, turns it into a text box. Custom names follow the entry-name rules (F3b).
  - Ticking a column suggests the field whose key or name matches the column name; otherwise Custom… with the column name in lowercase.
  - Two loaded columns of one file can't share a field.
- **Type:** Text, Number, Whole number, Yes/No, Date (`string`, `float`, `int`, `bool`, `datetime`).
  - A standard field preselects its dictionary type (number → Number, string → Text, boolean → Yes/No, date → Date, percent → Number). It can be changed.
  - **Date** needs a format: common formats plus Custom…, checked live against the sample values. "✓ 2025-03-14" shows the first sample as read; red means the samples don't read with that format. Ticking a date column preselects the first common format that reads all its samples.
  - **Yes/No** needs blank handling: Blank = No (`na_false`, preselected) or Blank = Yes (`na_true`). Which values count as yes is OpenAVMKit's rule, given in a tooltip.
  - A type with no extra is written as `[column, type]`; one with an extra as `[column, type, extra]`.
  - **Built:** the list also has **As in file**, which writes the bare column (`"field": "COLUMN"`), so entries written that way elsewhere show as they are. A text column whose samples read as dates is suggested as Date.
- **Filter** matches column names and sample values. **Show: Loaded** lists only ticked columns.
- **Geometry** is always loaded by OpenAVMKit, so it's a fixed row.
- **Saving:** each change saves at once to `oakbox.json` and `settings.json`. A row that isn't complete is not written, and says why in red: a Custom… field with no name, a clashing name, or a date with no format. It is written as soon as it is complete. Nothing else in the entry changes.
- **Columns in `load` that the file doesn't have** (e.g. after the file was replaced) are listed first, in red, with only Load (to untick them).

**Not in F3c:** `calc`, `tweak` and `drop_fields` (next), field classification (deferred), and joins (F3d, F4).

#### F3d. The Fields tab: a guided wizard over all the files

**Revised (built): the wizard comes first, and collects the files itself.** It supersedes "Step 1: Your files" below; the field steps, checks, guesses, assumptions and Review carry over.

- **Existing values** (the Assessed values step, revised 2026-10-31): sets of values to compare the models with, each a card: its name (the roll's proposed as "<jurisdiction> roll"), **The assessor's roll** (at most one set), **Remove**, and three field rows, Market value, Land value and Improvement value, read and checked as the roll's always were. **Add a set of values**. The roll's fields are `assr_*` (OpenAVMKit's `assessor` model, step 4's first); the others take slots of their own (`vset1_market_value` … `vset5_*`; OAK box's names, not offered elsewhere, never modeled with). Making another set the roll swaps their columns. In Model values each other set with a market value is a `pass_through` model under the set's name: never in the ensemble (`ensemble.models` lists the chosen models), and judged like the roll, off the holdout (OpenAVMKit `analysis.ratio_study.outside_models`, `engine/enrich-fixes`). Land and improvement values are kept for a later land-value comparison.
- **No "true" values.** The Existing values step asks for the assessed land, improvement and total values only. OpenAVMKit's `true_land_value`, `true_impr_value` and `true_market_value` are the answer key of synthetic data, never a real roll, so the wizard neither shows nor guesses them.
- **Nothing loaded is out of sight.** A field under a step's **More** shows in the main list as soon as it's loaded, whether guessed or chosen. The link (**2 more fields**) reveals only the ones not loaded, and says how many; it's gone when there are none. A column already loaded is named by its field ("UNITS is already loaded as Building units"), never by OpenAVMKit's key.
- **What a column holds: one pattern, "N values ▾".** Beside a field, the check line says only what was checked; it never lists sample values. A small **N values** button (**N areas** for a location field) counts the column's different values. It opens a list of every value with how many rows have it (most common first, with a bar), a summary ("25 different values in 9,359 rows, 4 blank") and a search box when there are more than 12. Up to 500 are listed; past that, "N more: search to find them". The check line wraps rather than hiding its end. The same button serves the field rows on every step, location fields and your own fields. (The column dropdown still shows a few samples beside each column, to help pick one.)

- **New project → the Data tab** (first after Metadata; Input files is the advanced view after it). Steps:
  1. **Welcome:** the two datasets, SALES and the PARCEL UNIVERSE, and why both are needed.
  2. **Parcel universe:** add one file (or take one already in the project). It must have shapes ("✓ Geometry detected") and becomes `geo_parcels`. Pick its parcel ID. **+ Add 2nd ID** (then **+ Add 3rd ID**) adds an optional extra ID (`key2`, `key3`: the ones OpenAVMKit knows by name), with a tooltip saying it's only needed when another file joins on a different ID. Extra IDs aren't checked: rows are kept or dropped by the parcel ID alone. Choosing (remove) on the 2nd ID moves the 3rd up, and files joined on it follow.
  3. **Sales:** add one file. It matches the universe by parcel ID, or by one of its extra IDs (OpenAVMKit then looks up `key` from `geo_parcels` by `key2`: `data.process.enrich.ref_tables.sales`). Sale ID (a column, or made from the ID + sale date), sale price, sale date, valid and vacant sale (or assumed, after a warning).
  4. **More details:** Big five (building size, required; land size, filled from the shapes if missing; year built / effective year built, quality, condition, recommended), Location, Land, Building, Rooms & features, Assessed values, Other details.
  5. **Review:** what blocks a run, then what's recommended, then every source. Its button is **Bring in data ›**, to the next tab; greyed while something blocks a run, and a click lists what (**Go to Bring in data anyway** / **Fix them first**).
- **Step marks come from what's on each step,** recomputed on every change, in the same colours as the issues: ✅ complete, ⚠ something to decide (or age missing on Big five), ❌ blocks a run. A step not visited yet shows only its number, never a ❌ ahead of time.
  - Parcel universe, Sales and Big five are complete when their required parts are there: a universe file with shapes and a resolved parcel ID; a sales file, its IDs, price, date, valid and vacant sale; building size. Big five shows ⚠ only for missing age; quality and condition are nice to have.
  - The optional steps (Location, Land, Building…) are complete once confirmed by **Next** or **I don't have these**. Welcome by **Start**.
  - More details shows the worst of its parts; Review shows ❌ while anything blocks a run, ⚠ while something is recommended.
- **Next is greyed only while the step shows ❌** (something that stops a run: a required field not picked, under half the sales finding a parcel), with what's left just above the button bar (so the buttons never move), named when there are three or fewer ("2 things left: Pick the valid sale; Pick the vacant sale"). It still answers a click: a dialog lists them with **Skip ahead anyway** and **Finish this step** (the default). Warnings (⚠) and notes stay on the step and in Review but never grey Next. Optional steps and Welcome keep Next enabled, since Next is what confirms them. The add-file panel's confirm button is **Import**, on the right, in line with Next.
- **Repeated IDs, wherever they're shown** (the duplicates dialog's examples, Bring in data's "more than one row for a parcel" rows): the ID column first, rows sorted by the ID (numbers in it as numbers: 99 before 100; each ID's rows in file order), and the rows of one ID share a background, white or grey, alternating from one ID to the next rather than row by row. The bands carry on from one page to the next. Bring in data's rows show every row of each repeated ID: a **kept?** column after the ID says **✓ kept** (in bold) or **left out**, so what was dropped can be compared with what stayed ("Every row of each repeated ID: 124 left out, and the 115 kept…"); when all are dropped, every row says left out. The dialog's title names the file ("building.csv: more than one row for a parcel: the first kept").
- **Tables of rows read across easily:** every other row grey (the "See them" rows of Bring in data, the value lists); repeated IDs band by ID instead (above).
- **A number's spread** (a number's details on Bring in data): a histogram of 24 bars under the statistics, over the middle 98% of its values (the lowest and highest 1% counted apart, so one 4-million-square-foot parcel doesn't flatten the rest), zeros left out and counted ("2,366 zeros not shown": often "no building", "no year"), on a log scale when the values span orders of magnitude; the low, middle and high values under it, and each bar's range and count on hover.
- **Lists of values with their counts** ("N values ▾", Bring in data's "details ▾") sort by either heading, Value or Rows: a click sorts by it, again the other way (rows most-first, values A→Z with numbers as numbers), done by the server since long lists are cut short. The popover is never taller than the room it has: its list scrolls inside.
- **Reconcile: sales IDs that don't match the parcel IDs as written** (zero-padded on one side, hyphens on the other, a stray space). The Sales row's match line has **Reconcile…** whenever under 100% of sales find a parcel; under 95% the step shows ⚠, under 50% ❌. The dialog shows the match live, with clean-up steps for each side (remove leading zeros, hyphens, spaces or other characters; trim; replace; keep the first/last N; text before/after a character), samples from each file (unmatched sales, or random), and a one-click suggestion from a few common clean-ups. Saved steps become an OpenAVMKit `calc` on the ID (`key`, or `key2`/`key3`) of each file, wrapped in `["where", ["isempty", <id>], null, …]` so blank IDs stay blank and are still dropped. IDs are compared as OpenAVMKit reads them: not trimmed. Sales only for now; the parcel side's steps also apply to every other file joined to the universe on that ID.
- **Sales (or rows) that find no parcel: what kind of problem it is.** Only plausible nits are cleaned up; the rest is said plainly, for the jurisdiction to fix. Checked on the rows that find no parcel, after the clean-up already saved, when under 95% match:
  - **Written differently** (Reconcile, as above): a common clean-up matches 2 points more or better (trim spaces, leading zeros, hyphens, spaces, `-. /`, capitals), or under 80% of the unmatched IDs are written like the parcel universe's (digits, capitals and small letters in the same pattern: `0012-104` is `9999-999`, `r0123456` is `a9999999`).
  - **Another numbering:** under half match, and the IDs are written like the parcel universe's: "Fewer than half find a parcel: is PID the parcel ID, the same one the parcel universe uses? Or does parcels.parquet cover a smaller area than sales.csv?" It holds up the step.
  - **Parcels missing** (10 or more): "788 sales are for parcels that aren't in the parcel universe. Their IDs are written like the parcel universe's, so cleaning them up won't help."; then where they are, if a project file not joined as parcels has them (its columns cleaned as this file's IDs or the parcel universe's), or a parcel file's rows have no shape ("…whose rows have no shape of their own: condos or other units, it seems. Set them up on the Condo units step.", with a **Condo units…** link), else "Usually they're parcels kept outside parcels.parquet: condos and other units without a shape of their own (timeshares, homes in a mobile-home park, buildings on leased land), or parcels made since. Have a file with them? Add it on More files; units are set up on the Condo units step."; and the other files missing the same parcels.
  - **Keying slips:** "About 480 of them look like keying slips: one digit off a parcel ID. See them to check; fixing them is for the file they came from." Counted as how much more often the unmatched IDs are one digit off a parcel ID than the matched ones are (short numbers are often one digit apart anyway). When nearly all are slips, nothing is said about missing parcels.
  - A note, not a to-do, on the ID check, with **See them…** in place of Reconcile…; listed on Review. Sales, parcel files and the permits file alike.
  - **Checked** on 8 ID schemes (plain and zero-padded integers, NC PIN, Arizona book-map-parcel, variable-length PACS IDs, Cook County 14-digit PIN, California APN, letter-prefixed schedule numbers, Tennessee dotted map-group-parcel), each in 7 situations (20% missing, written differently, both, another numbering, spaces and missing, 8% slips, 3% missing), 10,000 parcels each: `tools/id_robustness.py`, all 56 as expected. A county prefix (`081-`) is written differently, but no common clean-up removes it: Reconcile's "text after" does, by hand.
  - **Engine** (`engine/enrich-fixes`): the `upper` calc, for the capitals clean-up.

- **Dates: the format is a choice, previewed.** A date column gets the first common format that reads its first rows; **Change format…** (or **Check format…** when unsure) picks another, or a custom strftime pattern, and previews it on every row exactly as OpenAVMKit parses it (`pd.to_datetime(format=)`): how many read, the range, samples, and which don't read. "Unsure" means some rows don't read, or another format also reads every row but gives different dates (month/day against day/month). The chosen format is the load's third item.
- **Valid and vacant sale from any column: a rule.** A column that isn't yes/no (Q/U, a deed code) opens **Which sales are valid?**: its values with counts, ticked for yes (an `isin`), plus more tests on any sales column (is one of, is not one of, equals, contains, is blank, more/less than…) joined by all or any. The count and sample rows come from OpenAVMKit's own filter code on every row. Saved, it's a `["?", filter]` calc on the field (as in Baltimore's `vacant_sale`), and each column it tests is loaded (under its own lowercased name, or as the field it's already loaded as). A yes/no column still loads directly; **Use a rule…** turns it into one.
- **Money and measures (F1):** a project has units (imperial/metric), a currency (ISO 4217) and a number style (how the files write 1234.56: `1,234.56`, `1.234,56`, `1 234,56`, `1'234.56`, `1 234.56`). All three follow the country on the new-project form (from Unicode CLDR, generated into `locales.json` by `packaging/make_locales.py`) and can be changed there or later under Metadata. OpenAVMKit only takes the units; currency and number style are OAK box's, for reading and checking prices (the price dialog) and for showing money. Projects saved before take their country's.
- **Sizes are asked in the project's small unit, from a column in any unit.** Building and land size (and footprint) sit beside a unit dropdown: sq ft, m², acres, hectares, sq yd, tsubo, pyeong, mu. It's guessed from the column's name (`ACRES`, `LAND_HA`, `LOT_SQM`) or else the project's unit; the check line shows the conversion ("0.114 acres → 4,966 sq ft") and warns when the typical size says the unit is wrong. The project's unit decides what OpenAVMKit gets: `land_area_sqft` (imperial) or `land_area_sqm` (metric). A column in another unit is loaded under its own name and converted by a calc (`land_area_sqft = land_area_sqft_in_acres × 43,560`). The wizard names the fields in square metres in a metric project.
- **Big five, with only the universe loaded,** says building details often come in a separate file, and that **In another file…** adds it once for every field.
- **More files (step 4, after Sales):** the universe and sales steps take one main file each ("more files come later"); this step adds the rest one by one. For each: what it holds, **More about each parcel** (joins the universe on its parcel ID or an extra ID) or **More about each sale** (joins the main sales file on the sale ID, so that file needs a sale ID column); the ID column, guessed from the target's column name or else from the column whose values best match the target's IDs (compared loosely: no leading zeros, hyphens, spaces or case); and the same checks as the main files: repeated and blank IDs (Resolve…), and how many rows find their parcel or sale, with **Reconcile…** whenever not all do. Under half matching blocks; under 95% is a warning. **Don't use this file** sets it aside. Settings: parcel files join `merge.universe` (with `on` for an extra ID), sales details join `merge.sales` after the main file, each with `dupes` on its join key. **What it's about, then how it joins** (revised 2026-10-31): **More about each parcel** or **More about each sale**; then, under it, **How does it join?**: **Joined to each parcel / sale** on the ID (as above), or **Appended as extra rows: more parcels / more sales** (older sales, sales from another system, sales found some other way; a second parcel file). Joined to each sale works with a made sale ID too: the file's own is made the same way, from its parcel ID and a **Sale date** picked beside it ("Its sale ID is made as the sales record's"), and its match check warns when most don't match ("are these sales of their own? Then append them as extra rows"); a parcel ID repeating there is a parcel sold more than once, not flagged. **Appended** (holds `sale_rows` / `parcel_rows`; more parcels need shapes, as the universe's have): its parcel ID; then a **column check** ("Has 4 of the sales record's 4 fields. Not in it: …", warned at half or fewer: likely the wrong file, or a different layout) and a **key check** (its parcel IDs look like the main file's: length, digits, leading zeros, "9 digits, leading zeros kept"; warned when they don't); then the main file's fields, each matched to a column (the main file's column name, else one named as the field, else the usual guess; each changeable, "(not in it)" leaves it blank for its rows): valid sale takes the sales record's rule on this file's column, an assumed valid or vacant sale is assumed here too unless given a column; the sale ID made as the sales record's (or its own column). How many rows are already in the main file (the same sale ID, or parcel), "each kept once, the main file's row". Settings: `merge.sales` / `merge.universe` right after the main file, `{"id": …, "how": "append", "dupes": {"subset": "key_sale" | "key", "sort_by": [[key, "asc"], [rank, "asc"]]}}`, with a `sale_file_rank` / `parcel_file_rank` calc (0 the main file, then 1, 2… the appended) so the main file's row is the one kept (OpenAVMKit's sort before keeping the first isn't stable). Tested through OpenAVMKit: Petersburg's teardown sales (158, 28 already in the sales record).
- **Location (More details):** asks only for the **situs address** (the property's physical address, not the owner's mailing address; a column named for mail or owner is never guessed for it). Then:
  - **Coordinates:** latitude/longitude and polar coordinates are shown as worked out by OpenAVMKit (from each parcel's shape), nothing to load. **Show map** / **Hide map** (hidden at first; the choice is remembered on the computer). A map (the app's one map, `MapView`: OpenStreetMap tiles; the parcels drawn as dots from a sample of up to 3,000 centres, so it reads without tiles too) shows the centre polar coordinates are measured from: the middle of the parcels, or a point the user drags the pin to (`locality.center`, in degrees). **Use the middle of the parcels** clears it. OpenAVMKit reads the centre in degrees for projected parcel files too (`engine/polar-center`, merged).
  - **Location fields:** the user adds the areas parcels belong to one at a time: a column of a parcel file and a name for it (lowercase, digits, underscores; not a name OpenAVMKit computes). Loaded as text, listed in `field_classification.important.locations` and `other.categorical`. Each shows how many areas it has, and warns when it's one value for all or nearly one per parcel (an ID, not an area).
- **More details, for now:** Big five, Location, Assessed values, Shapefiles. Land, Building, Rooms & features and Other details are left out; their fields are still in the advanced view.
- **Shapefiles (More details):** map layers, added one by one (Shapefile, GeoPackage, GeoJSON, GeoParquet). Each says its kinds of geometry and needs a coordinate system. The user decides its use, with the controls OpenAVMKit's settings give:
  - **Stamp its areas onto parcels** (polygons only): `data.process.enrich.geometry`, `{"id", "predicate": "contains_centroid", "fields"}`. Columns are picked one at a time and named, each as a location (default: `important.locations` and `other.categorical`), a category or a number. The check: parcels in a shape, in more than one (the first wins), in none; none at all blocks (wrong place or projection).
  - **Measure distances** (any geometry): `data.process.enrich.distances.<name>` with `source`, `max_distance`, `unit` (miles for imperial projects, km for metric, changeable), and optionally a name column and `store_top`/`top_n`/`sort_field` for each of the largest features. Gives `dist_to_<name>`, `proximity_to_<name>`, `within_<name>`.
  - Layers load with `"dupes": "allow"` (OpenAVMKit would otherwise keep one shape per value of the first column) and never join `merge.universe`. **Show map** draws the layer over the parcel dots. **Don't use this layer** sets it aside.
  - **One compact card per layer, two lines.** The header: name, file, shape count, a **Stamp onto parcels | Distance to** switch (stamping greyed for points and lines, saying why), the check, a map button and × (don't use). The check names only what isn't zero: "every parcel in one shape", or "331 in a shape · 9,028 in none". A distance layer has no check line (its header counts its features). Below:
    - **Stamp:** "Copies" and one chip per column copied (`zoning ← ZONING location ▾ ×`; the kind changes from the chip), then **+ Field**, a small popover for column, name and kind.
    - **Distance:** "Gives `dist_to_`[name] up to [2] [miles]" on one line, saved when a box is left or on Enter, then **Options**, a popover with what it gives, feature names and the largest few, summarised beside it ("names from MAJORLAKES").
    - Anything still to do (no coordinate system, how to use it, a column to copy) is listed under the header.
  - Engine (`engine/shapefile-layers`, merged): GeoJSON loads; point and line layers load (every non-polygon was dropped); a distance layer from a file needs no `name` column and stops the run with the reason when it fails (it printed an error and was left out); docs say `enrich.geometry`, not `spatial_joins`.
- **Amounts of money** (sale price, assessed values): a column that isn't plain numbers (`$250,000.00`, `250.000,00`, `$250K`, `(10)`, `N/A`) is read, not refused. **How to read it…** works like the date dialog. Settings and checks:
  - **What it sets:** the decimal mark (found from the whole column; when the values don't settle it, "1.234", the project's number style), whether K/M mean thousands and millions, and a scale (as written, thousands, millions, cents). Every row is previewed as written → as read.
  - **What it writes:** the column is loaded as text (`<field>_text`) and read by a calc of OpenAVMKit's own operations, so no engine change. Currency signs, spaces, words and the thousands separator are dropped, `(10)` is −10, and anything left that isn't a number (blank, N/A, TBD, -) becomes missing. A valid-sale rule that tests the price reads its own copy (`<field>_num`): OpenAVMKit drops a calculated field another calc uses.
  - **The scale check** runs on every amount column, plain ones too, since thousands and cents load without error and quietly give wrong prices. It shows the median and the 10th–90th percentile range. The sale price is also compared with the assessed value of the parcel it sold (median ratio, at least 20 sales). A ratio of 30 or more, or 1/30 or less, says which scale to read it in; without assessed values, a median under 1,000 suggests thousands and over 50M suggests cents. One click applies it.
  - **Values flagged:** amounts written as Excel writes big numbers (`1.11E+06`, rounded, can't be repaired). The price dialog only reads prices; it never changes which sales are valid.
- **Condo units: a major step of its own (6, after More details), one decision per part.** OpenAVMKit's `data.process.condos`, for units on the roll but not on the map: each has a parcel ID of its own and no parcel shape, because it sits on a parcel it shares.
  - **What fits the pattern,** listed on the first part so the user recognises theirs: condos of any kind (homes, offices, shops, warehouse and flex units); parking spaces, storage units, boat slips and hangars sold as condos; timeshares where each share has a parcel ID; homes in a mobile-home park, on land the park owns; buildings on leased land (ground leases, hangars at an airport, cabins on public land). Not these: townhomes and other units on a lot of their own (they have shapes) and co-ops (usually one parcel for the building). Mineral and air rights, business property and common areas can sit in a units file without a shape: **Which rows** leaves them out. The words throughout are "the parcel it's on" (a building, complex or park), not "building".
  - **Do you have condos?** (`wizard.condos`; a project that set up units before the question existed has them.) Above the answer, what the files suggest: each parcel file's rows with a parcel ID but no shape ("condo_units.csv: 1,360 of 1,360 rows…"), and the sales for parcels the parcel universe lacks. Until answered, the part shows ⚠ whenever the files suggest units, even before the step is reached. **No** finishes the step and stops any units (their settings and the fields given them); the rows without a shape stay left out and noted. **Yes** brings in the other parts, shown in the step list only then:
    1. **Units file:** the parcel files joined to the parcel universe, those mostly without shapes first and said to be likely; a file with only some ("1 of 6,864 rows…") is said to be more likely more about the units. Not listed: add it on More files. One units file (OpenAVMKit has one condos block): picking another moves the units.
    2. **Which rows:** every row without a shape, or rows where a test holds.
    3. **The parcel they're on:** how each unit finds it (below), said as a guess until changed, with examples.
    4. **Land:** four choices, each explained, with each example's share.
    5. **Their fields:** what the units carry: from their own file, and from the parcel they're on.
    6. **As a location:** the shared parcel as `condo_group`, with examples.
    7. **Summary:** what OpenAVMKit will do, in order, and how many sales now find a parcel.
  - **Earlier steps point here, never stop for it.** On More files, a parcel file whose rows mostly have no shape says "1,360 rows without a shape of their own: condos or other units? Set them up on Condo units" (⚠, not ❌; "…are left out: no units, you said" after No), with a **Condo units…** link; its low match isn't a run problem. Sales and other files' missing-parcels notes link there too. Each part's problems (no units file, no unit found, the land can't be worked out) are ❌ on that part and on Review ("Condo units › Land: …").
  - **Which rows are units:** **Every row** of the file, or **Rows where…** (one-line tests, values from the checklist dropdown).
  - **How each finds the parcel it's on:** **The start of an ID** (the first *n* characters of a column of this file match those of a column of the parcel universe file: `7865782948-030` → `7865782948`; OpenAVMKit's `id_prefix`, from the parcel universe file), or **A column naming it** (the building's parcel ID, cleaned as the parcel ID is; `parent_id`). Guessed the first time (of the columns both files have, the start that links the most units, ending before a separator) and with **Guess again**, and said to be a guess, with what it's based on ("Guessed: PIN_PLUS_EXT is in both files, and its first 10 characters (up to the "-") match one building's for more units than any other column or length…"), until the user changes it. Examples show both sides: the unit's value, the building it finds, what it matched there (`7864663668-023 → building 142468 (matches 7864663668-000)`), and the unit's land share; the check says how many units find their building, in how many buildings, and how many find none (left out).
  - **Land** (each choice explained beside it, with each example's share shown, e.g. "1/186 of 3,644 sq ft = 20 sq ft"):
    - **Equal shares** (the default): the building's land (its shape's area) in equal shares, one per unit. Needs nothing from the units (OpenAVMKit `land_share.method: equal`).
    - **Shared by finished area**: by each unit's finished area, from whichever parcel file loads it (the units' building cards, say: OpenAVMKit shares it out after the merge).
    - **Each unit's own land size**: from a column of the units file, picked right there.
    - **No land of their own**: the land is the shared parcel's (homes in a mobile-home park, buildings on leased land); each unit's land size is 0 (OpenAVMKit `land_share.method: none`, `engine/enrich-fixes`).
    - When the chosen way can't be worked out (no finished area loaded, no land column, or one blank for every unit), it's ❌ on Land and in the run's problems: OpenAVMKit would stop.
  - **Fields** (revised 2026-10-31), in three parts. **From the units file:** the parcel universe's fields picked from one searchable list (`MultiPick`; a field with a same-named column in the units file shows it, and ticking it gives it that column; land size is the Land part's), each chosen field a row below with its column's dropdown and ✕. Until the same-named ones are given or declined, Their fields shows ⚠ and Review says which fields the units go without. They're the units' own values, not a second source: the field rows don't call them a conflict. **From the parcel they're on:** the parcel files' land and location fields the units' own file doesn't give them (land use & zoning fields, location fields from the dictionary and the user's own; never the address, census fields or `condo_group`), picked from one list; each unit takes them where its own is blank (OpenAVMKit `condos.inherit`, `engine/enrich-fixes`). Changing these doesn't clear the enrichment cache (the rows are the same). **From its shape:** a plain list of what every unit gets as every parcel does: map layers, OpenStreetMap distances, census, elevation, and the parcel as a location when it is one.
  - **Also use the building as a location** (`condo_group` in `important.locations`; it's always a land category, and `land_area_alloc_sqft` a land number).
  - **What it writes:** OpenAVMKit tests `select` on every parcel file, so each gets a yes/no calc `condo_unit`: the rule (or "has an ID") in the units file, "blank ID" (never true) in the others; `select` is `condo_unit == true`. The link ID is loaded as `condo_link` in both files (prefix) or `condo_parent` in the units file.
  - **Elsewhere:** units that find their building count as parcels for the sales check, for other parcel files' match and in Bring in data's predictions. Bring in data's receipt adds "+ 1,360 units from condo_units.csv, with their building's shape" to the parcel universe and "units that find no building: left out" to the units file; a map layer's check counts parcels with shapes of their own (units take their building's). Changing condo handling clears OpenAVMKit's enrichment cache (it refuses a different set of parcels) and says "condo units" changed.
  - **Engine** (`engine/merge-one-conflict`, then `engine/enrich-fixes`): a field two files carry is filled from the second where the first is blank; land in equal shares; finished area from another file shared after the merge; each unit's land size set to its share after the merge (a blank one would later get the whole building's shape area).
- **Rule dialogs (valid sale, vacant sale):** each test is one line: the column, the test, the values, ×. The values are the same checklist dropdown as model group conditions (chosen values listed on the button; searchable checklist with each value's row count, All, Clear, a value typed in when the list is cut short).
- **Valid sale rule, price tests:** which prices count is decided only in the valid-sale rule, where it can be seen and changed. **+ Sale price is at least $1,000** is always offered once a sale price is chosen. It adds an ordinary test on the price column (at least 1,000, editable or removable like any test), read as the price dialog reads it. Below it are the zero, under-1,000 and negative counts, for information. The sample rows show that column as read.
- **Quality and condition (Big five 4 and 5):** each has two rows, **Number** (used for modelling) and **Category** (kept as text, for reports). Where both exist, only the number is guessed and loaded; the category is loaded only if the user picks it. OpenAVMKit gets a number where higher is better. Nothing is written for a number until its meaning is said, so a guess never writes a wrong direction. Columns are converted as they load, by OpenAVMKit calcs (`<field>_src` plus a calc):
  - **Quality number:** higher is better (as written) or lower is better (flipped within the column's range: low + high − x).
  - **Condition number:** % good (as written; ×100 from a 0–1 fraction), % depreciation (100 − x), tiers higher-better, tiers lower-better (flipped), or remaining economic life (years, as written). Whether it's a 0–1 fraction or 0–100 is found from the values and can be changed. **No condition: effective age carries it** is an explicit answer, not a blank.
  - **A category as the number:** **Rank the tiers…** puts each value worst to best, in equal steps (1, 2, 3…; one number for names meaning the same, VG and Very Good), and any number can be typed instead. A starting order comes from tier names it knows: letter grades (AA best, with + and −), Excellent…Poor and their codes (EX, VG, GD, AV, FR, PR), Q1–Q6 and C1–C6 (1 best), and numbered codes. Unknown names go last, labelled to be placed. It's written as a `map` calc; a value not ranked reads as missing. The same column can be both the category and, ranked, the number.
  - **Compare columns…** (on each Category row): every parcel-file column that looks like quality (qual, grade) or condition (cond, depr, good, CDU; not air conditioning), checked over every row. It shows numbers or text, how full, how many values, samples and notes: one value only, mostly blank, fractions, a code with a percent (`A  12%`, `B+5  130%`: the percent may be the better number), whether the tier names are known, and for condition numbers whether they rise or fall with age. The number and the category are picked there.
  - **One column, two fields:** a category can be both the text and, ranked, the number. Such a column is loaded once, as text (`<column>_raw`), and each field is worked out from it by a calc.
  - **Combined codes** (`Q4C3`, `B+5  130%`, CDU) are not split by the wizard: guessing the parts was too much magic. The plan is a custom expression builder the user writes the split in. Until then such a column can still be ranked whole. Compare columns notes a code with a percent in one value, and that CDU measures more than condition.
  - **Evidence**, shown and never applied, worked out each time a dialog opens from what's chosen then. Each part says what it's based on and is left out, with a note, when its inputs aren't there:
    - **Words:** "In the file" is the number as the file writes it; "Loaded as" is what OpenAVMKit gets, higher always better. Said once above the tables, and the sample line reads "In the file → loaded as: 8 → 10 · …" (revised 2026-10-31).
    - **Against age:** condition's median, in the file and loaded as, by effective age band (year built if there's no effective year; the project's valuation date). A meaning that makes newer buildings come out better is marked as fitting, and the verdict ("✓ Loaded this way, newer buildings come out in better condition", or older: "is it the other way round?") is shown only when condition does move with age (the rank correlation, as for the fitting mark). When it doesn't, as when nearly every building is one code, it says "Age doesn't tell: condition is about the same at every age (median 4 in the file). Go by what the values mean, and what they sell for below", never a tick for whichever meaning is picked.
    - **Against price:** a row per value loaded as when there are 10 or fewer (a grade of 7 to 11 is five rows, never "7 and up" bands); more, and five bands with as many parcels each, labelled as ranges ("under 40", "40–55", "85 and up"); % good and % depreciation in fixed bands. Each row: the **text beside it** (the paired category, bldg_quality_txt or bldg_condition_txt, when loaded: "C-", most common first), the sales, the **median sale price** (with a bar), the **median price per sq ft** (with a building size), and the same within the **most common type** alone ("SFR_DETACHED sales", its median price; the type from land use, else building type, description, class or style). Said above it: better should sell for more, but a grade is often tied to a kind and size of building and price per area falls as buildings get bigger, so across every sale it can run the wrong way; compare within the one type. The building's main card (its first row) is used. Valid sales only once there's a valid-sale rule or column, all matched sales before.
    - **Tier flags:** tiers with under 10 sales are flagged as thin. A tier ranked above another that sells for less is flagged (both with 10 or more sales), and the count of such steps is shown.
- **Sample county:** `sample/us-nc-guilford-synth` (shipped in the bundles under `sample/`) is a slice of Guilford County's public data, altered, with these problems planted: see its README.
- **"In another file…"** on every parcel field: pick or add the file, its ID column (matching the parcel ID, or the second ID), and the field's column. The file joins the universe (`merge.universe`, on `key2` when matched that way), and the steps already seen guess from it too.
- One universe file and one sales file for now; more complex merges come later.
- **Repeated and blank IDs** (one standard notice and dialog, wherever an ID is checked):
  - **Stray repeats** (fewer than 10 extra rows *and* under 1% of the rows) are a warning, not an error: "⚠ 1 repeated ID", with no choice made for you (OpenAVMKit would keep the first row of each meanwhile). Once you choose, it shows as resolved with the choice: "✅ 1 repeated ID, first kept". More than that blocks until you choose, since it usually means several rows per parcel or the wrong ID.
  - **The check is two lines:** the result ("219,381 parcels"), then the issues, each with ⚠ or ✅, then Resolve….
  - **Resolve…** opens the duplicates dialog: every row of a few repeated IDs side by side, then keep the first (sorted by a loaded field, ascending or descending) or drop every repeated row, with the result ("2,000 rows → 1,995 parcels"). Combining rows (`agg`) comes later. Written as the file's `dupes`.
  - **Blank IDs** block until confirmed (❌): a row with no ID can't be joined, and OpenAVMKit drops rows with no `key` when it joins the parcel files. The dialog explains it and has a tick box, "Drop the 442 rows with no ID"; ticked, it's ✅. In a sales file it's a warning, acknowledged the same way.
  - **Colours mean what's left to do:** ✅ green, decided; ⚠ yellow, something to decide; ❌ red, blocks a run. Every issue has an action, so the aim is all green.


Choosing fields file by file (F3c) shows every column of every file, most of them blank. The **Fields** tab instead asks one small question at a time, across the whole project, and writes the same OpenAVMKit settings: each file's `load`, plus the merge lists that stitch the files together (`data.process.merge`). F3c stays as the **Advanced view**. Both edit the same settings, so you can switch at any point.

**Where:** a third tab, **Fields**, after Input files (`#/projects/<id>/fields`, with `/<step>` for each step). It opens at the first step that isn't done, or at Review when all are.

```
┌─────────────────────┬───────────────────────────────────────────────────────────────┐
│ 1 Your files        │ STEP 5 OF 9 · BUILDING › AGE                                  │
│ ✓ Shapes            │ When were the buildings built?                                │
│ ✓ Location          │ Age drives depreciation. If you only have one of these, fine. │
│ ✓ Land              │                                                               │
│ 5 Building          │ Year built            [ YR_BLT · cama  ▾ ]  ✓ years 1890–2025 │
│   ✓ Basics          │ Effective year built  [ (none)         ▾ ]                    │
│   ✓ Size            │ Age in years          [ (none)         ▾ ]  Worked out from…  │
│   ▸ Age             │                                                               │
│     Quality & cond. │                                                               │
│     Rooms           │                                                               │
│     Features        │                                                               │
│ 6 Sales             │                                                               │
│ 7 Assessed values   │                                                               │
│ 8 Other details     │                                                               │
│ 9 Review            ├───────────────────────────────────────────────────────────────┤
│                     │ Advanced view            [‹ Back] [I don't have these] [Next ›]│
└─────────────────────┴───────────────────────────────────────────────────────────────┘
```

- **Layout:** a classic installer wizard. The step list on the left shows done (✓), skipped (–) and the current step, and any step can be clicked. The question is on the right, with Back / I don't have these / Next at the bottom. (**Advanced view**, to the Input files list, went with that tab on 2026-10-31.)
- **Saving:** each pick saves at once, as in F3c. Next only moves on.

**Step 1: Your files.** One table, one row per data file:

```
  File      Rows     Holds          Parcel ID column
  parcels   48,310   [ Parcels  ▾ ] [ PARCEL_ID ▾ ]  ✓ one row per parcel · has shapes
  cama      48,212   [ Parcels  ▾ ] [ PROP_ID   ▾ ]  ✓ one row per parcel · 99.8% match parcels
  sales     61,804   [ Sales    ▾ ] [ PROP_ID   ▾ ]  ✓ 99.5% of sales match a parcel
  permits    9,140   [ Not used ▾ ] [ PERMIT_PR ▾ ]  several rows per parcel: not used yet

  Each sale also needs its own ID
  sales              Sale ID column  [ Make one: parcel ID + date ▾ ]
```

- **Holds:** Parcels (one row per parcel), Sales (one row per sale) or Not used.
  - **Guessed:** a file with a price-like and a date-like column is Sales; any other file is Parcels.
  - Parcel files go into `merge.universe`, sales files into `merge.sales`. Not used files are in neither, and keep their `load`.
  - **The base** is the first parcel file with shapes. It is first in `merge.universe`, so every parcel in it is kept and the others left-join to it on `key`. The rest follow in file-list order.
  - **OpenAVMKit requires the base to be named `geo_parcels`** and to have shapes (`load_dataframes`, and enrichment and condos use that name). So the wizard renames the base's entry `geo_parcels` (an entry already using that name gets another), and a project with no parcel file with shapes is a problem listed on Review, not a "No shapes" step.
  - **Built:** what a file holds is kept on its entry in `oakbox.json` (`holds`), and the merge lists are written from it.
  - v1 has one sales file. Several sales files (e.g. one per year, appended) come later.
- **Parcel ID column** is loaded as `key` in that file.
  - **Guessed:** a column whose name looks like an ID (PIN, PARCEL, PROP_ID, ACCOUNT, KEY, GEO_ID…) and whose values are all, or nearly all, different.
  - **Checked once picked**, on the whole column:
    - parcel files: whether each parcel appears once, and, other than the base, how many of its IDs are in the base;
    - sales files: how many sales find a parcel in the base (repeats are normal).
  - **A parcel file with repeats** (permits, several buildings per parcel) is set to Not used, with "several rows per parcel: not used yet". Summarising such files comes later.
  - **A file with no usable ID** is flagged on its row, and can't be Parcels or Sales. (An ID made from row numbers, for a single parcel file, needs an engine change: §7 B14.)
- **Sale ID** (`key_sale`, §7 B13): a column of the sales file whose values are all different, or **Make one: parcel ID + date**, written as an entry `calc` that joins `key` and `sale_date`.
- **Second ID** (`key2`) is asked here too, per parcel file, and is optional.

**Steps 2 to 8: one topic at a time.** Each asks for at most about five fields, from the data dictionary's groups:

| Step | Fields |
|---|---|
| 2 Shapes | `geometry`: shown, not asked (which file has it). Without a parcel file with shapes, it says OpenAVMKit needs one. |
| 3 Location | Address, neighborhood, city, school district, census tract and block group, flood risk… |
| 4 Land | Land area, zoning (code, description), land class, minimum buildable size |
| 5 Building: Basics | Building type, class, description, count, units, stories |
| Building: Size | Finished area, footprint |
| Building: Age | Year built, effective year built, age, effective age. A year column may hold 0 for none: only the rest need be years ("✓ years 1988–2006 · 0 = no renovation: the year built"). An effective year built of 0 or blank is no renovation on record: with a year built too, `enrich.calc.universe` makes it the year built after the merge (OpenAVMKit would read a 0 as a brand-new building, an effective age of 0) |
| Building: Quality & condition | Quality and condition (as text, or as a number) |
| Building: Rooms | Bedrooms, bathrooms (total, full, half) |
| Building: Features | Style, exterior, heating, AC, foundation |
| 6 Sales | Sale price, sale date, valid sale, vacant sale |
| 7 Assessed values | Assessor's land, improvement and market values |
| 8 Other details | Deed (book, page, grantor, grantee) and mailing address fields |

- **Each field is a row:** its readable name (description on hover, D42), a column dropdown, then a check and a few sample values.
- **The column dropdown** lists columns grouped by file: every parcel file for parcel fields, the sales file for sales fields, plus (none). A column already used shows as "used: Year built" and can't be picked twice. Except (revised 2026-10-31): a yes/no field made by a rule (valid sale, vacant sale) only tests a column's values, it doesn't take it, so it can read a column another field uses ("also read by Valid sale"): valid and vacant sale from one sale type column, each its own rule on the one loaded column; and a category's text and ranked number (quality, condition) share one.
- **The check** reads the samples for that field's type: numbers, a year range for years, the date format found ("✓ reads as month/day/year"), the yes/no reading ("✓ Y = yes, blank = no"). A column that doesn't read as its field's type is shown in red, not saved, with the Advanced view as the place to fix it.
- **Types and formats are not asked:** the type is the dictionary's (as in F3c), dates take the first common format that reads all samples, and yes/no columns are Blank = No.
- **Guesses are made when a step is first shown**, and saved like a choice, so the settings always match the screen.
- **Guessed, but not too clever:** a field is preselected only when a column's name matches the field's key or name, or a short alias list (e.g. YR_BLT, YEAR_BUILT → `bldg_year_built`), and the column passes the field's check. Otherwise it stays (none). Nothing fuzzy. A guess never replaces a choice already made, including (none).
- **Computed fields** (`either`) are asked only when what they're computed from isn't loaded: "Age in years" only without a year built. They're labelled "Only if there's no year built".
- **I don't have these** sets the step's fields to (none) and marks it skipped (–).
- **Valid sale and vacant sale are required** (OpenAVMKit won't run without them). Each has a last option: **I don't have this: treat all sales as valid** / **…treat no sales as vacant**. Picking it asks for confirmation in a warning dialog ("Every sale will be used to build and test the models, including ones that aren't arm's-length." / "…vacant-land sales will be treated as improved."). It's written as an entry `calc` setting the field to true / false, and shows as **Assumed** everywhere.

**Step 9: Review.** Every field with its source, grouped by step: the file and column, "Assumed", or "—". Each has **Change**, which opens its step. Above, a count and the columns not loaded ("18 fields from 24 columns. Not loaded: OWNER_NAME, MAIL_ADDR and 4 more"). Problems are listed first: no parcel ID, no sales, a missing valid/vacant sale, a column that doesn't read.

**What it writes**, and nothing else:
- each file's `load` (as F3c), and the entry `calc` for a made-up sale ID (`["join", ["values", "key", "sale_date"], "str:-"]`) and for assumed valid/vacant sales (`["set", true]` / `["set", false]`);
- the sales file's `dupes`, on `key_sale`. Without it OpenAVMKit de-duplicates on `key`, which drops every repeat sale of a parcel;
- `data.process.merge.universe` and `.sales`, rebuilt from the Holds column whenever it or the file list changes.

**What it keeps in `oakbox.json`:** only its own state: the base, the steps seen and skipped, and the fields already decided (so a guess is made once). The assumptions are the `calc` entries themselves.

**Changes made elsewhere:** the wizard reads the settings each time. A field loaded from two parcel files (possible in the Advanced view) shows both, with a warning, until one is set to (none).

**Templates** for common CAMA exports fit on top later: a template is a set of file roles and a column → field map, recognised by its column names. Not in F3d.

**Not in F3d:** files with several rows per parcel, several sales files, ``calc`/`tweak` beyond the three above, templates, and the joined-result preview (F4).

- **Out of the flow for now:** the Input files tab (§F3b) and each file's own fields (§F3c), which the wizard's "Advanced view" link opened. They no longer match the wizard. Their links open the Data wizard, and **Project › Data** (Ctrl+2) replaces **Input files** and **Add a file…** in the menu; files are added on the wizard's steps. The code stays until we decide whether to bring them back or remove them.

#### F3e. Data › Enrichments: public data about each parcel (built)
A step of its own, after More details. One compact card per kind of public data: an on/off box, where it comes from, one line saying exactly what goes online, its options once on, and the fields it adds. A note above says that only the rectangle around the parcels is sent (its area shown), never the parcel data, and that downloads are kept and reused. The step's settings start, the first time it's shown, with distances, footprints and elevation on and census off (it needs a key).
- **Distances to features** (OpenStreetMap, `data.process.enrich.distances`, entries with `osm: true`): a summary line ("Water bodies, parks… · up to 1–2 miles") and **Change…** for each feature's on/off, farthest distance (in miles or km, the project's long unit) and, for named features, also measuring to each of the N largest (`store_top`, `top_n`). OpenAVMKit's built-in features: water bodies, parks, colleges & universities, golf courses, railways (`transportation`), airports, coastline; and major roads by tags (`osm_tags` highway motorway/trunk). Defaults: water 2 mi (3 largest), parks 1 mi (3 largest), colleges 2 mi, golf 2 mi on; the rest off. A map layer measured under the same name keeps it (the OSM feature is then not measured); a layer can't take a name an OSM feature uses. Columns: `dist_to_osm_<feature>`, `within_…`, `proximity_to_…`.
- **Building footprints** (Overture Maps, `overture`): each parcel's buildings' total footprint and height, `bldg_area_footprint_sqft`/`_sqm`, `bldg_height_ft`/`_m`.
- **Census** (US Census Bureau ACS 5-year, `census`): the county, picked from the project's state's counties (a list bundled from TIGERweb: `packaging/make_counties.py`), preset from the project's place; the survey year (2018–2024). The user's free API key is saved in OAK box's own settings on this computer (**Save**, **Forget**, its last four characters shown), never in the project, and handed to OpenAVMKit as `CENSUS_API_KEY`. Census on without a county or a key is ⚠ on the step, never ❌.
- **Elevation** (USGS 3DEP, `dem`): 10, 30 or 60 m tiles, the suggestion by area (10 m up to 600 km², 30 m to 8,000 km², 60 m beyond). Adds `elevation_mean_ft`, `elevation_stdev_ft`, `slope_mean_deg`.
- **Which fields: the user's choice.** Each card says **Adds [3 fields ▾]** (or "2 of 3 fields") and the names of those it adds, in the same button style as "N values ▾". The button opens **Fields from Building footprints**: a checkbox per field, with what each is under its name ("Median gross rent: rent plus utilities (ACS B25064)"); all ticked to start with. Distances tick the three kinds for every feature at once (`dist_to_osm_<feature>`, `within_…`, `proximity_to_…`), the largest features' columns included. Unticked fields go in `data.process.enrich.drop_fields` (universe and sales), which OpenAVMKit applies after every enrichment; the largest features' columns are named as they're found, so they're dropped by a pattern (`within_osm_parks_*`: `drop_fields` takes `*` patterns, `engine/enrich-fixes`). An enrichment with none ticked isn't downloaded, and the card and the step say so (⚠, not ❌). The receipt lists only the fields that came out.
- **Yes/no fields OAK box makes** (valid sale and vacant sale, assumed or by a rule) never have blanks, so they need no blank handling; OpenAVMKit warned about it on every run regardless, and now only warns when a yes/no field really has blanks (`engine/enrich-fixes`). A yes/no column from a file gets the user's choice (Blank = No / Blank = Yes, on its step), so nothing about blanks is left for the user to see.
- **When Bring in data runs:** each enrichment says when it starts ("Downloading building footprints from Overture Maps"). Before downloading, the service is asked whether it answers (a 10-second request, made with `requests` as the downloads are, so the check and the download agree about certificates); one that doesn't is skipped at once, unless what it downloaded before is kept, rather than waited on (OpenStreetMap's library waits a minute and tries again). The reason is short: "overpass-api.de's certificate couldn't be checked (certificate has expired)", "…didn't answer within 10 seconds".
- **While it runs, it's never a mystery.** The clock is the server's and moves every second. The step that's running shows what it's doing inside ("Parks (2 of 4)", "Downloading buildings: 12,400 so far", "Working out slopes"), its own bar when that's known, and "working · 0:42 on this step". The run says it's alive every 2 seconds; with no word for over 10 seconds it says it may be stuck (stop it, or wait). Until the first step, "Starting Python and OpenAVMKit". The detail comes from OpenAVMKit's progress events (`progress.report(..., sub=, part=)`) and, between them, the latest line it printed.
- **Skip this step** (footprints, census, distances, elevation): the step stops at its next checkpoint (between OSM features, Overture batches, elevation stages, census download and join), the parcels come back as they went in (nothing half-done kept: OpenAVMKit saves a download only once the part is done), the receipt says "Skipped: you skipped it while it ran", and the run carries on. A checkpoint can be as far off as one download (a single slow Overpass query). The app asks by a line in `out/oakbox/bring_in.skip`, which the run reads at each checkpoint. Loading and joining the files can't be skipped: Stop ends the whole run. Engine (`engine/enrich-fixes`): `progress.report` takes `sub` and `part`; `reporting(skip=)` raises `Skipped` (a `BaseException`, so the part's own `except Exception` handlers can't swallow it).
- **Certificates are checked as the computer does** (`truststore`, in every process OAK box starts: `oakbox/net.py`): Windows' own verifier, so an old cross-signed certificate in the Windows store (which made Python report "certificate has expired" for sites the browser opens) or a county network's own HTTPS root no longer stops a download.
- **A good OpenStreetMap citizen.** Overpass is a shared, volunteer-run service. OSMnx says it's OAK box (`OAK box/<version> (+https://github.com/larsiusprime/oakbox)`, not OSMnx's own name), keeps its rate limit on (it asks Overpass for a free slot before each query), and asks one query per feature chosen over the rectangle around the parcels, kept and reused (OSMnx's cache and OpenAVMKit's). When Overpass doesn't answer, nothing is sent to it: distances are skipped like any enrichment. Far under Overpass's guidelines (10,000 queries and 1 GB a day). Attribution: "© OpenStreetMap contributors" on every map, and on the receipt with a link to the Open Database License wherever OSM distances came in; the fields' source is "OpenStreetMap contributors (ODbL)". Map backgrounds still load OpenStreetMap's own tiles (light use, allowed), before a wide release, a tile provider meant for apps.
- **Census is for the county the parcels are in.** `counties.json` has the rectangle around each county (from TIGERweb). The county is guessed from the project's place if the parcels are in it, else from where the parcels are; a county they aren't in is ⚠ on the card and the step ("the parcels aren't in Wake County, NC: they look to be in Guilford County, NC (37081)", with **Use it**): its census figures would all be blank. An enrichment that fails is skipped, its fields missing, and Bring in data carries on. Each one's log is kept at `out/oakbox/enrich_logs/`.
- **Receipt:** an **Enrichments** card above the parcel universe: each one's result (✓ coverage as the parcel universe ended up: "6,589 parcels (70%) have a building", "every parcel"; ⚠ for distances when some features failed, naming them; ✗ "Skipped: overpass-api.de didn't answer"), its time or "reused from last time", the fields it added, and **Run again** beside one that didn't work. Its fields are grouped as **Public data (Enrichments)** in the field tables, with the source. "Out of date" says "building footprints", "census", "elevation" or "distances to OpenStreetMap features".
- **Engine** (`engine/enrich-fixes`): elevation stats for parcels sharing a shape (condo units borrow their building's) and for slivers that lost every cell to a neighbour; both were blank.

#### F3f. Data › Deeds (built)
A step of its own, after More details: **Which deed was each sale recorded under?** The deed ID (`deed_id`: OAK box's own field, OpenAVMKit's settings name it), or the deed book and page; grantor and grantee under More. Guessed from the sales file's column names. Optional: **I don't have these**.
- **What it's for:** sales scrutiny (notebook 2) flags sales sharing a deed ID and a sale date as one sale of several parcels, and sets them aside. The step says how many it will find ("123 deeds have more than one sale on the same day: 361 sales…") and how many sales have no deed ID.
- **What it writes:** `analysis.sales_scrutiny.deed_id`: `deed_id`, or `deed_book_and_page`, a calc on the sales file joining book and page ("123-45"), blank when either is.
- **Engine** (`engine/enrich-fixes`): sales without a deed ID were all read as one deed ("None") and flagged together; blank deed IDs are now left out.
- **Sample:** a deed's sales move together when the sample's dates and prices are nudged, so the real multi-parcel deeds stay on one day (123 of them).
- **Buyers' and sellers' surnames** (for sales scrutiny's same-surname check, F6): under More, the seller and buyer names (`deed_grantor`, `deed_grantee`) and, optionally, their surnames already split (`deed_grantor_surname`, `deed_grantee_surname`: used as given). Once names are loaded the step asks **How are the names written?** Surname first (`SMITH JOHN A`), surname, a comma, given names (`Smith, John A`), surname last (`John A Smith Jr`), or **my own pattern** (a regular expression with a `surname` group). Nothing is guessed silently: the format is guessed from the names and said why ("100% of the names are in capitals without a comma, the way recorders write SURNAME GIVEN"), with a **live preview** of real names and the surname read from each (six sharing one, six not) and the counts (names read as people, skipped as companies, trusts, banks or governments, with no surname found; sales sharing a surname). Trying a format is a preview; **That's right** / **Use this** keeps it (written as `analysis.sales_scrutiny.same_surname.pattern`). Names too irregular for any pattern are better split before they come in: the step says to give the file surname columns and load them as the surname fields. Unconfirmed when Check sales is first used, the guess is written down. On the sample: 196 of 3,804 sales share a surname (about 150 made so, the rest by chance).

#### F3g. Data › Permits (built)
A step of its own, after Enrichments: **Do you have building permits?** Add the permits file (one row per permit, with the parcel ID; it can't be the parcel universe or sales file), or **I don't have these**.
- **The file:** its parcel ID (the usual ID row: matched against the parcel universe, units included, with **Reconcile…**; "2,140 permits · 100% find a parcel"), the **date issued** (a column that reads as a date, its range shown), and **what each permit is** (a column with a few kinds). All three are guessed when the file is added.
- **What each kind means:** a table of the kinds with their counts, each **Teardown (demolition)**, **Major renovation**, **Minor renovation** or **— not a renovation**, guessed from its words (demo… teardown; addition, remodel, renovat… major; alter, repair, interior… minor) and marked "(guessed)" until said.
- **A sale demolished within N days** (365) of selling is a teardown sale, counted as vacant. **Major renovations reset the effective year built** (on unless there's no year built: "needs the year built").
- **What it writes:** the permits file's `date` and `permit_type`; calcs `is_teardown`, `is_renovation`, `renovation_num` (3 major, 1 minor, 0) and `renovation_txt` (the kind); `dupes: allow` (a parcel has many permits); and `data.process.enrich.permits` (`sources`, `max_days_to_demo`, `calc_effective_age`). The file isn't merged into the parcel universe.
- **Receipt:** "42 of them teardown sales: demolished within 365 days, so counted as vacant" under the sales record's vacant count, with **see them**.
- **Engine** (`engine/enrich-fixes`): on the sales, teardowns and renovations went to every sale of the parcel (worked out on the parcel ID, not the sale ID), so a house sold twice before its demolition had both sales made land sales; the effective year stopped with an error on sales without a year built (sales take their parcel's); `reno_date` was filled with "UNKNOWN" as an improvement category.
- **Sample:** `in/permits.csv`, 2,140 made-up permits, 40 of them demolitions within a year of an improved sale (planted problem 15).

#### F4. Step 1, Bring in data (its own tab, **1 Bring in data**)
- **One task at a time** (the frame of F5): **What runs** (❌ when Data has something to fix, with what changed since the last run) › **Bring in data** (the run: **Bring in data ›** where Next is, progress with Skip, then the results open) › **The parcel universe** › **The sales** (each with its funnel and fields) › **Public data and checks** (⚠ when public data was skipped or a check differs), whose Next is **Looks right › Model groups**.
- **Terms:** the joined parcel table is always the **parcel universe** and the joined sales table the **sales record**, here and in every message (the wizard's messages name the files holding them that way too).
- **Ready:** what will run (the parcel universe, the sales record, the files joined to them, the map layers, how many fields). It can't run while Data has a problem; the first is shown, with a link to Data.
- **Run:** OpenAVMKit's 1-assemble up to model groups (`load_dataframes`, `process_dataframes`), which needs no model groups and no engine change. It runs in a process of its own (`python -m oakbox.bring_in <project>`), so the app stays responsive and **Stop** ends it. It reports its steps; the page shows them, time so far, and time left from the last run. Results are written to `out/oakbox/bring_in/` via a temporary folder, so a stopped or failed run leaves the last receipt. A failure shows the last line of its log (`out/oakbox/bring_in.log`).
- **Receipt:** the counts, for the parcel universe and the sales record alike:
  - **Where the rows came from:** for the parcel universe, its file's rows, those without a parcel ID, repeated IDs, the parcels; for each file joined to it, its rows, blank IDs, extra rows, rows for parcels not in the parcel universe, and the parcels with and without a row from it (with a note when it holds the building size: OpenAVMKit treats a parcel without one as vacant land, building fields 0). For the sales record: its file's rows, those not valid by the valid-sale rule or column (OpenAVMKit leaves them out as it loads, so these are counted from the file), repeated sale IDs, valid sales, improved and vacant, and those that don't find a parcel.
  - **Fields:** every field (helpers left out), grouped as from your files, from map layers, and worked out by OpenAVMKit: how many have it, a summary (numbers: lowest, median, highest; years without a thousands comma; categories: how many values and the commonest; dates: the range; yes/no: the counts; IDs: "all different"), where it came from (file and column, "cleaned up", "your valid-sale rule", "made from the parcel ID and sale date"), and notes (0 for no building; measured from the shape; only parcels in a layer's shapes; farther than the distance limit is blank).
  - **Checked against Data:** what the wizard predicted (parcels, valid sales, share finding a parcel, parcels in each stamped layer) beside what OpenAVMKit got.
  - OpenAVMKit's own warnings, folded away; the libraries' notices only counted. Under the hood: the calls and their times, and what was written.
- **Each field in detail:** each field's name is a link with a faint magnifier, and its whole row highlights on hover; clicking either opens its details (notebook 1's "examine in ridiculous detail", one field at a time): for a number, its count, zeros, lowest, 10th/25th/50th/75th/90th percentiles, highest and mean; for everything else (and a number too), every value with its count, most common first and searchable (dates by year). Read from the one column, not the whole table.
- **Rows:** each count with rows behind it has **see them**, and each table **View all rows**: a dialog that reads one page (50 rows) at a time from Parquet written in 1,000-row groups, so a large parcel universe is never loaded whole, with **Export CSV**, streamed a row group at a time. Dropped rows show as written in their file.
- **Out of date:** when the settings it depends on (`data`, `field_classification`, `locality`) change, the step says what changed (a file added or removed, how a file is read, how the files join, map layers, the centre, location fields) and greys the last receipt until it runs again.
- **Looks right** is required: **2 Model groups** opens only once it's pressed on an up-to-date receipt, and closes again when Data changes.

#### F5. Step 2, Model groups (its own tab, **2 Model groups**; §3.5 as built so far)
- **One task at a time,** in the Data wizard's frame (steps on the left, ✅ ⚠ ❌ marks, Back and Next at the bottom right): **How to start** › **Build the groups** › **Check them** › **Tag and write** › **What each group got**. Each tab will work this way (Bring in data and Check sales next): the run is a step whose button is where Next is, its progress fills that step, and when it's done the results open by themselves; the results are steps, not dialogs; **Looks right › Check sales** is the last step's Next. The tab opens on the first step not done (on the results when they're up to date).
  - **How to start:** the two choices; once started, starting again asks first ("This replaces your 6 groups").
  - **Build the groups:** the builder below, filling the step. Next saves unsaved changes (**Save and continue ›**).
  - **Check them:** each saved group's parcels and sales with its checks, Unassigned last; ⚠ on the step when any needs a look. None stops the run.
    - **Model it** (first column, a tick per group; added 2026-10-31): what to do with each group. Ticked by default only with enough improved sales to model (15). A group not ticked is greyed, "Not modeled", with nothing left to look at, here and after: in Check sales' time adjustment (no choice; never borrowed from), Check my values (not offered), the variable tests (skipped) and Model values (every model skipped: OpenAVMKit `instructions.main.skip.<group>`; "Not modeled" in its tables). Saved with the groups (`modeled`); the tag-and-write run doesn't depend on it.
  - **Tag and write:** the formats, then **Tag and write ›** (**Tag and write again ›** when out of date); progress while it runs, with **Stop**; then the results. Up to date, it says when it was written, with **Tag and write again** beside **Next ›**.
  - **What each group got:** what the receipt dialog showed; **Looks right › Check sales** marks notebook 1 done and opens Check sales.
- **Land use & building type on Data.** A Data wizard step under More details asks for **Land use** (`land_class`) and **Building type** (`bldg_type`), with building description, class, units and stories under More. Both are guessed from common column names (`LAND_USE`, `LUC`, `PROP_CLASS`, `BLDG_TYPE`…). Model groups are made from these, so they need to be in the parcel universe.
  - **Your own fields:** any other column of a parcel file (the parcel universe or a file joined to it), loaded under a name the user chooses. The name can be one of OpenAVMKit's own input fields that nothing else sets (zoning, bldg_rooms_bed, bldg_style…: 51 of them), loaded under OpenAVMKit's name so it's treated as OpenAVMKit treats it. Refused, saying why: the IDs, geometry and polar coordinates, and what OpenAVMKit works out itself ("OpenAVMKit works out sale_year itself"); what's filled in as Bring in data runs (condo_group, census_*, dist_to_*; and true_*, synthetic data's answer key); and a field with its own row in the wizard ("land_class has its own row in the wizard (Land use): pick its column there"). Each one has a class, **Land/location**, **Improvement** or **Other**, and whether it's **a category** or **a number** (guessed from the column). This writes OpenAVMKit's `field_classification` (`land` / `impr` / `other`, `categorical` / `numeric`), and the field can be tested in model group rules. The line for a new one has **Add field** and, once anything is filled in, **×** to empty it without adding anything.
  - Names use lowercase letters, digits and underscores. OpenAVMKit's own field names, location fields' names and names already used are refused, with the reason shown. A refused add keeps what was typed.
  - Your own fields are one table: column, name, class, kind, values (the **N values** button, and a warning when there is one, such as how many values of a number aren't numbers and will be blank), and remove. Its last row adds one. Changing them puts Bring in data out of date ("your own fields").
- **How to start:** the first time, the user chooses **Start with suggested groups** or **Define my own from scratch**. Suggested groups are made from the values of land use, building type, building description and building class, by the words in them: condos and townhomes, small multi-family, apartments, manufactured homes, commercial and industrial, agricultural, public and exempt, then single-family. The specific kinds come first, so a duplex on residential land lands in small multi-family. A group is suggested only if some value matches, and suggesting needs one of those fields (otherwise it says to add one on Data).
- **Layout:** the ordered group list (left); the selected group's editor (middle); a full-height map (right) that can be **Docked**, **Full** (filling the editor's place) or hidden.
  - **List:** colour, name, parcels, improved and vacant sales, the worst check, and how many parcels moved in or out since the last save (+161, −161). Up/down buttons change the order. **Unassigned** is last, in grey; pressing it shows only those parcels on the map (every group switched off in the legend), and pressing it again, a legend square or **Show all** brings the rest back.
  - **Map legend:** each colour's square is a checkbox, filled while its parcels are shown and hollow when they're hidden (not drawn, and not clickable). By changes, the squares are where parcels move to, Unassigned, and no change. **Show all** appears while anything is hidden.
  - **Editor:** name, colour, parcels (vacant), improved sales, vacant sales, median sale price; the rule ("any of" / "all of" these conditions). Each condition is one line: the field (by name), the test, the values, ×. The values are one dropdown that lists what's chosen ("CONDO, TOWNHOUSE, TWINHOME  3 ▾") and opens a searchable checklist with each value's parcel count, **All** (or **All shown** while searching) and **Clear**; a value not listed can be typed in when the list is cut short. what moved since the last save, with **Show them on the map**; the checks; Delete group.
  - **Start from a field…:** pick a category field (land use first) and send each value (with parcels, vacant parcels and valid sales) to a group, or to a new one. Each group gets a condition on that field and keeps its others.
- **Live preview:** every edit is re-run (after a 200 ms pause) with OpenAVMKit's own filter code on the parcel universe Bring in data wrote, in order, first match wins, as its model-group tagging does; about 30 ms on the sample. Sales follow their parcel's group. Changes stay a draft until **Save groups**, which writes `modeling.model_groups` (`{id: {name, filter}}`, the id kept when renamed); **Undo changes** goes back to the saved groups. Saving doesn't put Bring in data out of date.
- **Checks per group:** its rule isn't finished; no parcel meets it; every parcel it meets is in a group above; under 15 improved sales: too few to model; under 20: too few for a vertical-equity test; over 80% of its parcels look vacant (no building size), so building data may be missing for them. Unassigned: "N parcels in no group: they won't be valued".
- **Map:** the parcel shapes on OpenStreetMap tiles when online, plain background offline. Coloured by **Group**, or by **Changes** (parcels in a different group than when saved, coloured by their new group; the rest grey). The shapes are made once from Bring in data's results (`out/oakbox/groups/shapes.geojson`, simplified to about half a metre, in degrees) and recoloured, not redrawn, on each preview.
- **Inspect:** clicking a parcel shows its key fields (address, land use, building type and description, units, size, year built, land size, zoning, neighbourhood, assessed value, and every field a rule tests), its valid sales, and why it's in its group: each group in order, with the values it was tested on, ✓ for the group it's in (and the conditions it met), and any later group it also meets. It also counts the parcels like it (the same values in the category fields the rules test) and how many sold, with **Show them on the map**.
- **Checked against OpenAVMKit:** a test runs OpenAVMKit's own `tag_model_groups` on the saved settings and gets the preview's counts.
- **The end of notebook 1 (assemble): Tag and write.** The **Tag and write** step runs OpenAVMKit's own `tag_model_groups_sup` and `write_notebook_output_sup("1-assemble")` on what Bring in data loaded (`out/oakbox/bring_in/sup.pickle`, so nothing is loaded again), in a process of its own (`python -m oakbox.assemble <project>`), like Bring in data. It runs on the saved groups: unsaved changes, no groups, or Bring in data out of date stop it, saying which.
  - **Written:** `out/1-assemble-sup.pickle` (what notebook 2, clean, starts from) and, in `out/look/`, the parcel universe, the sales and the hydrated sales as Parquet. **Formats** adds GeoPackage, zipped Shapefile or CSV, for map viewers and spreadsheets.
  - **What each group got** (a step): per model group, parcels, vacant parcels, improved and vacant sales (the sales get their parcel's group, as OpenAVMKit hydrates them), then Unassigned (`UNKNOWN`, not valued); whether every count matches the builder's preview (the preview's column shows when one doesn't); the files written, their size and what each is; **Show in folder**; OpenAVMKit's own warnings, folded.
  - **Looks right** marks notebook 1 done. Changing the groups or the formats, or running Bring in data again, puts it out of date (and un-done) until it runs again; a change on Data makes it wait for Bring in data (§6.4).
  - **Left out of notebook 1:** cloud sync (a desktop app's files are on the desktop), and street frontages (`enrich_sup_streets`: the street network is deferred, D29). Its "examine" cells are Bring in data's receipt; "examine in ridiculous detail" is each field's details (click its name).
- **Not yet:** common areas (deferred), hand edits (map lasso), nested AND/OR, undo/redo, export/import, and a map for very large counties (the shapes are sent whole: fine at 10k parcels, too much at 500k; vector tiles then).

#### F6. Step 3, Check sales (its own tab, **3 Check sales**; notebook 2, clean) (built, but for the parts listed under "Not built yet")
Notebook 2 makes the data ready to model, and it's where subjective calls go in: which sales count, how prices are brought to one date, what stands in for blanks. So the step shows each call before it runs, and every sale it sets aside with the reason. It starts from the 1-assemble hand-off (F5) and writes the 2-clean hand-off that step 4 (Check my values) and step 5 (model values) read.

**What runs, in OpenAVMKit's order** (`openavmkit.headless` stage `clean`, in its own process like F4 and F5; about 10 s on the Guilford sample, minutes at 500k parcels):
1. **Fill blanks** (`data.process.fill`, per model group).
2. **Equity clusters** (`analysis.horizontal_equity`, `land_equity`, `impr_equity`): groups of similar parcels, `he_id`, `land_he_id`, `impr_he_id`, used later by the equity studies and the models' CHD. Nothing to decide here beyond the location (below).
3. **Sales:** the sales window (`modeling.metadata.use_sales_from`), the user's own invalid-sale rules (`data.process.invalid_sales`, the Advanced rule templates of §3.6), then **time adjustment** (`data.process.time_adjustment`).
4. **Sales scrutiny** (`analysis.sales_scrutiny`): heuristics, the user's exclusions (`invalid_key_file`), then outliers within clusters of similar sales.
5. **Rare categories** (`data.process.collapse_sparse_categories`), then the hand-off: `out/2-clean-sup.pickle` and `out/look/2-clean-*.parquet`.

**Before running: one panel, a card per call, each with its default already chosen and what it does in numbers.** Nothing needs an answer to run; each card says what it will do.
- **Sales window.** "Sales from 2021 on (5 years before the valuation date, 2026): 1,901 of 3,804." A bar per year of sales, the years outside it greyed, the chart as wide as the text above it. One year for every sale (revised 2026-10-31: vacant land isn't modeled on its own yet, so it has no window of its own); **by model group** under Advanced. Writes `use_sales_from` (`{improved, vacant}`, both the one year, or `{default, by_model_group}`).
- **Time adjustment** (on by default; `time_adjustment.use`). Plain words: "Prices change over time. Each sale's price is brought forward to [the latest sale] by how much prices of similar property moved since it sold, per model group." After a run, a line per model group: the index over time with its sales per period, the change per year ("+7.5% a year": the sample's single-family sales, 2021 to late 2024), and the granularity OpenAVMKit settled on (months, quarters or years: it needs 5 sales in most periods). Choices: start from months or quarters (`period`, default quarters); per model group, **Time adjustment from** its own sales (the default), **another group's** (`time_adjustment.borrow.<group> = <source>`: OpenAVMKit works out the source's index, from its sales or its file, and applies it to this group's sales, held level outside the source's dates; for a group with few sales), or **my own file…** (`from_file.<group>`). The file is a CSV of two columns, said exactly where it's chosen: `period` (a day 2023-04-15, a month 2023-04, a quarter 2023-Q2 or a year 2023; one row each, at least two) and `index` (the price level then, any base, positive); more columns are ignored, and a schedule OpenAVMKit wrote (`period, start_indexed, end_indexed, correction_factor`) works too. OpenAVMKit's own reader (`read_schedule`) checks it when chosen and lists every problem, quoting the rows as written (a period that isn't a date, a value that isn't a positive number or is blank, a period twice, fewer than two); a file with problems isn't kept. A kept file is copied to `in/oakbox/time_adjustment/<group>.csv` (its digest in the settings, so replacing it puts the step out of date) and shown with its name, periods and dates; **Replace…**, or pick its own sales to set it aside. OpenAVMKit interpolates the index day by day, brings each sale to the last period, and holds sales outside the file's dates at its first or last level. The sample has a synthetic one (`in/time_adjustment_index.csv`, quarterly 2015 to 2024) and a broken one to see the problems (`in/time_adjustment_index_broken.csv`). Said plainly: prices are brought to the latest sale in the group, not past it (OpenAVMKit doesn't extrapolate); a group with too few sales gets no adjustment, and says so. Groups with no listed model group (Unassigned) get none. **Previewed before running:** nothing runs on opening the step (as Check sales waits for its button); **Work it out** works the time adjustment out alone (OpenAVMKit's own sales processing on step 2's hand-off, in a scratch folder so the last run's schedules stay; about a second on the sample), shown as a chart per model group with its change a year; **Work it out again** after a change. Both are the step's footer action, where Next goes: Next comes only once it's worked out with the calls as they are (revised 2026-10-31). **Each chart expands in place** (one at a time; another pressed shrinks it): every sale it's worked out from as a faint dot of its price per area as sold (log scale, the middle 90% of sales with room around them; how many far-off ones aren't drawn is said), the index drawn through their median, what the index is of (price per finished area or per land area, as OpenAVMKit chose) and the period it settled on with how many periods had 5 sales; hovering a dot shows its address, date, price, price per area and time-adjusted price. A group indexed on land area by OpenAVMKit's own choice is warned about (for condos, whose land is a share of their parcel's, it's rarely right). **Index on** (a column per group with its own sales): **Automatic** (OpenAVMKit works it out from the sales; once worked out it says which, "Automatic (land area)"), **Finished area** or **Land area** (`time_adjustment.per.<group>`, `engine/enrich-fixes`). **No time adjustment** lists each group without one and why, in OpenAVMKit's terms (no sale with a size; no period with 5 sales with one, even by year; no change), never a bare "too few sales".
- **Fill blanks** and **Rare categories** moved to step 5 (F7, **Prepare the fields**): nothing in this step uses them, they only change what the models learn from. Check sales runs with OpenAVMKit's own fills (its template's, and its automatic tidy-ups) but not the user's, and doesn't fold.
- **Sales scrutiny.** What it does, in plain words: "Similar properties sold near each other should sell for similar prices per square foot. Sales that stand far apart from their group are set aside for you to look at: they may be non-market sales, or the property's data may be wrong."
  - **Where "near" is** (`analysis.sales_scrutiny.location`): one of the user's location fields (Data › Location, map layers stamped onto parcels, census tract or block group, `condo_group`). Proposed: the user's first location field; else census block group when census is on; else **none**, said as a warning: "Sales are compared across the whole county, by size only." (Without a location field OpenAVMKit silently skips the location split; the sample has none, so its single-family sales were compared county-wide.) The same location is proposed for the equity clusters (`horizontal_equity`, `land_equity`, `impr_equity`), where OpenAVMKit's template has none for land and improvement.
  - **What "similar" is:** the numbers (default: land size, finished area, quality, age, condition, whichever are loaded) and, optionally, categories (`fields_numeric`, `fields_categorical`); clusters keep at least 5 sales.
  - **Checks, each on or off with its rule:** a nominal price, above zero but under 1,000 (changeable): a $10 deed, not a price (the sample: 67 sales; a $10 deed had reached step 4, its ratio 49,360); sales on the same deed on the same day (needs a deed ID: Data › Deeds; off without one, saying why); sales on the same day at the same price; sold as vacant but the building is older than the sale; sold as improved but the building was built after the sale year (likely land when sold; needs year built); sold as vacant for at least half the median improved sale in its model group and location (likely had a building); buyer and seller share a surname (possibly between family; needs the names, Data › Deeds, below). And the cluster outliers: outside median ± 2 standard deviations of price per area, 4× the median or more, or 0.35× or less and more than one deviation below.
  - **Each cluster outlier diagnosed** (after "Amateurs talk Algorithms, Professionals talk Data Cleaning", Center for Land Economics, 2025): its price, price per area and size each read **low**, **in range** or **high** against its group, by the thresholds sales are flagged at (2 standard deviations; or 0.35× / 4× the median, which matter in a small group, whose spread the outlier itself stretches: a $10 deed among $300,000 houses is low), and each gets exactly one of the five patterns: **1** odd price per area and odd size (the size is likely wrong); **2** low price, low price per area (likely not a market sale: foreclosure, between family, a partial interest; or worse condition than recorded); **3** high, high (likely more than this parcel: several parcels, business assets, a related party, a partial interest scaled up); **4** ordinary price, high per area (finished area under-recorded, or unrecorded upgrades); **5** ordinary price, low per area (finished area over-recorded, or several parcels' areas added). One fitting none is **flagged but left in**: it counts unless the user excludes it. (OpenAVMKit's classic reading counts any price below the median as low and its size test always passes, so a sale could show several patterns; engine A6b.)
  - **And a second look** (`passes: 2`): a sale far off its cluster can stretch the cluster's spread so much that another far-off sale doesn't stand out (1502 Colonial Ave, $2.43 per sq ft, beside a sale at several times the median). Each cluster that had a sale set aside is compared again without it.
  - **Always flag, then decide** (below): OAK box never lets OpenAVMKit drop a sale the user hasn't seen.
- **No checks before running** (removed 2026-10-31): sales sold vacant on parcels improved now (and the reverse) are pointed out on Data › Sales, sales for parcels not in the parcel universe on Data's Sales and Condo units steps, and a group's sales in the window on Time adjustment.

**Run:** **Check sales** (like Bring in data: progress per part with what it's doing, heartbeat, Stop; per model group inside each part, which needs engine progress events in clustering, time adjustment and scrutiny). No part can be skipped: each one's output is needed downstream.

**Receipt:**
- **The sales funnel,** continuing from Bring in data's: valid sales from Data → outside the sales window (improved, vacant) → invalid by your rules → set aside by scrutiny, by check and by pattern (each **See them**) → kept by you (+) → excluded by you (−) → **= sales for modeling**, per model group in a table beside it (sales, set aside, used, time adjustment per year, clusters).
- **Far from their group, by pattern:** the five-pattern table, all model groups or one: each pattern's sales and % of sales, its likely cause and what to check first, **See them**; then the flagged total. Sales flagged but left in are said under the funnel, with **See them**.
- **Time adjustment:** the chart per model group (above), with **Show schedule** (the daily factors).
- **Filled:** per field, how many values in each model group were filled, and how.
- **Equity clusters:** per model group, how many, their typical size; ones under 15 parcels said.
- **Rare categories folded,** per field.
- OpenAVMKit's own notes, folded; the files written (and the per-group scrutiny reports OpenAVMKit writes, `out/sales_scrutiny/<group>/`, for the record), **Show in folder**.

**Review: the sales set aside (the sales register of §3.6, first used here).** A list and a map of every sale set aside, filterable by model group, check, pattern and status, each in plain words with its numbers, e.g. "Sold for $41 per sq ft; the 23 similar sales nearby went for $118 (median). 2,400 sq ft, built 1978, Elm St." The cluster's other sales on the map and in a small table beside it, the sale's own data (to spot a wrong size or year), and its deed and dates.
- **Its diagnosis:** the readings table (price, price per area, size: this sale, its group's median, standard deviations from it, low / in range / high); its pattern with the likely cause and a checklist of what to check; for the other checks what they found ("built 2023", the shared surname, "67% of the median improved sale"); buyer and seller.
- **Recorded with it** (a sale set aside as same deed, same day, or same day, same price): the sales on its deed that day (or the same day at the same price), itself first, with model group, price, finished and land area; **Open it** on each one set aside too; "Each recorded at $10: likely the price of all 13 parcels together" (or their total).
- **Related sales:** the same deed; the same day within 500 ft; the same day to the same buyer; the same buyer within a year (with how far away, and whether set aside too): a sale of several parcels, or an investor's.
- **Look at it:** **Street View** and **Aerial** (Google Maps at its coordinates), **Zillow** (by address) and **Redfin** (no address link: the first Redfin search result), in one viewer window beside the app, reused from sale to sale (a browser tab outside the desktop app). Those sites refuse to be shown inside another page, so they can't share one window.
- **Keep** (a note required): it counts after all. **Exclude** any sale, set aside or not (a note optional). Each says that it applies on the next **Check sales** run (seconds).
- **What it writes:** kept sales go in a keep-list (engine A6: `analysis.sales_scrutiny.keep_file`, a CSV of `key_sale`), exclusions in `invalid_key_file`; both in `in/`, so notebook users get the same sales. Overrides survive re-runs; a kept sale stays kept only while the same check still sets it aside (otherwise it's just counted).
- **Looks right** marks step 3 done, as F5.

**Out of date when** Model groups runs again or anything on this tab changes; it says which. Step 4 and 5 then wait for it (§6.4).

**Engine changes** (built on `engine/enrich-fixes`, up to commit `9fc828a`; then upstream). Anything generally useful is built in the engine, not OAK box:
- **A6, scrutiny for review (built):** drops as settings (`analysis.sales_scrutiny.drop.clusters`, `.drop.heuristics`); a `keep_file` (CSV of `key_sale`) whose sales are flagged but never dropped; every sale a check flagged, kept or dropped alike, in `out/sales_scrutiny/flags.parquet`: `check` (`dupe_deed_date`, `dupe_date_price`, `false_vacant`, `excluded`, `cluster`), and for clusters `count`, `price`, `price_per_area`, `median`, `stdev`, `relative_ratio`, `med_dist_stdevs`, `rules` (thresholds crossed), `pattern` (anomaly 1–5), `scrutiny_pass`; then `kept`, `dropped`. Before, with drops off a flagged sale stayed valid and reached modeling, and the heuristics' flags existed only in Excel files. OAK box runs with drops on, the keep-list holding the user's keeps, so a sale set aside never reaches modeling unless kept (§3.6's rule).
- **Outliers hidden by another outlier (built):** `analysis.sales_scrutiny.passes: 2` compares each cluster that had a sale flagged again, without it, on the ratio thresholds only (4× the median; 0.35× and a deviation below). On the sample it finds 6 more single-family sales, all far off (four sold for about $12; 1502 Colonial Ave at $2.43 per sq ft), and nothing ordinary. With 2 deviations in the second pass it set aside 25, many at 1.3–1.5× the median (a small cluster without its outlier has a narrow spread), so that's not used. OAK box sets `passes: 2`; the review says "found once the sale that hid it was set aside".
- **Each heuristic on or off (built):** `analysis.sales_scrutiny.heuristics.<name>: false` (`dupe_deed_date`, `dupe_date_price`, `false_vacant`); the sold-as-vacant check is skipped, with a warning, when there's no year built (it failed the run).
- **A6b, scrutiny as a diagnosis (built, opt-in):** `patterns: "strict"` (the readings and one pattern each, or `other`: `flag_only`, never dropped; the readings and the group's median price and size in the flags file); new heuristics, off unless turned on: `built_after_sale`, `vacant_priced_improved` (`share`, `location`, `min_sales`), `same_surname` (`pattern`, `skip_words`; `surnames()`; the `deed_grantor_surname` / `deed_grantee_surname` fields win where filled; a name of several people is split on & ; / AND, a one-word part sharing another's surname; names with LLC, TRUST, BANK, COUNTY… aren't people). Heuristic flags carry a `detail`. OAK box turns all of it on.
- **Template key (fixed):** the template's never-read `fields_categorical_improved` is `fields_categorical`.
- **Progress per model group (built):** `do_per_model_group` reports which group it's on (`progress.detail`: "Scrutinizing sales: single_family (6 of 6)", with the step's own completion), so time adjustment, equity clusters and scrutiny say where they are.
- **B9, provenance flags for fills (built):** `out/filled.parquet`, `key` and a column per field with any value filled, true where it was blank before.
- **Also fixed:** a model group with no flagged sales lost its sales from the scrutiny output and report counts; the cluster output now includes each cluster's median.
- **Reports (OAK box side):** scrutiny's PDF reports need wkhtmltopdf (they warn without it); OAK box asks for Markdown only (`analysis.report.formats`) until Typst (A5).

**As built** (`src/oakbox/clean.py`, `web/src/screens/CheckSales.tsx`): the tab opens once Model groups has Looks right (Looks right there moves on to it).
- **One task at a time** (the frame of F5): a step per call, **Sales window** (with the checks before running; ⚠ while there are any) › **Time adjustment** (the preview) › **Sales scrutiny** (⚠ with no location) › **Check sales** (the run: **Check sales ›** where Next is, then **The sales** opens) › **The sales** (the funnel, by model group, the files) › **Sales set aside** (the review; ⚠ while any is undecided), whose Next is **Looks right › Check my values** (it opens step 4; once pressed, **Check my values ›**). The note and Keep, Exclude and Next are pinned to the bottom of the window, so Next stays put from sale to sale, and each sale opens at its top. **See them** on the funnel opens Sales set aside filtered by that check.
- **The calls** are the project's `clean` state. Nothing is written to settings.json until the step is first used; then the proposals (fills, the location, the categories to fold) are written down and every call is explicit. Fills are added to OpenAVMKit's own fill lists (`+median`), never replacing them. The keeps and exclusions are `in/oakbox/keep.csv` and `in/oakbox/exclude.csv` (`key_sale, note`). The calls don't put Bring in data or Model groups out of date (they're left out of those steps' settings hashes).
- **The run** (`python -m oakbox.clean <id>`) calls OpenAVMKit's clean stage part by part, so each part is counted: fill, equity clusters, sales (window, validity, time adjustment), scrutiny, rare categories, then the 2-clean hand-off. Progress names the model group each part is on. About 25 seconds on the Guilford sample.
- **The receipt:** the funnel adds up from the valid sales to the sales for modeling, each check counted once at the first, kept sales added back, exclusions taken off. The model-group table includes **No parcel**, the sales whose parcel isn't in the parcel universe: they stay in OpenAVMKit's sales but no model can use them (386 on the sample, condo units switched off on the copy). Then the time adjustment charts (from each group's schedule; **Show schedule** shows the CSV), what was filled (from `out/filled.parquet`), and the files written.
- **The review:** the sales set aside (and those flagged but left in), furthest from their group first, filtered by model group, check or pattern, and status. Each sale shows why, in words from its checks; its readings and pattern with what to check; Street View, the aerial, Zillow and Redfin; a dot plot (log scale) and a table of the sales it was compared with; its related sales; and its own data. On the sample: every sale far from its group fits a pattern (8, 36, 21, 12, 7), 98 share a surname, 7 were built after their sale. Said first (revised 2026-10-31): every sale here is out (the models don't learn from it, the ratio studies leave it out) because a check flagged it; one not decided stays out for as long as a check flags it. Each sale says where it stands now ("out, set aside by the checks. Not decided"; "put back"; "left out for good"). **Put it back** (OpenAVMKit's keep file: flagged, never dropped) needs a note saying why it's a market sale; **Leave it out for good** (its invalid-sales file: out whatever the checks say later) can have one; **Undo**. Both apply on the next run, and the tab says so. The status filter: Not decided: out for now, Put back, Left out for good.
- **No checks before running:** what they said is shown where it's fixed (Data, Time adjustment).

**Not built yet:** a sales window per model group; the granularity OpenAVMKit settled on per group; a map of the sales set aside; excluding a sale that wasn't set aside (the API takes any sale; the review only lists sales set aside); "vacant at sale = vacant now" as Data's assumption, which needs OpenAVMKit to take a sale's vacancy from its parcel. OpenAVMKit's own notes are listed raw.

**Not in this step:** street frontages, spatial lag and area statistics (step 5), the ratio study (step 4), model outliers (step 5's review, in the same register).

#### F8. Step 4, Check my values (its own tab, **4 Check my values**; built, but for the parts under "Not built yet")
It opens once Check sales has Looks right. The assessor's own values, against what parcels sold for, checked the way a state reviewer would: nothing is modeled. openratiostudy.com (`larsiusprime/openratiostudy`) is the reference for the statistics and views.
- **Only with existing values** (revised 2026-10-31): the tab is greyed, its tip saying "No existing values to check: add them on Data › Existing values", until a value set has a market value. Model values doesn't wait for it.
- **What to check** (first): **Check them** or **Skip this step** (Next becomes **Go to Model values ›**; the step's parts are greyed); which value sets (MultiPick, every one by default) and which model groups (every one by default; the studies, overall included, are of those groups only). Only market values are checked: land and improvement values aren't sold on their own.
- **Several sets:** the results show one set at a time, a switch at the top of each part; the choice stays as you go from part to part.
- **One task at a time:** **What to check** › **Which sales** › **Whose standards** › **The standards** › **Which groups** › **Check my values** (the run) › **Summary** › **By model group** › **Across prices** › **On the map** › **Neighbourhood price levels** › **Similar parcels** › **Extreme ratios**, whose Next is **Looks right › Model values** (it opens step 5; once pressed, **Model values ›**).
- **Which sales:** the sales Check sales kept for modeling, in the window, valid for a ratio study (the parcel looks as it did when sold). The window is two date pickers. Proposed: from the year before the valuation date (the IAAO's window), reaching back a year at a time (up to five) until it holds 30 sales; when the IAAO's year has none it says so ("the latest sale is 2024-11-09"); **Back to the proposed window**. The price: **as sold** (default, the formal ratio study) or brought to the valuation date with Check sales' time adjustment. A small count: for modeling, − outside the window, − the parcel changed since, = sales the values answer to; and per model group.
- **Standards, in three parts** (revised 2026-10-31). **Whose standards:** **The IAAO's** or **Custom** (a state's, an office's), Custom starting from the IAAO's figures or empty. **The standards:** a row per standard, its name and every target changeable: level (median ratio from–to; missed only when the median's whole 90% range is outside, 11.1), uniformity (COD from–to: above missed, below suspect, possibly sales chasing, 11.2.5), PRB good within ± and unacceptable outside ± (neither between), VEI within ± % (missed only when significantly outside, Appendix E steps 5 to 7), judged with at least N sales; each heading's tip says what it means; **Remove**, **Add a standard**, **Back to the IAAO's**; the PRD and MKI reported, not judged (Table 4); trimming below. The IAAO's are one standard per property category (Table 7): residential 5 to 15, homogeneous (condos) 4 to 10, rural or manufactured 10 to 20, apartments 7 to 20, commercial 10 to 25, vacant land 10 to 20, agricultural 10 to 25, each level 0.90 to 1.10, PRB ±0.05 / ±0.10, VEI ±10%, 5 sales. **Which groups:** a model-group picker per standard (only groups modeled and checked), proposed from the groups' names until one is chosen (then every standard's are as shown); a group in one standard at most; a group in none is shown, not judged, and named. OpenAVMKit judges each group by its standard's own targets (`standards.by_class`, `engine/enrich-fixes`), and Model values pills its figures the same way. Outlying ratios are trimmed (on by default) as Appendix C sets out: beyond 1.5 × IQR with the Standard's quartile positions, at most a tenth of a group, the furthest first. The statistics without them are judged; every sale's are shown beside them, never compared (C.6).
- **The run** (`python -m oakbox.ratio <id>`): OpenAVMKit's `run_value_field_studies` on `out/2-clean-sup.pickle`, with the window, the price, trimming, the IAAO's order-statistic interval for the median (`median_ci="iaao"`, as openratiostudy) and the targets; a few seconds. Writes `out/oakbox/ratio/` (the receipt, OpenAVMKit's study files, every sale studied with its ratio).
- **Pills never move a figure:** in By model group, each figure's pill sits at the cell's left edge and the figure at its right. **Across prices** draws the VEI's groups as a chart too (median and 90% range per group).
- **Summary:** a paragraph a board member can read ("Assessed market values are about 67% of what parcels sold for, 2024-01-01 to 2025-12-31. That's outside the 90% to 110% the standard asks for in every model group judged. Not uniform enough: Single-family (COD 19.2). No significant vertical inequity."), then a scorecard: a row per model group, a column per question (**Level**: the median ratio; **Uniformity**: the COD; **Cheaper vs dearer**: the VEI, or the PRB with too few sales for it), each cell the pill every judged figure wears (✓ met, ~ near, ✗ missed, as in How they did; the PRB between good and unacceptable is ~), the figure and a word ("too low", "too varied", "no significant difference") in the same place on every row, so groups compare down a column; what each measures is in the header's tip. Groups with too few sales or none say so across the row. Nominal prices among the trimmed sales are pointed out (Check sales now sets them aside first).
- **By model group:** sales, trimmed, median ratio, its 90% range, COD, VEI (with its reading: compliant, not significant, regressive, progressive, too few sales), PRB, PRD and MKI; the judged ones with ✓ / ✗, every sale's figure beneath each ("all"); all groups as the total. Headers explain themselves on hover.
- **Across prices:** per model group, each sale's ratio against its price (log scale; trimmed in grey), the median of each fifth of sales by price, the standard's level band; the fifths as a table; the VEI's groups by value with their medians and 90% ranges.
- **On the map** and **Neighbourhood price levels** (openratiostudy's further analysis): each sale where its parcel is, coloured by its ratio in openratiostudy's colours (blue under 1, white at 1, red over; trimmed grey), per model group or all; and the median ratio by the price level of each sale's neighbourhood (the neighbourhood's median market value proxy), sales grouped as openratiostudy groups them (2, 4 or 10 groups by the number of sales, as the VEI; a neighbourhood never split), cheapest to dearest, drawn as the VEI's chart (each group's median with its 90% range) beside the same chart by each sale's own price level, then the table: flat by neighbourhood while the VEI by sale isn't points to invalid sales, not real inequity. Neighbourhoods by a location field (Check sales' by default; changing it checks again); without one it points to Data › Location. Engine: `region` on `run_value_field_studies`.
- **Similar parcels:** horizontal equity from the equity clusters: parcels, groups of similar parcels, the median spread (CHD); shown, not judged (the IAAO sets no target).
- **Extreme ratios:** the trimmed sales, furthest first, nominal prices said; **Exclude in Check sales** marks the sale excluded (it applies when Check sales runs again).
- **Out of date when** Check sales runs again or a call changes.
- **Engine (built, opt-in; `engine/enrich-fixes`):** `run_value_field_studies` gained `sale_field`, `trim_outliers` (the trimmed study beside every sale's, the trimmed sales listed, a per-sale table; quartiles as Appendix C.4, `trim_share`), `median_ci="iaao"`, `standards` / `classes` with `IAAO_STANDARDS` (the draft's targets; a `verdict` per group, both ways), VEI percentile groups and reading (Appendix E), the MKI (`calc_mki`), `region` (neighbourhood price levels). Fixed: the VEI's market value proxy is the average of price and median-adjusted value. (The draft prints it as 0.50·SP + AV/median, but says equal weight, as its PRB definition does; its worked example gives the same groups either way.) Checked against the draft: its demonstration report (Table 6: median 0.868, 90% range 0.787 to 0.984, COD 24.65, PRD 0.993, PRB 0.1871 with 95% range 0.0665 to 0.3078, VEI 48.53%, significance 17.57%) and its trimming example (Tables 9 and 10) are reproduced exactly, as engine tests.
- **openratiostudy.com, settled:** OAK box and OpenAVMKit follow the IAAO: the PRB is the Standard's (percentage deviation from the median regressed on log2 of the value proxy), not a regression of the ratio on ln(price); VEI significance compares the groups with the highest and lowest medians (Appendix E step 7), not always the last and first; trimmed and untrimmed are both shown. openratiostudy itself is unchanged for now.
- **On the sample** (2024 to 2025, 181 sales): values are about 67% of prices; single-family COD 19.2, PRB +0.056, VEI +24.3% inconclusive; a $10 deed (2901 St Regis Rd) that Check sales kept is trimmed and pointed out.

**Not built yet:** breakdowns by neighbourhood; the PDF report (step 6); land values against vacant land sales; model values side by side (step 5).

#### F7. Step 5, Variables: Prepare the fields (its own tab, **5 Variables**; the tests, lists and models are F9)
It opens once Check sales has Looks right. Steps: **Fill blanks** › **Rare categories** › **Prepare the fields** (the run) › **What changed** (Looks right) › **Test the variables** › **Variable lists** (F9). **6 Model values** (the models, a try, how they did) opens once What changed has Looks right (revised 2026-10-31: the variables are a tab of their own).
- **Why here:** they're notebook 2's first and last calls in OpenAVMKit's order, but nothing in Check sales depends on them (the equity groups and the sales checks compare land size, finished area, quality, age and condition, which aren't filled here). Some models fail on a blank (the linear ones); the others read it as unknown.
- **Fill blanks:** each number the models can use that's blank somewhere after step 2, with what a blank means and a proposal from it: zero where blank means none (renovation permits: `renovation_num`); leave blank where there's nothing to stand in (`days_to_*`: no permit, no date; `land_area_alloc_*`: only condo units have a share of land; finished area and year built: blank means no building); the model group's median for census fields (a block group not matched), elevation and slope (a tile not covering the parcel) and the rest. Changeable to median, mean, most common, zero, smallest, largest or leave blank, for every parcel or only improved or only vacant ones. Written as OpenAVMKit's `data.process.fill` lists, added to its own (`+median`).
- **Rare categories:** off by default. The category fields the models use, but not locations, the model group, IDs and addresses (or anything with more distinct values than half the parcels), or dates. With the thresholds (fewer sales than, fewer parcels than), a table per field: its values, how many fold, their parcels, and which ("Become Other"), counted on the sales Check sales kept, as OpenAVMKit counts them.
- **Prepare the fields:** OpenAVMKit's `fill_unknown_values_sup` and `collapse_sparse_categories_sup` on Check sales' hand-off (`out/oakbox/clean/sup.pickle`), in a process of its own (`python -m oakbox.prepare`), then notebook 2's output written again (`out/2-clean-sup.pickle`, `out/look/2-clean-*`): the same as notebook 2 writes with the same settings. Out of date when Check sales runs again or a fill or the folding changes. The receipt: what was filled (per field, how many, how) and folded (per field, the values and their parcels), and the files.

#### F9. Step 5, Build model values: the models (spec; not built)
What stands between Prepare the fields (F7) and values a model made, and how step 5 continues. It replaces §3.10's earlier draft where they differ.

**The spike** (2026-10-29, the sample: 7,994 parcels, 1,477 sales; Prepare's output; a hand-written variable list of finished area, land area, effective age, units, normalized latitude and longitude, polar coordinates, elevation and slope; LightGBM and local-area with a median ensemble; OpenAVMKit's defaults, 5-fold nested cross-validation): `write_canonical_splits`, then `model_runner.run_models` (try, no vacant models), ran headless in **29 s** and wrote `out/models/`. The plumbing works. What it showed:
1. **No variables, no models.** OpenAVMKit has no default list: `modeling.models.main.default.ind_vars` must be written, or every model raises. Nothing in OAK box writes it yet.
2. **Linear models refuse blanks.** MRA stopped on `slope_mean_deg`, blank on 1 of 359 small multi-family parcels. Trees take blanks; linear models need every variable filled (F7's Fill blanks), so the variable list and the fills must agree before running.
3. **Small groups get no values.** Groups under 15 sales are skipped with a warning: apartments (106 parcels) and public & exempt (564) got no value at all, and Unassigned (22) none either.
4. **Tiny groups get nonsense.** Commercial & industrial, 9 sales for 1,217 parcels: LightGBM's holdout median ratio was −0.12 (COD −2,610); 118 parcels got **negative** values, and the ensemble kept them.
5. **The results are in memory.** `run_models` returns each group's benchmark (per model: sales, median ratio, COD, PRD, PRB, VEI and its significance, trimmed versions; out-of-fold, the holdout); the pipeline's `try_models` and `finalize_models` return nothing, and nothing machine-readable about them is written. `out/models/all_model_groups/universe.parquet` has `model_group_x` and `model_group_y` (a merge that keeps both).
6. **Variables matter more than plumbing.** Single-family holdout COD 34.5 (20.4 trimmed) against the roll's 18.9 in step 4: the sample has no quality or condition. Not a blocker for building it; the first thing a user will see.

**Blockers, in order** (each one is work; slice 1 is what it takes to run models from the app):
- **Slice 1, run models and see how they did:**
  - **Variables:** a default list from what's loaded (below), written as `default.ind_vars`; ones with blanks left out of linear models, or filled (a link to Fill blanks).
  - **Models:** a picker with **Choose for me**.
  - **Try:** the run, its own process (`python -m oakbox.model`), with progress per group and model (`progress.report` exists in `_run_models`), Stop, and the results kept as `out/oakbox/model/results.json` from `run_models`' return.
  - **Results:** per model group, the models side by side, with the roll's own value beside them, judged as step 4 judges.
- **Slice 2, values for every parcel and the ones that ship:**
  - **Small groups:** left unvalued by default (below), and no negative values shipped.
  - **Finalize:** `finalize_models`, then the model values checked as step 4 checks the roll's, side by side. **Looks right** ends step 5.
- **Slice 3, working on them:** outliers back into Check sales; testing variables; per-group variables and models; "why this value" from the contributions OpenAVMKit already writes (`contributions_universe.csv`).

**Steps** (the tab continues after What changed): Fill blanks › Rare categories › Prepare the fields › What changed › **Variables** › **Models** › **Try them** (the run) › **How they did** › **Small groups** › **Finalize** (the run) › **Model values** (Looks right).
- **Variables.** One table: each candidate with what it is, its coverage after Prepare, and whether it has blanks left. Ticked by default:
  - **The big five:** finished area, land area, effective age (else age), quality, condition; units for multi-family.
  - **Location:** normalized latitude and longitude, polar radius and angle; the location fields as categories (trees only).
  - **Public data:** elevation, slope, distances (`dist_to_*`), census fields, when brought in.

  Missing ones are skipped and named ("No quality: Data › Building"). Written as `modeling.models.main.default.ind_vars`. Said plainly: OpenAVMKit prunes the default list per group by its own variable tests (`feature_selection`: correlation, VIF, p-value, coefficient sign) before linear models use it; trees keep it all. A variable with blanks is **trees only** unless filled, said on its row with **Fill it…**.
- **Models.** (Superseded 2026-10-31: per-group models and variable lists, as built below.) **Choose for me** (preselected): LightGBM, MRA on log price (`"log": true`, so no negative values) and local-area, median ensemble (settled 2026-10-29). The picker lists each engine in a line: LightGBM, XGBoost, CatBoost (gradient-boosted trees: the most accurate, harder to explain), MRA (a linear model: explainable, needs every variable filled), multi-MRA (one per neighbourhood), GWR (slow), local-area (the neighbourhood's price per area: a baseline). The ensemble combines the chosen models, never the roll's value. Written as `modeling.instructions.main.run` and `.ensemble`. Speed: OpenAVMKit's default (5-fold nested cross-validation) on every size until a Quick tier is measured (M0: fewer folds is slower at 150k+); the run's time is said beforehand from the last run or the parcel count.
- **Try them.** `try` (no values written for keeps), no vacant models (`run_vacant=False`, §3.10). The step shows each group and model as it trains. Before training, each modeled group's variables are checked for infinite (or float-overflowing) values, in its sales and its parcels: any found stop the run, named ("land_area_gis_delta_percent in Single family: 3 sales and 12 parcels (used by LightGBM, MRA)"), never OpenAVMKit's bare "Input contains infinity". Any error while training is reported with what can be said about it: the model group and model it was training (OpenAVMKit's progress says which) and its variable list ("While training LightGBM on Single family, variable list "Houses" (12 variables)"; or "while combining …'s models into the ensemble"); for an infinite value, the variables and prices that could cause it, or, when the data holds none, the variables whose parcels reach far past that group's sales (10 times the sales' spread past their edge: where a log-price model's prediction overflows), furthest first; where it stopped (the last frame in OpenAVMKit, then the last library frames: "OpenAVMKit inference.py:1184 _calculate_metrics › … › validation.py:133 _assert_all_finite"); and the whole traceback in out/oakbox/model_error.txt.
- **How they did.** OpenAVMKit's benchmark, a model group at a time (settled 2026-10-30): models as rows, figures as columns; every heading sorts, every column's edge drags wider (remembered on the computer). A switch between **IAAO** and **Academic** figures; each is a table untrimmed, then a table trimmed, each collapsible; **Timings** collapsible under either. IAAO: the **Holdout** (each sale predicted by a model that never saw it), **After the valuation date** when there are such sales, and the **Study set** (OpenAVMKit's look-back before the valuation date); columns utility score, parcels, sales, median ratio, COD, PRD, PRB, VEI, VEI significance, CHD (where figured); trimmed, in the same columns: sales, median ratio, COD, PRD, PRB, VEI and its significance (utility, parcels and CHD are left blank: none of them is a figure of the trimmed sales). **The roll** (OpenAVMKit's `assessor` model, run whenever the universe has `assr_market_value`) only on the study set, first: the holdout is OpenAVMKit's own draw and the roll may have seen those sales. Academic, on the holdout: sales, MAPE, MSE, RMSE, median and mean ratio, slope (`academic_metrics`; its VEI left out: the IAAO view has it). Median ratio, COD and PRB carry the step 4 pill (✓, ~, ✗ against the project's targets), pinned left; figures written as step 4 writes them (ratios and the PRD to three decimals, the COD to one, the VEI in percent). A group may ship one model instead of the ensemble (the others skipped for that group: `instructions.main.skip.<group>`).
- **Small groups** (any group under 15 sales, or whose models came out implausible: a holdout median ratio outside 0.5 to 2, or a negative value). **Left unvalued** by default (settled 2026-10-29): OpenAVMKit already skips a group with too few sales to fit; OAK box also skips the implausible ones (`instructions.main.skip.<group>`: every model), so a 9-sale group's negative values never ship. Said plainly per group: its parcels (count), why ("9 sales: too few to model"), and that they get no model value; the report and export say the same. **Model it anyway** per group, with its figures shown. (Keeping the roll's value or borrowing another group's model are not offered for now; each would need an engine fallback.)
- **Finalize.** `finalize_models`: writes `out/models/` and the values (`market_value`). Then step 4's study on `market_value` (holdout, by group), shown beside the roll's.
- **Model values** (Looks right): the scorecard, the roll's beside it, how many parcels got a model value, how many are unvalued (and why), and the files.
- **Out of date when** Prepare runs again, or a variable, model or small-group choice changes. Tuning is reused unless **Re-tune** (§3.10); Stop never deletes it.

**As built** (`src/oakbox/model.py`, `varlists.py`, `locstack.py`; `web/src/screens/Variables.tsx`, `VarLists.tsx`, `ModelValues.tsx`, `Models.tsx`, `components/LocationStack.tsx`; revised 2026-10-31): **5 Variables** runs Fill blanks › Rare categories › Prepare the fields › What changed › **Test the variables** › **Variable lists**; What changed's Looks right opens Test the variables. **6 Model values** is **Models** › **Try them** › **How they did**. The one list of ticked variables is gone: each model takes a variable list.
- **The variables there are:** every field OpenAVMKit classifies as land, building or other (`field_classification`, with the user's own fields, map layers' and public data's), less identifiers, the roll's values, sale and deed fields, raw coordinates, land area as given or measured, years (ages are offered), Check sales' groups of similar parcels, and distances: each feature's `proximity_to_` is offered instead (it rises near the feature and is 0 beyond the distance that matters; `dist_to_cbd` stays, having none). A category with one value, or more than 50 and over half the parcels, isn't offered; nor a number the same everywhere, nor one infinite anywhere (a ratio over a zero: no model can take it). Only once the fields are prepared.
- **Test the variables** (after What changed; `python -m oakbox.vartest`, a few seconds): OpenAVMKit's own variable tests on each model group's sales (15 or more) with the variables ticked (`get_variable_recommendations(..., return_tests=True)`, engine work below), then the tests as its parts, nested under it in the step list (shown while it's open; the step frame takes a `parent` on a step): **Represented**, **Correlation**, **Redundancy (VIF)**, **What to keep**. **Tests to run**, on the step itself: Represented always; Correlation and Redundancy as the user ticks (both to start, at least one; `tests_to_run`, saved as `model.tests`); a test not run isn't listed, and a change of tests makes the results out of date. OpenAVMKit's other four aren't run (settled 2026-10-30): each mostly repeats one of these: R² on its own is the correlation with price squared; the t-value is the significance test's regression read another way; the elastic net asks again whether a variable adds anything beside the others; signs agree checks those three point the same way. **No significance (p-value) test** (settled 2026-10-31): represented, correlation with price and VIF are what the variable lists need; a p-value judged in one regression of every variable says little about a list. (Engine fix: `tests_to_run` without R² failed while combining the scores.) Each says in a line what it measures and when a variable passes (thresholds from `feature_selection`), with a model group to show (the one with most sales first): a table, a row per variable: a category is one row (its best value's figure, passing if any of its values does, and "2 of 7 values pass", which unfolds its values, each a column to the tests, indented under it), its figure with a pass or fail pill pinned left, and a bar against the threshold (VIF on a log scale). No ticks (revised 2026-10-31): the tests run on every variable, the evidence the variable lists are built from. Recursive tests pass what survives their drops. **Correlation judges the relation to price alone** (revised 2026-10-31): a variable passes with a correlation with sale price of 0.10 or more, either way, whatever it overlaps; overlap is the VIF test's alone (OpenAVMKit `feature_selection.correlation_overlap: false`, `engine/enrich-fixes`: no clarity in the score, no pass dropping a variable more correlated with a stronger one than with price). A failure's pill says **too weak**. **how ›** on any row (or a category's value) unfolds its correlation with price (with a bar and the threshold) and the five variables it moves with most (signed), which VIF judges. **What to keep:** OpenAVMKit's weighted score per variable and model group, and its pick per group (the set that predicts best in cross-validation) as a pill. A variable not tested yet (prepared since) puts the tests out of date. The tests fill a variable's blanks with its median; a variable with no value among a model group's sales (days to renovation where none of its parcels had a permit) has none, and stopped OpenAVMKit's elastic net, failing the whole group: it's left out of that group's tests and named there, with **Fill it…** (and the engine now leaves such a column out of the elastic net, warning, rather than failing).
- **Variable lists** (settled 2026-10-31): named lists of variables, each with a **type**, Regression or Machine learning, and the **model groups** it's for (one list can serve several). A table of the lists (name, type, groups, how many variables, which models take it: "MRA · 5 groups"), one open at a time: its name, type (a switch) and groups (MultiPick); what's recommended for its type; then every variable, ticked in or out, with its kind, Represented, Correlation with price and VIF in one of its groups (**Scores for**, a dropdown of the groups tested, the others named as not tested; the variables in a box of their own that scrolls, so the other lists stay in sight), and a pill: **recommended**, or why not. For a regression: in the sales, a correlation of 0.10 or more, survives VIF (10), no blanks (a linear model can't take one), not a category with more than 8 values ("has blanks", "barely in the sales", "weak with price", "overlaps others", "too many values"); for machine learning: in the sales, and not a category with more than 20 values (CatBoost slows with each). **Tick the recommended for <group>** (what the pills say for the group shown; revised 2026-10-31: it had ticked what's recommended in the groups holding most of the list's sales, which read as haphazard beside another group's pills), **Untick all**. Warnings: a regression list with fewer than 10 sales per variable in one of its groups ("a shorter list of its own would suit it"), variables with blanks on a regression list (left out by its linear models), categories with many values. **Add a variable list** (empty: a regression list with no groups and nothing ticked; until its groups are chosen it says so, and Scores for offers every tested group), **Remove**. **None to start** (revised 2026-10-31; it had proposed a Regression and a Machine learning list of every modeled group): a list's ticks are the same for every group it's for, which a proposed list of every group hid; making them one by one shows it, and a group's own variables are a list of its own. Written to OpenAVMKit's settings as `variable_lists.<id>` (an id from its first name, kept through renames), each model pointing at its list: `"ind_vars": "$$variable_lists.<id>"` (OpenAVMKit resolves `$$` paths as it loads the settings).
- **Models** (settled 2026-10-31): one model group at a time (revised 2026-10-31, were tabs): a header names it plainly ("Model group 2 of 5", its name large, its sales), groups not modeled passed over; the footer's button goes on to the next group ("Small multi-family ›"), Back to the one before; on the last, **Next ›** (to Try them) waits until every group's models have a variable list with variables, the footer naming the groups still without one. Its models in a table (Model · Engine · Variables · **Configuration**): each a name (changeable; the engine's unless given), its engine, and its variable list (a picker: any list, "Regression · 10 variables"), every group starting with **LightGBM** (the first machine-learning list for the group), **MRA** and **Multi-MRA** (the first regression list); a list for other groups or of the other type only when picked; with no list for it yet, a model says **No variable list** (its picker reads Choose a list) and a try is stopped until it has one. Local area takes no list (its areas' price per area); Multi-MRA and Local area take a **location stack** too (below). Under a model, said plainly: a machine-learning list on a regression model or the other way ("it'll run, but…"), its list removed, its list empty (stops a try), the variables with blanks its linear engine leaves out, no locations (Multi-MRA then fits one regression, as MRA does; Local area can't run). **Add a model** (a row: engine, name, list; Add / Cancel), **Remove**, **Copy these models to…** (a group, or every other), **Back to the default models**. Written per group as `modeling.models.main.<group>` (OpenAVMKit takes a group's block in place of the shared one): `default` (the land and finished areas, for Local area and the roll), each model under a key from its name (`{"model": <engine>, "ind_vars": "$$variable_lists.<id>", "log": true, "locations": [...]}`; a linear model whose list has variables with blanks gets the list without them, written out), and the other value sets as `pass_through`. `instructions.main.run` names every group's models (then the roll and the other value sets), `ensemble.models` the models, and `skip.<group>` the models a group hasn't (every one for a group not modeled). The results show each model by its name.
- **Configuration** (settled 2026-10-31; `ModelOptions.tsx`): a model's own settings, as OpenAVMKit reads them from its entry. Its cell: a one-line summary ("log price · intercept · no interactions", "Locations: School district › Neighborhood · …", "50 tuning trials"), what differs from the default in bold, then **Change…**; GWR has "No settings of its own" but for interactions, which it has. **Change…** opens them in a panel under the row, one at a time (**Done**), each saved as it changes: **Fit on log price** (MRA, Multi-MRA; on; `log`), **Intercept** (MRA, Multi-MRA; on; `intercept`), **Interactions** None / Categories × size (MRA, Multi-MRA, GWR; None; `interactions: {"default": …}`: each land category times land area, each building category times finished area), **Trim variables in each area** (Multi-MRA; off; `optimize_vars`), **Tuning trials** (LightGBM, XGBoost, CatBoost; 50, 1 to 500; `n_trials`), **Use the graphics card if there is one** (CatBoost; on; `use_gpu`), and the location stack (Multi-MRA, Local area; moved here from the Variables column). Each with a line on what it does; warned: log price off ("can value parcels below zero"), intercept off, fewer than 20 trials, no locations. Every option the engine reads is written, defaults too (`OPTIONS`, `DEFAULTS` in `model.py`), and only those; a change makes the try out of date; Copy these models to… copies them. Not offered: sales chasing (a test mode), global settings, hand-picked interaction pairs (OpenAVMKit's `interactions.fields`; later, if Categories × size is too blunt). **Layered comps** (OpenAVMKit's `lcomp`, added 2026-11-01): comparable sales as a model, the sales split into ever-closer groups by the list's variables and a parcel valued from the trimmed mean prices of the groups it falls in, the closest weighted most (`layeredcompmodel`'s bagging model: 10 trees, OpenAVMKit's fixed settings). A machine-learning engine like the trees (`ML` in `model.py`): it takes a machine-learning list, blanks and all; no settings of its own (OpenAVMKit doesn't tune it: `n_trials` is unused), so its Configuration cell says so. On the synthetic sample's single-family sales (held out): COD 18.5 against LightGBM's 19.1. **Not offered** of OpenAVMKit's other engines: NGBoost and kernel regression (could be: their libraries are in the bundle), spatial lag and spatial-lag-area (possible now that the spatial lag enrichment is built), naive per-area, mean and median (baselines; Local area serves), ground truth (synthetic data's answer key), garbage and garbage-normal (random predictions, for testing).
- **Location stack** (`components/LocationStack.tsx`, reusable; settled 2026-10-31): the location fields a model reads, shown broadest first under **Whole model group**, written finest first as OpenAVMKit takes them (`locations`); each level with its areas, their median sales, the areas with 15 or more (enough for Multi-MRA's own regression), and whether it nests in the level above ("✓ nests in Neighborhood", or "3 areas span more than one Neighborhood"); ↑ ↓ and Remove per level, **Add a level** from the location fields (the user's own, map layers', census areas). Opened in its model's Configuration panel. Proposed per group: every location field with at least two areas of 15 or more sales in it, fewer areas above more. Preview: `GET /model/stack/{group}?fields=…`.
- **Try them:** `python -m oakbox.model`: the prepared hand-off, `write_canonical_splits`, then `try_models` (no vacant models), with progress per group and model and Stop. 28 s on the sample.
- **How they did:** as above (2026-10-30). The figures are OpenAVMKit's own numbers: the benchmark's frames, read after the engine has printed them (printing no longer turns them into text), and `academic_metrics`. On the study set each model is judged by its holdout predictions (`analysis.ratio_study.study_set_predictions: "holdout"`, an engine opt-in OAK box always sets; Check sales ignores it), like for like with the roll: by OpenAVMKit's default, its predictions on every sale, it would be judged on sales it trained on. The trimmed median ratio and VEI are the benchmark's own too (`median_ratio_trim`, `vei_trim`, `vei_sig_trim`: engine, in its frames, not its printout). Groups with too few sales say so. OpenAVMKit's notes fold away underneath. **Try again**.
- **Small groups** (slice 2; built 2026-10-31, `smallgroups.py`, `SmallGroups.tsx`), after How they did: a row per model group with the try's figures (parcels, sales, the ensemble's holdout median ratio and COD, values below zero) and why it can't be trusted, as pills: fewer than 15 sales ("too few to model"; OpenAVMKit's own floor), no model produced values, no sales held out to judge it by, a holdout median ratio outside 0.5 to 2, values below zero. Both kinds are flagged (settled 2026-10-31): groups ticked on Model groups whose try came out badly, and groups with too few sales. A flagged group is **Leave unvalued** by default, or **Model it anyway** (not offered when no model produced values for it); saved as `model.small`. Under the table, the parcels left unvalued and in which groups, and the parcels in groups modeled anyway that came out below zero. No engine floor (settled 2026-10-31): OpenAVMKit already skips a model on fewer than 15 sales, MRA and Multi-MRA fit log price (never below zero) and the ensemble drops models that don't help; a value below zero that's left is a check, and the parcel stays blank and is counted. The try counts each group's valued parcels and values below zero (the ensemble's universe predictions). The choices apply when the values are made (Finalize, next): the try models every group, to judge it.
- **Small groups' Looks right** (2026-11-01): accepts the try (`model` step's accept), so Finalize starts from it; a try out of date can't be accepted.
- **Finalize** (slice 2; built 2026-11-01, `final.py`, `FinalValues.tsx`): `python -m oakbox.final`, OpenAVMKit's `finalize_models` from the same starting point as Try them (`model.for_models`: the prepared hand-off, the folds, the nearby averages), its saved tuning reused, no vacant models. The groups Small groups leaves unvalued skip every model (`instructions.main.skip`); a value below zero is left blank and counted. Writes `out/oakbox/final/`: the receipt, the studies, and `values.parquet` (each parcel's key, model group, model value, whether it came out below zero, and the roll's). Progress per group and model, and Stop, as Try them. 39 s on the synthetic sample. **Out of date when** the try runs again, a small group's choice changes, or Check my values' window, price, trimming, standards, classes or region change (it's judged as step 4 judges).
- **Model values** (Looks right ends step 6): the values against the sales, as Check my values judges the roll's (step 4's studies, standards and window; `run_value_field_studies` on the hand-off with the values put on each sale), on a set of sales the user picks (**Judged on**, settled 2026-11-01; the report will offer the same three, all by default):
  - **Out of fold:** each sale valued by a model that never saw it (the ensemble's out-of-fold predictions, every trainable sale): honest, every sale.
  - **Held out:** the sales the final models never trained on (under cross-validation, those after the valuation date; with a single split, its test sales), valued by the final models. Greyed when there are none (the synthetic sample has none).
  - **As valued:** every sale, valued by the final models, most of which they trained on: the values as they ship, flattering.
  - The model's scorecard (Check my values' `Scorecard`, under the statistics' own names here, revised 2026-11-01: **Median ratio**, **COD**, **Horizontal equity** (the median CHD within the equity clusters, with a word: alike under 20, some spread under 40, wide spread; shown, not judged, as the IAAO sets no target; of every parcel's value, so the same whichever sales judge them: the final values' for the model, the roll's own for the roll), **Vertical equity** (VEI, or PRB), per group and for all groups), and under it the roll's (the roll if loaded, else the first set of existing values) **on the same sales**: only the sales the model values in that set, so the two compare like for like. Same columns, same widths.
  - **On the map** (2026-11-01): **Show** Ratio (the sales of the set judged on, coloured as on openratiostudy.com, trimmed ones grey), Value per finished area (every parcel, in tenths of the parcels shown, light to dark), or Change from the roll (every parcel, model ÷ roll, blue lower, red higher; not offered with no roll); a model group or all. Hovering a parcel says its group, model value, the roll's, the change and the value per area. Parcels with no model value grey. Read from `values.parquet` (`GET /final/parcels`, as columns) and the set's studied sales (`GET /final/sales`).
  - **What every parcel got:** per group its parcels, how many were valued (or why none: not modeled, left unvalued, too few sales), values left blank below zero, the median change from the roll (model ÷ roll − 1), parcels up or down more than 20%, and the total value beside the roll's on the same parcels. OpenAVMKit's notes fold away underneath.
  - On the synthetic sample (2025's 242 sales): out of fold, single-family median 0.945 and COD 13.2, VEI −2.1% (alike) against the roll's 0.843, 14.1 and −27.5% (dearer valued lower); as valued, COD 8.9 overall (flattering, as expected). 7,302 of 9,332 parcels valued; single-family up 13.1% from the roll at the median.
- **Out of date when** Prepare runs again, or a list, a model or a stack changes.
- On the sample: every model's level is in range where the roll's is about 0.74, but none is uniform enough (single-family ensemble COD 33.7 against the roll's 27.3 on the same 826 sales): no quality or condition in the sample.

**Engine work** (opt-in, defaults unchanged):
- **Correlation's first pass:** `calc_correlations(..., min_strength=)` / `correlation_strength`, and its correlation matrix returned. **Done** (`engine/enrich-fixes`).
- **Variable tests one by one:** `get_variable_recommendations(..., return_tests=True)` returns each test's results for every variable before and after its drops, with thresholds, weights and one-hot columns; `calc_representation` keeps its shares as numbers. **Done** (`engine/enrich-fixes`).
- **Results returned:** `try_models` and `finalize_models` return `run_models`' results, and `run_models` returns them without writing them. **Done** (`engine/enrich-fixes`).
- **No negative values:** an opt-in floor (`modeling.instructions.min_value`), with the count clipped reported; and a model whose holdout median ratio is outside a sane range left out of the ensemble (`ensemble.exclude_implausible`).
- **`all_model_groups/universe.parquet`:** one `model_group` column, not `_x` and `_y`.
- **Outliers machine-readable** (C-list B8) and **headless `try_variables`** (C1), for slice 3.

**Settled (2026-10-29):** small groups are left unvalued; one variable list for every group in slice 1 (per-group lists in slice 3). **Revised 2026-10-31:** no Choose for me: every group starts with LightGBM, log MRA and Multi-MRA, each changeable; variable lists serve any groups.

#### F10. Step 7, Report (its own tab, **7 Report**; built 2026-11-01, `report.py`, `ReportTab.tsx`)
Opens once Model values has had Looks right (the tab waits for it, as the others do). Reads Finalize's output; runs nothing. Two steps:
- **Export:** every parcel, one row each: key, model group, model value, the roll's value, change from the roll (%), value per finished area, why there's no value (not modeled, left unvalued, below zero…), the latest sale in the study window (price, date) and the ratio of the value as made to it, latitude and longitude. **Format** (a switch): CSV, GeoPackage, Excel, Shapefile, GeoParquet; GIS formats carry each parcel's shape (Bring in data's), or a point where there's none (said). Written to `out/oakbox/report/export/<project>_<year>_model_values.<ext>`, with **Show in folder**. Shapefile: names cut to 10 characters with a `_fields.csv` key, a warning over 2 GB. Excel: split across sheets past 1,048,575 rows. On the synthetic sample (9,354 parcels): CSV 0.1 s, Excel 1.3 s, GeoPackage 1.4 s (7 MB).
- **Report:** a printable HTML page (settled 2026-11-01: HTML first, as good-looking as it can be made; Typst only if it falls short), previewed in the step, **Open in browser to print** (print, or save as PDF), and written to `out/oakbox/report/`. Calls: its **Title** (made from the project's name to start) and **Judge the values on** (the user decides: out of fold, held out, as valued; all three to start; at least one), saved as `project.report`. Its parts:
  - **In brief** (a board member's page): how many parcels got a value, then per model group a sentence with the figures and targets ("Single-family: values sit at 0.945 of sale prices at the median (low; target 0.95 to 1.10), COD 13.2 (uniform; target 5 to 15), dearer and cheaper alike (VEI −2.1%); 158 sales. The roll on the same sales: 0.843, COD 14.1."), groups with too few sales or none said so, and the groups with no model value and why. A set chosen with no sales is said, not dropped.
  - **Judged on … sales**, one per set chosen: per group, model values and the roll's on the same sales (in italics): sales, median ratio and its 90% interval, COD, PRD, PRB, VEI, CHD, vertical equity in words; marks that read in black and white (✓ met, ✗ missed, none: not judged).
  - **Across prices:** the median ratio by fifths of the sales by price, per group, against the target band (SVG).
  - **On the map:** each sale of the first set, by its ratio (SVG, no tiles: it prints).
  - **What every parcel got:** as on Model values.
  - **How the values were made:** the files, the sales kept and set aside, time adjustment, the ratio study's window and trimming, the standards, each group's models (and their variable lists), the variables, and what each statistic means.
  - Letter pages, a page break before the long sections, system fonts; the footer names OpenAVMKit's version and when the values were finalized.
- Not yet: picking sections, a logo and header text, filtering by location or class, saved presets and editable templates (§4.3).

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

A tab asked for that waits on an earlier step (it isn't accepted on an up-to-date run) opens the first step, in order, that isn't, with a notice above the tabs saying why: "Variables waits for Bring in data. Bring in data is out of date: run it again, then press Looks right. What changed: fields worked out after the files join." Never a silent switch to another tab (revised 2026-10-31). Bring in data always names what changed; a change no line names (a newer OAK box writing the step's settings differently) is "how OAK box writes this step's settings (a newer OAK box)". Opening a project rewrites its settings.json if this OAK box would write it differently, so what that changes shows on opening, not at the next unrelated change (a Variables tick once put Bring in data out of date this way, and the screen jumped to Check sales).

| Step | What runs (OpenAVMKit stage boundaries) | Internet? |
|------|------------------------------------------|-----------|
| 1. Bring in data | Load, merge, condo handling, enrichment (§3.12). The street enrichment is explicitly off. Ends before model group tagging. Then Data health and Field profile (§3.9) | Only for online enrichments |
| 2. Define model groups | Model group tagging (§3.5). Writes the 1-assemble hand-off | No |
| 3. Check sales | Clean, in OpenAVMKit's order: OpenAVMKit's own fills (the user's are step 5's), equity clusters, sale processing (sales window, validity rules, **time adjustment**), scrutiny (sales set aside, minus the user's keeps, plus their exclusions: §3.6, F6). Writes the 2-clean hand-off (rare categories: step 5) | No |
| 4. Check my values | Ratio, vertical-equity and horizontal-equity studies on the named value fields, per model group and overall (§4.2). Reads the 2-clean hand-off explicitly, never stale step-5 output | No |
| 5. Build model values | Prepare the fields (the user's fills, rare categories: F7), then splits, spatial lag, area stats, optional variable testing (§3.10), **Try** models (repeatable) → outlier review → **Finalize** → ratio study on model values. Main models only (`run_vacant=False`) | No |
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
*Superseded by §3.0 F9 where they differ (the variables, models, small groups and the steps); kept for Re-tune, speed tiers and total value only.*

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
- **Spatial lag: built (2026-11-01), as Variables › Nearby sales and buildings**, after What changed (Prepare accepted). **On by default** (a tick: "Average nearby sales and buildings"; off writes nothing and offers nothing). OpenAVMKit's `enrich_sup_spatial_lag`: the k nearest of each, however far, weighted by distance (a Gaussian whose width is their mean distance, so it adapts to density). OpenAVMKit's `BANDWIDTH_MILES` (half a mile) only scales the `_confidence` columns, not the averages: there is no distance limit (an earlier note here, and the step's text, said otherwise; corrected 2026-11-01).
  - **How many nearest** (a number box, 5 to start, 1 to 50; added 2026-11-01; `LagState.k`): one k for every average, written as `spatial_lag.sale_price` (the price averages) and each `fields` entry. The step's notes follow it ("Averages the 8 nearest of each", "9 or fewer sales"). A distance limit isn't offered: it needs an engine setting (proposed, not built).
  - **What it adds**, as variables (kind: location; in any variable list, tested like the rest): **Nearby sale price** and **Nearby price per finished sq ft** (from the sales), then, from the parcels, nearby finished area, land area, floor area ratio, bedrooms per land area, building age, effective age, quality and condition: those whose fields are there. Not offered: the land and vacant-land price averages (they need vacant sales, which are few), and OpenAVMKit's `_confidence` columns.
  - **Averages** (a MultiPick, every one picked to start; revised 2026-11-01): which of OpenAVMKit's own averages are worked out and offered. Written with OpenAVMKit's `spatial_lag.only: true` (`engine/enrich-fixes`), so only those picked (and those under Also average) are worked out: the price ones as `sales` (`"price"`, `"price_impr"`), the parcels' as `fields` (k nearest each), only for fields the prepared data has. One not picked leaves any list it was in. Stored as the ones skipped (`LagState.skip`), so an average newly there (quality, once a quality field is loaded) starts picked. On the synthetic sample: 8 columns instead of 11. The picker's names leave out "Nearby" (the step says it once) and its summary is the first picked and a count ("Sale price + 6 other fields"); as variables they keep it.
  - **Names:** the price averages are offered under a plain name (`spatial_lag_sale_price…`) and written as OpenAVMKit names them, after the price averaged (`spatial_lag_sale_price_time_adj…` when Check sales adjusts prices), so a list survives time adjustment being turned off or on.
  - **Per model group** (a table: group, sales, **Averages the sales of**): its own always; others added with a MultiPick ("Its own only" to start). `data.process.enrich.spatial_lag.model_groups.<group>.sample_from`.
  - **Also average:** more numbers of the parcels around each one, besides OpenAVMKit's own (a MultiPick, **nothing to start**): `spatial_lag.fields`, k nearest each.
  - **When:** as the models run, after the sales are split (Try them, and Test the variables, which also split): a sale's nearby price comes only from training sales outside its own fold, so a model never sees the price it's judged on. Bring in data's settings leave it out (it doesn't put Bring in data out of date); Test the variables and Try them are out of date when it changes.
  - **Too few sales:** with k + 1 or fewer training sales to average, OpenAVMKit writes 0 for every parcel. Test the variables leaves such a variable out for that group (named); Try them leaves it out of that group's models for the run (the settings file unchanged) and says so in its notes ("Apartments: Nearby sale price, Nearby price per finished sq ft left out of its models: too few of its sales to average (0 for every parcel). Let it borrow another group's sales"); a model left with no variable stops the run, saying so.
  - **Small groups:** OpenAVMKit looks up each parcel's k nearest parcels in its group and stops on a smaller group (an IndexError); a group with fewer than 10 parcels, or than twice k, is left out of the lag for the run (nor borrowed from), and its models do without, said as above.
  - On the synthetic sample (9,354 parcels, 1,770 sales) it takes 1.6 s.
- **Area stats** (not built): the chosen location fields × price and size medians. **Advanced:** locations, fields, statistics, minimum count.

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

### 3.14 Menus and window

Inside a project: the oak band (▒) with the plate on it (D21), the folder tabs standing on its edge, and the open one (here Model groups) running into the page:

```
┌ Travis County 2026 – OAK box ───────────────────────────────────────── _ □ × ┐
│ File  View  Project  Help                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ╔═════════════════════════════════════════════════╗ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ║ ⊘ OAK box │ Travis County 2026 · Tax year 2026 ⊘ ║ the plate: where you  ▒│
│▒ ╚═════════════════════════════════════════════════╝ are, and home          ▒│
│▒ ┌──────────┬──────┬────────────┬────────────────┬─────────┬──────────────┐ ▒│
│▒ │ Metadata │ Data │ 1 Bring in │ 2 Model groups │ 3 Check │ 4 … 7 locked │ ▒│
├──┴──────────┴──────┴────────────┘                └─────────┴──────────────┴──┤
│  Model groups waits for Bring in data… (only when the tab asked for waits)   │
│ ┌────────────────┬─────────────────────────────────────────────────────────┐ │
│ │ ✓ How to start │ STEP 2 OF 7                                             │ │
│ │ ▸ Build them   │ Model groups                                            │ │
│ │   …            │ …                                                       │ │
```

On Projects and New project the band carries the plate alone, the page below it:

```
┌ OAK box ───────────────────────────────────────────────────────── _ □ × ┐
│ File  View  Project  Help                                               │
├─────────────────────────────────────────────────────────────────────────┤
│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ╔══════════════════════════╗ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ║ ⊘ OAK box │ Projects   ⊘ ║ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ╚══════════════════════════╝ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
├─────────────────────────────────────────────────────────────────────────┤
│ ┌ Projects ────────────────────────────────────────── [+ New project] ┐ │
│ │ Travis County 2026 · Tax year 2026  [Open] [Show in folder] [Delete]│ │
```

- **File:** New project… (Ctrl+N), Open recent ▸ (the last projects opened), Show project folder, Close project (back to Projects), Exit.
- **View:** Density ▸ Compact · Comfortable; Large text; High contrast (the existing modes from §3.4, now switchable here).
- **Project:** Metadata (Ctrl+1), Data (Ctrl+2), Add a file…. Greyed out on the home screen.
- **Help:** OpenAVMKit documentation (opens in the browser), About OAK box (version, OpenAVMKit version, licences).
- **No Edit menu.** Ctrl+C / V / X / A work in text boxes without one on Windows and Linux. On macOS, where the shortcuts need an Edit menu, pywebview adds the standard one itself; OAK box's own View menu replaces pywebview's default one there.
- **No Undo or Save:** changes save as they are made, and a partial undo would mislead.
- **The title** changes with the screen: "OAK box" on Projects and New project, "<project name> – OAK box" inside a project.
- **Built (Windows and Linux):** real native menu bars from one definition (`oakbox/menus.py`):
  - Windows: the Win32 menu bar on pywebview's window, using .NET's classic `MainMenu` (`oakbox/winmenu.py`).
  - Linux: pywebview runs on Qt (PySide6, LGPL), and the menus are Qt's own menu bar on its window (`oakbox/qtmenu.py`). See §6.1 for the window.
  - Shortcut labels (Ctrl+N, Ctrl+1, Ctrl+2), Alt-key letters, check marks (Large text, High contrast), radio items (Density), and Project items greyed out on the home screen.
  - Each menu is brought up to date as it opens. That includes **Open recent**: the last 8 projects opened, kept in OAK box's settings.
  - The web view keeps the keyboard, so the page handles the shortcuts and passes Alt (+ a letter) on to the menu bar.
  - Python owns what the menus show. View items save the setting there and tell the page to restyle; the page says which project is open.
  - CI opens the real window on Windows, and on Linux under a virtual display, and clicks through the menus (`python -m oakbox --selftest-menus`). The keyboard (Alt, Alt+letter, Ctrl+N/1/2), which the self-test can't press, was checked by hand on Windows.
- **Elsewhere** (macOS, from source), pywebview's own menus are the fallback: same items, but fixed at start-up (no check marks or greyed items). macOS gets native menus when it gets a native window.

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
- **Rendering:** printable HTML (built 2026-11-01, F10): the browser prints it or saves it as PDF. Typst (open source, a Python wheel with no system install) remains the fallback if HTML can't do what a report needs.
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

- **Python backend, TypeScript frontend** (§6.5). WebView2 ships with Windows 10 through Windows Update; on Linux the window is Qt, or a browser app window (§6.1).
- **The engine runs in a worker process.** OpenAVMKit changes the working folder, uses relative paths, and can crash or run out of memory. The worker is given an explicit project directory and environment (API keys).
- **Large maps.** The app service builds vector tiles on the fly from GeoParquet, so the browser never loads 500k polygons.
- **Packaging:**
  - a standalone CPython build plus pre-installed wheels, with no freezing (PyInstaller struggles with GDAL, PROJ and numba)
  - **Windows:** a per-user Inno Setup installer into `%LOCALAPPDATA%\Oakbox`, with no admin rights, plus a portable `.zip` fallback. Measured in M0: 1.7 GB installed, 544 MB zipped; roughly 350 MB after upstream A13
  - **Linux:** a portable `.tar.gz`. Its launcher installs per user into `~/.local/share/oakbox` and adds a desktop-menu entry (`.desktop` file), with no root. An AppImage may follow. Measured in M0: 2.5 GB installed, 974 MB compressed. 469 MB of that was NVIDIA's NCCL library, which XGBoost's Linux wheel pulls in to train one model across several GPUs. The bundle leaves it out (CPU and single-GPU training don't use it); Qt for the native window adds about 385 MB once trimmed (`packaging/prune_qt.py`). **Revisit with modelling:** an optional download for multi-GPU training (NCCL), offered in the app rather than shipped to everyone (upstream A13)
  - **Both bundles are built on Linux** from one script (`packaging/build_bundle.sh`) and one lockfile. CI smoke-tests each on a clean machine of its platform
- **Projects** are ordinary folders: an OpenAVMKit locality plus `oakbox.json`. Easy to copy, zip and back up.
- **Reproducibility.** Each project records the Oakbox and OpenAVMKit versions and the seed. Versions install side by side.
- **Updates.** **Check for updates** reads GitHub Releases, sending only a plain version request. The user approves each install, and the old version is kept.
- **Privacy.** No telemetry and no crash upload. **Send log to support** builds a zip the user emails themselves.

### 6.1 Cross-platform: Linux now, macOS possible
**Windows text is UTF-8, always.** Most users are on Windows, where Python reads and writes text in the code page (cp1252) unless told otherwise, so a "−" or an "é" can stop a run there and nowhere else. Every text read and write names `encoding="utf-8"` (`tests/test_encoding.py` checks the source). Every Python process OAK box starts, the launchers included, runs in UTF-8 mode (`-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`), so OpenAVMKit's own I/O is UTF-8 too. The app's console output is reconfigured to UTF-8. CI runs the whole suite a second time with a non-UTF-8 default encoding. AGENTS.md has the rules for contributors and coding agents.

**Linux (supported).** It's the development environment as well as a target. Many contributors and most CI already run on it, and the engine runs there unchanged.
- **Window:** a native Qt window (pywebview on PySide6, which the bundle includes). Qt still needs the desktop's usual display libraries (libEGL, and libxcb-cursor on X11), which some minimal installs lack. Before opening the window, OAK box tries Qt in a short-lived process (a missing library makes Qt abort rather than fail cleanly). If that fails, it opens the UI in the user's browser instead: Chromium/Chrome "app" mode (a chromeless window) when one is installed, else a normal tab.

  The UI is identical either way; only the native menus (§3.14) are missing in a browser.
- Chromium's sandbox inside Qt WebEngine is off: the window only shows OAK box's own UI from 127.0.0.1, and the sandbox can't start on some systems (as root, or under Ubuntu 24.04's user-namespace restriction).
- **Baseline:** glibc 2.34+ (the `manylinux_2_34` wheels, which Qt needs): Ubuntu 22.04+, Debian 12+, RHEL/Rocky 9+. x86_64. ARM64 Linux is later; its wheels mostly exist.
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
Oakbox keeps a hash of what each step depends on: its own calls, and the run of the step it starts from (settled 2026-10-30: "follow the run before"). A step is **out of date** when one of its calls changed or the step before it has run again since; nothing further back. A change further back shows only where it was made: every step after that one **waits** for it ("Run Bring in data again first: something it depends on changed since it ran"), and can't start or be accepted until each step before it is accepted (Looks right) on an up-to-date run. So a re-run with nothing changed still puts the steps after it out of date. OpenAVMKit checkpoints are deleted before the re-run.

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
  - **One map for every map** (settled 2026-11-01, replacing Leaflet): MapLibre GL JS draws the street map (OpenStreetMap raster tiles; a **Street map** box takes it away, remembered on the computer) and deck.gl (WebGL, `@deck.gl/mapbox`'s overlay) draws what's on it, so half a million parcels draw as smoothly as a few hundred sales. One component, `components/MapView.tsx` (fit to a box, resize, hover text, a hook for markers such as Location's pin); MapLibre's worker is bundled (`?worker&url`, ES format) as the bundle doesn't keep it beside MapLibre. Used by Model groups' parcel shapes, Location's dots and pin, a map layer over the parcels, Check my values' ratio map and Model values' map. Parcels as dots for now; shapes for every parcel on the value maps are a later choice (deck.gl draws them; at county size, likely as vector tiles made on the computer).
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
11. **Data dictionary: which fields OpenAVMKit computes.** Each entry in `resources/settings/data_dictionary.json` gets `"source"`:
    - `"input"`: only ever comes from the user's data (e.g. `sale_price`, `bldg_area_finished_sqft`);
    - `"derived"`: always computed by OpenAVMKit, so loading a column into it is overwritten (e.g. `model_market_value`, `geom_vertices`, `dist_to_cbd`);
    - `"either"`: computed when missing, kept when given (e.g. `land_area_sqft` from GIS, `bldg_age_years` from year built).

    **Done** on `engine/dictionary-source` and `engine/dictionary-reserved`, merged into `openavmkit-oakbox`: 63 input, 42 derived, 15 either, 43 `reserved` (names kept for values OpenAVMKit means to compute but nothing writes yet: model outputs, assessor and "true" ratios, OSM street/corner/waterfront fields, vacancy warnings, some geometry metrics). Reviewed by the maintainer. Each value was checked against the code that writes the field; the classification is open for the maintainer's review. Entries missing a name or type (14 today) are filled in at the same time. A test asserts every entry has a valid `source`. Topic branch `engine/dictionary-source`. OAK box's field list (F3c) offers `input` and `either` fields.
12. **CSV yes/no columns.** **Done** on `engine/csv-bool`, merged: `data.load` passed `bool` to `pd.read_csv`, which fails on "Y"/"N"; such columns are now read as text and converted after loading, as dates already were. Also, a blank value became True whatever `na_handling` said ("<NA>" and "" weren't treated as missing). Still as before: any unrecognised text counts as Yes.
13. **The sale ID in the data dictionary.** `key_sale` is required by the sales merge but has no dictionary entry. Add it (`"source": "input"`, type string). **Done** on `engine/dictionary-key-sale`, merged into `openavmkit-oakbox`.
15. **Polar coordinates from `locality.center`.** The centre is in degrees, but `_enrich_polar_coordinates` placed it in the parcel file's own coordinates, so with a projected file (State Plane, UTM) every `polar_radius` was wrong (about 600 km off for Guilford in NC State Plane feet). **Done** on `engine/polar-center` with a test, merged into `openavmkit-oakbox`; without a centre nothing changes.
14. **An ID from row numbers** (optional): a `calc` operation giving each row its number, so a single parcel file with no ID column can still be loaded. Topic branch `engine/calc-row-number`, only if F3d needs it in use.
### C. Needed for M3 (model values) and later
1. **Headless variable tests**, each test per variable: **done** (`return_tests`, F9).
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
  - Step 5 (§3.0 F9): slice 1 (variables, models, Try, how they did), slice 2 (small groups, Finalize, model values checked), slice 3 (outliers, testing variables, per-group choices, why this value); speed tiers once measured
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
