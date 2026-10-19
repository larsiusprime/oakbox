# Running Oakbox

## The portable bundle (no installs needed)
1. On GitHub, open the latest green run: **Actions → bundles**. Download `bundle-windows` or `bundle-linux` from **Artifacts**. Artifacts expire after 7 days; re-run the workflow for fresh ones.
2. Unpack it.
   - **Windows:** extract to a short path such as `C:\oak`. Long paths can hit Windows' 260-character limit.
   - **Linux:** `tar -xzf oakbox-linux-x86_64.tar.gz`
3. Start Oakbox.
   - **Windows:** double-click `Oakbox.cmd`.
   - **Linux:** run `./oakbox-linux-x86_64/oakbox.sh`.

   It opens a native window. On Linux without WebKitGTK it opens a browser window instead.
4. Click **Try a sample county → Download and open**, then **Run** each step in order.

Projects are stored in `Documents/Oakbox/` (override with the `OAKBOX_HOME` environment variable).

**Unattended test:** `smoke.cmd` / `smoke.sh` downloads the sample, runs steps 1–4 through the app service, and prints `SMOKE OK`.

## From source
Requires [uv](https://docs.astral.sh/uv/), git and Node 22.

```
git clone https://github.com/larsiusprime/oakbox && cd oakbox
git checkout claude/openavmkit-desktop-wrapper-639lvu
uv sync
cd web && npm ci && npm run build && cd ..
uv run python -m oakbox            # window (or --browser)
```

## Developing the UI with hot reload
In two terminals:
```
uv run python -m oakbox --no-window --port 8765
cd web && npm run dev                # opens http://localhost:5173, proxies /api to 8765
```

## Checks (the same ones CI runs)
```
uv run ruff check src tests && uv run ruff format --check src tests && uv run pyright && uv run pytest -q tests
cd web && npx biome check src && npx eslint src && npx tsc --noEmit
```

After changing a backend API model, regenerate the TypeScript types:
```
uv run python -c "import json; from oakbox.app import create_app; print(json.dumps(create_app().openapi(), indent=1))" > web/openapi.json
cd web && npm run api
```

## M0 benchmarks
The M0 spike scripts are still in `spikes/m0/`; see [`docs/m0/RUNNING.md`](m0/RUNNING.md).
