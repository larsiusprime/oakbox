# How OAK box is built

What the code does today, for someone about to change it. SPEC.md says what OAK box should do and why;
AGENTS.md has the rules for writing code here. When this page and the code disagree, the code is right and this page
is fixed.

## The pieces

```
python -m oakbox (__main__.py)
 ├─ the app service: FastAPI on 127.0.0.1, a random free port, in a thread (app.py, routes/)
 │    answers the page's JSON calls and serves the built page (src/oakbox/web/)
 ├─ the window: pywebview (WebView2 on Windows, Qt on Linux) with native menus (menus.py, winmenu.py, qtmenu.py);
 │    no window possible, or --browser: the user's browser instead
 └─ a run: python -X utf8 -m oakbox.<step> <project id>, one process per run, started by the app service (steps.py)
      imports OpenAVMKit, runs its part of the notebooks, prints a JSON line per part, writes a receipt, exits
```

- **The page** is React 19 + TypeScript (web/), built by Vite into `src/oakbox/web/`. It talks to the service with
  `openapi-fetch`, typed from `web/src/api/schema.d.ts`, which is generated from the service's OpenAPI (CI checks it's
  up to date). Server state is TanStack Query. Progress is polled (`api/steps.ts`, every 700 ms while a run runs);
  there are no server-sent events.
- **The service never runs OpenAVMKit's pipeline itself.** OpenAVMKit changes the working folder, uses relative
  paths, takes seconds to import and can crash or run out of memory; each run gets a process of its own, so a crash
  fails that run, not the app. The service does import OpenAVMKit (warmed in the background at start-up,
  `app._warm_engine`) for small things, such as reading settings with OpenAVMKit's defaults.
- **Runs end with the app.** `steps._jobs` holds each run's progress, in memory only. Stop, and the app closing
  (`steps.stop_all`, on every way out of `__main__`), end a run and every process it started: on Linux each run
  leads a process group of its own (`start_new_session`), and `steps.end` signals the group and the process tree,
  then kills what's left after 3 s. For the ways the app can't run its code as it goes (a crash, Task Manager), each
  run watches the app's process (`steps.die_with_app`, from `OAKBOX_APP_PID`) and ends itself and its workers when
  it's gone. `tests/test_runs_end.py` checks all three.

## The code, by job

**Start-up and the window:** `__main__.py` (arguments, the service's thread, the window or the browser),
`menus.py` (the one definition of the menus) with `winmenu.py` (Win32) and `qtmenu.py` (Qt); pywebview's own menus
are the fallback. `net.py` (certificates as the computer checks them, the User-Agent), `engines.py` (XGBoost and
CatBoost, downloaded when asked for).

**The service:** `app.py` builds it; `routes/` has one APIRouter per area. `routes/common.py` has what they share:
`load_project` (or a 404), `editing` (a change to a project, under its lock), the views a step's routes answer with.
`errors.py`: `NotFound` (404) and `NotReady` (409).

**Projects and settings:** `projects.py` (the `Project` model in oakbox.json, finding projects, the per-project lock,
writing `in/settings.json` for OpenAVMKit), `appsettings.py` (OAK box's own settings: where projects are, display),
`atomic.py` (whole-file writes).

**Setting up the data** (the Data tab, before step 1): `datafiles.py` (a file brought into `in/` and its `data.load`
entry), `fields.py` (what's in a file), `wizard/` (the Fields wizard: `core.py` builds its view and makes its
changes; `base.py` is its steps as data; the other modules are its parts: IDs, money, quality, condos, map layers,
rows appended, user fields, deeds and permits, existing values), `enrichments.py`, `names.py` (deed names),
`valuesets.py`.

**The steps that run OpenAVMKit**, each a module with a `STEP` (`steps.Step`) and a `run()` that is its process:

| # | Step (its run) | Module | Starts from | Writes for the next |
|---|---|---|---|---|
| 1 | Inputs (Bring in data) | `bring_in.py` | the files and settings | `out/oakbox/bring_in/sup.pickle` |
| 2 | Model groups | `assemble.py` (run), `groups.py` (the builder) | Bring in data | `out/1-assemble-sup.pickle` |
| 3 | Sales (Check sales) | `clean.py`, `salereview.py` (the review of the sales it set aside), `time_preview.py` (the time adjustment alone, a run of its own) | `out/1-assemble-sup.pickle` | `out/oakbox/clean/` (its hand-off, and copies of its sales and universe), `out/2-clean-*` |
| 4 | Evaluate (Check my values) | `ratio.py` | `out/oakbox/clean/`: Check sales as it ran, never `out/2-clean-*` | its receipt only |
| 5 | Variables | `prepare.py` (Prepare the fields), `vartest.py` (Test the variables), `varlists.py` | `out/oakbox/clean/sup.pickle` | `out/2-clean-*` again, filled and folded |
| 6 | Models (Try them, Finalize) | `model.py` (Try them), `spatiallag.py` (nearby sales and buildings), `smallgroups.py`, `locstack.py`, `final.py` (Finalize) | Prepare the fields | the model values |
| 7 | Report | `report.py` (no run of its own: it reads Finalize's) | Finalize | exports, the printable report |

Shared by the steps: `steps.py` (running, the receipt, out of date, accepted), `cells.py` (values read out of
OpenAVMKit's tables).

**The page** (`web/src/`): `screens/` (one per tab and its panels), `components/` (shared pieces: buttons, file
entries, tables, maps), `api/` (the typed client and the hooks on it: `steps.ts` for every step's state and runs),
`lib/` (formatting, hooks, the address and moving between places: `route.ts`, where you've been: `place.ts`), `wording/` (every word shown, `en.json`).

## The life of a run

1. The step's Run button calls `useStepAct(id, projectId).mutate("run")` (`web/src/api/steps.ts`), which POSTs
   `/api/projects/<id>/<step>/run`.
2. The route (`_step_routes`, `routes/steps.py`) takes the project's lock, runs the step's `before` (usually: write
   `in/settings.json` from the project), checks what blocks it (`blocked()`: an earlier step not accepted, a file
   missing), and calls `steps.start`.
3. `steps.start` spawns `python -X utf8 -m oakbox.<module> <project id>` with `steps.child_env()` (UTF-8 mode, the
   user's Census key), stdout piped, stderr to `out/oakbox/<module>.log`. A thread reads its stdout: each JSON line
   (`steps.emit`: a part, a detail, a heartbeat every 2 s) updates the in-memory `Job`.
4. The page polls the step's state route while it runs; the state is `RunView`: status, the job, stale, blocked.
5. In the process, `steps.main(run)` sets up certificates and the optional engines, then `run(project_id)`: load the
   project, `steps.workdir()` (an empty `out/oakbox/<module>.tmp/`), OpenAVMKit's calls, the receipt and what it
   depended on written into the work folder, then `steps.publish()` moves it into place as `out/oakbox/<module>/`
   (the last run's moved aside first, so a failed run leaves it as it was). An exception prints its traceback and a
   last line the page shows, and exits 1.
6. Some steps also write OpenAVMKit's own hand-offs (`out/1-assemble-*`, `out/2-clean-*`, `out/look/`), as its
   notebooks do; those are written in place, not through the work folder.
7. **Looks right** POSTs `…/accept`: the step's current key hash is stored in `project.accepted[<module>]`.
8. After any change to a step (a call, a run, a mark), the page calls `stepChanged`, which asks that step, what its
   screen also shows, and every step after it (`NEXT`) again.

## Out of date, waits, accepted

Each step's `key` (in its module) is what it depends on now: its own calls, and `ran_at` of the step it starts from
(`after`). `steps.key_hash` fingerprints it (sorted JSON, sha256).

- **out of date** (`stale`): the hash its last run recorded (`out/oakbox/<module>/settings.json`) differs from the
  hash now.
- **accepted**: Looks right was pressed at the hash it has now, and nothing before it waits.
- **waits** (`waiting`): an earlier step isn't accepted on an up-to-date run; a step can't start or be accepted
  until every step before it is.

A change further back only puts its own step out of date; the steps after it wait. A run puts every step after it
out of date (their key holds its `ran_at`).

## A project on disk

```
<storage location>/<project name>/       Documents/OAK box/… by default; anywhere, found by id
  oakbox.json                             the Project model: everything the user chose
  in/                                     the user's files, brought in (moved or copied)
    settings.json                         OpenAVMKit's settings, written from oakbox.json (projects.write_settings)
    oakbox/                               OAK box's own inputs to runs: keep.csv, exclude.csv, time adjustment files
  out/
    oakbox/<step>/                        each step's last finished run: receipt.json, settings.json (what it
                                          depended on), and its own tables
    oakbox/<step>.log                     the last run's stderr
    1-assemble-*, 2-clean-*, look/        OpenAVMKit's hand-offs and exports, as its notebooks write them
  cache/                                  enrichment downloads (OpenAVMKit's)
```

Code finds these through `steps.py`: `out_dir(pdir, module)`, `settings_path`, `handoff(pdir, "2-clean")`,
`look_dir` and `look(pdir, "2-clean-universe")`; never by spelling the path out.

OAK box's own settings (`appsettings.py`): `%APPDATA%\OAK box\settings.json` on Windows, `~/.config/oakbox/` on
Linux; downloaded engines: `%LOCALAPPDATA%\OAK box\engines\`, `~/.local/share/oakbox/engines/`. `OAKBOX_HOME` (tests,
CI) puts projects, settings and engines in one folder.

## Packaging

`packaging/build_bundle.sh <windows|linux>` builds a bundle on Linux: a standalone CPython 3.11, every wheel from
`uv.lock` for that platform, the built page, a launcher (`Oakbox.cmd`, `oakbox.sh`) and `smoke.cmd`/`smoke.sh`
(`oakbox/smoke.py`). Nothing is frozen. `packaging/oakbox.iss` makes the Windows installer. CI
(`.github/workflows/bundles.yml`) runs the checks, the native menus on both platforms, and builds and smoke-tests
both bundles; a `v*` tag publishes a release. docs/RUNNING.md has the commands.
