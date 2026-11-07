# Engine: OpenAVMKit changes

## 7. Engine: OpenAVMKit changes

**Where the work lives (updated 2026-11-07).** OpenAVMKit's own `master`. OAK box's engine changes went upstream in
six PRs, #409 to #414 (merged 2026-11-03), and OAK box pins `master` by commit (`pyproject.toml`, `[tool.uv.sources]`:
`openavmkit @ git+https://github.com/larsiusprime/openavmkit@<commit>`, now `7617e9d`, #429's merge (the tuning trial log; Skip this model; CatBoost takes a fold's share of the cores, its depth is searched up to 8, and its `categories` setting one-hot encodes on Windows by default, where CatBoost's own encoding costs ~20 ms a round; SHAP no longer fails on a category listed twice). Before it `fa4dc85`, #428's merge (census `total_population`
is a land field, so a vacant parcel keeps its block group's population; before it #427, LightGBM tuning
evaluates one trial at a time: two at once crashed it; #426, five functions OAK box calls made public; #425,
CSV text encodings worked out, OpenAVMKit's own text files UTF-8; #424, each sales cluster reads one column; #423,
sales clustering on NumPy and the area-weighted middle; #422, census and elevation; #419, cloud SDKs and NGBoost as
extras OAK box doesn't install)). There are no submodules and no runtime patches.

**Before that**, the work was on the branch `openavmkit-oakbox` in the Oakbox repo (OpenAVMKit's history from `master`
at `f35b089`, after v0.7.0), latterly `engine/enrich-fixes`, with topic branches merged into it. The branch names
below
(`engine/…`) say where each change was first made; all of them are now in OpenAVMKit's `master`.

**Next:** pin OpenAVMKit's next tagged release once it's cut.

### A. Needed for M1 ("Check my values")
1. **Headless stage API:** `run_stage(project_dir, stage, on_progress, cancel)`. No `os.chdir`, no IPython (including
   in
   `try_variables`). The environment is passed in. `ipython`, `pytest` and `pipreqs` leave the runtime dependencies.
2. **Structured progress events** replace `print`; warnings go through the same channel.
3. **Value-field studies that persist.** Ratio, vertical and horizontal studies on any named field, for all model
   groups
   plus overall, with breakdowns, written to disk, with no model required. Remove the hard-coded `assr_market_value`.
4. **Report statistics** (parity with openratiostudy, §4.2).
   - Print PRD, PRB and VEI in the report; add MKI.
   - Standards profiles with pass/fail.
   - An exact ratio-study date window.
   - Honour the bootstrap `iterations` argument (it's ignored today, and fixed at 10,000).
   - Fix the trimmed table showing the untrimmed median.
   - **VEI definition mismatch with openratiostudy.** OpenAVMKit's market-value proxy is `0.5 × sale + value ÷ median
     ratio`; openratiostudy's spec uses `0.5 × sale + 0.5 × (value ÷ median ratio)`. OpenAVMKit also needs 20 sales
     for
     VEI, where openratiostudy needs 10 (2 strata for 10–50). Agree on one definition and test both against the IAAO
     exposure-draft fixture.
5. **Typst report rendering** replaces wkhtmltopdf.
6. **Scrutiny outputs for review:**
   - write every flagged or dropped sale, with its reason, to a machine-readable file;
   - a **keep-list** that exempts named sales from scrutiny drops;
   - drop behaviour as a setting, not a function argument.

   Flagged sales still never reach modeling.
7. **Settings schema and validation** with field-level, plain-language errors.
8. **Settings-hashed checkpoints,** or at least a documented stage-to-settings map.
9. **Provenance flags** for default fills, and for the step 1 rule that turns blank finished area into 0. Also a
   setting
   to **opt out** of that rule, with vacancy taken from an explicit field instead.
10. **Tagged releases.** The version already comes from tags, but Oakbox must pin tagged commits.
11. **Safe `dupes` default** for geometry files: de-duplicate on `key`, or raise an error. Never use an arbitrary
    column.
12. **Performance hotspots from M0:**
    - the horizontal-equity study (473 s at 500k)
    - equity clusters plus scrutiny (about 220 s at 500k)
    - `finalize_models` when `cv_folds=1` (1,395 s at 500k)
13. **Leaner runtime dependencies.** Drop IPython from module-level imports. Make CatBoost and XGBoost optional
    extras;
    XGBoost's Linux wheel also pulls in NCCL (469 MB). Together these cut the Windows download from 544 MB to roughly
    350 MB, and the Linux download by more. **Done:** IPython (#417), Polars (#418), the cloud SDKs and NGBoost
    (#419),
    XGBoost and CatBoost (#420) are extras or gone; OAK box downloads XGBoost and CatBoost when asked (§6, Optional
    engines).
14. **Stage receipts.** Each stage reports structured counts through the progress channel (A2): rows in and out per
    file
    and per merge, rows collapsed by `dupes`, and sales removed with the reason (office code, outside window, scrutiny
    rule, override). Today these are only printed, if at all. Oakbox's receipts and the sales funnel depend on it.

### B. Needed for M2 (enrichment, model groups, sales)
1. **Enrichment plumbing:** progress per enrichment, a cost-estimate helper, and running an enrichment on a subset of
   parcels.
2. **Per-enrichment cache signatures.** Today the Overture signature covers the whole `enrich` block, and the
   estimation
   cache has no settings signature.
3. **"Overlaps" / area-weighted** spatial-join rule.
4. **Census:** configurable variables and geography; key via parameter; multi-county FIPS.
5. *(Dropped: invalid sales must never enter the pipeline. Oakbox handles office-code keeps by rewriting `valid_sale`
   at
   load.)*
6. **Explain model group assignment:** which model group and which rule matched a parcel.
7. **Data health checks** as a library function returning structured problems.
8. **Machine-readable model outliers** for the sales register.
9. **Vectorise the Overture parcel × building intersection.**
10. **GIS and Excel loaders** in OpenAVMKit itself. GeoPackage and shapefile: **done** on topic branch
    `engine/gis-loaders` (also case-insensitive extensions and a GeoPackage `layer` option), merged into
    `openavmkit-oakbox`. Still to do: GeoJSON, zipped shapefile, FileGDB, Excel, and a fixed-width loader for PACS
    exports.
11. **Data dictionary: which fields OpenAVMKit computes.** Each entry in `resources/settings/data_dictionary.json`
    gets
    `"source"`:
    - `"input"`: only ever comes from the user's data (e.g. `sale_price`, `bldg_area_finished_sqft`);
    - `"derived"`: always computed by OpenAVMKit, so loading a column into it is overwritten (e.g.
      `model_market_value`,
      `geom_vertices`, `dist_to_cbd`);
    - `"either"`: computed when missing, kept when given (e.g. `land_area_sqft` from GIS, `bldg_age_years` from year
      built).

    **Done** on `engine/dictionary-source` and `engine/dictionary-reserved`, merged into `openavmkit-oakbox`: 63
    input,
    42 derived, 15 either, 43 `reserved` (names kept for values OpenAVMKit means to compute but nothing writes yet:
    model outputs, assessor and "true" ratios, OSM street/corner/waterfront fields, vacancy warnings, some geometry
    metrics). Reviewed by the maintainer. Each value was checked against the code that writes the field; the
    classification is open for the maintainer's review. Entries missing a name or type (14 today) are filled in at the
    same time. A test asserts every entry has a valid `source`. Topic branch `engine/dictionary-source`. OAK box's
    field
    list (F3c) offers `input` and `either` fields.
12. **CSV yes/no columns.** **Done** on `engine/csv-bool`, merged: `data.load` passed `bool` to `pd.read_csv`, which
    fails on "Y"/"N"; such columns are now read as text and converted after loading, as dates already were. Also, a
    blank value became True whatever `na_handling` said ("<NA>" and "" weren't treated as missing). Still as before:
    any
    unrecognised text counts as Yes.
13. **The sale ID in the data dictionary.** `key_sale` is required by the sales merge but has no dictionary entry. Add
    it (`"source": "input"`, type string). **Done** on `engine/dictionary-key-sale`, merged into `openavmkit-oakbox`.
15. **Polar coordinates from `locality.center`.** The centre is in degrees, but `_enrich_polar_coordinates` placed it
    in
    the parcel file's own coordinates, so with a projected file (State Plane, UTM) every `polar_radius` was wrong
    (about
    600 km off for Guilford in NC State Plane feet). **Done** on `engine/polar-center` with a test, merged into
    `openavmkit-oakbox`; without a centre nothing changes.
14. **An ID from row numbers** (optional): a `calc` operation giving each row its number, so a single parcel file with
    no ID column can still be loaded. Topic branch `engine/calc-row-number`, only if F3d needs it in use.
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
7. **Speed, decided 2026-11-06** (from the performance runs, §5), in
   [larsiusprime/openavmkit#423](https://github.com/larsiusprime/openavmkit/pull/423):
   - **Sales scrutiny's clustering on NumPy, with the same results:** `_crunch` takes one `np.percentile` call and
     `np.searchsorted` instead of nine pandas `quantile` calls and up to three `pd.cut` per cluster, reproducing
     pandas exactly (types included). At 50,000 parcels: `make_clusters` 13.9 s → 3.6 s, the whole sales scrutiny 25.6
     s → 15.6 s, every output identical. Equivalence tests keep the old version verbatim as the reference.
   - **The parcels' middle without the dissolve** (decided 2026-11-06: no option, the dissolve removed): without
     `locality.center`, the middle polar coordinates are measured from is the area-weighted mean of the distinct
     parcels' centroids, about 50 ms instead of about 5 s at 50,000 parcels. It's the same point as the dissolved
     shape's centroid where parcels don't overlap, and stacked duplicates count once; where shapes partly overlap it
     can move slightly (the default middle stands in for downtown and is a guess anyway). Merged (#423) and pinned:
     the Coordinates page's pin is worked out with the engine's own `area_weighted_center`, so it stays the point the
     engine measures from. Nothing in a project's settings changes, so no step goes out of date: a project keeps the
     polar values it has until Bring in data runs again (they differ only where shapes partly overlap).
   - **`make_clusters` reads only the column each cluster is split on** (decided and merged 2026-11-06,
     [larsiusprime/openavmkit#424](https://github.com/larsiusprime/openavmkit/pull/424)): 3.4 s → 1.6 s at 50,000
     parcels, outputs identical. Joining the labels once per field too was measured (0.3 s more) and left out.

### D. Documentation fixes found during review
- **Spatial-join key name.** The real key is `geometry`. `advanced_settings` §4.2 calls it `spatial_joins`.
- **Unsupported file formats.** `advanced_settings` §4.5 and `tutorial` L102 claim `.shp`/GeoPackage loading, which
  the
  loader doesn't support.
- **Distances.** The per-feature `enabled` default is documented as true; it is false. `config.md` shows an obsolete
  distances schema and enrich keys without the `data.` prefix.
- **Wrong stage for spatial lag.** `advanced_settings` §4.8 lists it as a step 1 enrichment and omits the required
  per-model-group `model_groups` entries.
- **Run order.** `ref_tables` is documented as running before estimation; it runs after.
- **Checkpoints.** They're documented as "self-invalidating" (`advanced_settings` L1502, `tutorial` L575); they
  aren't.
- **Re-run point after a model group change.** The tutorial says to re-run from notebook 3; it must start at tagging.
- **Recipe.** `recipe.md` lists `process_sales` in assemble.
- **infer's `fill` key** is described backwards (the code copies *into* the target).
- **`time_adjustment` docstring** says it feeds ratio studies; it hasn't since 0.7.0.
- **Missing model.** `lcomp` is absent from `models_reference.md`.
- **Naming.** Consider renaming one of the three different "fill" concepts.
