# OAK box

**OpenAVMKit in a box:** a desktop app for assessors. It takes a county's parcel and sales files through
[OpenAVMKit](https://github.com/larsiusprime/openavmkit), step by step: bring the data in, check the sales,
check the roll's values, build models and value every parcel, and report. No Python or notebooks needed.

An early preview, for Windows 10 and 11 (64-bit). Linux runs from a portable bundle.

## Install (Windows)

1. Download `OAKbox-<version>-setup.exe` from **[Releases](https://github.com/larsiusprime/oakbox/releases)**.
2. Run it. It installs for you alone, with no admin rights, and adds OAK box to the Start menu.
   It isn't signed yet: if Windows says "Windows protected your PC", click **More info**, then **Run anyway**.
3. Open OAK box and click **New project**. To try it on sample data first, see [`sample/`](sample/README.md).

**Optional model engines.** LightGBM, the linear models and the rest come with OAK box. **XGBoost** (about 100 MB
download) and **CatBoost** (about 110 MB) don't, to keep the download small: tick them in the installer, or
choose one when adding a model and OAK box offers to download it then. **Help › Model engines** installs or
removes them later. They come from the Python Package Index, so a network that blocks it blocks them too.

Updating: run the newer installer. Your projects (in `Documents\OAK box`) are never touched by installing,
updating or uninstalling.

## Run from source (Windows or Linux)

Needs [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org/) 22. uv fetches Python 3.11 itself.

```sh
git clone https://github.com/larsiusprime/oakbox && cd oakbox
uv sync                                          # Python dependencies, every model engine included
cd web && npm ci && npm run build && cd ..       # the UI, built into src/oakbox/web
uv run python -X utf8 -m oakbox                  # opens the app window (--browser for a browser instead)
```

On Windows, `build.bat` then `run.bat` do the last two steps.

## More

- [docs/RUNNING.md](docs/RUNNING.md): the portable bundle, developing the UI, editing wording live, the checks CI
  runs, and making a release.
- [AGENTS.md](AGENTS.md): conventions for working on the code (people and coding agents alike).
- [SPEC.md](SPEC.md): what OAK box does and why, screen by screen.

MIT licensed. OpenAVMKit itself is dual-licensed (AGPL-3.0 or commercial): see its repository.
