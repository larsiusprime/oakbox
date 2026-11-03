# M0 spike report

**Status:** done. The Windows and Linux bundles pass their CI smoke tests, the synthetic benchmarks are complete, and Petersburg ran end to end.
**Engine:** OpenAVMKit `f35b089` (after v0.7.0), from branch `openavmkit-oakbox`, unmodified.
**Raw data:** [`bench.jsonl`](bench.jsonl). Each row is one step, with wall-clock time, peak memory and per-sub-step timestamps.

## What was built
| Piece | Where | Result |
|---|---|---|
| Headless step runner | `spikes/m0/stage.py` | Runs the notebook pipeline without Jupyter: assemble → clean → check values → model, main models only (`run_vacant=False`). Prints a progress mark per sub-step |
| Synthetic county generator | `spikes/m0/make_synthetic.py` | Writes a complete locality (GeoParquet parcels, sales, `settings.json`) of N parcels |
| Benchmark driver | `spikes/m0/bench.py` | Runs each step as a subprocess and samples peak memory of the whole process tree, workers included |
| Portable bundles (Windows and Linux) | `packaging/build_bundle.sh` | Built on Linux from `uv.lock` and standalone CPython 3.11 |
| Sample fetcher | `spikes/m0/fetch_sample.py` | Download-only; never uses `cloud_sync`; skips non-data files |
| CI smoke tests | `.github/workflows/bundles.yml` | **Pass.** Clean `windows-latest` and `ubuntu-latest` runners, using only the bundled Python, run all four steps end to end |

## Benchmarks
- **Machine:** Linux, 4 cores, 15 GB RAM, SSD.
- **Settings:** OpenAVMKit 0.7 defaults with a single "All properties" model group and LightGBM.
- **Variables:** the "big five", latitude/longitude and neighbourhood, plus spatial-lag and area-stat features.
- **Sales:** 10% of parcels have a sale.

### Time and peak memory per step

| Parcels | 1. Bring in data | 3. Check sales | 4. Check my values | 5. Build model values: Thorough (5-fold) | 5. Build model values: "Quick" (1 fold) |
|---|---|---|---|---|---|
| 2k | 5 s / 0.7 GB | 8 s / 0.7 GB | 5 s / 0.7 GB | 21 s / 2.1 GB | — |
| 50k | 15 s / 0.9 GB | 40 s / 0.8 GB | 17 s / 1.1 GB | 97 s / 3.4 GB | 110 s / 1.6 GB |
| 150k | 29 s / 1.5 GB | 81 s / 1.1 GB | 69 s / 1.9 GB | 288 s / 5.4 GB | 658 s / 3.0 GB |
| 500k | 86 s / 3.3 GB | 229 s / 2.1 GB | **527 s** / 4.6 GB | 1,289 s / **9.2 GB** | 1,938 s / 7.1 GB |

**500k end to end (Thorough):** about 36 minutes on this machine. A low-end office PC will be slower. M0 couldn't measure by how much (see Not yet measured).

### Findings
1. **Fixed overhead per process: ~0.7 GB.** Importing OpenAVMKit costs about 0.7 GB, and each cross-validation fold worker (a separate process) costs about as much again. On 4 cores OpenAVMKit runs 2 fold workers (`cores − 2`). This is why the Thorough model step jumps from 1.6 GB to 3.4 GB even at 50k.
2. **"Quick" is not quicker.** Setting `cv_folds=1` gives up fold parallelism. At 150k and 500k it took *longer* than 5-fold. Almost all of the time went into `finalize_models → run_models` (1,395 s of 1,454 s at 500k), not into training LightGBM (17 s). The root cause is still open.
   - **Spec change:** the speed tier must not be built on `cv_folds`. Candidates are fewer tuning trials and reusing tuned parameters. Re-measure in M1.
3. **Horizontal equity is the 500k hotspot.** In step 4 it took 473 s of 527 s, and in step 3 the equity clusters plus scrutiny took about 220 s. These are upstream optimisation targets.
4. **Disk grows fast.** A 500k project produced **3.9 GB** of outputs from 27 MB of input (pickles, parquet "look" files, models). Multiplied across tax years, the 25 GB disk floor is tight. Oakbox should prune intermediate outputs, and the spec should count disk per project.
5. **Memory scales well below the RAM tiers.** The highest peak was 9.2 GB (500k, Thorough).
   - **Caveat:** synthetic parcels carry about 10 fields; real extracts carry 50–150. The data-proportional part of memory will grow by an unknown factor. Real extracts are needed before the tiers are final.
6. **Model accuracy on synthetic data means nothing.** COD was 22–25 here. The generator is for load testing only, not for judging model quality.

### Proposed §5 hardware tiers (provisional, synthetic data)
| Tier | Machine | Model step setting | Parcels |
|---|---|---|---|
| Floor | 4 cores, 8 GB | 1 fold worker (`cv_max_workers=1`) | up to ~150k comfortably. 500k "Quick" peaked at 7.1 GB, too close to 8 GB once Windows is counted |
| Recommended | 4+ cores, 16 GB | 2 workers | 500k (9.2 GB peak) |
| Large | 8+ cores, 32 GB | `cores − 2` workers | 500k+; also real data with many columns |

## Petersburg, VA (real data, as-shipped settings)
- **Data:** 14,460 parcels; 6,777 valid sales at load and 1,348 after cleaning (study window).
- **Settings:** Petersburg's own `settings.json`, with six model groups and ten models (assessor, MRA, multi-MRA, local area, CatBoost, XGBoost, LightGBM, lcomp, NGBoost, ensemble).
- **Engine changes for the run:** main models only (`run_vacant=False`) and the streets enrichment skipped, matching the spec.
- **Download:** fetched download-only (`spikes/m0/fetch_sample.py`, 36 MB). The fetcher skipped the PDFs and the `.py`/`.pyc` files in the container.

| Step | Time | Peak memory |
|---|---|---|
| 1. Bring in data (with online enrichment) | 391 s | **4.9 GB** |
| 3. Check sales | 31 s | 0.7 GB |
| 4. Check my values (6 model groups) | 9 s | 0.7 GB |
| 5. Build model values (Thorough, 10 models) | 1,421 s | 4.6 GB |
| **Total** | **~31 min** | |

**Enrichment results:**
- **Worked:**
  - Building footprints (Overture S3): 100% coverage
  - Elevation and slope (USGS 3DEP): 99%
  - Census: median income 92%, tract 100%. This worked **with no API key set**, so the key may only be needed above the Census API's anonymous quota. Worth confirming before the wizard insists on one.
  - Distance to downtown, from a local layer
- **Failed:** the four OpenStreetMap distance features (golf, water, parks, rivers). Overpass is blocked in this environment. Each was retried, then skipped without failing the step, but the retries cost minutes. This is the "Retry or Skip" case the spec designs for. Oakbox should time out quickly and say which feature was skipped.

**Real data confirms the column-count caveat.** Step 1 peaked at 4.9 GB for 14k parcels with 93 columns. The synthetic 500k-parcel county (about 10 columns) peaked at only 3.3 GB. Enrichment and wide real tables, not parcel count alone, drive memory. Final hardware tiers need more real extracts.

**Model quality on the study set (COD):** assessor 19.4; LightGBM 4.0; ensemble 9.7. LightGBM's 4.0 on the study set suggests overfitting. On the holdout set, LightGBM scored 26.0 and the ensemble 22.9, against the assessor's 28.3. These numbers are for the record; judging models isn't M0's job.

## Bundles
### Windows
- **Size:** 1.7 GB unpacked, 544 MB zipped. Expand-Archive took 75 s on the CI runner.
- **Every compiled file is a native Windows build** (`win_amd64` / `abi3`). No Linux binaries leaked in. Pure-Python source-only packages, such as `autograd-gamma`, are built into universal wheels during the build.
- **Biggest items:** CatBoost 353 MB, Polars 155 MB, XGBoost 138 MB, llvmlite 103 MB, SciPy 95 MB, pyarrow 84 MB.
  - CatBoost and XGBoost aren't needed by "Choose for me" (LightGBM).
  - The IPython / jedi / debugpy stack (~70 MB) comes in only because OpenAVMKit imports IPython at module level (upstream A1).
  - Trimming these brings the download to roughly 350 MB.
- **First launch is slow:** the first OpenAVMKit import on Windows took 16.6 s (cold start plus Defender scanning), and later imports about 4 s. The app should show a splash screen with progress.
- **CPU detection noise.** joblib detects CPU cores by calling `wmic`, which newer Windows 11 builds no longer ship. It prints a traceback, then falls back. The engine worker should set `LOKY_MAX_CPU_COUNT`.

### Linux
- **Size:** 2.5 GB unpacked, 974 MB as `.tar.gz`. 469 MB of that is NVIDIA NCCL, which XGBoost's Linux wheel pulls in; a CPU-only app never uses it.
- **Smoke test:** passes in an empty environment (`env -i`, no system Python), both locally and in CI.

## Upstream bugs found
1. **Silent parcel loss (serious).** If a geometry file has no `dupes` setting, `get_dupes` de-duplicates on the *first non-geometry column*. That column comes from `list(set(...))`, so its order changes between runs. It dropped 2,021 of 2,025 parcels in one run and 968 in another, with only a warning.
   - **Oakbox fix:** always write `dupes` explicitly.
   - **Upstream fix:** default to `key`, or raise an error.
2. **Synthetic generator geometry.** `generate_basic` gives every parcel a rectangle the size of the whole study area.
3. **Stale test settings.** `tests/data/nc-guilford/settings.json` uses the old model config layout (`instructions.run`, `models.default.dep_vars`). The current layout is `instructions.main.run` / `models.main.default.ind_vars`. A user copying that file would get no models configured; I hit the same thing ("Could not generate results for model: default").

## Blockers and not yet measured
- **A real low-end PC.** CI Windows runners have 16 GB and server-class CPUs. Timing on a real 8 GB office PC still needs a person with the machine.
- **Real extracts.** These are needed to calibrate memory against real column counts.
