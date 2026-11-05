# Performance runs

How long OAK box takes, and how much memory it needs, from loading the files to the report, on machines like the
ones county assessors' offices have.

## What's here

- `make_county.py`: a synthetic county at any size: a parcel file with shapes (`parcels.parquet`) and a sales file
  (`sales.csv`), with neighbourhoods, prices that follow size, age, quality, condition and place, sales that aren't
  arm's-length, vacant land and the blanks real files have.
- `drive.py`: starts OAK box without a window and takes a project through every step over its API, as a user would:
  the files and their fields, Bring in data, Model groups (the suggested ones), Check sales, Prepare, Check my values,
  the variable tests, the models (lists of the recommended variables), Finalize and the report. It records each
  step's time. With `--ui`, it then times the main pages in a slowed-down headless Chromium (`ui.js`).
- `profiles.py`: the machine profiles, as Linux cgroup limits on OAK box and everything it starts: cores, their
  speed, memory, and disk reads. Each step's CPU time, peak memory, disk reads and writes and any out-of-memory kill
  are measured there.
- `matrix.py`: every profile on every size, one after another, results as JSON.

## The profiles

| Profile | Stands for | Cores | Speed | Memory for OAK box | Disk reads | Pages slowed |
|---|---|---|---|---|---|---|
| `vdi` | a virtual desktop session on a shared county host | 2 | 60% | 2 GB | 50 MB/s | 6× |
| `floor` | a 2018–19 budget machine (Pentium Gold, old i3) | 2 | 75% | 2 GB | 100 MB/s | 6× |
| `potato` | the main target: a 2018–20 OptiPlex (i3-8100 or i5-8500), 8 GB | 4 | full | 2.5 GB | — | 4× |
| `current` | a 2025–26 purchase (i5 or Ultra 5), 16 GB | 4 | full | 8 GB | — | 1× |

"Memory for OAK box" is what's left of the machine's memory after Windows, a browser, Outlook, Teams, the CAMA
client and antivirus. Speeds are relative to the machine the run is on (the first runs: a 2.1 GHz cloud Xeon).

What the profiles can't stand for: Windows itself (WebView2, antivirus scanning every file written, paths), an old
chip's caches and missing instructions (a quota only slows it down), a hard disk's seek time, writes held back by a
slow disk (cgroup v1 only slows reads), paging to disk when memory runs out (here it's killed instead), and the
downloads (OpenStreetMap, footprints, census, elevation: the runs are offline).

## Running

On Linux as root (for the profiles), from the repository:

```bash
uv run python perf/matrix.py /tmp/perf
```

One run, any OS, no limits (the numbers a cgroup gives are left out):

```bash
uv run python perf/make_county.py /tmp/perf/data/20000 20000
```

```bash
uv run python perf/drive.py /tmp/perf/data/20000 --out /tmp/perf/results/mine-20000.json --ui
```

On real hardware, run the second pair: the step times and page times are the comparison with these runs.
