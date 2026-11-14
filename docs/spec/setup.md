# Project setup: the Data tab and before it

A new project, adding files, and the Data tab's wizard (§3.0, F1 to F3g), feature by feature.

## 3.0 Project setup, feature by feature
Agreed one small feature at a time, each mapped to OpenAVMKit's own onboarding steps (its tutorial, "Build a
jurisdiction from scratch", part B). Where this section and §3.2 differ, this section wins.

## F1. New project
OpenAVMKit: creating a locality folder (`in/`, `out/`) and the `locality` block of `settings.json`, plus
`modeling.metadata.valuation_date`.

**The user enters:**
- **Project name**: free text, e.g. "Travis County 2026". It names the folder and appears in OAK box. It is not the
  OpenAVMKit slug.
- **Country**, from the ISO 3166-1 list (two-letter codes).
- **State, province or region.** For the United States, picked from the ISO 3166-2 list of states and DC. For other
  countries, free text.
- **Jurisdiction**: what the office calls itself, e.g. "Travis County". Becomes `locality.name`, which OpenAVMKit prints
  on reports.
- **Tax year.** OpenAVMKit has no tax-year setting; it is OAK box's project identity (one project per jurisdiction per
  year, D24) and sets the valuation date's default.
- **Valuation date**: defaults to 1 January of the tax year. A one-line note: it should match the roll being checked.
- **Units**: imperial or metric, defaulting from the country: a dropdown (revised 2026-11-05), so other local units of area can join it later. Becomes `locality.units`.

**OAK box creates:**
- The project folder `<storage location>/<project name>/`, with OpenAVMKit's `in/` and `out/`.
- `in/settings.json` with only:
  - `locality`: `name`, `state`, `units` and `slug`.
    - The slug is internal and never shown: `<country>-<region>-<jurisdiction>`, lowercase, no dashes inside a part
      (e.g. `us-tx-traviscounty`).
    - `center` is left out until the map step. OpenAVMKit falls back to the centroid of the parcel geometry when it is
      missing.
  - `modeling.metadata.valuation_date`.
- `oakbox.json`: OAK box's own state (project name, country and region codes, tax year, stage status).

**Storage location:** a Settings item, "Where projects are kept". It defaults to a folder named `OAK box` in the user's
Documents (on Windows, `C:\Users\<name>\Documents\OAK box`). Changing it affects new projects only.

**Not in F1:** the center (from the map step, after a parcel map is loaded), data files, `data.load`.

**Open (F1):** editing core settings after creation. Name, units and the valuation date must stay editable, but changing
units or the valuation date affects everything downstream, which must be shown as out of date ("dirty") before anything
re-runs. How that is indicated is to be designed.

## F1b. Project actions on the home screen
- **Show in folder** opens the project folder in the system file manager (Explorer on Windows).
- **Delete** sends the whole project folder to the system's Recycle Bin (or the desktop trash on Linux), so it can be
  recovered there. A confirmation names the project and its size on disk first. A project with a step running can't be
  deleted.

## F2. Add a data file
OpenAVMKit: raw files live in the locality's `in/`, and each one is declared as an entry under `data.load` with its
`filename`.

- **Formats:** exactly what OpenAVMKit's `data.load` reads: CSV, Parquet/GeoParquet, GeoPackage and shapefile.
  GeoPackage and shapefile reading was added on the engine branch for this (§7 B10). Any other format (Excel, zipped
  shapefile, FileGDB, GeoJSON, PACS fixed-width) is added upstream first, then offered here.
- **Move or copy.** Everything belongs in one place, the project's `in/`. When adding a file, the user chooses:
  - **Move**: the file leaves its original location.
  - **Copy**: the original stays where it was.

  A shapefile moves or copies with its sidecar files (`.shx`, `.dbf`, `.prj`, …). If a file of that name is already in
  `in/`, the user picks a new name or cancels.
- **Entry name.** OAK box suggests the `data.load` key from the file name (lowercase letters, digits and underscores,
  e.g. `parcels_2026`). The user can change it. The workflow around names will evolve with use.
- **GeoPackage layers.** If the file has several layers, the user picks one, and it is written as `"layer"`.
- **What gets written:** `data.load.<name> = {"filename": ...}` (plus `layer`). Nothing else. OpenAVMKit only loads
  columns an entry maps, so a new entry contributes nothing until later features map its columns.

- **Built:** Copy is pre-selected, as the choice that can't lose anything. A file already in `in/` is only declared, not
  moved. A shapefile missing its `.shx` or `.dbf` is refused before anything moves.

- **The add flow** *(revised after F3).* The file picker drives it:
  - **Add a file** opens the system file picker straight away. Cancelling the picker changes nothing.
  - Picking a file checks it at once (exists, supported format, shapefile companions, layers, size). There is no Check
    button.
  - The path is shown, not typed. **Browse…** picks another file; **Cancel** closes the form.
  - Format and size are pills on the File label's line, right-aligned to the path field's edge. A shapefile's companions
    are a third pill. The path field has a fixed width, so the buttons never move. A long path is cut short with "…",
    and the full path is in a tooltip.
  - A file that can't be used shows the reason in red under the path, and **Add file** stays disabled.
  - The file name isn't repeated below the path.
  - The name's explanation is a hover tooltip on the field (D42).
  - Outside the OAK box window (browser mode) there is no file picker, so **Add a file** is disabled, with a tooltip
    saying why.

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

## F3. The project view: one tabbed panel

Under the project's name and tax year, everything about a project lives in one tabbed panel. Each later feature becomes
a tab; a tab's own design always assumes this frame.

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
- **Tab icons** are the Noto Color Emoji images: the SVG files from Google's `noto-emoji` repository (Apache 2.0),
  bundled with the app. They are never the system's emoji font. They are placeholders for OAK box's own imagery later.
- **Look:** the selected tab joins the panel below it, like a folder tab. Other tabs sit behind it.
- **Which tab opens:** Input files when the project has no input files yet, otherwise Metadata.
- **Addresses:** each tab has one (`#/projects/<id>/metadata`, `#/projects/<id>/files`), so back and forward, and
  reopening a project, land on the same tab. The desktop window doesn't show addresses; this mostly matters in browser
  mode.
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

**Input files tab** (removed 2026-10-31, see F3b): F2, unchanged in what it does. One line per file (its columns are in
F3b). **Add a file** sits at the top right; the add flow opens inline at the top of the tab, above the list. Empty
state: "No input files yet." with **Add a file**.

**The sample county is removed** (D19): the home screen's sample, the old steps screen (Run, Stop, results), and the
code and API behind them, including the M1a settings generator. Projects made from the sample by earlier builds are no
longer listed. The CI smoke test changes with it (§8).

## F3b. The input file list: show, rename, remove

> **Removed 2026-10-31:** the Input files tab, its list (F3b) and the per-file field view (F3c) are gone, with the API
> only they used (rename, remove, show a file; a file's columns, load, the dictionary, date formats). Files are added
> and described in the Data wizard (F3d), which keeps F2's add flow.

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
- **Row buttons:** show (📁), rename (✏️) and remove (🗑️) sit to the left of the name, always shown (revised from
  hover-only after review). The folder button shows the file in the system's file manager (Explorer selects it;
  elsewhere its folder opens). Its tooltip is the file name, and the layer for a GeoPackage, e.g. "county.gpkg, layer
  parcels" (D42). For a missing file it opens `in/`.
- **Type** comes from the extension: CSV, Parquet (`.parquet` and `.geoparquet` alike), GeoPackage, Shapefile.
- **Size** includes a shapefile's companions.
- **Geometry** is checked in the file itself, the way OpenAVMKit does it: the file has a column named `geometry`
  (`data._snoop_column_names`: the Parquet schema, or pyogrio's layer info). Only column names are read, never the data.
- **A missing file** has "—" for size and "Missing" (red) for geometry.
- Rename and Remove have the tooltips "Rename" and "Remove". The icons are Noto Color Emoji SVGs, like the tabs.

**Rename** edits the row in place:

```
                      [ cama_2026     ] [ Save ] [ Cancel ]   CSV   11 MB   No
```

- Enter saves and Esc cancels.
- It renames the `data.load` key only. The file keeps its name.
- The new name follows the suggested-name rules (lowercase letters, digits and underscores) and must not clash with
  another entry. A problem shows in red under the field, and Save stays disabled.
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
- The box is not ticked by default. Unticked, the file stays in `in/`. Ticked, it goes to the Recycle Bin (send2trash),
  with a shapefile's companions.
- For a missing file, there is no box.
- **Built:** if another entry uses the same file (e.g. two layers of one GeoPackage), the file is not sent to the
  Recycle Bin; the dialog says why and nothing is removed.
- A removed file left in `in/` can be added again later. Its add form shows "Already in the project folder" instead of
  the copy/move choice (F2).

## F3c. Choosing a file's fields

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

**The field view** replaces the list inside the Input files tab, at `#/projects/<id>/files/<name>`, with "‹ Input files"
to go back.

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
  - These are read from the file without changing it: the column list (as for Geometry, F3b), and a few distinct
    non-blank values from its first rows.
  - "In file" is the column's own type: Text, Number, Yes/No, Date or Geometry.
  - The row count is shown when it's cheap to get (Parquet and GeoPackage metadata). For CSV it's left out rather than
    read.
- **Load** puts the column in `load`, or takes it out.
- **Field and Type on an unticked row** are shown greyed out. They hold what ticking would choose, so you can see that
  before ticking.
- **Field** is a searchable dropdown of OpenAVMKit's data dictionary:
  - It offers the `input` and `either` fields (§7 B11), except `dist_to_*` (computed when a distance is configured),
    grouped by the dictionary's groups.
  - **A loaded field OpenAVMKit computes is flagged**, whether picked or typed under Custom…: `derived` ("OpenAVMKit
    computes it, so it will overwrite this column") or `reserved` ("kept for a value it computes; load this column under
    another name"). The row is still saved. `either` fields aren't flagged: your column is used.
  - Each option shows the readable name with the key in brackets; the description is a tooltip (D42).
  - Where OpenAVMKit's dictionary says `{jurisdiction}` (assessed values, land-area checks), the project's jurisdiction
    is filled in: "Travis County land value". The wizard (F3d) shows the same names.
  - **Custom…**, at the top, turns it into a text box. Custom names follow the entry-name rules (F3b).
  - Ticking a column suggests the field whose key or name matches the column name; otherwise Custom… with the column
    name in lowercase.
  - Two loaded columns of one file can't share a field.
- **Type:** Text, Number, Whole number, Yes/No, Date (`string`, `float`, `int`, `bool`, `datetime`).
  - A standard field preselects its dictionary type (number → Number, string → Text, boolean → Yes/No, date → Date,
    percent → Number). It can be changed.
  - **Date** needs a format: common formats plus Custom…, checked live against the sample values. "✓ 2025-03-14" shows
    the first sample as read; red means the samples don't read with that format. Ticking a date column preselects the
    first common format that reads all its samples.
  - **Yes/No** needs blank handling: Blank = No (`na_false`, preselected) or Blank = Yes (`na_true`). Which values count
    as yes is OpenAVMKit's rule, given in a tooltip.
  - A type with no extra is written as `[column, type]`; one with an extra as `[column, type, extra]`.
  - **Built:** the list also has **As in file**, which writes the bare column (`"field": "COLUMN"`), so entries written
    that way elsewhere show as they are. A text column whose samples read as dates is suggested as Date.
- **Filter** matches column names and sample values. **Show: Loaded** lists only ticked columns.
- **Geometry** is always loaded by OpenAVMKit, so it's a fixed row.
- **Saving:** each change saves at once to `oakbox.json` and `settings.json`. A row that isn't complete is not written,
  and says why in red: a Custom… field with no name, a clashing name, or a date with no format. It is written as soon as
  it is complete. Nothing else in the entry changes.
- **Columns in `load` that the file doesn't have** (e.g. after the file was replaced) are listed first, in red, with
  only Load (to untick them).

**Not in F3c:** `calc`, `tweak` and `drop_fields` (next), field classification (deferred), and joins (F3d, F4).

## F3d. The Fields tab: a guided wizard over all the files

**Revised (built): the wizard comes first, and collects the files itself.** It supersedes "Step 1: Your files" below;
the field steps, checks, guesses, assumptions and Review carry over.

- **Existing values** (the Assessed values step, revised 2026-10-31): sets of values to compare the models with, each a
  card: its name (the roll's proposed as "<jurisdiction> roll"), **The assessor's roll** (at most one set), **Remove**,
  and three field rows, Market value, Land value and Improvement value, read and checked as the roll's always were.
  **Add a set of values**. The roll's fields are `assr_*` (OpenAVMKit's `assessor` model, step 4's first); the others
  take slots of their own (`vset1_market_value` … `vset5_*`; OAK box's names, not offered elsewhere, never modeled
  with). Making another set the roll swaps their columns. In Model values each other set with a market value is a
  `pass_through` model under the set's name: never in the ensemble (`ensemble.models` lists the chosen models), and
  judged like the roll, off the holdout (OpenAVMKit `analysis.ratio_study.outside_models`, `engine/enrich-fixes`). Land
  and improvement values are kept for a later land-value comparison.
- **No "true" values.** The Existing values step asks for the assessed land, improvement and total values only.
  OpenAVMKit's `true_land_value`, `true_impr_value` and `true_market_value` are the answer key of synthetic data, never
  a real roll, so the wizard neither shows nor guesses them.
- **Nothing loaded is out of sight.** A field under a step's **More** shows in the main list as soon as it's loaded,
  whether guessed or chosen. The link (**2 more fields**) reveals only the ones not loaded, and says how many; it's gone
  when there are none. A column already loaded is named by its field ("UNITS is already loaded as Building units"),
  never by OpenAVMKit's key.
- **What a column holds: one pattern, "N values ▾".** Beside a field, the check line says only what was checked; it
  never lists sample values. A small **N values** button (**N areas** for a location field) counts the column's
  different values. It opens a list of every value with how many rows have it (most common first, with a bar), a summary
  ("25 different values in 9,359 rows, 4 blank") and a search box when there are more than 12. Up to 500 are listed;
  past that, "N more: search to find them". The check line wraps rather than hiding its end. The same button serves the
  field rows on every step, location fields and your own fields. (The column dropdown still shows a few samples beside
  each column, to help pick one.)

- **New project → the Data tab** (first after Metadata; Input files is the advanced view after it). Steps:
  - **Overview** (the tab's landing page, revised 2026-11-04): the welcome: the two datasets, SALES and the PARCEL
    UNIVERSE, and why both are needed. There is no separate Welcome step; **Start: Parcel universe ›**.
  1. **Parcel universe:** add one file (or take one already in the project). It must have shapes ("✓ Geometry detected")
     and becomes `geo_parcels`. Pick its parcel ID. **+ Add 2nd ID** (then **+ Add 3rd ID**) adds an optional extra ID
     (`key2`, `key3`: the ones OpenAVMKit knows by name), with a tooltip saying it's only needed when another file joins
     on a different ID. Extra IDs aren't checked: rows are kept or dropped by the parcel ID alone. Choosing (remove) on
     the 2nd ID moves the 3rd up, and files joined on it follow.
  2. **Sales:** add one file. It matches the universe by parcel ID, or by one of its extra IDs (OpenAVMKit then looks up
     `key` from `geo_parcels` by `key2`: `data.process.enrich.ref_tables.sales`). Sale ID (a column, or made from the ID +
     sale date), sale price, sale date, valid and vacant sale (or assumed, after a warning).
  3. **Big five** (revised 2026-11-04: a step of its own, a part each): **Building size** (required), **Land size**
     (filled from the shapes if missing), **Age** (year built / effective year built), **Quality**, **Condition**
     (recommended). Quality's "which way is better" (Higher is better | Lower is better) and Condition's "what its
     numbers mean" (radio cards: % good, % depreciation, higher, lower, years of life left) are on the part's page, a
     row of their own under the number. A project saved when Big five was one step has each part seen, skipped or
     moved on from as it was.
  4. **More details:** Location, Land, Building, Rooms & features, Assessed values, Other details. Location is three
     parts (revised 2026-11-04): **Address**, **Coordinates** (worked out by OpenAVMKit, and the centre they're
     measured from) and **Location fields**; **Your own fields** is a part of its own after Land use & building type.
     A project saved before has those parts seen, skipped or moved on from as Location (and Land use & building type)
     were.
  4. **Review:** what blocks a run, then what's recommended, then every source. Its button is **Bring in data ›**, to
     the next tab; greyed while something blocks a run, and a click lists what (**Go to Bring in data anyway** / **Fix
     them first**).
- **Step marks come from what's on each step,** shown beside the step's number (both always show, revised 2026-11-04),
  recomputed on every change, in the same colours as the issues: ✅ complete, ⚠ something to decide (or age missing on
  Big five), ❌ blocks a run. A step not visited yet shows only its number, never a ❌ ahead of time.
  - Parcel universe, Sales and Big five are complete when their required parts are there: a universe file with shapes
    and a resolved parcel ID; a sales file, its IDs, price, date, valid and vacant sale; building size. Big five shows ⚠
    only for missing age; quality and condition are nice to have.
  - The optional steps (Location, Land, Building…) are complete once confirmed by **Next** or **I don't have these**.
  - More details shows the worst of its parts; Review shows ❌ while anything blocks a run, ⚠ while something is
    recommended.
- **Next is greyed only while the step shows ❌** (something that stops a run: a required field not picked, under half
  the sales finding a parcel), with what's left just above the button bar (so the buttons never move), named when there
  are three or fewer ("2 things left: Pick the valid sale; Pick the vacant sale"). It still answers a click: a dialog
  lists them with **Skip ahead anyway** and **Finish this step** (the default). Warnings (⚠) and notes stay on the step
  and in Review but never grey Next. Optional steps and Welcome keep Next enabled, since Next is what confirms them. The
  add-file panel's confirm button is **Import**, on the right, in line with Next.
- **Repeated IDs, wherever they're shown** (the duplicates dialog's examples, Bring in data's "more than one row for a
  parcel" rows): the ID column first, rows sorted by the ID (numbers in it as numbers: 99 before 100; each ID's rows in
  file order), and the rows of one ID share a background, white or grey, alternating from one ID to the next rather than
  row by row. The bands carry on from one page to the next. Bring in data's rows show every row of each repeated ID: a
  **kept?** column after the ID says **✓ kept** (in bold) or **left out**, so what was dropped can be compared with what
  stayed ("Every row of each repeated ID: 124 left out, and the 115 kept…"); when all are dropped, every row says left
  out. The dialog's title names the file ("building.csv: more than one row for a parcel: the first kept").
- **Tables of rows read across easily:** every other row grey (the "See them" rows of Bring in data, the value lists);
  repeated IDs band by ID instead (above).
- **A number's spread** (a number's details on Bring in data): a histogram of 24 bars under the statistics, over the
  middle 98% of its values (the lowest and highest 1% counted apart, so one 4-million-square-foot parcel doesn't flatten
  the rest), zeros left out and counted ("2,366 zeros not shown": often "no building", "no year"), on a log scale when
  the values span orders of magnitude; the low, middle and high values under it, and each bar's range and count on
  hover.
- **Lists of values with their counts** ("N values ▾", Bring in data's "details ▾") sort by either heading, Value or
  Rows: a click sorts by it, again the other way (rows most-first, values A→Z with numbers as numbers), done by the
  server since long lists are cut short. The popover is never taller than the room it has: its list scrolls inside.
- **Reconcile: sales IDs that don't match the parcel IDs as written** (zero-padded on one side, hyphens on the other, a
  stray space). The Sales row's match line has **Reconcile…** whenever under 100% of sales find a parcel; under 95% the
  step shows ⚠, under 50% ❌. The dialog shows the match live, with clean-up steps for each side (remove leading zeros,
  hyphens, spaces or other characters; trim; replace; keep the first/last N; text before/after a character), samples
  from each file (unmatched sales, or random), and a one-click suggestion from a few common clean-ups. Saved steps
  become an OpenAVMKit `calc` on the ID (`key`, or `key2`/`key3`) of each file, wrapped in `["where", ["isempty", <id>],
  null, …]` so blank IDs stay blank and are still dropped. IDs are compared as OpenAVMKit reads them: not trimmed. Sales
  only for now; the parcel side's steps also apply to every other file joined to the universe on that ID.
- **Sales (or rows) that find no parcel: what kind of problem it is.** Only plausible nits are cleaned up; the rest is
  said plainly, for the jurisdiction to fix. Checked on the rows that find no parcel, after the clean-up already saved,
  when under 95% match:
  - **Written differently** (Reconcile, as above): a common clean-up matches 2 points more or better (trim spaces,
    leading zeros, hyphens, spaces, `-. /`, capitals), or under 80% of the unmatched IDs are written like the parcel
    universe's (digits, capitals and small letters in the same pattern: `0012-104` is `9999-999`, `r0123456` is
    `a9999999`).
  - **Another numbering:** under half match, and the IDs are written like the parcel universe's: "Fewer than half find a
    parcel: is PID the parcel ID, the same one the parcel universe uses? Or does parcels.parquet cover a smaller area
    than sales.csv?" It holds up the step.
  - **Parcels missing** (10 or more): "788 sales are for parcels that aren't in the parcel universe. Their IDs are
    written like the parcel universe's, so cleaning them up won't help."; then where they are, if a project file not
    joined as parcels has them (its columns cleaned as this file's IDs or the parcel universe's), or a parcel file's
    rows have no shape ("…whose rows have no shape of their own: condos or other units, it seems. Set them up on the
    Condo units step.", with a **Condo units…** link), else "Usually they're parcels kept outside parcels.parquet:
    condos and other units without a shape of their own (timeshares, homes in a mobile-home park, buildings on leased
    land), or parcels made since. Have a file with them? Add it on More files; units are set up on the Condo units
    step."; and the other files missing the same parcels.
  - **Keying slips:** "About 480 of them look like keying slips: one digit off a parcel ID. See them to check; fixing
    them is for the file they came from." Counted as how much more often the unmatched IDs are one digit off a parcel ID
    than the matched ones are (short numbers are often one digit apart anyway). When nearly all are slips, nothing is
    said about missing parcels.
  - A note, not a to-do, on the ID check, with **See them…** in place of Reconcile…; listed on Review. Sales, parcel
    files and the permits file alike.
  - **Checked** on 8 ID schemes (plain and zero-padded integers, NC PIN, Arizona book-map-parcel, variable-length PACS
    IDs, Cook County 14-digit PIN, California APN, letter-prefixed schedule numbers, Tennessee dotted map-group-parcel),
    each in 7 situations (20% missing, written differently, both, another numbering, spaces and missing, 8% slips, 3%
    missing), 10,000 parcels each: `tools/id_robustness.py`, all 56 as expected. A county prefix (`081-`) is written
    differently, but no common clean-up removes it: Reconcile's "text after" does, by hand.
  - **Engine** (`engine/enrich-fixes`): the `upper` calc, for the capitals clean-up.

- **Sales, in six parts (revised 2026-11-05; 2026-11-14),** as Big five is: **Sales** itself is where the file is
  picked (nothing else is asked there; Start goes on), then **Parcel ID** (first: the sales finding their parcels is
  what everything after needs), **Sale date**, **Sale ID** (after both: it can be made from them), **Sale price**,
  **Valid sale** and **Vacant sale**, each a page of its own; Sales takes the worst of its parts. Nothing on them is
  in a popup, and every change is saved as it settles (no Save or Cancel). Projects saved with Sales as one step count
  each part as seen, skipped or moved on from as Sales was; the file's part (`sales_file`, briefly), then both IDs on
  one part (`sales_ids`, until 2026-11-14), count as both **Parcel ID** (`sales_match`) and **Sale ID** (`sale_id`).
  - **Parcel ID:** the sales file's parcel ID column, then **Do the sales find their parcels?**: why some don't (what
    the ⚠ chip held), and the reconcile layout (the match meter, the clean-up steps on each side, samples, random or
    unmatched) right there; no **See them…** or **Reconcile…**.
  - **Sale ID:** a column, or made from the parcel ID and the sale date (a parcel can sell more than once); made, it
    waits on the sale date ("Pick the sale date first").
  - **Sale price:** the column and its values; **Decimal mark** and **Amounts are** as dropdowns (as written, in
    thousands, millions, cents…), K and M as a tick; under it **As it's read**: the median and spread, how many read,
    blank or don't, the scale check against assessed values (with a one-press fix when it looks wrong), Excel's
    rounding, and "As written → Read as" samples.
  - **Sale date:** the column and **Written as**, every format in one dropdown (and Custom…); under it how many read
    and their range, other formats that also read (use that), samples, and **Sales by year**, a bar chart, the most
    recent year first.
  - **Valid sale, vacant sale:** the column, then the logic in a box of its own: "A sale is valid if [All of these ▾]
    are true", each condition a white row with its red −, **+ Add condition** (and, for valid sale, **+ Sale price is
    at least $1,000**) at its bottom right; under it **Which sales it picks**: how many, the price counts, and sample
    rows with their result. They can't be skipped (each can still be assumed, with a warning).
- **Dates: the format is a choice, previewed.** A date column gets the first common format that reads its first rows;
  **Change format…** (or **Check format…** when unsure) picks another, or a custom strftime pattern, and previews it on
  every row exactly as OpenAVMKit parses it (`pd.to_datetime(format=)`): how many read, the range, samples, and which
  don't read. "Unsure" means some rows don't read, or another format also reads every row but gives different dates
  (month/day against day/month). The chosen format is the load's third item.
- **Valid and vacant sale from any column: a rule** (revised 2026-11-04: a yes/no column too: which of its values mean
  a valid or vacant sale is the user's to say, never "true = yes" on its own; picking or guessing the column starts
  the rule with nothing chosen, the row asking "Choose values…"; a rule cleared and saved is kept so, asking again). A
  column that isn't yes/no (Q/U, a deed code) opens **Which sales are valid?**: its values with counts, ticked for yes
  (an `isin`), plus more tests on any sales column (is one of, is not one of, equals, contains, is blank, more/less
  than…) joined by all or any. The count and sample rows come from OpenAVMKit's own filter code on every row. Saved,
  it's a `["?", filter]` calc on the field (as in Baltimore's `vacant_sale`), and each column it tests is loaded
  (under its own lowercased name, or as the field it's already loaded as). A yes/no column still loads directly; **Use
  a rule…** turns it into one.
- **Money and measures (F1):** a project has units (imperial/metric), a currency (ISO 4217) and a number style (how the
  files write 1234.56: `1,234.56`, `1.234,56`, `1 234,56`, `1'234.56`, `1 234.56`). All three follow the country on the
  new-project form (from Unicode CLDR, generated into `locales.json` by `packaging/make_locales.py`) and can be changed
  there or later under Metadata. OpenAVMKit only takes the units; currency and number style are OAK box's, for reading
  and checking prices (the price dialog) and for showing money. Projects saved before take their country's.
- **Sizes are asked in the project's small unit, from a column in any unit.** Building and land size (and footprint) sit
  beside a unit dropdown: sq ft, m², acres, hectares, sq yd, tsubo, pyeong, mu. It's guessed from the column's name
  (`ACRES`, `LAND_HA`, `LOT_SQM`) or else the project's unit; the check line shows the conversion ("0.114 acres → 4,966
  sq ft") and warns when the typical size says the unit is wrong. The project's unit decides what OpenAVMKit gets:
  `land_area_sqft` (imperial) or `land_area_sqm` (metric). A column in another unit is loaded under its own name and
  converted by a calc (`land_area_sqft = land_area_sqft_in_acres × 43,560`). The wizard names the fields in square
  metres in a metric project.
- **Location fields on a map (revised 2026-11-05):** the fields on the left, the add form no wider than they are; once
  there's one, a map on the right filling the page: **On the map** picks a location field, and each parcel of the
  universe is a dot coloured by its area (a colour each, spread round the colour wheel; grey for none), its area's
  name on hover (`GET …/wizard/locations/{name}/map`: up to 20,000 parcel centres with their area).
- **Land use & building type (revised 2026-11-05)** asks land use, building type and stories; building description,
  class and units are under More, never guessed, only picked.
- **Census and elevation, fixed in the engine (2026-11-05, OpenAVMKit `30c98a2`, larsiusprime/openavmkit#422):** every
  code the ACS writes for a figure it doesn't give is missing (only −666,666,666 was; the others went in as hugely
  negative values); a block group the ACS gives no figure for takes its tract's (`census.tract_fallback: true`, which
  OAK box sets: median rent is withheld where few rent), and a parcel whose centre is in no block group takes the
  nearest within 250 m (`census.nearest_m`). The elevation is fetched with a margin round the parcels, so those on the
  locality's edge get a slope (reprojecting left empty edge cells, and slope needs a cell's neighbours).
- **Maps and the mouse wheel (revised 2026-11-05):** a map that is a tab's page zooms with the wheel; a map inside a
  step's page (Coordinates, a map layer) zooms with it once it's clicked or tabbed into, and the wheel scrolls the
  page again once something else is.
- **Big five's spreads (revised 2026-11-05):** under a size (building, land) or a year (year built, effective year
  built) that's loaded, a histogram of its values as loaded: sizes in the project's unit, years as years (0, written
  for none, left out); about 24 round-width bins across the middle 98%, the counts under and over them, blanks, and
  the median said under it (`GET …/wizard/fields/{key}/histogram`).
- **Quality and condition, laid out (revised 2026-11-05):** the column first, in a box of its own (it's often picked
  for you), with a category from a column of its own under it; then the choices in a second box: **It's written as**,
  **Which way is better** (or what its numbers mean, and 0–1 or 0–100), the switches as wide as the dropdown. No to-do
  text beside the column ("say which way is better"): the second box is the to-do.
- **Big five, with only the universe loaded,** says building details often come in a separate file, and that **In
  another file…** adds it once for every field.
- **More files, a part per file (revised 2026-11-05):** a landing page, then **Add files**, where the files are added
  one by one and nothing else is asked ("just add all the extra files you'll be using: you'll configure them one by
  one in the next steps"; each with **Set it up ›** and its red −), then a part for each file, titled by its name
  (`more:<name>`, made from the project's files, not a fixed list). A file's part is the file entry below, then
  whether its rows find their parcels (or sales), why some don't and the ID clean-up with samples, laid out under it
  as on Sales file (no **See them…**, **Reconcile…** or ⚠ chip). A file's part shows its mark once Add files has been
  seen; setting the file aside there goes back to Add files. A file added there that was set aside before goes back to
  not said what it holds (`added`). Projects saved with More files as one step count Add files as seen.
- **More files (step 4, after Sales):** the universe and sales steps take one main file each ("more files come later");
  this step adds the rest one by one. For each: what it holds, **More about each parcel** (joins the universe on its
  parcel ID or an extra ID) or **More about each sale** (joins the main sales file on the sale ID, so that file needs a
  sale ID column); the ID column, guessed from the target's column name or else from the column whose values best match
  the target's IDs (compared loosely: no leading zeros, hyphens, spaces or case); and the same checks as the main files:
  repeated and blank IDs (Resolve…), and how many rows find their parcel or sale, with **Reconcile…** whenever not all
  do. Under half matching blocks; under 95% is a warning. Its red − sets it aside (D47), with Undo. Settings: parcel
  files join `merge.universe` (with `on` for an extra ID), sales details join `merge.sales` after the main file, each
  with `dupes` on its join key. **What it's about, then how it joins** (revised 2026-10-31, 2026-11-04): **It's about**
  **Parcels** or **Sales**; then, under it, **It**: **Joins new columns** (more about each parcel / sale, joined on the ID, as
  above), or **Appends new rows** (more parcels / sales) (revised 2026-11-10); both choices are segmented controls on the entry's two
  columns (revised 2026-11-04) (older sales, sales from another system, sales found some other way; a second parcel
  file). Joined to each sale works with a made sale ID too: the file's own is made the same way, from its parcel ID and
  a **Sale date** picked beside it ("Its sale ID is made as the sales record's"), and its match check warns when most
  don't match ("are these sales of their own? Then append them as extra rows"); a parcel ID repeating there is a parcel
  sold more than once, not flagged. **Appended** (holds `sale_rows` / `parcel_rows`; more parcels need shapes, as the
  universe's have): its parcel ID; then a **column check** ("Has 4 of the sales record's 4 fields. Not in it: …", warned
  at half or fewer: likely the wrong file, or a different layout) and a **key check** (its parcel IDs look like the main
  file's: length, digits, leading zeros, "9 digits, leading zeros kept"; warned when they don't); then the main file's
  fields, each matched to a column (the main file's column name, else one named as the field, else the usual guess; each
  changeable, "(not in it)" leaves it blank for its rows): valid sale takes the sales record's rule on this file's
  column, an assumed valid or vacant sale is assumed here too unless given a column; the sale ID made as the sales
  record's (or its own column). How many rows are already in the main file (the same sale ID, or parcel), "each kept
  once, the main file's row". Settings: `merge.sales` / `merge.universe` right after the main file, `{"id": …, "how":
  "append", "dupes": {"subset": "key_sale" | "key", "sort_by": [[key, "asc"], [rank, "asc"]]}}`, with a `sale_file_rank`
  / `parcel_file_rank` calc (0 the main file, then 1, 2… the appended) so the main file's row is the one kept
  (OpenAVMKit's sort before keeping the first isn't stable). Tested through OpenAVMKit: Petersburg's teardown sales
  (158, 28 already in the sales record).
- **Location (More details):** asks only for the **situs address** (the property's physical address, not the owner's
  mailing address; a column named for mail or owner is never guessed for it). Then:
  - **Coordinates:** latitude/longitude and polar coordinates are shown as worked out by OpenAVMKit (from each
    parcel's shape), nothing to load. The map is always shown (revised 2026-11-04: the step is its own page), taking
    the rest of the page down to the buttons (never under 18rem; revised 2026-11-05), with the centre and **Use the
    middle of the parcels** above it. A map (the app's one map, `MapView`: OpenStreetMap tiles; the parcels drawn as
    dots from a sample of up to 3,000 centres, so it reads without tiles too) shows the centre polar coordinates are
    measured from: the middle of the parcels, or a point the user drags the pin to (`locality.center`, in degrees).
    **Use the middle of the parcels** clears it. OpenAVMKit reads the centre in degrees for projected parcel files too
    (`engine/polar-center`, merged).
  - **Location fields:** the user adds the areas parcels belong to one at a time: a column of a parcel file and a name
    for it (lowercase, digits, underscores; not a name OpenAVMKit computes). Loaded as text, listed in
    `field_classification.important.locations` and `other.categorical`. Each shows how many areas it has, and warns when
    it's one value for all or nearly one per parcel (an ID, not an area).
- **More details, for now:** Address, Coordinates, Location fields, Land use & building type, Your own fields,
  Assessed values, Shapefiles (Big five is its own step). Land, Building, Rooms & features and Other details are left
  out; their fields are still in the advanced view.
- **Shapefiles (More details):** map layers, added one by one (Shapefile, GeoPackage, GeoJSON, GeoParquet). Each says
  its kinds of geometry and needs a coordinate system. The user decides its use, with the controls OpenAVMKit's settings
  give:
  - **Stamp its areas onto parcels** (polygons only): `data.process.enrich.geometry`, `{"id", "predicate":
    "contains_centroid", "fields"}`. Columns are picked one at a time and named, each as a location (default:
    `important.locations` and `other.categorical`), a category or a number. The check: parcels in a shape, in more than
    one (the first wins), in none; none at all blocks (wrong place or projection).
  - **Measure distances** (any geometry): `data.process.enrich.distances.<name>` with `source`, `max_distance`, `unit`
    (miles for imperial projects, km for metric, changeable), and optionally a name column and
    `store_top`/`top_n`/`sort_field` for each of the largest features. Gives `dist_to_<name>`, `proximity_to_<name>`,
    `within_<name>`.
  - Layers load with `"dupes": "allow"` (OpenAVMKit would otherwise keep one shape per value of the first column) and
    never join `merge.universe`. **Show map** draws the layer over the parcel dots. **Don't use this layer** sets it
    aside.
  - **One compact card per layer, two lines.** The header: name, file, shape count, a **Stamp onto parcels | Distance
    to** switch (stamping greyed for points and lines, saying why), the check, a map button and × (don't use). The check
    names only what isn't zero: "every parcel in one shape", or "331 in a shape · 9,028 in none". A distance layer has
    no check line (its header counts its features). Below:
    - **Stamp:** "Copies" and one chip per column copied (`zoning ← ZONING location ▾ ×`; the kind changes from the
      chip), then **+ Field**, a small popover for column, name and kind.
    - **Distance:** "Gives `dist_to_`[name] up to [2] [miles]" on one line, saved when a box is left or on Enter, then
      **Options**, a popover with what it gives, feature names and the largest few, summarised beside it ("names from
      MAJORLAKES").
    - Anything still to do (no coordinate system, how to use it, a column to copy) is listed under the header.
  - Engine (`engine/shapefile-layers`, merged): GeoJSON loads; point and line layers load (every non-polygon was
    dropped); a distance layer from a file needs no `name` column and stops the run with the reason when it fails (it
    printed an error and was left out); docs say `enrich.geometry`, not `spatial_joins`.
- **Amounts of money** (sale price, assessed values): a column that isn't plain numbers (`$250,000.00`, `250.000,00`,
  `$250K`, `(10)`, `N/A`) is read, not refused. **How to read it…** works like the date dialog. Settings and checks:
  - **What it sets:** the decimal mark (found from the whole column; when the values don't settle it, "1.234", the
    project's number style), whether K/M mean thousands and millions, and a scale (as written, thousands, millions,
    cents). Every row is previewed as written → as read.
  - **What it writes:** the column is loaded as text (`<field>_text`) and read by a calc of OpenAVMKit's own operations,
    so no engine change. Currency signs, spaces, words and the thousands separator are dropped, `(10)` is −10, and
    anything left that isn't a number (blank, N/A, TBD, -) becomes missing. A valid-sale rule that tests the price reads
    its own copy (`<field>_num`): OpenAVMKit drops a calculated field another calc uses.
  - **The scale check** runs on every amount column, plain ones too, since thousands and cents load without error and
    quietly give wrong prices. It shows the median and the 10th–90th percentile range. The sale price is also compared
    with the assessed value of the parcel it sold (median ratio, at least 20 sales). A ratio of 30 or more, or 1/30 or
    less, says which scale to read it in; without assessed values, a median under 1,000 suggests thousands and over 50M
    suggests cents. One click applies it.
  - **Values flagged:** amounts written as Excel writes big numbers (`1.11E+06`, rounded, can't be repaired). The price
    dialog only reads prices; it never changes which sales are valid.
- **Sales record fields: a major step of its own (6, after More details; built 2026-11-07, `wizard/as_sold.py`,
  `AsSold.tsx`).** After the characteristics are chosen, since it compares with them. First a screen to itself, how it
  works: a sale described as the property was when it sold (it may have changed since); those are what the models
  learn from; parcels are valued on what they are now (the parcel files); so it's best practice to freeze the
  characteristics at the sale; where a sale has none, today's are assumed (the sales are *hydrated* from the parcels):
  a modeling assumption. Then the main sales file's columns that mirror a characteristic loaded for the parcels (Big
  five, Land use & building type: the parcel's own column name, or a name the field dictionary knows), each checked
  against today's value of the sale's parcel: sales with a value, the share the same as today's (a number within
  0.5%), examples where they differ; **written differently** when today's are numbers and the sale's mostly aren't
  (Guilford's `GRADE`, "B-5  120%" where today's is 1.2), or text with almost no values in common: then the sale's
  can't be chosen, and the answer is a cleaner export (the same codes), not a reading in OAK box (settled
  2026-11-07). Per field, **The sale's** or **Today's** (`wizard.as_sold`); until chosen, today's (nothing changes
  silently), with a suggestion: the sale's, never today's (revised 2026-11-10: a sale's value a little off today's may
  be the property as it sold, so near-sameness isn't a reason to drop it). The sale's loads its column into the sales file read as the parcel's
  is (number format, scale; an area in its own unit), so OpenAVMKit's hydration uses it per sale and fills the rest
  from the parcel; the parcel's reading changing changes it too, and the parcel field gone takes it with it. A
  characteristic only the sales file has isn't offered: a model can't value a parcel on it.

  **Found by its values too, in its own unit** (2026-11-07). Nothing by name: the sales file's column that agrees with
  today's for at least half the sales on the same parcels (up to 4,000 compared), an area tried in each unit. An area
  found by name takes the unit its name gives away (`ACREAGE`: acres), else the one that agrees. Compared in today's
  unit (Guilford's `ACREAGE` in acres against `Shape__Area` in sq ft: the same for 77%). Nothing found: said, and any
  column can still be picked.

  **The spread, its range set live** (2026-11-08, `FieldHistogram.tsx`). A size's or a year's histogram starts on the
  automatic range: the middle half of the values and three times its width each side, within the smallest and
  largest (Guilford's land: to 125,380 sq ft, where the 1st–99th percentile reached 1.2 million and flattened the
  rest). Two handles under the bars, on a track over the column's whole range (spaced by order of magnitude when it
  spans a hundredfold or more), and From/To typed (thousands separated; read on Enter or leaving the box); **Reset**
  once changed. The bars are drawn in the page from the field's values at every 0.2% (`FieldSpread.quantiles`, sent
  once), so they follow a handle as it's dragged. **🔗 linked** (on; shown when both datasets' histograms of the field
  are there): the 🌐 Parcel universe's and 💰 Sales record's share one range, bar for bar; unlinked, each keeps the
  range they shared, and linked again they share the one linked from. Only the view, for the visit: nothing in the
  data or the settings changes.
  The same spread, range and controls (`RangedBars`) on **Data › Sale price** (under As it's read: the prices as
  OpenAVMKit will read them, with the currency; $10 deeds and portfolio sales no longer flatten the rest) and in
  **Inputs › a field's details** (every number field of the parcel universe and sales record after Bring in data;
  results from before 2026-11-08 keep their old drawing until it runs again).

  **Picked for you, conservatively** (2026-11-08, `as_sold.autopick`). The sale's column is picked, and marked
  **picked for you**, only when it's obvious: the sales file has a column of the very same name as the parcel's, it
  isn't written differently, and it's the same as today's for 90% or more of at least 20 sales. Never over a choice
  (the user's, or *none: today's* chosen); choosing takes the mark off. Looked for when a characteristic is guessed or
  chosen for the parcels, and when the sales file or a parcel file is set. Guilford: `YEAR_BUILT`, 99.7%.

  **Only in the sales file** (2026-11-08, `wizard/sales_only.py`). Under the step's table, the sales file's columns
  no parcel file has (not loaded for a field, not a parcel column's name nor one the field dictionary knows; blank,
  one-valued and nearly unique ones left out): each with its share of sales and most common values. A model can't use
  them (it values every parcel; parcels don't have them); they can decide which sales count (a rule on **Valid
  sale**, linked), and they show beside each sale in Outliers. Guilford: `SALE_TYPE`, `SALE_STATUS`,
  `REVENUE_STAMP_VALUE`, `GRADE_UNEDIT`… In **Outliers**, a sale's details show its own values in them (**At the
  sale, only in the sales file**), its row found by its parcel and sale date, as the run makes its key.

  **At the sale, on each characteristic's own screen** (2026-11-07, `AtSale` in `AsSold.tsx`). Beside its column
  (**Today's**, the parcels: what's valued), **At the sale** (the sales: what the models learn from), the same widget
  reading the sales file: **Column** (*none: today's*; the one found, marked found, not used until picked; any of the
  sales file's columns; picking a column is using it, no second switch), **Its unit** for an area (today's said when
  it differs), its values, its spread for a size or a year (in the project's unit), then against today's: the share
  the same, the sales that differ with the first three, **See them** (up to 50: parcel, sale date, at the sale,
  today's), and what that suggests. Side by side where there's room (Big five at 1,400 px), else stacked: each pair
  wraps on its own. Big five's parts pair per field (Age's two each under its name); Quality and Condition beside
  their column's boxes; Land use & building type a table under the step (field, today's, at the sale, against
  today's). Sales record fields' own table has the same picker. 1.5-2.7 s on Guilford with the quick-read copies (8 s
  before), shown waiting, with the time and Stop.
- **Condo units: a major step of its own (7, after Sales record fields), one decision per part.** OpenAVMKit's
  `data.process.condos`, for units on the roll but not on the map: each has a parcel ID of its own and no parcel shape,
  because it sits on a parcel it shares.
  - **What fits the pattern,** listed on the first part so the user recognises theirs: condos of any kind (homes,
    offices, shops, warehouse and flex units); parking spaces, storage units, boat slips and hangars sold as condos;
    timeshares where each share has a parcel ID; homes in a mobile-home park, on land the park owns; buildings on leased
    land (ground leases, hangars at an airport, cabins on public land). Not these: townhomes and other units on a lot of
    their own (they have shapes) and co-ops (usually one parcel for the building). Mineral and air rights, business
    property and common areas can sit in a units file without a shape: **Which rows** leaves them out. The words
    throughout are "the parcel it's on" (a building, complex or park), not "building".
  - **Do you have condos?** (`wizard.condos`; a project that set up units before the question existed has them.) Above
    the answer, what the files suggest: each parcel file's rows with a parcel ID but no shape ("condo_units.csv: 1,360
    of 1,360 rows…"), and the sales for parcels the parcel universe lacks. Until answered, the part shows ⚠ whenever the
    files suggest units, even before the step is reached. **No** finishes the step and stops any units (their settings
    and the fields given them); the rows without a shape stay left out and noted. **Yes** brings in the other parts,
    shown in the step list only then:
    1. **Units file:** the parcel files joined to the parcel universe, those mostly without shapes first and said to be
       likely; a file with only some ("1 of 6,864 rows…") is said to be more likely more about the units. Not listed:
       add it on More files. One units file (OpenAVMKit has one condos block): picking another moves the units.
    2. **Which rows:** every row without a shape, or rows where a test holds.
    3. **The parcel they're on:** how each unit finds it (below), said as a guess until changed, with examples.
    4. **Land:** four choices, each explained, with each example's share.
    5. **Their fields:** what the units carry: from their own file, and from the parcel they're on.
    6. **As a location:** the shared parcel as `condo_group`, with examples.
    7. **Summary:** what OpenAVMKit will do, in order, and how many sales now find a parcel.
  - **Earlier steps point here, never stop for it.** On More files, a parcel file whose rows mostly have no shape says
    "1,360 rows without a shape of their own: condos or other units? Set them up on Condo units" (⚠, not ❌; "…are left
    out: no units, you said" after No), with a **Condo units…** link; its low match isn't a run problem. Sales and other
    files' missing-parcels notes link there too. Each part's problems (no units file, no unit found, the land can't be
    worked out) are ❌ on that part and on Review ("Condo units › Land: …").
  - **Which rows are units:** **Every row** of the file, or **Rows where…** (one-line tests, values from the checklist
    dropdown).
  - **How each finds the parcel it's on:** **The start of an ID** (the first *n* characters of a column of this file
    match those of a column of the parcel universe file: `7865782948-030` → `7865782948`; OpenAVMKit's `id_prefix`, from
    the parcel universe file), or **A column naming it** (the building's parcel ID, cleaned as the parcel ID is;
    `parent_id`). Guessed the first time (of the columns both files have, the start that links the most units, ending
    before a separator) and with **Guess again**, and said to be a guess, with what it's based on ("Guessed:
    PIN_PLUS_EXT is in both files, and its first 10 characters (up to the "-") match one building's for more units than
    any other column or length…"), until the user changes it. Examples show both sides: the unit's value, the building
    it finds, what it matched there (`7864663668-023 → building 142468 (matches 7864663668-000)`), and the unit's land
    share; the check says how many units find their building, in how many buildings, and how many find none (left out).
  - **Land** (each choice explained beside it, with each example's share shown, e.g. "1/186 of 3,644 sq ft = 20 sq ft"):
    - **Equal shares** (the default): the building's land (its shape's area) in equal shares, one per unit. Needs
      nothing from the units (OpenAVMKit `land_share.method: equal`).
    - **Shared by finished area**: by each unit's finished area, from whichever parcel file loads it (the units'
      building cards, say: OpenAVMKit shares it out after the merge).
    - **Each unit's own land size**: from a column of the units file, picked right there.
    - **No land of their own**: the land is the shared parcel's (homes in a mobile-home park, buildings on leased land);
      each unit's land size is 0 (OpenAVMKit `land_share.method: none`, `engine/enrich-fixes`).
    - When the chosen way can't be worked out (no finished area loaded, no land column, or one blank for every unit),
      it's ❌ on Land and in the run's problems: OpenAVMKit would stop.
  - **Fields** (revised 2026-10-31), in three parts. **From the units file:** the parcel universe's fields picked from
    one searchable list (`MultiPick`; a field with a same-named column in the units file shows it, and ticking it gives
    it that column; land size is the Land part's), each chosen field a row below with its column's dropdown and ✕. Until
    the same-named ones are given or declined, Their fields shows ⚠ and Review says which fields the units go without.
    They're the units' own values, not a second source: the field rows don't call them a conflict. **From the parcel
    they're on:** the parcel files' land and location fields the units' own file doesn't give them (land use & zoning
    fields, location fields from the dictionary and the user's own; never the address, census fields or `condo_group`),
    picked from one list; each unit takes them where its own is blank (OpenAVMKit `condos.inherit`,
    `engine/enrich-fixes`). Changing these doesn't clear the enrichment cache (the rows are the same). **From its
    shape:** a plain list of what every unit gets as every parcel does: map layers, OpenStreetMap distances, census,
    elevation, and the parcel as a location when it is one.
  - **Also use the building as a location** (`condo_group` in `important.locations`; it's always a land category, and
    `land_area_alloc_sqft` a land number).
  - **What it writes:** OpenAVMKit tests `select` on every parcel file, so each gets a yes/no calc `condo_unit`: the
    rule (or "has an ID") in the units file, "blank ID" (never true) in the others; `select` is `condo_unit == true`.
    The link ID is loaded as `condo_link` in both files (prefix) or `condo_parent` in the units file.
  - **Elsewhere:** units that find their building count as parcels for the sales check, for other parcel files' match
    and in Bring in data's predictions. Bring in data's receipt adds "+ 1,360 units from condo_units.csv, with their
    building's shape" to the parcel universe and "units that find no building: left out" to the units file; a map
    layer's check counts parcels with shapes of their own (units take their building's). Changing condo handling clears
    OpenAVMKit's enrichment cache (it refuses a different set of parcels) and says "condo units" changed.
  - **Engine** (`engine/merge-one-conflict`, then `engine/enrich-fixes`): a field two files carry is filled from the
    second where the first is blank; land in equal shares; finished area from another file shared after the merge; each
    unit's land size set to its share after the merge (a blank one would later get the whole building's shape area).
- **Rule dialogs (valid sale, vacant sale):** each test is one line: the column, the test, the values, ×. The values are
  the same checklist dropdown as model group conditions (chosen values listed on the button; searchable checklist with
  each value's row count, All, Clear, a value typed in when the list is cut short).
- **Valid sale rule, price tests:** which prices count is decided only in the valid-sale rule, where it can be seen and
  changed. **+ Sale price is at least $1,000** is always offered once a sale price is chosen. It adds an ordinary test
  on the price column (at least 1,000, editable or removable like any test), read as the price dialog reads it. Below it
  are the zero, under-1,000 and negative counts, for information. The sample rows show that column as read.
- **Quality and condition (Big five 4 and 5):** one column the models use, and the user says first whether it's
  written as **Numbers** or **Categories** (a segmented control; revised 2026-11-04). The column is then one or the
  other: numbers (1–6) can be codes ranked as tiers too, and a column of text can't be read as numbers (the page says
  so). Numbers: which way is better (quality) or what they mean (condition), right on the page, with a live table
  under it of what each value sold for as read, best at the top: sales, median price and median price per sq ft as
  bars, and a verdict ("✓ Better sells for more", or "⚠ 2 steps up sell for less: does it run the other way?").
  Categories: its tiers ranked on the page, best at the top, each with its number (best the highest), buildings,
  sales, median price and median price per sq ft as bars; ↑↓ move a tier and every move is saved; a suggested order
  says so and waits for **Use this order**. A category's text (kept for reports) follows the ranked column; a text
  column loaded from a column of its own still shows as a Category row. Where both a number and a category exist, only
  the number is guessed. OpenAVMKit gets a number where higher is better. Nothing is written for a number until its
  meaning is said, so a guess never writes a wrong direction. Columns are converted as they load, by OpenAVMKit calcs
  (`<field>_src` plus a calc):
  - **Quality number:** higher is better (as written) or lower is better (flipped within the column's range: low + high
    − x).
  - **Condition number:** % good (as written; ×100 from a 0–1 fraction), % depreciation (100 − x), tiers higher-better,
    tiers lower-better (flipped), or remaining economic life (years, as written). Whether it's a 0–1 fraction or 0–100
    is found from the values and can be changed. **No condition: effective age carries it** is an explicit answer, not a
    blank.
  - **A category as the number:** its tiers are ranked on the page, in equal steps (1, 2, 3…, the best the highest;
    one number for names meaning the same, VG and Very Good). A starting order comes from tier names it knows: letter
    grades (AA best, with + and −), Excellent…Poor and their codes (EX, VG, GD, AV, FR, PR), Q1–Q6 and C1–C6 (1 best),
    and numbered codes. Unknown names go last, labelled to be placed. It's written as a `map` calc; a value not ranked
    reads as missing. The same column can be both the category and, ranked, the number.
  - **No popups (revised 2026-11-04):** the Column row has the column only, and what's still to do ("rank its 8
    tiers"). Which way is better, what the numbers mean, whether % are 0–1 or 0–100, the tiers and the evidence are
    all on the page; no reading button, values list or Compare columns, and no notes beside the segmented controls,
    which are as wide as the dropdowns. What condition numbers mean is a compact list of radios; what the chosen one
    means is under the row's label. Big five's parts (revised 2026-11-04): each field is a capsule of its own, their
    columns lined up; no grey line under a label ("Required", "Used for modelling"); an area's reading is left out
    unless it needs a look (the unit is chosen beside it); a year's reading is the range alone ("1945–2017"). The
    candidates endpoint stays, unused by the page.
  - **One column, two fields:** a category can be both the text and, ranked, the number. Such a column is loaded once,
    as text (`<column>_raw`), and each field is worked out from it by a calc.
  - **Combined codes** (`Q4C3`, `B+5  130%`, CDU) are not split by the wizard: guessing the parts was too much magic.
    The plan is a custom expression builder the user writes the split in. Until then such a column can still be ranked
    whole. Compare columns notes a code with a percent in one value, and that CDU measures more than condition.
  - **Evidence**, shown and never applied, worked out live from what's chosen. The Numbers table's first column is the
    original value as the file writes it (or its range), then the value as loaded. Each part says what it's based on
    and is left out, with a note, when its inputs aren't there:
    - **Words:** "In the file" is the number as the file writes it; "Loaded as" is what OpenAVMKit gets, higher always
      better. Said once above the tables; no sample line (revised 2026-11-04).
    - **Against age:** condition's median, in the file and loaded as, by effective age band (year built if there's no
      effective year; the project's valuation date). A meaning that makes newer buildings come out better is marked as
      fitting, and the verdict ("✓ Loaded this way, newer buildings come out in better condition", or older: "is it the
      other way round?") is shown only when condition does move with age (the rank correlation, as for the fitting
      mark). When it doesn't, as when nearly every building is one code, it says "Age doesn't tell: condition is about
      the same at every age (median 4 in the file). Go by what the values mean, and what they sell for below", never a
      tick for whichever meaning is picked.
    - **Against price:** a row per value loaded as when there are 10 or fewer (a grade of 7 to 11 is five rows, never "7
      and up" bands); more, and five bands with as many parcels each, labelled as ranges ("under 40", "40–55", "85 and
      up"); % good and % depreciation in fixed bands. Each row: the **text beside it** (the paired category,
      bldg_quality_txt or bldg_condition_txt, when loaded: "C-", most common first), the sales, the **median sale
      price** (with a bar), the **median price per sq ft** (with a building size), and the same within the **most common
      type** alone ("SFR_DETACHED sales", its median price; the type from land use, else building type, description,
      class or style). Said above it: better should sell for more, but a grade is often tied to a kind and size of
      building and price per area falls as buildings get bigger, so across every sale it can run the wrong way; compare
      within the one type. The building's main card (its first row) is used. Valid sales only once there's a valid-sale
      rule or column, all matched sales before.
    - **Tier flags:** tiers with under 10 sales are flagged as thin. A tier ranked above another that sells for less is
      flagged (both with 10 or more sales), and the count of such steps is shown.
- **Sample county:** `sample/us-nc-guilford-synth` (shipped in the bundles under `sample/`) is a slice of Guilford
  County's public data, altered, with these problems planted: see its README.
- **"In another file…"** on every parcel field: pick or add the file, its ID column (matching the parcel ID, or the
  second ID), and the field's column. The file joins the universe (`merge.universe`, on `key2` when matched that way),
  and the steps already seen guess from it too.
- One universe file and one sales file for now; more complex merges come later.
- **Repeated and blank IDs** (one standard notice and dialog, wherever an ID is checked):
  - **Stray repeats** (fewer than 10 extra rows *and* under 1% of the rows) are a warning, not an error: "⚠ 1 repeated
    ID", with no choice made for you (OpenAVMKit would keep the first row of each meanwhile). Once you choose, it shows
    as resolved with the choice: "✅ 1 repeated ID, first kept". More than that blocks until you choose, since it usually
    means several rows per parcel or the wrong ID.
  - **The check is two lines:** the result ("219,381 parcels"), then the issues, each with ⚠ or ✅, then Resolve….
  - **Resolve…** opens the duplicates dialog: every row of a few repeated IDs side by side, then keep the first (sorted
    by a loaded field, ascending or descending) or drop every repeated row, with the result ("2,000 rows → 1,995
    parcels"). Written as the file's `dupes`.
  - **Combine each parcel's rows into one** (2026-11-14; a file of more parcel details only; `wizard/combine.py`,
    `Combine.tsx`), for a file whose rows each say something different about the parcel (one row per amenity: Lee
    County's parcel amenities, 259,105 rows for 224,882 parcels). **Each row is about** a column (guessed: the text
    column whose values don't repeat within an ID, fewest values first); its values, capitals and spaces ignored, in
    **groups**, a yes/no field each (`has_open_water`, 1/0), suggested from the values' words (water, canal, golf,
    rail...; **Edit groups…**: rename, move a value to another group, a group of its own, or out; one field per value
    instead); each **number column** one number per parcel (largest, smallest, total, average, how many; a distance
    the smallest, else the largest); and, ticked, **the main value**, a category (`main_amenity`): the first value
    in an order the user sets that the parcel has (**Set the order…**: ⤒ ↑ ↓, with how many parcels each is the main
    one for). A line shows what the first example ID becomes; the footer "259,105 rows → 224,882 parcels · 15
    fields". OpenAVMKit can't reshape a file, so OAK box writes `<name>.combined.parquet` beside the original in
    `in/` (made again when the original or the set-up changes: its key is in the file's metadata), and the project
    loads that; the fields are the user's own (Your own fields, land). Keeping the first row or dropping repeats
    goes back to the original. The ID check reads "30,112 repeated IDs, rows combined" (the original's repeats).
  - **Blank IDs** block until confirmed (❌): a row with no ID can't be joined, and OpenAVMKit drops rows with no `key`
    when it joins the parcel files. The dialog explains it and has a tick box, "Drop the 442 rows with no ID"; ticked,
    it's ✅. In a sales file it's a warning, acknowledged the same way.
  - **Colours mean what's left to do:** ✅ green, decided; ⚠ yellow, something to decide; ❌ red, blocks a run. Every
    issue has an action, so the aim is all green.


Choosing fields file by file (F3c) shows every column of every file, most of them blank. The **Fields** tab instead asks
one small question at a time, across the whole project, and writes the same OpenAVMKit settings: each file's `load`,
plus the merge lists that stitch the files together (`data.process.merge`). F3c stays as the **Advanced view**. Both
edit the same settings, so you can switch at any point.

**Where:** a third tab, **Fields**, after Input files (`#/projects/<id>/fields`, with `/<step>` for each step). It opens
at the first step that isn't done, or at Review when all are.

```
┌─────────────────────┬───────────────────────────────────────────────────────────────┐
│ 1 Your files        │                                                               │
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

- **Layout:** a classic installer wizard. The step list on the left shows done (✓), skipped (–) and the current step,
  and any step can be clicked. The question is on the right, with Back / I don't have these / Next at the bottom.
  (**Advanced view**, to the Input files list, went with that tab on 2026-10-31.)
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
  - Parcel files go into `merge.universe`, sales files into `merge.sales`. Not used files are in neither, and keep their
    `load`.
  - **The base** is the first parcel file with shapes. It is first in `merge.universe`, so every parcel in it is kept
    and the others left-join to it on `key`. The rest follow in file-list order.
  - **OpenAVMKit requires the base to be named `geo_parcels`** and to have shapes (`load_dataframes`, and enrichment and
    condos use that name). So the wizard renames the base's entry `geo_parcels` (an entry already using that name gets
    another), and a project with no parcel file with shapes is a problem listed on Review, not a "No shapes" step.
  - **Built:** what a file holds is kept on its entry in `oakbox.json` (`holds`), and the merge lists are written from
    it.
  - v1 has one sales file. Several sales files (e.g. one per year, appended) come later.
- **Parcel ID column** is loaded as `key` in that file.
  - **Guessed:** a column whose name looks like an ID (PIN, PARCEL, PROP_ID, ACCOUNT, KEY, GEO_ID…) and whose values are
    all, or nearly all, different.
  - **Checked once picked**, on the whole column:
    - parcel files: whether each parcel appears once, and, other than the base, how many of its IDs are in the base;
    - sales files: how many sales find a parcel in the base (repeats are normal).
  - **A parcel file with repeats** (permits, several buildings per parcel) is set to Not used, with "several rows per
    parcel: not used yet". Summarising such files comes later.
  - **A file with no usable ID** is flagged on its row, and can't be Parcels or Sales. (An ID made from row numbers, for
    a single parcel file, needs an engine change: §7 B14.)
- **Sale ID** (`key_sale`, §7 B13): a column of the sales file whose values are all different, or **Make one: parcel ID +
  date**, written as an entry `calc` that joins `key` and `sale_date`.
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

- **Each field is a row:** its readable name (description on hover, D42), a column dropdown, then a check and a few
  sample values.
- **The column dropdown** lists columns grouped by file: every parcel file for parcel fields, the sales file for sales
  fields, plus (none). A column already used shows as "used: Year built" and can't be picked twice. Except (revised
  2026-10-31): a yes/no field made by a rule (valid sale, vacant sale) only tests a column's values, it doesn't take it,
  so it can read a column another field uses ("also read by Valid sale"): valid and vacant sale from one sale type
  column, each its own rule on the one loaded column; and a category's text and ranked number (quality, condition) share
  one.
- **The check** reads the samples for that field's type: numbers, a year range for years, the date format found ("✓
  reads as month/day/year"), the yes/no reading ("✓ Y = yes, blank = no"). A column that doesn't read as its field's
  type is shown in red, not saved, with the Advanced view as the place to fix it.
- **Types and formats are not asked:** the type is the dictionary's (as in F3c), dates take the first common format that
  reads all samples, and yes/no columns are Blank = No.
- **Guesses are made when a step is first shown**, and saved like a choice, so the settings always match the screen.
- **Guessed, but not too clever:** a field is preselected only when a column's name matches the field's key or name, or
  a short alias list (e.g. YR_BLT, YEAR_BUILT → `bldg_year_built`), and the column passes the field's check. Otherwise
  it stays (none). Nothing fuzzy. A guess never replaces a choice already made, including (none).
- **Computed fields** (`either`) are asked only when what they're computed from isn't loaded: "Age in years" only
  without a year built. They're labelled "Only if there's no year built".
- **I don't have these** sets the step's fields to (none) and marks it skipped (–).
- **Valid sale and vacant sale are required** (OpenAVMKit won't run without them). Each has a last option: **I don't
  have this: treat all sales as valid** / **…treat no sales as vacant**. Picking it asks for confirmation in a warning
  dialog ("Every sale will be used to build and test the models, including ones that aren't arm's-length." /
  "…vacant-land sales will be treated as improved."). It's written as an entry `calc` setting the field to true / false,
  and shows as **Assumed** everywhere.

**Step 9: Review.** Every field with its source, grouped by step: the file and column, "Assumed", or "—". Each has
**Change**, which opens its step. Above, a count and the columns not loaded ("18 fields from 24 columns. Not loaded:
OWNER_NAME, MAIL_ADDR and 4 more"). Problems are listed first: no parcel ID, no sales, a missing valid/vacant sale, a
column that doesn't read.

**What it writes**, and nothing else:
- each file's `load` (as F3c), and the entry `calc` for a made-up sale ID (`["join", ["values", "key", "sale_date"],
  "str:-"]`) and for assumed valid/vacant sales (`["set", true]` / `["set", false]`);
- the sales file's `dupes`, on `key_sale`. Without it OpenAVMKit de-duplicates on `key`, which drops every repeat sale
  of a parcel;
- `data.process.merge.universe` and `.sales`, rebuilt from the Holds column whenever it or the file list changes.

**What it keeps in `oakbox.json`:** only its own state: the base, the steps seen and skipped, and the fields already
decided (so a guess is made once). The assumptions are the `calc` entries themselves.

**Changes made elsewhere:** the wizard reads the settings each time. A field loaded from two parcel files (possible in
the Advanced view) shows both, with a warning, until one is set to (none).

**Templates** for common CAMA exports fit on top later: a template is a set of file roles and a column → field map,
recognised by its column names. Not in F3d.

**Not in F3d:** files with several rows per parcel, several sales files, ``calc`/`tweak` beyond the three above,
templates, and the joined-result preview (F4).

- **Out of the flow for now:** the Input files tab (§F3b) and each file's own fields (§F3c), which the wizard's
  "Advanced view" link opened. They no longer match the wizard. Their links open the Data wizard, and **Project › Data**
  (Ctrl+2) replaces **Input files** and **Add a file…** in the menu; files are added on the wizard's steps. The code
  stays until we decide whether to bring them back or remove them.

## F3e. Data › Enrichments: public data about each parcel (built)
A step of its own, after More details. One compact card per kind of public data: an on/off box, where it comes from, one
line saying exactly what goes online, its options once on, and the fields it adds. A note above says that only the
rectangle around the parcels is sent (its area shown), never the parcel data, and that downloads are kept and reused.
The step's settings start, the first time it's shown, with distances, footprints and elevation on and census off (it
needs a key).
- **Distances to features** (OpenStreetMap, `data.process.enrich.distances`, entries with `osm: true`): a summary line
  ("Water bodies, parks… · up to 1–2 miles") and **Change…** for each feature's on/off, farthest distance (in miles or
  km, the project's long unit) and, for named features, also measuring to each of the N largest (`store_top`, `top_n`).
  OpenAVMKit's built-in features: water bodies, parks, colleges & universities, golf courses, railways
  (`transportation`), airports, coastline; and major roads by tags (`osm_tags` highway motorway/trunk). Defaults: water
  2 mi (3 largest), parks 1 mi (3 largest), colleges 2 mi, golf 2 mi on; the rest off. A map layer measured under the
  same name keeps it (the OSM feature is then not measured); a layer can't take a name an OSM feature uses. Columns:
  `dist_to_osm_<feature>`, `within_…`, `proximity_to_…`.
- **Building footprints** (Overture Maps, `overture`): each parcel's buildings' total footprint and height,
  `bldg_area_footprint_sqft`/`_sqm`, `bldg_height_ft`/`_m`.
- **Census** (US Census Bureau ACS 5-year, `census`): the county, picked from the project's state's counties (a list
  bundled from TIGERweb: `packaging/make_counties.py`), preset from the project's place; the survey year (2018–2024).
  The user's free API key is saved in OAK box's own settings on this computer (**Save**, **Forget**, its last four
  characters shown), never in the project, and handed to OpenAVMKit as `CENSUS_API_KEY`. Census on without a county or a
  key is ⚠ on the step, never ❌.
- **Elevation** (USGS 3DEP, `dem`): 10, 30 or 60 m tiles, the suggestion by area (10 m up to 600 km², 30 m to 8,000 km²,
  60 m beyond). Adds `elevation_mean_ft`, `elevation_stdev_ft`, `slope_mean_deg`.
- **Which fields: the user's choice.** Each card says **Adds [3 fields ▾]** (or "2 of 3 fields") and the names of those
  it adds, in the same button style as "N values ▾". The button opens **Fields from Building footprints**: a checkbox
  per field, with what each is under its name ("Median gross rent: rent plus utilities (ACS B25064)"); all ticked to
  start with. Distances tick the three kinds for every feature at once (`dist_to_osm_<feature>`, `within_…`,
  `proximity_to_…`), the largest features' columns included. Unticked fields go in `data.process.enrich.drop_fields`
  (universe and sales), which OpenAVMKit applies after every enrichment; the largest features' columns are named as
  they're found, so they're dropped by a pattern (`within_osm_parks_*`: `drop_fields` takes `*` patterns,
  `engine/enrich-fixes`). An enrichment with none ticked isn't downloaded, and the card and the step say so (⚠, not ❌).
  The receipt lists only the fields that came out.
- **Yes/no fields OAK box makes** (valid sale and vacant sale, assumed or by a rule) never have blanks, so they need no
  blank handling; OpenAVMKit warned about it on every run regardless, and now only warns when a yes/no field really has
  blanks (`engine/enrich-fixes`). A yes/no column from a file gets the user's choice (Blank = No / Blank = Yes, on its
  step), so nothing about blanks is left for the user to see.
- **When Bring in data runs:** each enrichment says when it starts ("Downloading building footprints from Overture
  Maps"). Before downloading, the service is asked whether it answers (a 10-second request, made with `requests` as the
  downloads are, so the check and the download agree about certificates); one that doesn't is skipped at once, unless
  what it downloaded before is kept, rather than waited on (OpenStreetMap's library waits a minute and tries again). The
  reason is short: "overpass-api.de's certificate couldn't be checked (certificate has expired)", "…didn't answer within
  10 seconds".
- **While it runs, it's never a mystery.** The clock is the server's and moves every second. The step that's running
  shows what it's doing inside ("Parks (2 of 4)", "Downloading buildings: 12,400 so far", "Working out slopes"), its own
  bar when that's known, and "working · 0:42 on this step". Each finished line shows how long it took, muted
  ("✓ Single-family: training CatBoost 3:31"), so a model much slower than the others shows without a warning of its
  own (2026-11-07: in place of the slow-model alert mocked earlier). The run says it's alive every 2 seconds; with no word for
  over 10 seconds it says it may be stuck (stop it, or wait). Until the first step, "Starting Python and OpenAVMKit".
  The detail comes from OpenAVMKit's progress events (`progress.report(..., sub=, part=)`) and, between them, the latest
  line it printed.
- **Skip this step** (footprints, census, distances, elevation): the step stops at its next checkpoint (between OSM
  features, Overture batches, elevation stages, census download and join), the parcels come back as they went in
  (nothing half-done kept: OpenAVMKit saves a download only once the part is done), the receipt says "Skipped: you
  skipped it while it ran", and the run carries on. A checkpoint can be as far off as one download (a single slow
  Overpass query). The app asks by a line in `out/oakbox/bring_in.skip`, which the run reads at each checkpoint. Loading
  and joining the files can't be skipped: Stop ends the whole run. Engine (`engine/enrich-fixes`): `progress.report`
  takes `sub` and `part`; `reporting(skip=)` raises `Skipped` (a `BaseException`, so the part's own `except Exception`
  handlers can't swallow it).
- **Certificates are checked as the computer does** (`truststore`, in every process OAK box starts: `oakbox/net.py`):
  Windows' own verifier, so an old cross-signed certificate in the Windows store (which made Python report "certificate
  has expired" for sites the browser opens) or a county network's own HTTPS root no longer stops a download.
- **A good OpenStreetMap citizen.** Overpass is a shared, volunteer-run service. OSMnx says it's OAK box (`OAK
  box/<version> (+https://github.com/larsiusprime/oakbox)`, not OSMnx's own name), keeps its rate limit on (it asks
  Overpass for a free slot before each query), and asks one query per feature chosen over the rectangle around the
  parcels, kept and reused (OSMnx's cache and OpenAVMKit's). When Overpass doesn't answer, nothing is sent to it:
  distances are skipped like any enrichment. Far under Overpass's guidelines (10,000 queries and 1 GB a day).
  Attribution: "© OpenStreetMap contributors" on every map, and on the receipt with a link to the Open Database License
  wherever OSM distances came in; the fields' source is "OpenStreetMap contributors (ODbL)". Map backgrounds still load
  OpenStreetMap's own tiles (light use, allowed), before a wide release, a tile provider meant for apps.
- **Census is for the county the parcels are in.** `counties.json` has the rectangle around each county (from TIGERweb).
  The county is guessed from the project's place if the parcels are in it, else from where the parcels are; a county
  they aren't in is ⚠ on the card and the step ("the parcels aren't in Wake County, NC: they look to be in Guilford
  County, NC (37081)", with **Use it**): its census figures would all be blank. An enrichment that fails is skipped, its
  fields missing, and Bring in data carries on. Each one's log is kept at `out/oakbox/enrich_logs/`.
- **Receipt:** an **Enrichments** card above the parcel universe: each one's result (✓ coverage as the parcel universe
  ended up: "6,589 parcels (70%) have a building", "every parcel"; ⚠ for distances when some features failed, naming
  them; ✗ "Skipped: overpass-api.de didn't answer"), its time or "reused from last time", the fields it added, and **Run
  again** beside one that didn't work. Its fields are grouped as **Public data (Enrichments)** in the field tables, with
  the source. "Out of date" says "building footprints", "census", "elevation" or "distances to OpenStreetMap features".
- **Engine** (`engine/enrich-fixes`): elevation stats for parcels sharing a shape (condo units borrow their building's)
  and for slivers that lost every cell to a neighbour; both were blank.

## F3f. Data › Deeds (built)
A step of its own, after More details: **Which deed was each sale recorded under?** The deed ID (`deed_id`: OAK box's
own field, OpenAVMKit's settings name it), or the deed book and page; grantor and grantee under More. Guessed from the
sales file's column names. Optional: **I don't have these**.
- **What it's for:** sales scrutiny (notebook 2) flags sales sharing a deed ID and a sale date as one sale of several
  parcels, and sets them aside. The step says how many it will find ("123 deeds have more than one sale on the same day:
  361 sales…") and how many sales have no deed ID.
- **What it writes:** `analysis.sales_scrutiny.deed_id`: `deed_id`, or `deed_book_and_page`, a calc on the sales file
  joining book and page ("123-45"), blank when either is.
- **Engine** (`engine/enrich-fixes`): sales without a deed ID were all read as one deed ("None") and flagged together;
  blank deed IDs are now left out.
- **Sample:** a deed's sales move together when the sample's dates and prices are nudged, so the real multi-parcel deeds
  stay on one day (123 of them).
- **Buyers' and sellers' surnames** (for sales scrutiny's same-surname check, F6): under More, the seller and buyer
  names (`deed_grantor`, `deed_grantee`) and, optionally, their surnames already split (`deed_grantor_surname`,
  `deed_grantee_surname`: used as given). Once names are loaded the step asks **How are the names written?** Surname
  first (`SMITH JOHN A`), surname, a comma, given names (`Smith, John A`), surname last (`John A Smith Jr`), or **my own
  pattern** (a regular expression with a `surname` group). Nothing is guessed silently: the format is guessed from the
  names and said why ("100% of the names are in capitals without a comma, the way recorders write SURNAME GIVEN"), with
  a **live preview** of real names and the surname read from each (six sharing one, six not) and the counts (names read
  as people, skipped as companies, trusts, banks or governments, with no surname found; sales sharing a surname). Trying
  a format is a preview; **That's right** / **Use this** keeps it (written as
  `analysis.sales_scrutiny.same_surname.pattern`). Names too irregular for any pattern are better split before they come
  in: the step says to give the file surname columns and load them as the surname fields. Unconfirmed when Check sales
  is first used, the guess is written down. On the sample: 196 of 3,804 sales share a surname (about 150 made so, the
  rest by chance).

## F3g. Data › Permits (built)
A step of its own, after Enrichments: **Do you have building permits?** Add the permits file (one row per permit, with
the parcel ID; it can't be the parcel universe or sales file), or **I don't have these**.
- **The file:** its parcel ID (the usual ID row: matched against the parcel universe, units included, with
  **Reconcile…**; "2,140 permits · 100% find a parcel"), the **date issued** (a column that reads as a date, its range
  shown), and **what each permit is** (a column with a few kinds). All three are guessed when the file is added.
- **What each kind means:** a table of the kinds with their counts, each **Teardown (demolition)**, **Major
  renovation**, **Minor renovation** or **— not a renovation**, guessed from its words (demo… teardown; addition,
  remodel, renovat… major; alter, repair, interior… minor) and marked "(guessed)" until said.
- **A sale demolished within N days** (365) of selling is a teardown sale, counted as vacant. **Major renovations reset
  the effective year built** (on unless there's no year built: "needs the year built").
- **What it writes:** the permits file's `date` and `permit_type`; calcs `is_teardown`, `is_renovation`,
  `renovation_num` (3 major, 1 minor, 0) and `renovation_txt` (the kind); `dupes: allow` (a parcel has many permits);
  and `data.process.enrich.permits` (`sources`, `max_days_to_demo`, `calc_effective_age`). The file isn't merged into
  the parcel universe.
- **Receipt:** "42 of them teardown sales: demolished within 365 days, so counted as vacant" under the sales record's
  vacant count, with **see them**.
- **Engine** (`engine/enrich-fixes`): on the sales, teardowns and renovations went to every sale of the parcel (worked
  out on the parcel ID, not the sale ID), so a house sold twice before its demolition had both sales made land sales;
  the effective year stopped with an error on sales without a year built (sales take their parcel's); `reno_date` was
  filled with "UNKNOWN" as an improvement category.
- **Sample:** `in/permits.csv`, 2,140 made-up permits, 40 of them demolitions within a year of an improved sale (planted
  problem 15).

## Later: building the joins live (intent; to be designed feature by feature)
A stage where the user builds the joins between their files in real time: inspect what is in each file and in the joined
result as it grows, so they can make informed decisions about how to build it up. Everything it does maps to
OpenAVMKit's own settings (`data.load` mappings, `dupes`, `data.process.merge`).
