# Running OAK box

## The Windows installer (simplest)
Download `OAKbox-<version>-setup.exe` from the latest release (**Releases** on the GitHub page) and run it. It installs for the current user only, with no admin rights, into `%LOCALAPPDATA%\Programs\OAK box`, and adds OAK box to the Start menu (and, if ticked, the desktop). It isn't signed yet: if Windows says "Windows protected your PC", click **More info**, then **Run anyway**. A newer installer replaces the old version; **Apps & features** uninstalls it. Projects in `Documents\OAK box` are never touched by either.

**Making a release** (maintainers): set the version in `pyproject.toml`, commit, then tag and push it (`git tag v0.1.0 && git push origin v0.1.0`). CI builds the bundle and the installer, installs, starts and uninstalls it on a clean Windows machine, and publishes a pre-release with the installer and the portable zip (`packaging/RELEASE_NOTES.md` heads its notes). Every other push builds an installer too (the `installer-windows` artifact, kept a day).

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
In a browser there is no file picker, so **Add a file** is disabled; use the OAK box window to add files.

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
