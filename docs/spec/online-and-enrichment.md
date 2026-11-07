# Going online, and enrichment

## 3.11 Online features and the map background
**Map background:**
- Offline, maps show parcels only.
- Online, the user can turn on a street background built from OpenStreetMap data.
  - **Default provider:** a free, no-key service intended for third-party apps, such as OpenFreeMap. The tile URL lives
    in config, so the provider can change without a software update. **As built (2026-11-06):** OpenFreeMap's vector
    tiles, its light grey `positron` style (`appsettings.MAP_STYLE`), fetched when a map is shown with **Street map**
    ticked; offline, or unticked, the map is a plain background. The address can be changed in OAK box's settings
    (`map_style`), for a tile server of one's own. **Later:** hosting our own tile server for OAK box's users, so no one
    else's service carries them. The one-time online notice isn't built; the **Street map** box's ⓘ says where the map
    comes from and what's sent.
  - **Fallback:** OSMF's own `tile.openstreetmap.org`. Its [tile usage
    policy](https://operations.osmfoundation.org/policies/tiles/) allows it, but it has no service guarantee and may
    block heavy use without notice. If used, Oakbox must send an identifying User-Agent, show attribution, and not
    prefetch or cache tiles for offline use.
- The user's own aerial imagery (GeoTIFF/MBTiles) comes later.

**Online notices.**
- **Shown once, calmly, never recurring.** The notice appears the first time any online feature is switched on, and
  lists each service and what it receives. For example: "To draw the street map, Oakbox asks OpenFreeMap for map
  pictures of the area you're viewing, like any web map does. Your parcel data never leaves this computer."
- **Services covered:**
  - the map tile service
  - Overture
  - Census
  - OpenStreetMap Overpass
  - USGS
  - Azure, for the sample
  - GitHub, for updates
- **Settings → Online features** lists every service and lets the user switch each one off.

## 3.12 Enrichment
Enrichment adds context the office's data lacks. Some of it is cheap and local; some downloads gigabytes and runs for
hours on a large county. The screen treats it as a set of configurable jobs, not checkboxes.

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

**Try on a small area.** The user draws a box or picks a neighbourhood. Oakbox runs the enrichment on just those
parcels, with the same settings, into a scratch cache, never the project.

**Caching is visible.** Each card says "Up to date", "Will reuse downloaded data" or "Settings changed: will re-download
~1.2 GB". **Clear cache** is per card. Oakbox clears OpenAVMKit's enrichment cache automatically when columns change;
otherwise OpenAVMKit stops with an error.

**Results summary.**
- **Coverage:** % of parcels that got a value.
- **New columns,** with a histogram and a map layer.
- **Plain warnings,** such as "No buildings found in 312 parcels — mostly vacant land, as expected".
- New columns become available everywhere downstream.

**Failure handling.** A failed online enrichment never fails step 1. The card turns amber with the reason and offers
**Retry** or **Skip**. Skipped enrichments are listed in the report methodology.

**Oakbox writes every enrichment explicitly.**
- Each enrichment block and each distance feature needs `enabled: true`. OpenAVMKit's per-feature default is *off*,
  which contradicts its docs.
- The Census API key is written to the engine's environment. It is not a settings value, and OpenAVMKit's `.env` lookup
  fails outside notebooks.

### 3.12.1 The enrichments
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

### 3.12.2 Two different ways of filling blanks
OpenAVMKit has two separate features, and Oakbox keeps them apart, with different names, screens and labels.

| | **Estimate missing values** (`enrich.infer`) | **Default fills** (`data.process.fill`) |
|---|---|---|
| What it does | Predicts a value from similar nearby parcels with a model | Puts in a stand-in: model group median/mean/mode, zero, min/max, "UNKNOWN", or a fixed value. *Can be limited to improved or vacant parcels* |
| When | Step 1, after the other enrichments but **before** lookup tables, formulas and the vacancy rule | Step 3 (clean), per model group |
| Screen | Its card on the Enrichment screen | **"Fill blanks"** panel in step 3 |
| Typical use | Important characteristics with sizable gaps | Making every model input complete. Linear models crash on any blank; ML models tolerate them |
| Cost | Model training per field | Negligible |
| Label in UI | **"Estimate"** | **"Default"** |

**Shared rules.** Both are offered to everyone and always explained. The card or panel and a first-use dialog say, in
plain words:

> "This fills gaps so the model can run. A filled value is an **educated guess** (Estimate) or a **simple stand-in**
> (Default). It is **not a fact** about the property. It is used **for modeling only** and is never written back to your
> records."

- **Always marked.** Filled values have a distinct style and label in tables and pop-ups. Estimates carry `inferred_*`.
  Default fills need a new flag (upstream A9).
- **Never exported as data.** Exports return the office's original value from Oakbox's kept copy (§3.9). Optional,
  clearly named "estimated"/"default" columns can go alongside.
- **Reported.** Reports state how many values of each field were filled, and how.

**Specific to Estimate missing values:**
- **Building fields need a "which parcels" filter.** Without one, OpenAVMKit estimates every blank, including true
  vacant land. The vacancy rule then marks those parcels improved. Oakbox pre-fills the filter from the Field profile
  answer (§3.9).
- **Predictors** can't use lookup-table or formula outputs, because those run later.
- **Preview before committing:** how many values are missing, and a validation score from OpenAVMKit's experiment mode,
  e.g. "guesses are typically within ±18% of the real value".

**Specific to Default fills:**
- **Suggested automatically.** Before step 5, Oakbox lists every model input that still has blanks and proposes a fill
  (median for numbers, "UNKNOWN" for categories).
  - Accepting means re-running step 3, since fills live in clean.
  - Partial-coverage enrichment fields, such as census and elevation, are the usual cases.
- **Automatic steps are shown.** OpenAVMKit's automatic tidy-ups (year-built/age reconciliation, categorical "UNKNOWN")
  appear as read-only rules.
- **Blank finished area is not handled here.** It is already 0 (vacant) after step 1, so it's decided in the Field
  profile instead.

### 3.12.3 Modeling-time context (step 5)
**Spatial lag** (nearby sale prices and characteristics) and **area statistics** (neighbourhood means and medians) run
in step 6. They depend on model groups and train/test splits.
- **Spatial lag: built (2026-11-01), as Variables › Spatial average statistics** (named Nearby sales and buildings
  until 2026-11-07), after What changed (Prepare accepted).
  **On by default** (a tick: "Average nearby sales and buildings"; off writes nothing and offers nothing). OpenAVMKit's
  `enrich_sup_spatial_lag`: the k nearest of each, however far, weighted by distance (a Gaussian whose width is their
  mean distance, so it adapts to density). OpenAVMKit's `BANDWIDTH_MILES` (half a mile) only scales the `_confidence`
  columns, not the averages: there is no distance limit (an earlier note here, and the step's text, said otherwise;
  corrected 2026-11-01).
  - **How many nearest** (a number box, 5 to start, 1 to 50; added 2026-11-01; `LagState.k`): one k for every average,
    written as `spatial_lag.sale_price` (the price averages) and each `fields` entry. The step's notes follow it
    ("Averages the 8 nearest of each", "9 or fewer sales"). A distance limit isn't offered: it needs an engine setting
    (proposed, not built).
  - **What it adds**, as variables (kind: location; in any variable list, tested like the rest): **Nearby sale price**
    and **Nearby price per finished sq ft** (from the sales), then, from the parcels, nearby finished area, land area,
    floor area ratio, bedrooms per land area, building age, effective age, quality and condition: those whose fields are
    there. Not offered: the land and vacant-land price averages (they need vacant sales, which are few), and
    OpenAVMKit's `_confidence` columns.
  - **Averages** (a MultiPick, every one picked to start; revised 2026-11-01): which of OpenAVMKit's own averages are
    worked out and offered. Written with OpenAVMKit's `spatial_lag.only: true` (`engine/enrich-fixes`), so only those
    picked (and those under Also average) are worked out: the price ones as `sales` (`"price"`, `"price_impr"`), the
    parcels' as `fields` (k nearest each), only for fields the prepared data has. One not picked leaves any list it was
    in. Stored as the ones skipped (`LagState.skip`), so an average newly there (quality, once a quality field is
    loaded) starts picked. On the synthetic sample: 8 columns instead of 11. The picker's names leave out "Nearby" (the
    step says it once) and its summary is the first picked and a count ("Sale price + 6 other fields"); as variables
    they keep it.
  - **Names:** the price averages are offered under a plain name (`spatial_lag_sale_price…`) and written as OpenAVMKit
    names them, after the price averaged (`spatial_lag_sale_price_time_adj…` when Check sales adjusts prices), so a list
    survives time adjustment being turned off or on.
  - **Per model group** (a table: group, sales, **Averages the sales of**): its own always; others added with a
    MultiPick ("Its own only" to start). `data.process.enrich.spatial_lag.model_groups.<group>.sample_from`.
  - **Also average:** more numbers of the parcels around each one, besides OpenAVMKit's own (a MultiPick, **nothing to
    start**): `spatial_lag.fields`, k nearest each.
  - **When:** as the models run, after the sales are split (Try them, and Test the variables, which also split): a
    sale's nearby price comes only from training sales outside its own fold, so a model never sees the price it's judged
    on. Bring in data's settings leave it out (it doesn't put Bring in data out of date); Test the variables and Try
    them are out of date when it changes.
  - **Too few sales:** with k + 1 or fewer training sales to average, OpenAVMKit writes 0 for every parcel. Test the
    variables leaves such a variable out for that group (named); Try them leaves it out of that group's models for the
    run (the settings file unchanged) and says so in its notes ("Apartments: Nearby sale price, Nearby price per
    finished sq ft left out of its models: too few of its sales to average (0 for every parcel). Let it borrow another
    group's sales"); a model left with no variable stops the run, saying so.
  - **Small groups:** OpenAVMKit looks up each parcel's k nearest parcels in its group and stops on a smaller group (an
    IndexError); a group with fewer than 10 parcels, or than twice k, is left out of the lag for the run (nor borrowed
    from), and its models do without, said as above.
  - On the synthetic sample (9,354 parcels, 1,770 sales) it takes 1.6 s.
- **Per area statistics: built (2026-11-07), as Variables › Per area statistics**, its own
  page right after Spatial average statistics (its cousin: both worked out as each run starts, after the split).
  OpenAVMKit's area statistics (`area_stats.enrich_sup_area_stats`, `data.process.enrich.area_stats`): each parcel gets its area's figures (the median sale price of its census tract, the median finished area of its
  neighbourhood) as variables of their own. Nearby sales is a smooth surface of the nearest; this is the same idea by
  named areas.
  - **Work out per area statistics** (a tick; **off** to start). Off writes nothing and offers nothing, but everything under
    the tick is shown faded and can't be used, set as it would start: turning it on gives what's on show.
  - **Layout** (style guide): the tick; then **Figures** and **Blank under** as settings on two columns (labels, then
    what's set); then the grid, a table.
  - **The grid:** rows are the figures, columns the locations, a tick each.
    - **Columns:** the location fields Check sales offers for "near" (neighbourhoods, census tract and block group, the
      user's own): `area_stats.locations`.
    - **Rows, from the sales:** sale price, price per finished area, vacant price per land area (OpenAVMKit's
      `sale_price` family: a bare `sale_price` in `fields` expands to the price and its three per-area rates, time
      adjusted when Check sales adjusts), and the number of sales (its `sales_count`, always worked out).
    - **Rows, from the parcels:** the big five (finished area, land area, building age, quality, condition), those the
      data has. **Not built:** land use's most common value (`mode`, a category, and `mode_frac`, its share).
    - One engine block covers every location × field; a tick off leaves that column out of the variables offered (the
      engine still works it out: a few columns, milliseconds).
  - **Figures** (a MultiPick; **Median** to start): median, mean, spread (`std`), 25th and 75th percentile, smallest,
    largest (`area_stats.stats`).
  - **Blank under** (a number box, **5** to start; `area_stats.min_count`): an area with fewer sales (price figures)
    or parcels (the rest) has that figure blank, not borrowed. The coarser location's figure is there for the model to
    lean on. OpenAVMKit's `exclude_test_keys` isn't offered: prices already come from training sales only.
  - **The areas** (the grid's last rows, per location): how many areas, the sales in a typical (median) area, and
    those under the minimum: "—" for none, or "⚠ 4 areas" as a small warning button that opens which areas and their
    counts (the row stays one line high). Then "Adds N variables."
  - **To start:** the sales' figures for the location Check sales uses and the next coarser one; the parcels' for the
    first.
  - **When:** as the models run, after the sales are split, like Nearby sales: OpenAVMKit takes the price figures from
    the training sales only, so a model never sees the price it's judged on; the parcels' from every parcel. OAK box
    calls `enrich_sup_area_stats` after the lag in Try them and Test the variables, and leaves `area_stats` out of
    Bring in data's settings (as it does `spatial_lag`).
  - **As variables:** kind location, named "Census tract median sale price" (median and mean before the figure, the
    rest after it: "Census tract sale price, spread"), tested and listed like any other. Offered under stable names
    (`area_stat_<location>_sale_price…`) and written as OpenAVMKit names them (`…sale_price_time_adj…` when Check
    sales adjusts), as the nearby averages are. A price figure that can be blank (an area under the minimum, or a
    parcel in none; the vacant land price always) is left out of a linear model, as any variable with blanks.
  - **As built** (`src/oakbox/areastats.py`; `AreaState` in the project's model state; `web/src/screens/AreaStep.tsx`):
    the ticks are stored only once changed (`ticks`, None until then: they follow the proposal). Try them is out of
    date when its settings change, and only when it's on (a project without it keeps its fingerprint). Checked on a
    5,000-parcel county: Test the variables tested all 9 figures in every group (7 s), Try them trained on them (62 s).
