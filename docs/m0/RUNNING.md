# Running the M0 spike locally

> **A record of M0, not maintained.** Much of this no longer works: the bundle no longer ships `spikes/`, its
> `smoke.cmd` now runs `oakbox/smoke.py` (Petersburg's data, online), and artifacts are kept a day, not seven. To run
> OAK box, see [docs/RUNNING.md](../RUNNING.md).

M0 has **no user interface yet.** It's the headless engine, the benchmark scripts and the portable bundles. The UI starts in M1.

## Option A: portable bundle (no Python install needed)
1. Open the latest green run of the **bundles** workflow: GitHub → Actions → bundles. Download `bundle-windows` or `bundle-linux` from **Artifacts**. Artifacts expire after 7 days; re-run the workflow to get fresh ones.
2. Unzip it.
   - **Windows:** extract `oakbox-win64.zip` to a short path such as `C:\oak`. Long paths can hit Windows' 260-character limit.
   - **Linux:** `tar -xzf oakbox-linux-x86_64.tar.gz`
3. Run the smoke test: a 2k-parcel synthetic county, every step, offline. It takes about a minute.
   - **Windows:** double-click `smoke.cmd`, or run it from a terminal.
   - **Linux:** `./oakbox-linux-x86_64/smoke.sh`
4. Results appear in `work/bench.jsonl` (one line per step, with time and peak memory). Logs are in `work/*.log`.

### Bigger synthetic counties and Petersburg with the bundle
On Linux, use `python/bin/python3` in place of `python\python.exe`, and `/` for the path separators.

```
python\python.exe app\spikes\m0\make_synthetic.py 150000 work
python\python.exe app\spikes\m0\bench.py work us-zz-synth150k thorough

python\python.exe app\spikes\m0\fetch_sample.py work us/va/petersburgcity us-va-petersburgcity
python\python.exe app\spikes\m0\bench.py work us-va-petersburgcity thorough
```

## Option B: from source (developers)
Requires [uv](https://docs.astral.sh/uv/) and git. uv installs Python 3.11 itself.

```
git clone https://github.com/larsiusprime/oakbox && cd oakbox
git checkout claude/openavmkit-desktop-wrapper-639lvu
uv sync
uv run python spikes/m0/make_synthetic.py 50000 bench-data
uv run python spikes/m0/bench.py bench-data us-zz-synth50k thorough
```

To rebuild the bundles yourself, run `packaging/build_bundle.sh windows` or `packaging/build_bundle.sh linux`. This works on Linux or WSL, and output goes to `dist/`.

## Notes
- **Memory:** 500k parcels peaked at about 9 GB in the model step. On an 8 GB machine, stay at 150k or below for now.
- **Petersburg needs the internet** for its enrichments: Census, OpenStreetMap, Overture and USGS. If a service is unreachable, that enrichment is retried and then skipped, which can be slow. Building footprints (Overture) may stop the run entirely (see the M0 report).
- **Re-running the model step reuses saved tuning.** Delete `data/<slug>/out/models` for a clean re-run.
