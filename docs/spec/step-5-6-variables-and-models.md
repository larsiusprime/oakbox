# Steps 5 and 6, Variables and Models

Prepare the fields (F7), the variable tests, lists and models (F9), then the first draft of building model values
(§3.10), which F9 supersedes where they differ.

## F7. Step 5, Variables: Prepare the fields (its own tab, **5. Variables**; the tests, lists and models are F9)
It opens once Check sales has Looks right. Steps: **Fill blanks** › **Rare categories** › **Prepare the fields** (the
run) › **What changed** (Looks right) › **Test the variables** › **Variable lists** (F9). **6 Model values** (the
models, a try, how they did) opens once What changed has Looks right (revised 2026-10-31: the variables are a tab of
their own).
- **Why here:** they're notebook 2's first and last calls in OpenAVMKit's order, but nothing in Check sales depends on
  them (the equity groups and the sales checks compare land size, finished area, quality, age and condition, which
  aren't filled here). Some models fail on a blank (the linear ones); the others read it as unknown.
- **Fill blanks:** each number the models can use that's blank somewhere after step 2, one row each: the field, its
  **kind** (OpenAVMKit's field classification, a tag: Building, Land or Other), its blanks, and a method dropdown in
  three columns, **Improved**, **Vacant** and **All**. The columns that don't apply are hatched:
  - **Building** (`impr` fields): Improved only. Vacant is locked (🔒): OpenAVMKit has made it 0 there already, and
    those 0s would pull a median over every parcel down. Written as `+<method>_impr`.
  - **Land**: All only, never split. A fact about the land or the area it's in is the same built on or not: census
    figures (a fact about the block group), elevation, distances.
  - **Other**: All. Its dropdown also has **Split**: Improved and Vacant then each have their own (written
    `+<method>_impr`, `+<method>_vacant`), starting from All's; a method in All joins them again.
  - Each dropdown's first choice is **Auto (…)**: the fill proposed from what a blank means, followed if that changes
    (zero for renovation permits, `renovation_num`; leave blank where there's nothing to stand in, `days_to_*`,
    `land_area_alloc_*`, finished area and year built; the model group's median for the rest). Then median, mean,
    most common, zero, smallest, largest, leave blank. Written as OpenAVMKit's `data.process.fill` lists, added to
    its own (`+median`). Projects from before had their proposals written down as if chosen: each still as proposed
    is made Auto once (`fills_auto`); fills from before for only improved or only vacant parcels are a split.
  - **What each group gets**, under the choices: a row per field, a column per model group, the value that goes into
    that group's blanks, worked out as OpenAVMKit fills (each group from its own parcels' values, improved or vacant
    ones' when filled separately). "—" where the group has no blanks; **blank** (amber) where it has blanks but no
    values to take a median, mean, smallest or largest from: those stay blank; split, the vacant parcels' value under
    it.
- **Rare categories:** off by default. The category fields the models use, but not locations, the model group, IDs and
  addresses (or anything with more distinct values than half the parcels), or dates. With the thresholds (fewer sales
  than, fewer parcels than), a table per field: its values, how many fold, their parcels, and which ("Become Other"),
  counted on the sales Check sales kept, as OpenAVMKit counts them.
- **Prepare the fields:** OpenAVMKit's `fill_unknown_values_sup` and `collapse_sparse_categories_sup` on Check sales'
  hand-off (`out/oakbox/clean/sup.pickle`), in a process of its own (`python -m oakbox.prepare`), then notebook 2's
  output written again (`out/2-clean-sup.pickle`, `out/look/2-clean-*`): the same as notebook 2 writes with the same
  settings. Out of date when Check sales runs again or a fill or the folding changes. The receipt: what was filled (per
  field, how many, how) and folded (per field, the values and their parcels), and the files.

## F9. Steps 5 and 6, Variables and Models: the variable tests and lists, and the models (tab **6. Models**; slices 1 and 2 built, slice 3 in part: see As built)
What stands between Prepare the fields (F7) and values a model made, and how steps 5 and 6 continue. It replaces §3.10's
earlier draft where they differ.

**The spike** (2026-10-29, the sample: 7,994 parcels, 1,477 sales; Prepare's output; a hand-written variable list of
finished area, land area, effective age, units, normalized latitude and longitude, polar coordinates, elevation and
slope; LightGBM and local-area with a median ensemble; OpenAVMKit's defaults, 5-fold nested cross-validation):
`write_canonical_splits`, then `model_runner.run_models` (try, no vacant models), ran headless in **29 s** and wrote
`out/models/`. The plumbing works. What it showed:
1. **No variables, no models.** OpenAVMKit has no default list: `modeling.models.main.default.ind_vars` must be written,
   or every model raises. Nothing in OAK box writes it yet.
2. **Linear models refuse blanks.** MRA stopped on `slope_mean_deg`, blank on 1 of 359 small multi-family parcels. ML
   models take blanks; linear models need every variable filled (F7's Fill blanks), so the variable list and the fills
   must agree before running.
3. **Small groups get no values.** Groups under 15 sales are skipped with a warning: apartments (106 parcels) and public
   & exempt (564) got no value at all, and Unassigned (22) none either.
4. **Tiny groups get nonsense.** Commercial & industrial, 9 sales for 1,217 parcels: LightGBM's holdout median ratio was
   −0.12 (COD −2,610); 118 parcels got **negative** values, and the ensemble kept them.
5. **The results are in memory.** `run_models` returns each group's benchmark (per model: sales, median ratio, COD, PRD,
   PRB, VEI and its significance, trimmed versions; out-of-fold, the holdout); the pipeline's `try_models` and
   `finalize_models` return nothing, and nothing machine-readable about them is written.
   `out/models/all_model_groups/universe.parquet` has `model_group_x` and `model_group_y` (a merge that keeps both).
6. **Variables matter more than plumbing.** Single-family holdout COD 34.5 (20.4 trimmed) against the roll's 18.9 in
   step 4: the sample has no quality or condition. Not a blocker for building it; the first thing a user will see.

**Blockers, in order** (each one is work; slice 1 is what it takes to run models from the app):
- **Slice 1, run models and see how they did:**
  - **Variables:** a default list from what's loaded (below), written as `default.ind_vars`; ones with blanks left out
    of linear models, or filled (a link to Fill blanks).
  - **Models:** a picker with **Choose for me**.
  - **Try:** the run, its own process (`python -m oakbox.model`), with progress per group and model (`progress.report`
    exists in `_run_models`), Stop, and the results kept as `out/oakbox/model/results.json` from `run_models`' return.
  - **Results:** per model group, the models side by side, with the roll's own value beside them, judged as step 4
    judges.
- **Slice 2, values for every parcel and the ones that ship:**
  - **Small groups:** left unvalued by default (below), and no negative values shipped.
  - **Finalize:** `finalize_models`, then the model values checked as step 4 checks the roll's, side by side. **Looks
    right** ends step 5.
- **Slice 3, working on them:** outliers back into Check sales; testing variables; per-group variables and models; "why
  this value" from the contributions OpenAVMKit already writes (`contributions_universe.csv`).

**Steps** (the tab continues after What changed): Fill blanks › Rare categories › Prepare the fields › What changed ›
**Variables** › **Models** › **Try them** (the run) › **How they did** › **Small groups** › **Finalize** (the run) ›
**Model values** (Looks right).
- **Variables.** One table: each candidate with what it is, its coverage after Prepare, and whether it has blanks left.
  Ticked by default:
  - **The big five:** finished area, land area, effective age (else age), quality, condition; units for multi-family.
  - **Location:** normalized latitude and longitude, polar radius and angle; the location fields as categories (ML
    models only).
  - **Public data:** elevation, slope, distances (`dist_to_*`), census fields, when brought in.

  Missing ones are skipped and named ("No quality: Data › Building"). Written as
  `modeling.models.main.default.ind_vars`. Said plainly: OpenAVMKit prunes the default list per group by its own
  variable tests (`feature_selection`: correlation, VIF, p-value, coefficient sign) before linear models use it; trees
  keep it all. A variable with blanks is **trees only** unless filled, said on its row with **Fill it…**.
- **Models.** (Superseded 2026-10-31: per-group models and variable lists, as built below.) **Choose for me**
  (preselected): LightGBM, MRA on log price (`"log": true`, so no negative values) and local-area, median ensemble
  (settled 2026-10-29). The picker lists each engine in a line: LightGBM, XGBoost, CatBoost (gradient-boosted trees: the
  most accurate, harder to explain), MRA (a linear model: explainable, needs every variable filled), multi-MRA (one per
  neighbourhood), GWR (slow), local-area (the neighbourhood's price per area: a baseline). The ensemble combines the
  chosen models, never the roll's value. Written as `modeling.instructions.main.run` and `.ensemble`. Speed:
  OpenAVMKit's default (5-fold nested cross-validation) on every size until a Quick tier is measured (M0: fewer folds is
  slower at 150k+); the run's time is said beforehand from the last run or the parcel count.
- **Try them.** `try` (no values written for keeps), no vacant models (`run_vacant=False`, §3.10). The step shows each
  group and model as it trains. Before training, each modeled group's variables are checked for infinite (or
  float-overflowing) values, in its sales and its parcels: any found stop the run, named ("land_area_gis_delta_percent
  in Single family: 3 sales and 12 parcels (used by LightGBM, MRA)"), never OpenAVMKit's bare "Input contains infinity".
  Any error while training is reported with what can be said about it: the model group and model it was training
  (OpenAVMKit's progress says which) and its variable list ("While training LightGBM on Single family, variable list
  "Houses" (12 variables)"; or "while combining …'s models into the ensemble"); for an infinite value, the variables and
  prices that could cause it, or, when the data holds none, the variables whose parcels reach far past that group's
  sales (10 times the sales' spread past their edge: where a log-price model's prediction overflows), furthest first;
  where it stopped (the last frame in OpenAVMKit, then the last library frames: "OpenAVMKit inference.py:1184
  _calculate_metrics › … › validation.py:133 _assert_all_finite"); and the whole traceback in
  out/oakbox/model_error.txt.
- **How they did.** OpenAVMKit's benchmark, a model group at a time (settled 2026-10-30): models as rows, figures as
  columns; every heading sorts, every column's edge drags wider (remembered on the computer). A switch between **IAAO**
  and **Academic** figures; each is a table untrimmed, then a table trimmed, each collapsible; **Timings** collapsible
  under either. IAAO: the **Holdout** (each sale predicted by a model that never saw it), **After the valuation date**
  when there are such sales, and the **Study set** (OpenAVMKit's look-back before the valuation date); columns utility
  score, parcels, sales, median ratio, COD, PRD, PRB, VEI, VEI significance, CHD (where figured); trimmed, in the same
  columns: sales, median ratio, COD, PRD, PRB, VEI and its significance (utility, parcels and CHD are left blank: none
  of them is a figure of the trimmed sales). **The roll** (OpenAVMKit's `assessor` model, run whenever the universe has
  `assr_market_value`) only on the study set, first: the holdout is OpenAVMKit's own draw and the roll may have seen
  those sales. Academic, on the holdout: sales, MAPE, MSE, RMSE, median and mean ratio, slope (`academic_metrics`; its
  VEI left out: the IAAO view has it). Median ratio, COD and PRB carry the step 4 pill (✓, ~, ✗ against the project's
  targets), pinned left; figures written as step 4 writes them (ratios and the PRD to three decimals, the COD to one,
  the VEI in percent). A group may ship one model instead of the ensemble (the others skipped for that group:
  `instructions.main.skip.<group>`).
- **Small groups** (any group under 15 sales, or whose models came out implausible: a holdout median ratio outside 0.5
  to 2, or a negative value). **Left unvalued** by default (settled 2026-10-29): OpenAVMKit already skips a group with
  too few sales to fit; OAK box also skips the implausible ones (`instructions.main.skip.<group>`: every model), so a
  9-sale group's negative values never ship. Said plainly per group: its parcels (count), why ("9 sales: too few to
  model"), and that they get no model value; the report and export say the same. **Model it anyway** per group, with its
  figures shown. (Keeping the roll's value or borrowing another group's model are not offered for now; each would need
  an engine fallback.)
- **Finalize.** `finalize_models`: writes `out/models/` and the values (`market_value`). Then step 4's study on
  `market_value` (holdout, by group), shown beside the roll's.
- **Model values** (Looks right): the scorecard, the roll's beside it, how many parcels got a model value, how many are
  unvalued (and why), and the files.
- **Out of date when** Prepare runs again, or a variable, model or small-group choice changes. Tuning is reused unless
  **Re-tune** (§3.10); Stop never deletes it.

**As built** (`src/oakbox/model.py`, `varlists.py`, `locstack.py`; `web/src/screens/Variables.tsx`, `VarLists.tsx`,
`ModelValues.tsx`, `Models.tsx`, `components/LocationStack.tsx`; revised 2026-10-31): **5 Variables** runs Fill blanks ›
Rare categories › Prepare the fields › What changed › **Test the variables** › **Variable lists**; What changed's Looks
right opens Test the variables. **6 Model values** is **Models** › **Try them** › **How they did**. The one list of
ticked variables is gone: each model takes a variable list.
- **The variables there are:** every field OpenAVMKit classifies as land, building or other (`field_classification`,
  with the user's own fields, map layers' and public data's), less identifiers, the roll's values, sale and deed fields,
  raw coordinates, land area as given or measured, years (ages are offered), Check sales' groups of similar parcels, and
  distances: each feature's `proximity_to_` is offered instead (it rises near the feature and is 0 beyond the distance
  that matters; `dist_to_cbd` stays, having none). A category with one value, or more than 50 and over half the parcels,
  isn't offered; nor a number the same everywhere, nor one infinite anywhere (a ratio over a zero: no model can take
  it). Only once the fields are prepared.
- **Test the variables** (after What changed; `python -m oakbox.vartest`, a few seconds): OpenAVMKit's own variable
  tests on each model group's sales (15 or more) with the variables ticked (`get_variable_recommendations(...,
  return_tests=True)`, engine work below), then the tests as its parts, nested under it in the step list (shown while
  it's open; the step frame takes a `parent` on a step): **Represented**, **Correlation**, **Redundancy (VIF)**, **What
  to keep**. **Tests to run**, on the step itself: Represented always; Correlation and Redundancy as the user ticks
  (both to start, at least one; `tests_to_run`, saved as `model.tests`); a test not run isn't listed, and a change of
  tests makes the results out of date. OpenAVMKit's other four aren't run (settled 2026-10-30): each mostly repeats one
  of these: R² on its own is the correlation with price squared; the t-value is the significance test's regression read
  another way; the elastic net asks again whether a variable adds anything beside the others; signs agree checks those
  three point the same way. **No significance (p-value) test** (settled 2026-10-31): represented, correlation with price
  and VIF are what the variable lists need; a p-value judged in one regression of every variable says little about a
  list. (Engine fix: `tests_to_run` without R² failed while combining the scores.) Each says in a line what it measures
  and when a variable passes (thresholds from `feature_selection`), with a model group to show (the one with most sales
  first): a table, a row per variable: a category is one row (its best value's figure, passing if any of its values
  does, and "2 of 7 values pass", which unfolds its values, each a column to the tests, indented under it), its figure
  with a pass or fail pill pinned left, and a bar against the threshold (VIF on a log scale). No ticks (revised
  2026-10-31): the tests run on every variable, the evidence the variable lists are built from. Recursive tests pass
  what survives their drops. **Correlation judges the relation to price alone** (revised 2026-10-31): a variable passes
  with a correlation with sale price of 0.10 or more, either way, whatever it overlaps; overlap is the VIF test's alone
  (OpenAVMKit `feature_selection.correlation_overlap: false`, `engine/enrich-fixes`: no clarity in the score, no pass
  dropping a variable more correlated with a stronger one than with price). A failure's pill says **too weak**. **how
  ›** on any row (or a category's value) unfolds its correlation with price (with a bar and the threshold) and the five
  variables it moves with most (signed), which VIF judges. **What to keep:** OpenAVMKit's weighted score per variable
  and model group, and its pick per group (the set that predicts best in cross-validation) as a pill. A variable not
  tested yet (prepared since) puts the tests out of date. The tests fill a variable's blanks with its median; a variable
  with no value among a model group's sales (days to renovation where none of its parcels had a permit) has none, and
  stopped OpenAVMKit's elastic net, failing the whole group: it's left out of that group's tests and named there, with
  **Fill it…** (and the engine now leaves such a column out of the elastic net, warning, rather than failing).
- **Variable lists** (settled 2026-10-31): named lists of variables, each with a **type**, Regression or Machine
  learning, and the **model groups** it's for (one list can serve several). A table of the lists (name, type, groups,
  how many variables, which models take it: "MRA · 5 groups"), one open at a time: its name, type (a switch) and groups
  (MultiPick); what's recommended for its type; then every variable, ticked in or out, with its kind, Represented,
  Correlation with price and VIF in one of its groups (**Scores for**, a dropdown of the groups tested, the others named
  as not tested; the variables in a box of their own that scrolls, so the other lists stay in sight), and a pill:
  **recommended**, or why not. For a regression: in the sales, a correlation of 0.10 or more, survives VIF (10), no
  blanks (a linear model can't take one), not a category with more than 8 values ("has blanks", "barely in the sales",
  "weak with price", "overlaps others", "too many values"); for machine learning: in the sales, and not a category with
  more than 20 values (CatBoost slows with each). **Tick the recommended for <group>** (what the pills say for the group
  shown; revised 2026-10-31: it had ticked what's recommended in the groups holding most of the list's sales, which read
  as haphazard beside another group's pills), **Untick all**. Warnings: a regression list with fewer than 10 sales per
  variable in one of its groups ("a shorter list of its own would suit it"), variables with blanks on a regression list
  (left out by its linear models), categories with many values. **Add a variable list** (empty: a regression list with
  no groups and nothing ticked; until its groups are chosen it says so, and Scores for offers every tested group),
  **Remove**. **None to start** (revised 2026-10-31; it had proposed a Regression and a Machine learning list of every
  modeled group): a list's ticks are the same for every group it's for, which a proposed list of every group hid; making
  them one by one shows it, and a group's own variables are a list of its own. Written to OpenAVMKit's settings as
  `variable_lists.<id>` (an id from its first name, kept through renames), each model pointing at its list: `"ind_vars":
  "$$variable_lists.<id>"` (OpenAVMKit resolves `$$` paths as it loads the settings).
- **Models** (settled 2026-10-31): one model group at a time (revised 2026-10-31, were tabs): a header names it plainly
  ("Model group 2 of 5", its name large, its sales), groups not modeled passed over; the footer's button goes on to the
  next group ("Small multi-family ›"), Back to the one before; on the last, **Next ›** (to Try them) waits until every
  group's models have a variable list with variables, the footer naming the groups still without one. Its models in a
  table (Model · Engine · Variables · **Configuration**): each a name (changeable; the engine's unless given), its
  engine, and its variable list (a picker: any list, "Regression · 10 variables"), every group starting with
  **LightGBM** (the first machine-learning list for the group), **MRA** and **Multi-MRA** (the first regression list); a
  list for other groups or of the other type only when picked; with no list for it yet, a model says **No variable
  list** (its picker reads Choose a list) and a try is stopped until it has one. Local area takes no list (its areas'
  price per area); Multi-MRA and Local area take a **location stack** too (below). Under a model, said plainly: a
  machine-learning list on a regression model or the other way ("it'll run, but…"), its list removed, its list empty
  (stops a try), the variables with blanks its linear engine leaves out, no locations (Multi-MRA then fits one
  regression, as MRA does; Local area can't run). **Add a model** (a row: engine, name, list; Add / Cancel), **Remove**,
  **Back to the default models** (Copy these models to…, and the line saying where they're written, removed
  2026-11-07). Written per group as
  `modeling.models.main.<group>` (OpenAVMKit takes a group's block in place of the shared one): `default` (the land and
  finished areas, for Local area and the roll), each model under a key from its name (`{"model": <engine>, "ind_vars":
  "$$variable_lists.<id>", "log": true, "locations": [...]}`; a linear model whose list has variables with blanks gets
  the list without them, written out), and the other value sets as `pass_through`. `instructions.main.run` names every
  group's models (then the roll and the other value sets), `ensemble.models` the models, and `skip.<group>` the models a
  group hasn't (every one for a group not modeled). The results show each model by its name.
- **Configuration** (settled 2026-10-31; `ModelOptions.tsx`): a model's own settings, as OpenAVMKit reads them from its
  entry. Its cell: a one-line summary ("log price · intercept · no interactions", "Locations: School district ›
  Neighborhood · …", "50 tuning trials"), what differs from the default in bold, then **Change…**; GWR has "No settings
  of its own" but for interactions, which it has. **Change…** opens them in a panel under the row, one at a time
  (**Done**), each saved as it changes: **Fit on log price** (MRA, Multi-MRA; on; `log`), **Intercept** (MRA, Multi-MRA;
  on; `intercept`), **Interactions** None / Categories × size (MRA, Multi-MRA, GWR; None; `interactions: {"default":
  …}`: each land category times land area, each building category times finished area), **Trim variables in each area**
  (Multi-MRA; off; `optimize_vars`), **Tuning trials** (LightGBM, XGBoost, CatBoost; 50, 1 to 500; `n_trials`), **Use
  the graphics card if there is one** (CatBoost; on; `use_gpu`), and the location stack (Multi-MRA, Local area; moved
  here from the Variables column). Each with a line on what it does; warned: log price off ("can value parcels below
  zero"), intercept off, fewer than 20 trials, no locations. Every option the engine reads is written, defaults too
  (`OPTIONS`, `DEFAULTS` in `model.py`), and only those; a change makes the try out of date. Not offered: sales chasing (a test mode), global settings, hand-picked interaction pairs (OpenAVMKit's
  `interactions.fields`; later, if Categories × size is too blunt). **Layered comps** (OpenAVMKit's `lcomp`, added
  2026-11-01): comparable sales as a model, the sales split into ever-closer groups by the list's variables and a parcel
  valued from the trimmed mean prices of the groups it falls in, the closest weighted most (`layeredcompmodel`'s bagging
  model: 10 trees, OpenAVMKit's fixed settings). A machine-learning engine like the trees (`ML` in `model.py`): it takes
  a machine-learning list, blanks and all; no settings of its own (OpenAVMKit doesn't tune it: `n_trials` is unused), so
  its Configuration cell says so. On the synthetic sample's single-family sales (held out): COD 18.5 against LightGBM's
  19.1. **Not offered** of OpenAVMKit's other engines: NGBoost and kernel regression (could be: their libraries are in
  the bundle), spatial lag and spatial-lag-area (possible now that the spatial lag enrichment is built), naive per-area,
  mean and median (baselines; Local area serves), ground truth (synthetic data's answer key), garbage and garbage-normal
  (random predictions, for testing).
- **Location stack** (`components/LocationStack.tsx`, reusable; settled 2026-10-31): the location fields a model reads,
  shown broadest first under **Whole model group**, written finest first as OpenAVMKit takes them (`locations`); each
  level with its areas, their median sales, the areas with 15 or more (enough for Multi-MRA's own regression), and
  whether it nests in the level above ("✓ nests in Neighborhood", or "3 areas span more than one Neighborhood"); ↑ ↓ and
  Remove per level, **Add a level** from the location fields (the user's own, map layers', census areas). Opened in its
  model's Configuration panel. Proposed per group: every location field with at least two areas of 15 or more sales in
  it, fewer areas above more. Preview: `GET /model/stack/{group}?fields=…`.
- **Try them:** `python -m oakbox.model`: the prepared hand-off, `write_canonical_splits`, then `try_models` (no vacant
  models), with progress per group and model and Stop. 28 s on the sample.
- **How they did:** as above (2026-10-30). The figures are OpenAVMKit's own numbers: the benchmark's frames, read after
  the engine has printed them (printing no longer turns them into text), and `academic_metrics`. On the study set each
  model is judged by its holdout predictions (`analysis.ratio_study.study_set_predictions: "holdout"`, an engine opt-in
  OAK box always sets; Check sales ignores it), like for like with the roll: by OpenAVMKit's default, its predictions on
  every sale, it would be judged on sales it trained on. The trimmed median ratio and VEI are the benchmark's own too
  (`median_ratio_trim`, `vei_trim`, `vei_sig_trim`: engine, in its frames, not its printout). Groups with too few sales
  say so. OpenAVMKit's notes fold away underneath. **Try again**.
- **Small groups** (slice 2; built 2026-10-31, `smallgroups.py`, `SmallGroups.tsx`), after How they did: a row per model
  group with the try's figures (parcels, sales, the ensemble's holdout median ratio and COD, values below zero) and why
  it can't be trusted, as pills: fewer than 15 sales ("too few to model"; OpenAVMKit's own floor), no model produced
  values, no sales held out to judge it by, a holdout median ratio outside 0.5 to 2, values below zero. Both kinds are
  flagged (settled 2026-10-31): groups ticked on Model groups whose try came out badly, and groups with too few sales. A
  flagged group is **Leave unvalued** by default, or **Model it anyway** (not offered when no model produced values for
  it); saved as `model.small`. Under the table, the parcels left unvalued and in which groups, and the parcels in groups
  modeled anyway that came out below zero. No engine floor (settled 2026-10-31): OpenAVMKit already skips a model on
  fewer than 15 sales, MRA and Multi-MRA fit log price (never below zero) and the ensemble drops models that don't help;
  a value below zero that's left is a check, and the parcel stays blank and is counted. The try counts each group's
  valued parcels and values below zero (the ensemble's universe predictions). The choices apply when the values are made
  (Finalize, next): the try models every group, to judge it.
- **Small groups' Looks right** (2026-11-01): accepts the try (`model` step's accept), so Finalize starts from it; a try
  out of date can't be accepted.
- **Finalize** (slice 2; built 2026-11-01, `final.py`, `FinalValues.tsx`): `python -m oakbox.final`, OpenAVMKit's
  `finalize_models` from the same starting point as Try them (`model.for_models`: the prepared hand-off, the folds, the
  nearby averages), its saved tuning reused, no vacant models. The groups Small groups leaves unvalued skip every model
  (`instructions.main.skip`); a value below zero is left blank and counted. Writes `out/oakbox/final/`: the receipt, the
  studies, and `values.parquet` (each parcel's key, model group, model value, whether it came out below zero, and the
  roll's). Progress per group and model, and Stop, as Try them. 39 s on the synthetic sample. **Out of date when** the
  try runs again, a small group's choice changes, or Check my values' window, price, trimming, standards, classes or
  region change (it's judged as step 4 judges).
- **Model values** (Looks right ends step 6): the values against the sales, as Check my values judges the roll's (step
  4's studies, standards and window; `run_value_field_studies` on the hand-off with the values put on each sale), on a
  set of sales the user picks (**Judged on**, settled 2026-11-01; the report will offer the same three, all by default):
  - **Out of fold:** each sale valued by a model that never saw it (the ensemble's out-of-fold predictions, every
    trainable sale): honest, every sale.
  - **Held out:** the sales the final models never trained on (under cross-validation, those after the valuation date;
    with a single split, its test sales), valued by the final models. Greyed when there are none (the synthetic sample
    has none).
  - **As valued:** every sale, valued by the final models, most of which they trained on: the values as they ship,
    flattering.
  - The model's scorecard (Check my values' `Scorecard`, under the statistics' own names here, revised 2026-11-01:
    **Median ratio**, **COD**, **Horizontal equity** (the median CHD within the equity clusters, with a word: alike
    under 20, some spread under 40, wide spread; shown, not judged, as the IAAO sets no target; of every parcel's value,
    so the same whichever sales judge them: the final values' for the model, the roll's own for the roll), **Vertical
    equity** (VEI, or PRB), per group and for all groups), and under it the roll's (the roll if loaded, else the first
    set of existing values) **on the same sales**: only the sales the model values in that set, so the two compare like
    for like. Same columns, same widths.
  - **On the map** (2026-11-01): **Show** Ratio (the sales of the set judged on, coloured as on openratiostudy.com,
    trimmed ones grey), Value per finished area (every parcel, in tenths of the parcels shown, light to dark), or Change
    from the roll (every parcel, model ÷ roll, blue lower, red higher; not offered with no roll); a model group or all.
    Hovering a parcel says its group, model value, the roll's, the change and the value per area. Parcels with no model
    value grey. Read from `values.parquet` (`GET /final/parcels`, as columns) and the set's studied sales (`GET
    /final/sales`).
  - **What every parcel got:** per group its parcels, how many were valued (or why none: not modeled, left unvalued, too
    few sales), values left blank below zero, the median change from the roll (model ÷ roll − 1), parcels up or down
    more than 20%, and the total value beside the roll's on the same parcels. OpenAVMKit's notes fold away underneath.
  - On the synthetic sample (2025's 242 sales): out of fold, single-family median 0.945 and COD 13.2, VEI −2.1% (alike)
    against the roll's 0.843, 14.1 and −27.5% (dearer valued lower); as valued, COD 8.9 overall (flattering, as
    expected). 7,302 of 9,332 parcels valued; single-family up 13.1% from the roll at the median.
- **Out of date when** Prepare runs again, or a list, a model or a stack changes.
- On the sample: every model's level is in range where the roll's is about 0.74, but none is uniform enough
  (single-family ensemble COD 33.7 against the roll's 27.3 on the same 826 sales): no quality or condition in the
  sample.

**Engine work** (opt-in, defaults unchanged):
- **Correlation's first pass:** `calc_correlations(..., min_strength=)` / `correlation_strength`, and its correlation
  matrix returned. **Done** (`engine/enrich-fixes`).
- **Variable tests one by one:** `get_variable_recommendations(..., return_tests=True)` returns each test's results for
  every variable before and after its drops, with thresholds, weights and one-hot columns; `calc_representation` keeps
  its shares as numbers. **Done** (`engine/enrich-fixes`).
- **Results returned:** `try_models` and `finalize_models` return `run_models`' results, and `run_models` returns them
  without writing them. **Done** (`engine/enrich-fixes`).
- **No negative values:** an opt-in floor (`modeling.instructions.min_value`), with the count clipped reported; and a
  model whose holdout median ratio is outside a sane range left out of the ensemble (`ensemble.exclude_implausible`).
- **`all_model_groups/universe.parquet`:** one `model_group` column, not `_x` and `_y`.
- **Outliers machine-readable** (C-list B8) and **headless `try_variables`** (C1), for slice 3.

**Settled (2026-10-29):** small groups are left unvalued; one variable list for every group in slice 1 (per-group lists
in slice 3). **Revised 2026-10-31:** no Choose for me: every group starts with LightGBM, log MRA and Multi-MRA, each
changeable; variable lists serve any groups.

## 3.10 Building model values (steps 5 and 6)
*Superseded by §3.0 F9 where they differ (the variables, models, small groups and the steps); kept for Re-tune, speed
tiers and total value only.*

**Variables.** At the start of step 5, the user picks a path. They can switch later.
- **Plow forward** (default). OpenAVMKit has no built-in default variable list, so Oakbox ships one, using whichever of
  these fields are mapped or enriched:
  - **The "big five":** building size (finished area), land size, building age (effective age if available, otherwise
    age), building quality, building condition.
  - **Location:** latitude, longitude, and neighbourhood characteristics. These are the neighbourhood or other location
    fields, plus their spatial-lag and area-statistic features from step 6.

  Missing ones are skipped with a note. ML models (LightGBM, layered comps…) get this list plus any other well-covered
  fields.
- **Test variables first.** Oakbox runs variable analysis per model group on the candidate list and shows a review:
  - One row per variable with a plain verdict: *Drives value*, *Weak*, *Redundant with ___* or *Counter-intuitive*.
    Today `try_variables` only runs correlation and R²; the last two verdicts need VIF and coefficient-sign tests
    (upstream A5).
  - A **Details** expander shows the statistics, worded from the existing `variables.md`.
  - An include/exclude toggle per variable. Per the OpenAVMKit tutorial, the pruned list is applied to **linear** models
    only; ML models keep the broad list.

**Models.**
- **Picker.** Pick model(s), or **Choose for me**: LightGBM.
- **Small model groups.** Under 15 sales, "Choose for me" falls back to a simpler model (log-price linear regression or
  local-area) or suggests merging model groups.
- **Ensemble.** With several models, it's an explicit list that never includes the office's own value fields.
- **Speed tier.** **Quick** or **Thorough** (OpenAVMKit's default, 5-fold nested cross-validation), pre-selected by
  machine tier.
  - M0 found that 1-fold is *slower* than 5-fold at 150k+ parcels, so Quick must not be built on `cv_folds`. Quick will
    use fewer tuning trials and reuse saved tuning; to be measured in M1.
  - Parallel fold workers are capped by memory (`cv_max_workers`).

**Try, review, finalize.**
1. **Try** runs the chosen models and shows ratio statistics side by side. It's repeatable and cheap to re-run.
2. **Review outliers.** Model outliers appear in Sales review (§3.6) with likely causes.
3. **Finalize** commits the values and writes the model-value ratio study.
- **Re-tune.** Oakbox reuses saved tuning by default. A **Re-tune** toggle discards it, and is suggested after big data
  or model group changes. Cancelling never deletes tuning journals, so a cancelled tune can resume.

**Total value only.** Oakbox runs main models only (`run_vacant=False` on try and finalize). There is no vacant-stage
run, and no land values are shown, reported or exported. A separate land-value tool is planned.
