# Across the app: screens, rules, help and menus

What isn't one step's: the home screen, the guided build, the project screen, plain-language rules, tax years, help,
data health, transforms, and the menus and window.

## 3.1 Home screen
- **Projects**: name and tax year.
- **New project** (§3.0 F1), and **Show in folder** and **Delete** on each project (F1b).
- *(The sample county is removed for now, D19.)*

## 3.2 The guided build
*Being redesigned feature by feature in §3.0. The text below is the earlier draft, kept for reference until each part is
re-agreed.*

There is no up-front wizard. **New project** asks for a name and opens the project, and the project screen *is* the
guide. The user works down one ordered list: five **setup stages**, which describe the data, then the six **steps** of
§3.3, which run the engine. Each one is a single screen.

**Every stage and step has the same four parts:**
1. **Decide.** Choices are made against the user's real data: real column names, real distinct values with counts,
   previews. Every default is shown as a pre-filled choice with a one-line "why". Nothing is applied silently.
2. **Check.** Fast diagnostics before anything heavy: match rates, duplicates, what would be dropped and why. These run
   in the app service and read only the columns they need, so they take seconds even at 500k parcels. They never run the
   engine.
3. **Run.** Only steps run the engine. A setup stage just saves its decisions.
4. **Receipt.** What happened, in plain words: rows in and out, every drop with its reason, warnings. Each number opens
   the rows behind it. For runs, the receipt compares the engine's counts (upstream A14) with what Check predicted, and
   flags any difference.

A stage or step is done only when the user clicks **Looks right** on its receipt. **Back** always works, and every
decision is saved as soon as it's made. Changing an earlier decision marks later stages out of date, with the reason
(§6.4).

**Under the hood** is a collapsed panel on every stage and step, open to everyone. It shows the exact `settings.json`
fragment this stage wrote and which engine stage it runs. Settings can also be exported whole, for notebook users.

### Setup stages
1. **Basics.** Name, place, tax year, valuation date.
   - Oakbox derives the locality slug (no dashes inside the name), map centre and county FIPS.
   - It proposes **units** (imperial or metric) from the place, and the user confirms. Units decide every field name
     (`*_sqft` vs `*_sqm`).
   - **Valuation date.** Everything is valued as of this date; it also drives ages and time adjustment. *When checking
     an existing roll, it must match that roll's valuation date, or the comparison isn't like-for-like.*
2. **Your files.** The user adds any number of files, one at a time, in any format from §4.1. For each file Oakbox shows
   a preview of the rows, the column types and the row count, and the user says what it is:

   | Kind | Example | Becomes |
   |---|---|---|
   | **Parcel map** | Parcel polygons | The spine everything attaches to (`geo_parcels`) |
   | **One row per parcel** | Main CAMA table | Attached by ID |
   | **Several rows per parcel** | Buildings, land segments, improvement details | Collapsed to one row per parcel (Stitch) |
   | **Sales** | One or more sales files | The sales table; several files are stacked |
   | **Points** | Permits or addresses with latitude and longitude | Attached by position (`lat_long` merge) |
   | **Map layer** | Neighbourhoods, zoning, school districts | Attached by overlay (§3.12.1) |
   | **Not sure** | — | Oakbox suggests a kind from the columns and the ID check |

   - **ID column.** The user picks the parcel ID column, which is always read as **text** so leading zeros are kept.
     Oakbox checks uniqueness straight away: "12,431 rows but 11,902 IDs. Does this file have several rows per parcel?"
     A file can need several columns to identify a row (property + improvement + detail), and can belong to a parent
     file rather than to the parcel directly.
   - **Fixed-width text** (such as PACS appraisal exports) needs a layout: the user picks a known layout (Oakbox ships
     the PACS ones it has been tested on) or supplies one. A recognised export is added as a whole: Oakbox lists its
     files with sizes and a plain description, and preselects the ones modeling uses (for PACS: property, improvements,
     improvement details, land). Oakbox converts each file to Parquet in `in/`, keeping only the fields the user keeps
     (§4.1).
3. **Stitch.** How the files become one table of parcels and one table of sales. Oakbox drafts the plan and the user
   confirms each part:
   - **The spine.** The parcel map. Without a map (allowed only with a warning, D4), a one-row-per-parcel table.
   - **How each file attaches:** by ID, by position or by overlay; sales files stacked (`append`). A nested file rolls
     up through its parent: improvement details → improvements → parcel, collapsing at each level.
   - **Matching.** Each attachment shows its match rate both ways: "11,640 of 11,902 IDs match the map (97.8%). See the
     262 that don't." When IDs nearly match, Oakbox suggests a fix and shows how many more would match: "IDs here have
     dashes and the map's don't. Remove dashes? +247 matches." Fixes are trim, remove characters, pad with zeros, change
     case and keep only part. They compile to `calc` on that file (§3.13), so Check and the engine apply the same rule.
   - **Rows without an ID** are dropped with a named reason, counted in the receipt.
   - **Several rows per parcel.** Per field: **sum**, **largest**, **smallest** or **first**, with sensible defaults
     (areas sum; year built takes the earliest; codes take the row with the largest area). This becomes that file's
     `dupes` setting.
     - In the parcel table itself, duplicates usually mean versions or owners (PACS: supplement number, one row per
       owner). Oakbox proposes "latest version, primary owner" and shows how many rows that removes.
     - In the parcel map, several polygons for one ID are merged into one shape.
   - **On the roll, not on the map.** Parcels without a polygon are listed by type, because some are expected: condo
     units that share a polygon (handled by condo rules, §3.5), and accounts newer than the map.
   - **Column clashes.** When two files have a column of the same name, the user picks which one wins (`reconcile`); the
     other is kept with the file's name as a suffix.
   - **Context data starting point:** **None (offline)**, **Recommended**, or **Custom**, which opens the Enrichment
     screen (§3.12). Nothing heavy runs without a cost estimate first.
   - **Preview:** the stitched parcel table, with each column's source file, and the parcels each file left blank.
4. **Columns.** Oakbox maps the stitched columns onto OpenAVMKit's data dictionary (163 standard fields): "We think
   `SQFT_LIV` is *Finished building area*. Correct?" The user only confirms uncertain matches. Check shows each standard
   field after its transform: blanks, range and examples.
   - **Transforms** fix columns that don't match as-is: unit conversion, code→number tables, date formats, combining
     columns (§3.13).
   - **Year built, not age.** Age is derived from the valuation date.
   - **Other columns** the user wants to keep are classified automatically as land/building/other ×
     number/category/yes-no, shown for review. OpenAVMKit's fills and models ignore unclassified fields.
   - **Location fields** (neighbourhood, market area…) are marked as locations, so they can drive breakdowns, equity
     studies and estimation.
   - **Values to check.** "Which value(s) do you want to check against sales?" One or more **total value** columns, such
     as the current or last year's appraised value. Step 4 needs at least one. Land values are not checked in v1.
5. **Sales basics.** Decided before step 1, because OpenAVMKit applies them while loading.
   - **Required columns:** parcel ID, sale date and price.
   - **Sale ID:** OpenAVMKit needs a unique `key_sale`. If the file has none, Oakbox builds one from parcel ID + date (+
     a counter).
   - **Date format** is detected and confirmed with examples ("We read `03/04/2023` as 4 March 2023. Correct?").
     Unparseable dates are a blocking Data health problem.
   - **Validity:** the user ticks which office codes mean "valid", from the codes actually in the file, with counts.
     With no code column, all sales start valid.
   - **Vacant at sale:** which codes or rules mean "the land was vacant when sold". Default: same as the parcel's
     current vacancy.
   - Oakbox always produces `valid_sale` and `vacant_sale`; OpenAVMKit refuses to run without both.
   - **Check** starts the **sales funnel**: all sales → not matched to a parcel → invalid by office code → remaining.
     Step 3 completes it (§3.3).

After Sales basics, the project has one model group, "All properties", with a match-all rule. Real model groups are
built in step 2 (§3.5).

**The sample county is a walkthrough.** It goes through the same stages and steps, with Petersburg's answers pre-filled
and annotated ("Petersburg's sales file marks valid sales with code Q"). The user confirms each one. There is no "run
everything" button in the app; CI's smoke test drives the same API end to end (D40).

## 3.3 Project screen: the steps
The setup stages are followed by the steps that run the engine. Each step follows the four parts of §3.2. Its Run has a
progress bar, time remaining and **Stop**, and its receipt has **See results**.

Before running, a step shows what's stale and why ("Model groups changed: steps 3–6 will re-run"). A run ends with the
app: closing it (or the app ending any other way) stops every run and every process they started. **Not built:** picking
a run up again after the app reopens.

A tab asked for that waits on an earlier step (it isn't accepted on an up-to-date run) opens the first step, in order,
that isn't, with a notice above the tabs saying why: "Variables waits for Bring in data. Bring in data is out of date:
run it again, then press Looks right. What changed: fields worked out after the files join." Never a silent switch to
another tab (revised 2026-10-31). Bring in data always names what changed; a change no line names (a newer OAK box
writing the step's settings differently) is "how OAK box writes this step's settings (a newer OAK box)". Opening a
project rewrites its settings.json if this OAK box would write it differently, so what that changes shows on opening,
not at the next unrelated change (a Variables tick once put Bring in data out of date this way, and the screen jumped to
Check sales).

Each step is a tab, named short (settled 2026-11-05): 1 Inputs, 2 Model groups, 3 Sales, 4 Evaluate, 5 Variables, 6
Models, 7 Report. A step's name is its page's title and what Looks right and the tabs' notices say ("Press Looks right
on Sales first"). Its run keeps a verb: **Bring in data** (Inputs), **Check sales** (Sales), **Check my values**
(Evaluate); in Models, **Model values** is the step with its Looks right ("Models › Model values"). Elsewhere in this
spec the runs' names often stand for their steps.

| Step | What runs (OpenAVMKit stage boundaries) | Internet? |
|------|------------------------------------------|-----------|
| 1. Inputs (run: Bring in data) | Load, merge, condo handling, enrichment (§3.12). The street enrichment is explicitly off. Ends before model group tagging. Then Data health and Field profile (§3.9) | Only for online enrichments |
| 2. Model groups | Model group tagging (§3.5). Writes the 1-assemble hand-off | No |
| 3. Sales (run: Check sales) | Clean, in OpenAVMKit's order: OpenAVMKit's own fills (the user's are step 5's), equity clusters, sale processing (sales window, validity rules, **time adjustment**), scrutiny (sales set aside, minus the user's keeps, plus their exclusions: §3.6, F6). Writes the 2-clean hand-off (rare categories: step 5) | No |
| 4. Evaluate (run: Check my values) | Ratio, vertical-equity and horizontal-equity studies on the named value fields, per model group and overall (§4.2). Reads the 2-clean hand-off explicitly, never stale step-5 output | No |
| 5. Variables | Prepare the fields (the user's fills, rare categories: F7), then the variable tests and the variable lists (F9) | No |
| 6. Models | Splits, spatial lag, **Try** models (repeatable) → how they did → small groups → **Finalize** → the model values checked against the sales, beside the roll's (F9). Main models only (`run_vacant=False`) | No |
| 7. Report | Export (CSV, GeoPackage, Excel, Shapefile, GeoParquet) and a printable HTML report of the model values (F10). Runs nothing | No |

**Back and Next always in view** (2026-11-11). A project's page is the window's height: the lid (with the plate) and
the tab row stay put, and only the folder under them scrolls, both ways. A step's foot (Back, its extras, Next) sticks
to the folder's bottom while its sheet runs past it, a shadow over what's under it, and settles under the sheet at its
end. The plate has ‹ › at its right, pressing the step's own Back and Next (disabled with them), named on hover by the
step they go to.

**A tab that waits** (2026-11-11) on an earlier step, out of date or not yet accepted, is greyed in the tab bar but
still opens: its page dimmed under a bar that names the step it waits on and goes there. Nothing ever moves you off
the tab you're on; that step's Looks right (or Next on) brings you back to the tab you came from.

**An exclusion is a filter, not a reason to run again** (2026-11-11). A sale excluded by hand (Check sales' review,
Outliers' "invalid sale") leaves Check sales up to date: it changes no fill or equity cluster, and the time trend and
the other sales' flags only slightly. Everything after leaves it out as it reads the sales (the models through
OpenAVMKit's `load_cleaned_data_for_modeling`, Evaluate as it runs). A step whose results still have it says so
("3 sales excluded since this ran") with Run again offered, never asked; out of date it isn't. A keep (a sale scrutiny
set aside, brought back) still needs Check sales to run again. The models' part of the ratio study settings
(`study_set_predictions`, `outside_models`) is no part of Check sales' either.

**What each step's receipt shows:**
- **Step 1:** rows read from each file; each attachment's match rate, against the Stitch prediction; rows collapsed by
  several-rows rules; sales removed as office-invalid. Then Data health and Field profile (§3.9).
- **Step 2:** parcels and sales per model group, split improved/vacant; parcels left unassigned.
- **Step 3:** the full **sales funnel**, continuing from Sales basics: outside the sales window → flagged by scrutiny →
  overridden (§3.6) → used. Plus the time adjustment found per model group, as a chart.
- **Step 4:** the study tables (§4.2), with the funnel's final count beside each.
- **Steps 5–7:** as F7, F9 and F10.

**Results views:**
- a map coloured by ratio, value, model group or flag
- sortable tables
- charts
- "things to look at" lists: flagged sales, model outliers, sparse model groups

## 3.4 Plain-language rules
- **No jargon without an explainer.** "COD 14.2: your values are fairly uniform. The IAAO target is under 15."
- **Errors** say what happened, why, and what to click next. OpenAVMKit's fatal and warning messages, such as variable
  validation, are mapped to plain text. Stack traces go only to the log.
- **Zoom** (67% to 200%) is available. Nothing important is shown only by colour.

## 3.7 Tax years
- **Storage.** A project is one jurisdiction × one tax year: `Documents\Oakbox\<Jurisdiction>\<Year>\`, which holds a
  standard OpenAVMKit locality.
- **Shared cache.** Downloaded enrichment data (`cache/`) is shared per jurisdiction, so a new year doesn't re-download
  gigabytes.
- **Start next year** copies settings, model groups, column mappings, transforms, standards profile and report
  templates. It can optionally copy overrides still inside the sales window.
  - It does *not* copy model outputs or tuned parameters, and offers a fresh tune.
  - The user then imports new files, and the setup stages only ask about what changed: new or missing files, columns and
    codes.
- **Read-only past years.** Past years are read-only by default. Each records its engine version and random seed, so
  results can be reproduced for an appeal.

## 3.8 Help
- **"?" on every screen** opens an offline help page for that screen.
- **Glossary pop-ups** wherever a technical term appears.
- **Error screens** link to the matching help page and to the Discord.
- **Later, opt-in AI helper:**
  - (a) a small local model over the help pages, fully offline.
  - (b) the user's own frontier-model API key. This is an explicit, disclosed exception to D12.

## 3.9 Data health and Field profile
Shown after step 1 and after any re-import.

**Data health** (integrity problems). Each problem gets one card: what's wrong, how many rows, an example, and what to
do.

| Problem | Safe one-click fix | Otherwise |
|---------|--------------------|-----------|
| Duplicate parcel IDs | Combine per field (sum/largest/smallest/first, §3.2) | Export the list |
| Sales that match no parcel | Exclude them | Export the list |
| Sale dates that can't be read | — (blocking) | Fix the date format |
| Invalid or empty geometry | Repair / drop (dropped parcels listed) | Export the list |
| Parcels outside the jurisdiction | Drop | Show on map |
| Impossible values (negative area, year built 2099, $0 sale) | Treat as missing | Export the list |
| Wrong coordinate system | Reproject (with confirmation) | — |

**Field profile** (does the data mean what it says?). This reflects the QA the OpenAVMKit tutorial insists on before
model groups are defined.
- **Per field:** % filled, % zero, distinct values, top values. Mostly-empty fields are flagged.
- **Cross-checks on code labels:**
  - "412 parcels coded LAND have a building area"
  - "88 single-family parcels have no building area"
- **The blank-building-area rule (default, stated plainly).** OpenAVMKit treats a blank finished area as **0, which
  makes the parcel vacant** and erases its building fields. Oakbox shows a card: "1,240 parcels have no finished area.
  **By default they're treated as vacant land.**" A map and list of them are shown.
  - The user accepts with no action needed.
  - **To opt out** (project setting): "Don't treat blank finished area as vacant". The user then names an explicit
    vacancy signal, such as a land-use code or a vacant flag. The remaining blanks become candidates for an estimate
    (§3.12.2) or a fix at source. This needs upstream A9.

Rules for both screens:
- **Blocking or warning.** Only blocking problems stop the next step.
- **No silent fixes.** Every fix is logged and listed in each report's "Data corrections" appendix.
- **Originals are kept.** Oakbox keeps the originally imported values, so exports can always return the office's own
  data.
- **Download problem list (Excel),** so the office can fix the source in its appraisal (CAMA) system.

## 3.13 Transforms and corrections (`calc` / `tweak`)
Real extracts rarely match OpenAVMKit's fields as-is. There's no free-form editor in v1.
- **Transforms in Match columns.** These are typed, previewed on real rows, and compiled to `calc`:
  - **Unit converter** (acres → sq ft, …)
  - **Code → number table** (grade "B+" → 7), with an editable map and a list of unmapped values
  - **Date format**
  - **Combine columns into an ID**
  - **Trim / strip leading zeros**
- **Where they go.** Transforms referencing only the source file go into `data.load.<file>.calc`. Ones that reference
  enriched fields go into `data.process.enrich.calc`. Scratch columns are removed with `drop_fields`.
- **Advanced → Formula builder.** An operator picker over OpenAVMKit's calc reference, with a row preview. Safe
  defaults: divide-by-zero gives blank, empty → fill.
- **"Correct this parcel's value"** in the parcel pop-up. Stored as `tweak`, and listed in the Data corrections
  appendix.

## 3.14 Menus and window

Inside a project: the oak band (▒) with the plate on it (D21: where you are, and home when clicked; nothing written on
the bare wood), the folder tabs standing on its edge, and the open one (here Model groups) running into the page:

```
┌ Travis County 2026 – OAK box ───────────────────────────────────────── _ □ × ┐
│ File  View  Project  Help                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ╔═════════════════════════════════════════════════╗ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ║ ⊘ OAK box │ Travis County 2026 · Tax year 2026 ⊘ ║ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ╚═════════════════════════════════════════════════╝ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│▒ ┌──────────┬──────┬────────────┬────────────────┬─────────┬──────────────┐ ▒│
│▒ │ Metadata │ Data │ 1 Bring in │ 2 Model groups │ 3 Check │ 4 … 7 locked │ ▒│
├──┴──────────┴──────┴────────────┘                └─────────┴──────────────┴──┤
│  Model groups waits for Bring in data… (only when the tab asked for waits)   │
│ ┌────────────────┬─────────────────────────────────────────────────────────┐ │
│ │ ✓ How to start │                                                         │ │
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

- **File:** New project… (Ctrl+N), Open recent ▸ (the last projects opened), Show project folder, Close project (back
  to Projects), Settings… (Ctrl+,; also the gear on the plate, §5), Exit.
- **View:** Density ▸ Default · Compact; Zoom in, Zoom out, Actual size.
- **Project:** Metadata (Ctrl+1), Data (Ctrl+2), Add a file…. Greyed out on the home screen.
- **Help:** OpenAVMKit documentation (opens in the browser), About OAK box (version, OpenAVMKit version, licences).
- **No Edit menu.** Ctrl+C / V / X / A work in text boxes without one on Windows and Linux. On macOS, where the
  shortcuts need an Edit menu, pywebview adds the standard one itself; OAK box's own View menu replaces pywebview's
  default one there.
- **No Undo or Save:** changes save as they are made, and a partial undo would mislead.
- **The title** changes with the screen: "OAK box" on Projects and New project, "<project name> – OAK box" inside a
  project.
- **Built (Windows and Linux):** real native menu bars from one definition (`oakbox/menus.py`):
  - Windows: the Win32 menu bar on pywebview's window, using .NET's classic `MainMenu` (`oakbox/winmenu.py`).
  - Linux: pywebview runs on Qt (PySide6, LGPL), and the menus are Qt's own menu bar on its window (`oakbox/qtmenu.py`).
    See §6.1 for the window.
  - Shortcut labels (Ctrl+N, Ctrl+1, Ctrl+2, Ctrl+=, Ctrl+-, Ctrl+0, Ctrl+,), Alt-key letters, radio items (Density),
    and Project items greyed out on the home screen.
  - Each menu is brought up to date as it opens. That includes **Open recent**: the last 8 projects opened, kept in OAK
    box's settings.
  - The web view keeps the keyboard, so the page handles the shortcuts and passes Alt (+ a letter) on to the menu bar.
  - Python owns what the menus show. View items save the setting there and tell the page to restyle; the page says which
    project is open.
  - CI opens the real window on Windows, and on Linux under a virtual display, and clicks through the menus (`python -m
    oakbox --selftest-menus`). The keyboard (Alt, Alt+letter, Ctrl+N/1/2), which the self-test can't press, was checked
    by hand on Windows.
- **Elsewhere** (macOS, from source), pywebview's own menus are the fallback: same items, but fixed at start-up (no
  check marks or greyed items). macOS gets native menus when it gets a native window.

**A project opening** (2026-11-09): until its details and its files' first reading (the Data wizard's) are in, the
window shows only the lid with the project's name and one manila sheet: Opening Project "<name>"…, a loading bar (how
far while files' quick-read copies are made, else a moving bar), the time elapsed, and Cancel. Nothing else. No tabs, no map, no Settings: nothing to press that could act on a
half-opened project. Cancel stops the reading in the window and goes back to Projects; the server finishes what it's in
the middle of on its own (its quick-read copies are kept, so the next opening is quicker).

**Moving between steps** (2026-11-09): Next (and I don't have these) moves at once, the sidebar and the step's header
with it; the step's content shows a loading bar in its place until its first data is in, never the old step waiting.
Showing a step and moving on from one are quiet: no "Saving" or "Updating" in the corner (what they change shows on the
steps). The corner's Activity pill is for saves, runs and refreshes; a first load is shown where it will appear.

**Nothing runs past its box** (2026-11-09): a step's sheet shrinks with the window down to 36rem, then the folder
scrolls sideways within itself; inside it, rows wrap, pairs stack, tables scroll in their own wrapper (AGENTS.md). The
containment rules have zero specificity, so a widget's own sizing wins (the sales-by-year chart: a column per year
wide enough for its labels, scrolling sideways), and a map's own pieces are exempt (deck.gl's drawing layer sits in a
corner box as wide as the map). A field's reading and its values button stay side by side, lined up, wrapping only
near the sheet's narrowest. In the map window, Shapefiles shows the project's map layers over the parcels (Follow, or
"🗺 Your map layers" in the picker), each its own colour.

## 3.15 The map window (designed 2026-11-09; being built)

One map of the 🌐 Parcel Universe and 💰 Sales Record that stays with the user through every step: rich context to
understand the data and catch patterns a table hides (a subdivision whose IDs don't join, a township with no year
built, Guilford's land area differences: 23% of parcels, county-wide, deeded acres against surveyed shapes), during
setup and after the runs.

**Where it lives.** One map, in one of six states: docked right, bottom, left or top of the main window; popped out
into a window of its own; closed. 🗺 Map in the title bar, or Ctrl+M; first opened docked right. Docked, a divider
sets its size (25–70%); popped out, a desktop window (a browser window on the web build); popping out *moves* the map
(never two maps), and closing its window docks it back where it was. Where it is, its size and its layers are
remembered per computer. At phone width, docked bottom only, at 40%.

**Three ways a screen meets the map** (designed 2026-11-10). One map; no screen has a map of its own (the inline maps
retire into it, each screen redesigned to make sense without one).

1. **Take over: the map is the work.** The step can't be done without looking at or touching the map. Arriving, the
   map's state is saved (open or closed, docked or popped out, its field, Follow; its size is never changed), it opens
   where it last was (a popped-out map stays out) and shows the step's own view, with the step's own tools. Closed by
   the user on that step, it stays closed until **Show the map** (on the step's card) or the step is left and come back
   to. Leaving the step, the saved state comes back exactly (a map that was closed closes again).
2. **Summon: the map is evidence.** The step works without it, but a place helps judge something on it. A **🗺 Show on
   map** button sits beside the thing it shows (a count, a row, a pill): pressed, the map opens on exactly that (its
   layer, the parcels highlighted, zoomed to them) and Follow turns off (the next step doesn't wipe what was asked for);
   **Back to following** in the map's header. Nothing is saved or restored: it was asked for.
3. **None.** Settings, names, standards, model options: the map is left as the user set it.

**A take-over screen**, without a map: an **instruction card** at its top (🗺, one imperative sentence, "Do X on the
map"; with the map closed, or not showing the step's view, it says so and offers **Show the map**), then what's been
done there as plain readout and controls (the value chosen, its counts, what can be reset), then what
it means (its checks and warnings).

**Clicking on the map must be unmistakable.** Where the step expects a click on the map: the map shows the same
instruction in a **banner** along its top, naming the step ("Coordinates: drag the pin to…"); hovering the screen's card
flashes the banner, so the two read as one. The pointer is a hand only over what reacts, which is outlined on hover; a
pin to drag has a grab cursor and pulses until first moved. A click always answers at once (a card opens, the pin
moves, a parcel is picked) and the screen's matching row updates with it.

| Step | Way | The map shows; its tools |
|---|---|---|
| Data › Coordinates | Take over | The parcels and the centre pin; drag the pin (the screen shows where it is and Use the middle of the parcels; no typing a position, 2026-11-10). |
| Data › Location fields | Take over | The chosen location field's areas; each field on the screen has Show on map. |
| Data › Shapefiles | Take over | The project's layers over the parcels; each layer on the screen has Show on map. |
| Model groups › Build the groups | Take over | The groups as edited, by group or by what moved; click a parcel: why it's in its group (built 2026-11-10). |
| Evaluate › On the map | Take over | Ratios by area; the screen explains the colours and lists the worst areas, each with Show. |
| Models › Outliers | Take over | The outlier sales, a picked one's comps; picking on the map or in the list picks on both. |
| Models › Model values | Take over | The final values: ratio, value per area, change from the roll (built 2026-11-10). |
| Data › Parcel Universe | Summon | Its ID problems (blank, repeated, not found). |
| Data › field steps | Summon | The field, beside its values and histogram. |
| Sales record fields | Summon | The sales whose value differs, beside each pill. |
| Model groups › Check them | Summon | A group's parcels; Unassigned. |
| Review, summaries, How they did | Summon | Any count with a place. |
| Settings, Standards, Variables, Models, Report options | None | |

**Every screen says what it does with the map** (planned 2026-11-10), so the user learns the map always follows where
they are. A screen with nothing spatial holds the last view, and the map's header says so ("Nothing on this step to
map: still showing …"). The steps' own outputs are on the map too, any column of them: Bring in data's parcels,
Variables' prepared ones, what Variables' tests worked out (the nearby averages and per area statistics, which
otherwise reach the disk only with the models' try: `out/oakbox/vartest/universe.parquet`, 2026-11-12) and the models'
try (`out:<universe|prepared|tested|modeled>:<column>`, by `key`; the map picker's **From the steps**). Northerliness
and Easterliness (`latitude_norm`, `longitude_norm`) are among them. The plan, screen by screen (✓ built; **data**: needs data the server doesn't serve yet):

| Tab | Screen | The map |
|---|---|---|
| Data | Overview, Review | What stops a run, by kind, worst first (Review's summon buttons ✓) |
| Data | Sales Record (the file) | Its sales, found / not found in the parcel universe |
| Data | More files, Add files, a file's part | That file's rows on the parcels, joined / not (**data**: per-file match) |
| Data | Condo units | Condo parcels, units per parent; on The parcel they're on, units without one (**data**) |
| Data | Deeds | Sales by whether their deed has other sales that day (likely several parcels sold together) ✓ |
| Data | Permits | Parcels by the kind most of their permits are, else by how many (the picker's Permits) ✓ |
| Data | Enrichments | Each enrichment's Map button: its column, from Bring in data's parcels ✓ |
| Inputs | What runs, Bring in data | Hold; then the parcels loaded (**data**) |
| Inputs | The parcel universe, The sales | Parcels brought in or left out; each parcel's sales all brought in, some or all left out ✓ (by reason: **data**) |
| Inputs | Public data and checks | The public layers fetched (**data**) |
| Model groups | How to start | Hold |
| Model groups | Check them, Tag and write, What each group got | The groups as saved ✓; Check them's rows Show on map ✓ (unmodeled groups faded: not yet) |
| Sales | Sales window, Time adjustment | Sales by date ✓ (in vs out of the window: **data**) |
| Sales | The sales | Sales by price ✓ |
| Sales | Fill blanks, Sales scrutiny, Rare categories, Check sales | Hold (what they'd change: **data**) |
| Evaluate | What to check … The standards, Check my values | Hold |
| Evaluate | Which groups | The model groups ✓ (the ones not checked faded: not yet) |
| Evaluate | Across prices | Sales by ratio, a price band at a time (cheap / middle / dear) ✓ |
| Evaluate | Neighbourhood price levels | Each sale by its neighbourhood's median ratio, against the median of them all (the page's model group) ✓ |
| Variables | Fill blanks … What changed | Hold (what changed: **data**) |
| Variables | Spatial average, Per area statistics | The nearby sale price; per area, its first statistic: from the models' try ✓ |
| Variables | Test the variables … VIF | Each variable's Map button: the column, the models' try's first ✓ |
| Models | Models | The group on the page |
| Models | How they did | A set's sales by one model's ratio: Map on every model's row of every set (holdout, after the valuation date, study set; trimmed too; the roll), the ensemble on the holdout first ✓ |
| Report | Export, Report | The final values map |

What the map shows for a step is published by the step (`lib/groupmap.ts` first, for Build the groups; to be one
contract for every step: a view, its tools and their instruction, take over or summoned), and reaches a popped-out map as
the dock does. Phones: out of scope. **Built** (2026-11-10): the take-over (`lib/mapstep.ts`: `useTakeOver`, the banner, the
state given back), the instruction card (`components/MapInstruction.tsx`), Show on map (`components/ShowOnMap.tsx`, the step's
`pick`); Coordinates, Location fields, Shapefiles and Build the groups on it; Evaluate › On the map, Outliers and
Model values' map draw their own map (with its controls) into the map window (`components/OnTheMap.tsx`, a React
portal: the step keeps its state; popped out, the map is drawn on the step itself). Summon (`summonMap`, `SummonMap`): the Parcel Universe's blank and repeated
IDs (its step and Review), each 🌐 parcel file field's row where a step has several (not the Big five's cards: the map
follows that field already), each Sales record field that differs (Map them); the map's Follow button reads Back to
following. Not yet: Check them's groups, the summaries' counts.

**Layers**, each there once its data is:

| Group | Layers | From |
|---|---|---|
| 🌐 Parcel Universe | shapes coloured by any field (the histogram's live range) or by a problem | the universe |
| 💰 Sales Record | sales as dots: price, date, valid or not, 💰 vs 🌐 difference | a sales file |
| Problems | blank values, unmatched IDs, repeated IDs, 💰 differs from 🌐 | as soon as checked |
| Patterns | hot spots: cells over twice the county's share of a problem | with a problem layer |
| Results | model groups, values (or per area), ratios (blue under, red over), value against the roll | the last run |
| Context | shapefiles, public data, the street map (as the map settings say) | always |

One colour scale at a time (🌐 shapes or 💰 dots), its legend always shown. A results layer from a run older than the
settings says so ("from the run on 2026-11-07: out of date since Land size changed"). Outliers with their comps is a
second version; the Outliers screen keeps its map meanwhile.

**Follow** (in the map's header, on by default): the map takes the step's colouring and layers; it moves only when
something is picked. Off, it stays as set.

| Step | Shows |
|---|---|
| 🌐 Parcel Universe, its IDs | parcels; blank and repeated IDs |
| 💰 Sales Record, IDs | sales; those finding no parcel |
| Sale date, Sale price | sales by year, by price |
| Valid sale, Vacant sale | valid against invalid; vacant against improved |
| Big five, any field | parcels coloured by it; a 💰 column chosen: 💰 differs from 🌐, with hot spots |
| Address, Coordinates, Location fields | parcels by the location field; the centre |
| Land use & building type | parcels by the category |
| Sales record fields | 💰 vs 🌐 for the field picked |
| Shapefiles, Enrichments | the layer over the parcels |
| Model groups | the groups |
| Check sales | sales kept against set aside, by reason |
| Evaluate, Models | ratios |

**Picking.** A parcel's card: its 🌐 fields (the Big five first); its 💰 sales (date, price, each sale's own values
beside the 🌐 ones, differences flagged); its model group, value and ratio after a run; each a link to where it's set.
A sale's card the same, from the sale. "Show on map" from a few key places only: the problem counts (blank and
repeated IDs, unmatched sales, "differs for N sales"), See them, and Outliers' list; a row picked there flies the map
to it. Picking on the map never changes the step; only the card's links go anywhere.

**Performance.** Tested 2026-11-08 on Guilford (222,135 parcels, 1.43 million vertices after simplifying to 3 ft,
182,568 sales; 18 MB, prepared in 8 s): loaded and drawn in 1.1 s (3.2 s at a quarter of the CPU), 50 MB; selection to
a popped-out window in 0.7 s (BroadcastChannel; its redraw the time). Panning everything at once, drawn in software
(no GPU): about 1 frame a second, 0.3 with the sales dots; an empty map 60. So: zoomed out, the county as cells (about
1 km, finer as it zooms) coloured by the layer's figure; at street zoom, only the parcels and sales in view (a few
thousand), fetched from OAK box. Simplified shapes and cells made once, when the universe is set; on the machine
check's lower tiers, cells longer and sales dots off by default. Tested so the same day, in software: what costs is the
number of shapes drawn, hardly the pixels (half the window, a quarter faster). Panning the county as 474 cells: 59
frames a second (30 at a quarter of the CPU); 6,536 cells at 250 m: 27 (19); a street view with the 4,600 parcels
around it (the view and half its size again each side, reloaded as it pans, in 3 ms, 340 KB): 28 (20), 16 with its
1,710 sales as dots; a neighbourhood's 13,160 parcels: 16. Rules from it: a few thousand shapes at most; finer cells
(125 m: 49,745 for the county, 11 frames a second) only those in view; sales as dots only at street zoom, as cells'
figures before. Pop-out sync on Windows (WebView2 windows sharing one
engine) still to confirm; OAK box's server relays it if not.

**Built so far** (2026-11-09): docked on any side or closed (🗺 Map on the plate, Ctrl+M), the divider and the
side remembered on this computer (narrow windows: the bottom only), opened without waiting for a click when maps
otherwise do (opening it is the click); the 🌐 parcels coloured by any column of the parcel files (your fields first,
the Big five first among them; numbers on a light-to-dark scale over the histogram's live range, the legend; the 12
commonest values of a category in their own colours). Its data (`mapdata.py`, `out/oakbox/map/`) is made in the
background from the universe file when it's set: each shape simplified to a metre, its centre, the box around them all
(Guilford: 24 s). Cells from 8 km down to 30 m, the finest at least 16 pixels across, only around the view; the shapes
of the parcels in the view and a quarter more each side once zoomed in past the Map detail's level
(docs/spec/platform.md, Maps). The shapes file comes to the browser once,
the first time it zooms in that far, and the parcels in view are picked out there (what the test timed), not asked
for view by view. Its divider is a thin oak stile (or rail, docked top or bottom), grained as the frame, the map a pane
set into the box.

Then (same day): **Follow** (on by default; choosing a colour by hand stops it): a Data step's field (its first
loaded, in the step's order), the 💰 steps' sales, the 🌐 Parcel Universe step its ID problems (whichever has more
parcels), Sales record fields the field whose 💰 values differ most; a step with nothing to show keeps what was shown.
**💰 sales** at their parcels (`map/sales`): by price, date (light old, dark new), valid or vacant (dark yes; a cell its
share); cells of their sales zoomed out, dots on the plain parcels zoomed in. **Problems** (`map/problems`, worked
out once a change, kept until the project or its files change; Guilford: 5 s, then at once): 🌐 parcels with no ID or a
repeated one; 💰 sales whose value of a field differs from their parcel's, as Sales record fields compares them (not
one written differently, like grade codes against scores); cells by their share of it (light to dark orange, at three
times the county's share), **hot spots** outlined (more than twice the county's share, 30 or more). Sales whose parcel
isn't in the universe have no place: the legend says how many. Guilford's land area: 23% of sales differ, nearly all
in the rural parts, the cities hardly at all.

Then **the parcel's card** (`map/parcel/{index}`): a parcel, or a sale's dot, clicked opens it over the map, the parcel
outlined; a cell clicked zooms to it. Its 🌐 fields as each parcel file has them (the Big five first; each a link to
the step that sets it; a file with several rows says so, the first shown), its files' other columns folded away, and its
💰 sales, the latest first: date, price, valid or not, and each sale's own values beside the parcel's (as Sales record
fields compares them; a difference in red, ≠). Esc or ✕ closes it; clicking never changes the step. Its thumbtack (📌)
pins it as a column at the map's left (the default; the map beside it) or unpins it to float over the map, dragged by
its title, never past the map's edges; remembered on this computer. The pointer is a pointing finger over what a click
picks (a parcel, a sale), a magnifier over a cell (a click zooms to it), the map's drag hand elsewhere. The colour picker
is in sections, each folded or unfolded by its heading (remembered): the 🌐 Parcel Universe's fields (yours, the Big
five first; the first of them the map's colouring to start), the 💰 Sales Record's, Problems (parcel IDs), Differences
(a 💰 sale's value against its 🌐 parcel's), and the parcel files' other columns (Guilford: 319; folded to start).
Typing finds them all, folded or not. Names without their unit ("Building area (finished) (HEATED_AREA)"). On the
card, a field's name colours the map by it (a difference's, by that difference; Follow goes off, as for a choice by
hand); the › after it goes to the step that sets it. The hover label sits below and right of the pointer. Every histogram's range track (the map's legend, the
fields' capsules, Inputs) is laid out by percentile, not value: a handle a quarter of the way along is at the 25th
percentile, so a few huge values can't squeeze the rest into the track's first pixels (Guilford's land area: the
automatic range's top now 91% along, not 1%). And each histogram has an overflow bar at each end, hatched and set
apart: how many values are under and over the range shown (capped at the chart's height, a dashed top when it is). A row is read
alone (the row group holding it, or the one feature), not column by column: 0.2 s a card on Guilford, the first after
opening a few seconds (the sales' comparison, shared with the problems).

**Layers and legend** (2026-11-12): one thing, over the map's bottom left. Closed, a chip with the legend in brief
(the ramp or a category's first colours, a problem's count and share, the field's name); pressed, it opens up into a
panel: **Colour by** (the field picker, and its size) at the top, then each layer on a line of its own with its 👁
(shown or hidden, remembered): 🌐 Parcels (off: only the parcels with a sale; no sales record, none), 💰 Sales, and
the Street map (off: the plain background; it starts as Settings says, then is this map's own). A layer's legend sits
under its line (the sales' when they're what's coloured), its line says "squares now" while squares are drawn, and
its options open from a ⚙ beside it (Parcels: Detail, the Map detail of SPEC §5). The panel's 📌 pins it as a drawer
at the map's left, which narrows the map instead of covering it, and unpins it; ⌄ folds it back to the chip. Which of
the three it is, is remembered. The map window's header is then only 🗺 Map · the field shown, Follow, and the window's
buttons; the map itself has no corner box (its own maps elsewhere keep theirs).

**The legend and its controls** (2026-11-11), now in the layers: the histogram, its range,
Reset and **Hide the rest** (the parcels or sales outside the range not drawn, nor counted in a cell, rather than drawn
at the ramp's ends). **Per size**: a value field (a sale price, a value loaded, a value or prediction from the steps)
gets a box after the picker: **As-is**, **per building sq ft**, **per land sq ft** (m² in a metric project), a size
not loaded greyed with why. The division is the server's (each parcel's size in the project's unit, an acres column
converted; a sale by its parcel's size today), so the histogram, range and Hide the rest work on it as on any number;
no size, or zero, is blank, and the legend says how many. Chosen per field and kept; the box is blue while a size
divides, so it's never read as the value itself. The parcel's card folds its 🌐 and 💰 sections (kept for the next one). **A Map button keeps Follow on** (2026-11-11): it's what the step follows now, remembered for that step (a
step's own choice comes back on any step where nothing was picked); the button is pressed while it's the one shown.
Only picking a field by hand in the map's picker turns Follow off. **The step list can be a thin rail** (2026-11-11): each step its number and mark,
a part a dot until it has one, the name a tooltip; « at its top makes it thin, » full again (remembered). Left to
itself it goes thin when the folder is too narrow for the full list beside the sheet's least width, so the sheet gets
the room instead of the folder scrolling sideways. Inputs' field tables have a Map button on each row
the map can show (the universe's columns as brought in; of the sales, price, date, valid and vacant).

Then **full size and popping out** (2026-11-09). Full size (⤢): the map over the whole main window inside the frame,
under the lid, the page behind it; the same button (⤡) docks it again. Pop out (⧉): the map moves to a window of its own
(#/map/<project>: a desktop window, pywebview's, reused; in a browser, a popup), the main window shows none and its 🗺
Map says "Map (popped out)" (pressing it docks it back). Closing that window, or its Dock back, docks it back where it
was. The windows keep in step through the computer's storage (its `storage` event reaches every window of the app,
in a browser and in the desktop app's web view alike): the dock itself, where the main window is (the popped-out map
follows its step), and the card's links (the main window goes there). The desktop app also tells the main window when
the popped-out one closes. Tested in a browser; on Windows (WebView2) and Linux (Qt) still to confirm. Still to come:
the results layers and the card's group, value and ratio.

**The inline maps.** Coordinates (setting the centre) and Shapefiles (checking a layer) stay: they're their step's
control. Model groups' and Outliers' maps stay, with Open in map. The values and final maps become layers, with Open in
map from their pages.
