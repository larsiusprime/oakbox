# Running OAK box

## The portable bundle (no installs needed)
1. On GitHub, open the latest green run: **Actions → bundles**. Download `bundle-windows` or `bundle-linux` from **Artifacts**. Artifacts expire after 7 days; re-run the workflow for fresh ones.
2. Unpack it.
   - **Windows:** extract to a short path such as `C:\oak`. Long paths can hit Windows' 260-character limit.
   - **Linux:** `tar -xzf oakbox-linux-x86_64.tar.gz`
3. Start OAK box.
   - **Windows:** double-click `Oakbox.cmd`.
   - **Linux:** run `./oakbox-linux-x86_64/oakbox.sh`.

   It opens a native window. On Linux without WebKitGTK it opens a browser window instead.
4. Click **New project**, fill in the jurisdiction and tax year, then add files on the project's **Input files** tab.

Projects are kept in `Documents/OAK box/` by default; change it under **Where projects are kept** on the home screen. Projects made by earlier builds in `Documents/Oakbox/` still appear. (`OAKBOX_HOME` puts projects and OAK box's own settings in one folder, for testing.)

**Unattended test:** `smoke.cmd` / `smoke.sh` downloads Petersburg's public data and runs OpenAVMKit on it directly (assemble, clean, ratio study). Then it starts the app service, creates a project and adds a file. It prints `SMOKE OK`. It needs internet.

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
