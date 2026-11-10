# Step 4, Evaluate: Check my values

As built (F8), then the ratio study and its standards profiles (§4.2).

## F8. Step 4, Evaluate: Check my values (its own tab, **4. Evaluate**; built, but for the parts under "Not built yet")
It opens once Check sales has Looks right. The assessor's own values, against what parcels sold for, checked the way a
state reviewer would: nothing is modeled. openratiostudy.com (`larsiusprime/openratiostudy`) is the reference for the
statistics and views.
- **Only with existing values** (revised 2026-10-31): the tab is greyed, its tip saying "No existing values to check:
  add them on Data › Existing values", until a value set has a market value. Model values doesn't wait for it.
- **What to check** (first): **Check them** or **Skip this step** (Next becomes **Go to Model values ›**; the step's
  parts are greyed); which value sets (MultiPick, every one by default) and which model groups (every one by default;
  the studies, overall included, are of those groups only). Only market values are checked: land and improvement values
  aren't sold on their own.
- **Several sets:** the results show one set at a time, a switch at the top of each part; the choice stays as you go
  from part to part.
- **One task at a time:** **What to check** › **Which sales** › **Whose standards** › **The standards** › **Which
  groups** › **Check my values** (the run) › **Summary** › **Across prices** › **On the map** ›
  **Neighbourhood price levels** › **Similar parcels** › **Extreme ratios**, whose Next is **Looks right › Model
  values** (it opens the Model values tab, step 6, or Variables, step 5, while that waits; once pressed, **Model values
  ›**).
- **Which sales:** the sales Check sales kept for modeling, in the window, valid for a ratio study (the parcel looks as
  it did when sold). The window is two date pickers. Proposed: from the year before the valuation date (the IAAO's
  window), reaching back a year at a time (up to five) until it holds 30 sales; when the IAAO's year has none it says so
  ("the latest sale is 2024-11-09"); **Back to the proposed window**. The price: **as sold** (default, the formal ratio
  study) or brought to the valuation date with Check sales' time adjustment. A small count: for modeling, − outside the
  window, − the parcel changed since, = sales the values answer to; and per model group.
- **Standards, in three parts** (revised 2026-10-31). **Whose standards:** **The IAAO's** or **Custom** (a state's, an
  office's), Custom starting from the IAAO's figures or empty. **The standards:** a row per standard, its name and every
  target changeable: level (median ratio from–to; missed only when the median's whole 90% range is outside, 11.1),
  uniformity (COD from–to: above missed, below suspect, possibly sales chasing, 11.2.5), PRB good within ± and
  unacceptable outside ± (neither between), VEI within ± % (missed only when significantly outside, Appendix E steps 5
  to 7), judged with at least N sales; each heading's tip says what it means; **Remove**, **Add a standard**, **Back to
  the IAAO's**; the PRD and MKI reported, not judged (Table 4); trimming below. The IAAO's are one standard per property
  category (Table 7): residential 5 to 15, homogeneous (condos) 4 to 10, rural or manufactured 10 to 20, apartments 7 to
  20, commercial 10 to 25, vacant land 10 to 20, agricultural 10 to 25, each level 0.90 to 1.10, PRB ±0.05 / ±0.10, VEI
  ±10%, 5 sales. **Which groups:** a model-group picker per standard (only groups modeled and checked), proposed from
  the groups' names until one is chosen (then every standard's are as shown); a group in one standard at most; a group
  in none is shown, not judged, and named. OpenAVMKit judges each group by its standard's own targets
  (`standards.by_class`, `engine/enrich-fixes`), and Model values pills its figures the same way. Outlying ratios are
  trimmed (on by default) as Appendix C sets out: beyond 1.5 × IQR with the Standard's quartile positions, at most a
  tenth of a group, the furthest first. The statistics without them are judged; every sale's are shown beside them,
  never compared (C.6).
- **The run** (`python -m oakbox.ratio <id>`): OpenAVMKit's `run_value_field_studies` on `out/2-clean-sup.pickle`, with
  the window, the price, trimming, the IAAO's order-statistic interval for the median (`median_ci="iaao"`, as
  openratiostudy) and the targets; a few seconds. Writes `out/oakbox/ratio/` (the receipt, OpenAVMKit's study files,
  every sale studied with its ratio).
- **Pills never move a figure:** in By model group, each figure's pill sits at the cell's left edge and the figure at
  its right. **Across prices** draws the VEI's groups as a chart too (median and 90% range per group).
- **Summary:** a paragraph a board member can read ("Assessed market values are about 67% of what parcels sold for,
  2024-01-01 to 2025-12-31. That's outside the 90% to 110% the standard asks for in every model group judged. Not
  uniform enough: Single-family (COD 19.2). No significant vertical inequity."), then a scorecard: a row per model
  group, a column per question (**Level**: the median ratio; **Uniformity**: the COD; **Cheaper vs dearer**: the VEI, or
  the PRB with too few sales for it), each cell the pill every judged figure wears (✓ met, ~ near, ✗ missed, as in How
  they did; the PRB between good and unacceptable is ~), the figure and a word ("too low", "too varied", "no significant
  difference") in the same place on every row, so groups compare down a column; what each measures is in the header's
  tip. Groups with too few sales or none say so across the row. Nominal prices among the trimmed sales are pointed out
  (Check sales now sets them aside first).
- **Every figure, group by group** (folded under Summary's scorecard; was its own step, By model group, until
  2026-11-10; Summary takes the map over, each group's row with Show on map): sales, trimmed, median ratio, its 90% range, COD, VEI (with its reading: compliant, not
  significant, regressive, progressive, too few sales), PRB, PRD and MKI; the judged ones with ✓ / ✗, every sale's
  figure beneath each ("all"); all groups as the total. Headers explain themselves on hover.
- **Across prices:** per model group, each sale's ratio against its price (log scale; trimmed in grey), the median of
  each fifth of sales by price, the standard's level band; the fifths as a table; the VEI's groups by value with their
  medians and 90% ranges.
- **On the map** and **Neighbourhood price levels** (openratiostudy's further analysis): each sale where its parcel is,
  coloured by its ratio in openratiostudy's colours (blue under 1, white at 1, red over; trimmed grey), per model group
  or all; and the median ratio by the price level of each sale's neighbourhood (the neighbourhood's median market value
  proxy), sales grouped as openratiostudy groups them (2, 4 or 10 groups by the number of sales, as the VEI; a
  neighbourhood never split), cheapest to dearest, drawn as the VEI's chart (each group's median with its 90% range)
  beside the same chart by each sale's own price level, then the table: flat by neighbourhood while the VEI by sale
  isn't points to invalid sales, not real inequity. Neighbourhoods by a location field (Check sales' by default;
  changing it checks again); without one it points to Data › Location. Engine: `region` on `run_value_field_studies`.
- **Similar parcels:** horizontal equity from the equity clusters: parcels, groups of similar parcels, the median spread
  (CHD); shown, not judged (the IAAO sets no target). Takes the map over (2026-11-10): every parcel in the colour of its
  group of similar parcels' CHD (`ratio/similar`: 100 x mean absolute difference from the group's median over the
  median; under 20 green, under 40 amber, else red; a group of one grey), Show on map on each model group's row and
  Every group on the map. Summary and On the map take it over the same way, by model group.
- **Extreme ratios:** the trimmed sales, furthest first, nominal prices said; **Exclude in Check sales** marks the sale
  excluded (it applies when Check sales runs again).
- **Out of date when** Check sales runs again or a call changes.
- **Engine (built, opt-in; `engine/enrich-fixes`):** `run_value_field_studies` gained `sale_field`, `trim_outliers` (the
  trimmed study beside every sale's, the trimmed sales listed, a per-sale table; quartiles as Appendix C.4,
  `trim_share`), `median_ci="iaao"`, `standards` / `classes` with `IAAO_STANDARDS` (the draft's targets; a `verdict` per
  group, both ways), VEI percentile groups and reading (Appendix E), the MKI (`calc_mki`), `region` (neighbourhood price
  levels). Fixed: the VEI's market value proxy is the average of price and median-adjusted value. (The draft prints it
  as 0.50·SP + AV/median, but says equal weight, as its PRB definition does; its worked example gives the same groups
  either way.) Checked against the draft: its demonstration report (Table 6: median 0.868, 90% range 0.787 to 0.984, COD
  24.65, PRD 0.993, PRB 0.1871 with 95% range 0.0665 to 0.3078, VEI 48.53%, significance 17.57%) and its trimming
  example (Tables 9 and 10) are reproduced exactly, as engine tests.
- **openratiostudy.com, settled:** OAK box and OpenAVMKit follow the IAAO: the PRB is the Standard's (percentage
  deviation from the median regressed on log2 of the value proxy), not a regression of the ratio on ln(price); VEI
  significance compares the groups with the highest and lowest medians (Appendix E step 7), not always the last and
  first; trimmed and untrimmed are both shown. openratiostudy itself is unchanged for now.
- **On the sample** (2024 to 2025, 181 sales): values are about 67% of prices; single-family COD 19.2, PRB +0.056, VEI
  +24.3% inconclusive; a $10 deed (2901 St Regis Rd) that Check sales kept is trimmed and pointed out.

**Not built yet:** breakdowns by neighbourhood; a printed report of this check (Report, step 7, reports the model
values); land values against vacant land sales. (The roll's values beside the model values are on Model values, step 6.)

## 4.2 Ratio study report and standards profiles
**What exists upstream today:**
- Field-agnostic study functions: `run_ratio_study`, `run_vertical_equity_study`, `run_horizontal_equity_study`, already
  used on assessor values without modeling in the `assessment_quality` notebook. They display results but write nothing,
  take one model group per call, and have no breakdowns.
- A ratio-study **report** that reads only a finalized model, with the checked value hard-coded to `assr_market_value`.
  It shows count, median ratio, COD with a bootstrap CI, and trimmed COD.
- **Bootstrap confidence intervals.**
- PRD computed with a CI, but not printed.
- **PRB** and **VEI** in the vertical-equity study.
- Breakdowns by any field (`analysis.ratio_study.breakdowns`).
- A sales-chasing check (assessor vs model).
- openratiostudy.com exports. These are model-only today: key, sale key, prediction, sale price, time-adjusted price,
  lat/lon, locations.
- Since 0.7.0, the formal ratio study scores **raw** sale price, not time-adjusted.

**Oakbox needs (mostly upstream A3–A4):**
- **One report path for any value field,** with or without a model. Per model group, overall, by breakdown, written to
  disk.
- **IAAO statistics in the report:** median ratio, COD, PRD, PRB, with CIs and sale counts. Also VEI (exists) and MKI
  (new), so the report survives the IAAO draft revision.
- **Pass/fail badges against a standards profile.** A small file with targets per statistic and property class,
  trimming, minimum sample size and windows. It ships with an IAAO default; state profiles come later; users copy and
  edit in a form.
  - The minimum sample size must match OpenAVMKit's pooling of cells with 15 or fewer sales.
- **An exact ratio-study window** (date bounds, post-valuation sales excluded). Today the cut is by calendar year with
  no upper bound.
- **Charts:** ratio vs sale price, ratio distribution, and a map of ratios by location.
- **A first page a board member can read:** "Residential values meet IAAO uniformity standards (COD 11.8, target ≤15)
  but show mild regressivity (PRD 1.04, target ≤1.03)."
- **Appendices:** data corrections, sale overrides, filled values, excluded variables, skipped enrichments, methodology.
- **openratiostudy export** that also carries the checked value field and model group.

**openratiostudy.com is the reference.** Its source is `larsiusprime/openratiostudy` (a static single-page app). It
defines what the assessor sees, and Oakbox matches it:
- **Statistics** (per its `spec.md`):
  - median ratio with a **90%** bootstrap CI (10,000 resamples, seeded)
  - COD
  - PRD (mean ratio ÷ sale-weighted mean)
  - PRB (OLS of ratio on ln(sale price), HC3 robust standard errors, slope and p-value)
  - **VEI** and **VEI significance**, from market-value-proxy strata (2/4/10 strata by sample size, none under 10), with
    per-stratum median and CI
- **Views:**
  - results table with exclusion notes
  - VEI strata box plot
  - ratio map (lat/lon)
  - **neighbourhood price-level stats**: deciles of region price level vs median ratio, which separates real vertical
    inequity from invalid-sale artifacts
  - a **black-and-white print mode**, which Oakbox adopts for offices that print in greyscale
- **Parity tests.** Its test suite uses **Table 1 of the IAAO Ratio Studies Exposure Draft** (Sept 2025; 54
  observations) as a fixture. OpenAVMKit's study functions must reproduce openratiostudy's results on the same fixtures,
  within tolerance. This runs in Oakbox's CI. Any definition mismatch is fixed upstream (A4), for example VEI strata
  rules or the CI level. OpenAVMKit's report uses 95% CIs; the standards profile sets the level, defaulting to 90% to
  match.
