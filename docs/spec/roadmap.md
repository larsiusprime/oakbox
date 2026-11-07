# Milestones, scope and open items

## 8. Milestones

**Where it stands (2026-11-06).** The plan below predates the feature-by-feature redesign (D41, §3.0), and M1–M3 were
built in a different order from it: the guided build became the Data tab and its wizard (F3), and steps 1–7 run in the
app (F4–F10), with the Windows installer, the Linux bundle and the optional engines. §3.0 says what's built and what
isn't; the milestones are kept as they were planned.

- **Built since (2026-11-03 to 11-06): performance** (§5). A first-run computer check and Settings with every
  performance setting; tiers (Light, Standard, Strong) choosing the folds at once and the maps (on click, dots, street
  map); a large county said before the long steps. Engine: sales clustering about 4× faster, the parcels' middle
  without the dissolve, LightGBM tuning one trial at a time (a crash on Light computers), census population a land
  field. The Model groups map draws parcel files of small squares, and its shapes are binary arrays. Fill blanks by
  each field's kind, with what each model group gets.
- **Left of M3:** slice 3 of the models (outliers back into Check sales, per-group variables and models, why this
  value), CAMA export, the model summary report. Per area statistics (§3.12.3) is specified and mocked up, not built.
- **Speed:** Models and Finalize are 75–80% of a run (12 minutes at 50,000 parcels on the slowest profile tried).
- **Waiting on the maintainer:** real extracts (Travis CAD first), the usability test with three assessors, and timing
  on a real low-end PC.

- **M0 — Spike.** Prove the packaging and the hardware assumptions. **Done**, including a real-data run on Petersburg.
  See [`docs/m0/REPORT.md`](../m0/REPORT.md).
  - A portable build runs Petersburg end to end on a clean Windows 10 VM with 8 GB RAM. The only online step is the
    prompted sample download.
  - Benchmark under 0.7 defaults (§5) on synthetic cities of 50k, 150k and 500k parcels.
  - Rewrite §5 and the enrichment cost coefficients with measured numbers.
- **M1 — "Check my values."** Built as four slices, each one runnable:
  - **CI smoke test, after F3** (replacing the sample walk-through). On each platform, using only the bundled Python:
    1. **Engine:** download `us-va-petersburgcity` (download-only) and run OpenAVMKit's own stages (assemble, clean,
       value studies) on it with a checked-in `settings.json`, outside the app. This proves a bundle can run the engine.
    2. **App:** start the app service, load the UI (its script must be served as JavaScript), create a project and add
       one of the downloaded files to it.

    When the app's own flow can run steps again, the smoke test goes back to driving it.
  - **M1a, walking skeleton (done).** Real app shell: home screen, sample county download (since removed, D19), steps
    1–4 with live progress and Stop, and the results table with IAAO default targets. Engine changes: A1, A2, A3, A11,
    A12 (horizontal equity), plus a CatBoost Windows fix found by a user run. Bundles ship the app, and CI smoke-tests
    it end to end on Windows and Linux.
  - **M1b, own data.** The guided build's frame (four-part stages, Looks right, Under the hood, staleness of decisions)
    and the first three setup stages: Basics, Your files and Stitch, with their quick checks. Fixed-width import with
    the PACS layout, tested on the Travis CAD export. Step 1's receipt (upstream A14 for its counts). The sample becomes
    a walkthrough of the stages built so far.
  - **M1c, trust the data.** Setup stages Columns and Sales basics; the sales funnel and the receipts for steps 2–4;
    Data health, Field profile, the "From a field" model group builder, the read-only sales register.
  - **M1d, hand it over.** PDF report, exports, help.

  Full M1 scope:
  - Windows installer and Linux `.tar.gz`, both smoke-tested in CI; home screen; sample county
  - The guided build: all five setup stages, receipts and the sales funnel, including sale ID, vacant-at-sale, date
    format, dupes, ID fixes, units and transforms
  - Steps 1–4; the model group builder in "From a field" mode only; enrichment limited to map layers and basic geometry,
    so M1 runs offline
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
  - Steps 5 and 6 (§3.0 F9; slices 1 and 2 built, slice 3 in part): slice 1 (variables, models, Try, how they did),
    slice 2 (small groups, Finalize, model values checked), slice 3 (outliers, testing variables, per-group choices, why
    this value); speed tiers once measured
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
- OpenFreeMap is the map tile service (built 2026-11-06, §3.11); hosting our own is for later.
- Reports are printable HTML (F10, settled 2026-11-01; this replaced Typst).
- The default variables are the big five plus location.
- The IAAO default profile is accepted, to be revised later.
- The frontend is React (§6.5).
- The openratiostudy.com reference is settled: read from its source repo (§4.2).

**Open:**
1. **M0 follow-ups:**
   - Is a Census API key actually needed? Petersburg's Census enrichment worked with none set. If the anonymous quota
     covers a county, the key becomes optional on the Enrichment screen.
   - Fail fast on unreachable services. Petersburg spent minutes retrying a blocked OpenStreetMap server; Oakbox needs a
     short timeout and a plain "skipped" card.
   - timing on a real low-end PC
   - memory on real extracts
   - why `cv_folds=1` is slow
   - the enrichment cost coefficients, which need an M2 run with enrichment on
2. **Real extracts.** The maintainer has several. They'll be shared, anonymised if needed, for guided-build and Data
   health testing. The first is a full Travis CAD PACS export (fixed-width text, 391 MB zipped).
3. **Land-value tool:** how, if at all, should Oakbox hand off to it later (shared project folder, export format)?
4. **Usability test:** after M1, with assessors the maintainer recruits.
5. **Project files across versions** (§6.7): when to turn it on. Before the first release whose users are told
   their projects carry over; until then, a project that no longer loads is hidden and made again.
