# Step 3, Sales: Check sales

As built (F6), then the sales review as first specified (§3.6).

## F6. Step 3, Sales: Check sales (its own tab, **3. Sales**; notebook 2, clean) (built, but for the parts listed under "Not built yet")
Notebook 2 makes the data ready to model, and it's where subjective calls go in: which sales count, how prices are
brought to one date, what stands in for blanks. So the step shows each call before it runs, and every sale it sets aside
with the reason. It starts from the 1-assemble hand-off (F5) and writes the 2-clean hand-off that step 4 (Check my
values) and steps 5 and 6 (Variables, Model values) read.

**What runs, in OpenAVMKit's order** (`openavmkit.headless` stage `clean`, in its own process like F4 and F5; about 10 s
on the Guilford sample, minutes at 500k parcels):
1. **Fill blanks** (`data.process.fill`, per model group).
2. **Equity clusters** (`analysis.horizontal_equity`, `land_equity`, `impr_equity`): groups of similar parcels, `he_id`,
   `land_he_id`, `impr_he_id`, used later by the equity studies and the models' CHD. Nothing to decide here beyond the
   location (below).
3. **Sales:** the sales window (`modeling.metadata.use_sales_from`), the user's own invalid-sale rules
   (`data.process.invalid_sales`, the Advanced rule templates of §3.6), then **time adjustment**
   (`data.process.time_adjustment`).
4. **Sales scrutiny** (`analysis.sales_scrutiny`): heuristics, the user's exclusions (`invalid_key_file`), then outliers
   within clusters of similar sales.
5. **Rare categories** (`data.process.collapse_sparse_categories`), then the hand-off: `out/2-clean-sup.pickle` and
   `out/look/2-clean-*.parquet`.

**Before running: one panel, a card per call, each with its default already chosen and what it does in numbers.**
Nothing needs an answer to run; each card says what it will do.
- **Sales window.** "Sales from 2021 on (5 years before the valuation date, 2026): 1,901 of 3,804." A bar per year of
  sales, the years outside it greyed, the chart as wide as the text above it. One year for every sale (revised
  2026-10-31: vacant land isn't modeled on its own yet, so it has no window of its own); **by model group** under
  Advanced. Writes `use_sales_from` (`{improved, vacant}`, both the one year, or `{default, by_model_group}`).
- **Time adjustment** (on by default; `time_adjustment.use`). Plain words: "Prices change over time. Each sale's price
  is brought forward to [the latest sale] by how much prices of similar property moved since it sold, per model group."
  After a run, a line per model group: the index over time with its sales per period, the change per year ("+7.5% a
  year": the sample's single-family sales, 2021 to late 2024), and the granularity OpenAVMKit settled on (months,
  quarters or years: it needs 5 sales in most periods). Choices: start from months or quarters (`period`, default
  quarters); per model group, **Time adjustment from** its own sales (the default), **another group's**
  (`time_adjustment.borrow.<group> = <source>`: OpenAVMKit works out the source's index, from its sales or its file, and
  applies it to this group's sales, held level outside the source's dates; for a group with few sales), or **my own
  file…** (`from_file.<group>`). The file is a CSV of two columns, said exactly where it's chosen: `period` (a day
  2023-04-15, a month 2023-04, a quarter 2023-Q2 or a year 2023; one row each, at least two) and `index` (the price
  level then, any base, positive); more columns are ignored, and a schedule OpenAVMKit wrote (`period, start_indexed,
  end_indexed, correction_factor`) works too. OpenAVMKit's own reader (`read_schedule`) checks it when chosen and lists
  every problem, quoting the rows as written (a period that isn't a date, a value that isn't a positive number or is
  blank, a period twice, fewer than two); a file with problems isn't kept. A kept file is copied to
  `in/oakbox/time_adjustment/<group>.csv` (its digest in the settings, so replacing it puts the step out of date) and
  shown with its name, periods and dates; **Replace…**, or pick its own sales to set it aside. OpenAVMKit interpolates
  the index day by day, brings each sale to the last period, and holds sales outside the file's dates at its first or
  last level. The sample has a synthetic one (`in/time_adjustment_index.csv`, quarterly 2015 to 2024) and a broken one
  to see the problems (`in/time_adjustment_index_broken.csv`). Said plainly: prices are brought to the latest sale in
  the group, not past it (OpenAVMKit doesn't extrapolate); a group with too few sales gets no adjustment, and says so.
  Groups with no listed model group (Unassigned) get none. **Previewed before running:** nothing runs on opening the
  step (as Check sales waits for its button); **Work it out** works the time adjustment out alone (OpenAVMKit's own
  sales processing on step 2's hand-off, in a scratch folder so the last run's schedules stay; about a second on the
  sample), shown as a chart per model group with its change a year; **Work it out again** after a change. Both are the
  step's footer action, where Next goes: Next comes only once it's worked out with the calls as they are (revised
  2026-10-31). **Each chart expands in place** (one at a time; another pressed shrinks it): every sale it's worked out
  from as a faint dot of its price per area as sold (log scale, the middle 90% of sales with room around them; how many
  far-off ones aren't drawn is said), the index drawn through their median, what the index is of (price per finished
  area or per land area, as OpenAVMKit chose) and the period it settled on with how many periods had 5 sales; hovering a
  dot shows its address, date, price, price per area and time-adjusted price. A group indexed on land area by
  OpenAVMKit's own choice is warned about (for condos, whose land is a share of their parcel's, it's rarely right).
  **On the map** (2026-11-13, a take-over step: screens/TimeMap): a group's sales where they are (their parcel's
  latitude and longitude, in the preview's detail), coloured by price per area (log scale, 5th to 95th percentile),
  with the group to show in its panel (the chart shown larger, else the first that moved). **Prices in a window**:
  dragging across the expanded chart chooses a window in time (a blue band; a click clears it; under the chart its
  dates, sales and median); the map colours the sales in it, the rest faint. Under the map a time bar: ▶ steps the
  window on a month at a time, a slider moves it, its length (3, 6 or 12 months), **Every date**. **Change**: squares
  each coloured by how far its median price per area moved from the first year of sales to the last, beside the
  group's own index over the same years: grey as the index, orange faster, blue slower (±20% at the ends). The
  squares are a quadtree (2026-11-13): from 16 km, each splits into four while every quarter with sales keeps 8 in
  its first year and 8 in its last, down to the map's own square size at the zoom (lib/detail.ts), so dense places
  get small squares and sparse ones stay large; a square short of 8 in either year isn't drawn. Paler the fewer sales
  it rests on (pale at 8 a year, solid at 100); hovering says how many, its change and the index's.
  **Index on** (a column per group with its own sales): **Automatic** (OpenAVMKit works it out from the sales; once
  worked out it says which, "Automatic (land area)"), **Finished area** or **Land area** (`time_adjustment.per.<group>`,
  `engine/enrich-fixes`). **No time adjustment** lists each group without one and why, in OpenAVMKit's terms (no sale
  with a size; no period with 5 sales with one, even by year; no change), never a bare "too few sales".
- **Fill blanks** and **Rare categories** moved to step 5 (F7, **Prepare the fields**): nothing in this step uses them,
  they only change what the models learn from. Check sales runs with OpenAVMKit's own fills (its template's, and its
  automatic tidy-ups) but not the user's, and doesn't fold.
- **Sales scrutiny.** What it does, in plain words: "Similar properties sold near each other should sell for similar
  prices per square foot. Sales that stand far apart from their group are set aside for you to look at: they may be
  non-market sales, or the property's data may be wrong."
  - **Where "near" is** (`analysis.sales_scrutiny.location`): one of the user's location fields (Data › Location, map
    layers stamped onto parcels, census tract or block group, `condo_group`). Proposed: the user's first location field;
    else census block group when census is on; else **none**, said as a warning: "Sales are compared across the whole
    county, by size only." (Without a location field OpenAVMKit silently skips the location split; the sample has none,
    so its single-family sales were compared county-wide.) The same location is proposed for the equity clusters
    (`horizontal_equity`, `land_equity`, `impr_equity`), where OpenAVMKit's template has none for land and improvement.
  - **What "similar" is:** the numbers (default: land size, finished area, quality, age, condition, whichever are
    loaded) and, optionally, categories (`fields_numeric`, `fields_categorical`); clusters keep at least 5 sales.
  - **Checks, each on or off with its rule:** a nominal price, above zero but under 1,000 (changeable): a $10 deed, not
    a price (the sample: 67 sales; a $10 deed had reached step 4, its ratio 49,360); sales on the same deed on the same
    day (needs a deed ID: Data › Deeds; off without one, saying why); sales on the same day at the same price; a deed
    for several parcels whose other parcels' sales weren't valid, so the one left carries the whole deed's price (needs
    a deed ID; OpenAVMKit's `bulk_deed`, from its PR #406); sold as vacant but the building is older than the sale; sold
    as improved but the building was built after the sale year (likely land when sold; needs year built); sold as vacant
    for at least half the median improved sale in its model group and location (likely had a building); buyer and seller
    share a surname (possibly between family; needs the names, Data › Deeds, below). And the cluster outliers: outside
    median ± 2 standard deviations of price per area, 4× the median or more, or 0.35× or less and more than one
    deviation below.
  - **Each cluster outlier diagnosed** (after "Amateurs talk Algorithms, Professionals talk Data Cleaning", Center for
    Land Economics, 2025): its price, price per area and size each read **low**, **in range** or **high** against its
    group, by the thresholds sales are flagged at (2 standard deviations; or 0.35× / 4× the median, which matter in a
    small group, whose spread the outlier itself stretches: a $10 deed among $300,000 houses is low), and each gets
    exactly one of the five patterns: **1** odd price per area and odd size (the size is likely wrong); **2** low price,
    low price per area (likely not a market sale: foreclosure, between family, a partial interest; or worse condition
    than recorded); **3** high, high (likely more than this parcel: several parcels, business assets, a related party, a
    partial interest scaled up); **4** ordinary price, high per area (finished area under-recorded, or unrecorded
    upgrades); **5** ordinary price, low per area (finished area over-recorded, or several parcels' areas added). One
    fitting none is **flagged but left in**: it counts unless the user excludes it. (OpenAVMKit's classic reading counts
    any price below the median as low and its size test always passes, so a sale could show several patterns; engine
    A6b.)
  - **And a second look** (`passes: 2`): a sale far off its cluster can stretch the cluster's spread so much that
    another far-off sale doesn't stand out (1502 Colonial Ave, $2.43 per sq ft, beside a sale at several times the
    median). Each cluster that had a sale set aside is compared again without it.
  - **Always flag, then decide** (below): OAK box never lets OpenAVMKit drop a sale the user hasn't seen.
- **No checks before running** (removed 2026-10-31): sales sold vacant on parcels improved now (and the reverse) are
  pointed out on Data › Sales, sales for parcels not in the parcel universe on Data's Sales and Condo units steps, and a
  group's sales in the window on Time adjustment.

**Run:** **Check sales** (like Bring in data: progress per part with what it's doing, heartbeat, Stop; per model group
inside each part, which needs engine progress events in clustering, time adjustment and scrutiny). No part can be
skipped: each one's output is needed downstream.

**Receipt:**
- **The sales funnel,** continuing from Bring in data's: valid sales from Data → outside the sales window (improved,
  vacant) → invalid by your rules → set aside by scrutiny, by check and by pattern (each **See them**) → kept by you (+)
  → excluded by you (−) → **= sales for modeling**, per model group in a table beside it (sales, set aside, used, time
  adjustment per year, clusters).
- **Far from their group, by pattern:** the five-pattern table, all model groups or one: each pattern's sales and % of
  sales, its likely cause and what to check first, **See them**; then the flagged total. Sales flagged but left in are
  said under the funnel, with **See them**.
- **Time adjustment:** the chart per model group (above), with **Show schedule** (the daily factors).
- **Filled:** per field, how many values in each model group were filled, and how.
- **Equity clusters:** per model group, how many, their typical size; ones under 15 parcels said.
- **Rare categories folded,** per field.
- OpenAVMKit's own notes, folded; the files written (and the per-group scrutiny reports OpenAVMKit writes,
  `out/sales_scrutiny/<group>/`, for the record), **Show in folder**.

**Review: the sales set aside (the sales register of §3.6, first used here).** A list and a map of every sale set aside,
filterable by model group, check, pattern and status, each in plain words with its numbers, e.g. "Sold for $41 per sq
ft; the 23 similar sales nearby went for $118 (median). 2,400 sq ft, built 1978, Elm St." The cluster's other sales on
the map and in a small table beside it, the sale's own data (to spot a wrong size or year), and its deed and dates.
- **Its diagnosis:** the readings table (price, price per area, size: this sale, its group's median, standard deviations
  from it, low / in range / high); its pattern with the likely cause and a checklist of what to check; for the other
  checks what they found ("built 2023", the shared surname, "67% of the median improved sale"); buyer and seller.
- **Recorded with it** (a sale set aside as same deed, same day, or same day, same price): the sales on its deed that
  day (or the same day at the same price), itself first, with model group, price, finished and land area; **Open it** on
  each one set aside too; "Each recorded at $10: likely the price of all 13 parcels together" (or their total).
- **Related sales:** the same deed; the same day within 500 ft; the same day to the same buyer; the same buyer within a
  year (with how far away, and whether set aside too): a sale of several parcels, or an investor's.
- **Look at it:** **Street View** and **Aerial** (Google Maps at its coordinates), **Zillow** (by address) and
  **Redfin** (no address link: the first Redfin search result), in the computer's own web browser (revised 2026-11-10:
  the app's viewer window couldn't show them; outside the desktop app, one browser tab reused).
- **Keep** (a note required): it counts after all. **Exclude** any sale, set aside or not (a note optional). Each says
  that it applies on the next **Check sales** run (seconds).
- **What it writes:** kept sales go in a keep-list (engine A6: `analysis.sales_scrutiny.keep_file`, a CSV of
  `key_sale`), exclusions in `invalid_key_file`; both in `in/`, so notebook users get the same sales. Overrides survive
  re-runs; a kept sale stays kept only while the same check still sets it aside (otherwise it's just counted).
- **Looks right** marks step 3 done, as F5.

**Out of date when** Model groups runs again or anything on this tab changes; it says which. Step 4 and 5 then wait for
it (§6.4).

**Engine changes** (built on `engine/enrich-fixes`, up to commit `9fc828a`; then upstream). Anything generally useful is
built in the engine, not OAK box:
- **A6, scrutiny for review (built):** drops as settings (`analysis.sales_scrutiny.drop.clusters`, `.drop.heuristics`);
  a `keep_file` (CSV of `key_sale`) whose sales are flagged but never dropped; every sale a check flagged, kept or
  dropped alike, in `out/sales_scrutiny/flags.parquet`: `check` (`dupe_deed_date`, `dupe_date_price`, `bulk_deed`,
  `false_vacant`, `excluded`, `cluster`, and the checks added since), and for clusters `count`, `price`,
  `price_per_area`, `median`, `stdev`, `relative_ratio`, `med_dist_stdevs`, `rules` (thresholds crossed), `pattern`
  (anomaly 1–5), `scrutiny_pass`; then `kept`, `dropped`. Before, with drops off a flagged sale stayed valid and reached
  modeling, and the heuristics' flags existed only in Excel files. OAK box runs with drops on, the keep-list holding the
  user's keeps, so a sale set aside never reaches modeling unless kept (§3.6's rule).
- **Outliers hidden by another outlier (built):** `analysis.sales_scrutiny.passes: 2` compares each cluster that had a
  sale flagged again, without it, on the ratio thresholds only (4× the median; 0.35× and a deviation below). On the
  sample it finds 6 more single-family sales, all far off (four sold for about $12; 1502 Colonial Ave at $2.43 per sq
  ft), and nothing ordinary. With 2 deviations in the second pass it set aside 25, many at 1.3–1.5× the median (a small
  cluster without its outlier has a narrow spread), so that's not used. OAK box sets `passes: 2`; the review says "found
  once the sale that hid it was set aside".
- **Each heuristic on or off (built):** `analysis.sales_scrutiny.heuristics.<name>: false` (`dupe_deed_date`,
  `dupe_date_price`, `bulk_deed`, `false_vacant`, and the checks added since); the sold-as-vacant check is skipped, with
  a warning, when there's no year built (it failed the run).
- **A6b, scrutiny as a diagnosis (built, opt-in):** `patterns: "strict"` (the readings and one pattern each, or `other`:
  `flag_only`, never dropped; the readings and the group's median price and size in the flags file); new heuristics, off
  unless turned on: `built_after_sale`, `vacant_priced_improved` (`share`, `location`, `min_sales`), `same_surname`
  (`pattern`, `skip_words`; `surnames()`; the `deed_grantor_surname` / `deed_grantee_surname` fields win where filled; a
  name of several people is split on & ; / AND, a one-word part sharing another's surname; names with LLC, TRUST, BANK,
  COUNTY… aren't people). Heuristic flags carry a `detail`. OAK box turns all of it on.
- **Template key (fixed):** the template's never-read `fields_categorical_improved` is `fields_categorical`.
- **Progress per model group (built):** `do_per_model_group` reports which group it's on (`progress.detail`:
  "Scrutinizing sales: single_family (6 of 6)", with the step's own completion), so time adjustment, equity clusters and
  scrutiny say where they are.
- **B9, provenance flags for fills (built):** `out/filled.parquet`, `key` and a column per field with any value filled,
  true where it was blank before.
- **Also fixed:** a model group with no flagged sales lost its sales from the scrutiny output and report counts; the
  cluster output now includes each cluster's median.
- **Reports (OAK box side):** scrutiny's PDF reports need wkhtmltopdf (they warn without it); OAK box asks for Markdown
  only (`analysis.report.formats`) until Typst (A5).

**As built** (`src/oakbox/clean.py`, `web/src/screens/CheckSales.tsx`): the tab opens once Model groups has Looks right
(Looks right there moves on to it).
- **One task at a time** (the frame of F5): a step per call, **Sales window** (with the checks before running; ⚠ while
  there are any) › **Time adjustment** (the preview) › **Sales scrutiny** (⚠ with no location) › **Check sales** (the
  run: **Check sales ›** where Next is, then **The sales** opens) › **The sales** (the funnel, by model group, the
  files) › **Sales set aside** (the review; ⚠ while any is undecided), whose Next is **Looks right › Check my values**
  (it opens step 4; once pressed, **Check my values ›**). The note and Keep, Exclude and Next are pinned to the bottom
  of the window, so Next stays put from sale to sale, and each sale opens at its top. **See them** on the funnel opens
  Sales set aside filtered by that check.
- **The calls** are the project's `clean` state. Nothing is written to settings.json until the step is first used; then
  the proposals (fills, the location, the categories to fold) are written down and every call is explicit. Fills are
  added to OpenAVMKit's own fill lists (`+median`), never replacing them. The keeps and exclusions are
  `in/oakbox/keep.csv` and `in/oakbox/exclude.csv` (`key_sale, note`). The calls don't put Bring in data or Model groups
  out of date (they're left out of those steps' settings hashes).
- **The run** (`python -m oakbox.clean <id>`) calls OpenAVMKit's clean stage part by part, so each part is counted:
  fill, equity clusters, sales (window, validity, time adjustment), scrutiny, rare categories, then the 2-clean
  hand-off. Progress names the model group each part is on. About 25 seconds on the Guilford sample.
- **The receipt:** the funnel adds up from the valid sales to the sales for modeling, each check counted once at the
  first, kept sales added back, exclusions taken off. The model-group table includes **No parcel**, the sales whose
  parcel isn't in the parcel universe: they stay in OpenAVMKit's sales but no model can use them (386 on the sample,
  condo units switched off on the copy). Then the time adjustment charts (from each group's schedule; **Show schedule**
  shows the CSV), what was filled (from `out/filled.parquet`), and the files written.
- **The review:** the sales set aside (and those flagged but left in), furthest from their group first, filtered by
  model group, check or pattern, and status. Each sale shows why, in words from its checks; its readings and pattern
  with what to check; Street View, the aerial, Zillow and Redfin; a dot plot (log scale) and a table of the sales it was
  compared with; its related sales; and its own data. On the sample: every sale far from its group fits a pattern (8,
  36, 21, 12, 7), 98 share a surname, 7 were built after their sale. Said first (revised 2026-10-31): every sale here is
  out (the models don't learn from it, the ratio studies leave it out) because a check flagged it; one not decided stays
  out for as long as a check flags it. Each sale says where it stands now ("out, set aside by the checks. Not decided";
  "put back"; "left out for good"). **Put it back** (OpenAVMKit's keep file: flagged, never dropped) needs a note saying
  why it's a market sale; **Leave it out for good** (its invalid-sales file: out whatever the checks say later) can have
  one; **Undo**. Both apply on the next run, and the tab says so. The status filter: Not decided: out for now, Put back,
  Left out for good.
- **No checks before running:** what they said is shown where it's fixed (Data, Time adjustment).

**Not built yet:** a sales window per model group; the granularity OpenAVMKit settled on per group; a map of the sales
set aside; excluding a sale that wasn't set aside (the API takes any sale; the review only lists sales set aside);
"vacant at sale = vacant now" as Data's assumption, which needs OpenAVMKit to take a sale's vacancy from its parcel.
OpenAVMKit's own notes are listed raw.

**Not in this step:** street frontages, spatial lag and area statistics (step 6), the ratio study (step 4), model
outliers (step 6's review, in the same register).

## 3.6 Sales review and overrides
**Rule: a sale flagged invalid never touches the modeling pipeline.** The flag can come from the office code, a validity
rule, scrutiny, a model outlier or the assessor. OpenAVMKit already removes such sales as it goes, and Oakbox keeps it
that way.

Review happens **outside** the pipeline, in Oakbox's own **sales register**. The register is a separate record of every
imported sale, with every verdict it received:
- office code (step 1)
- validity rules and scrutiny (step 3)
- model outlier (step 5)

Each verdict comes with reasons in plain words.

- **Final status:** **Valid** or **Invalid**, plus who decided.
- **Overrides:**
  - **Exclude** a valid sale. A note is optional. Excluding a model outlier requires a reason from a checklist (bad
    data, non-market, partial interest, …).
  - **Keep** a flagged sale. A note is required. The sale re-enters the pipeline only through a re-run, and only because
    it is no longer flagged invalid:
    - Office-code invalid → re-run from step 1. Oakbox rewrites that sale's `valid_sale` at load.
    - Scrutiny or rule → re-run from step 3, through a keep-list (upstream A6).
    - Excluding → re-run from step 3, through `invalid_key_file`.
  - Overrides survive re-runs and are written into files OpenAVMKit reads, so notebook users see the same result.
  - Before applying, Oakbox says which steps will re-run.
- **Rule templates** (Advanced). Relative rules such as "price under 50% of current value" compile to `invalid_sales`
  filters.
- **Views:** a map, a list, and filters ("only flagged", "only overridden", "by model group", "model outliers").
- **Reported.** Reports list every override, with its note.
