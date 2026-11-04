# Guidance for coding agents (OAK box)

OAK box is a desktop app, and **most of its users are on Windows**. Develop and test on Linux, but write for
Windows first. SPEC.md is the product spec: keep it in step with what's built.

## Windows: text is always UTF-8 (non-negotiable)

Windows Python reads and writes text in the system code page (cp1252, "charmap") unless told otherwise. A "−", "é",
"²" or "✓" then stops a run on Windows that passes everywhere else (`UnicodeEncodeError: 'charmap' codec can't
encode character…`). Every time you touch I/O:

- **Every text read and write says `encoding="utf-8"`:** `open()`, `Path.read_text()` / `write_text()` / `.open()`,
  `importlib.resources` `read_text()`, `io.TextIOWrapper`, text-mode temp files, `subprocess` with `text=True`
  (also give `errors="replace"` when reading another program's output). Never rely on the default.
  `tests/test_encoding.py` fails on any that doesn't.
- **CSVs and other files the user brings** may not be UTF-8 (Excel writes cp1252, sometimes with a BOM). Read them
  as their files are, never as the computer's default; `utf-8-sig` drops a BOM.
- **Every Python process OAK box starts runs in UTF-8 mode** (`-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`:
  `bring_in.child_env()`), so OpenAVMKit's own reads, writes and prints are UTF-8 too. The launchers
  (`Oakbox.cmd`, `oakbox.sh`, `run.bat`) start it with `-X utf8`. A new launcher or subprocess does the same.
- **Printing:** `pythonw` has no console (`sys.stdout` is `None`); a console may not be UTF-8. The app reconfigures
  its streams to UTF-8; don't print where it can fail a run.
- **Also Windows:** paths with spaces and non-ASCII letters (`C:\Users\José\Documents\OAK box`), `\` separators
  (use `pathlib`, never string paths), a file open in Excel can't be replaced (say so, don't crash), names are
  case-insensitive, `os.rename` onto an existing file fails (use `os.replace`), CRLF line endings in files users
  bring.
- **Check it:** CI runs the whole suite a second time with a non-UTF-8 default encoding (ASCII, stricter than
  cp1252). Do the same before pushing:
  `PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 LC_ALL=C LANG=C uv run pytest -q tests`

## Engine or app?

OAK box is a front end to OpenAVMKit, and the engine is ours to change (the fork's branch, pinned in
`pyproject.toml`, then upstream). Anything generally useful (a check, a statistic, a file of results, progress)
is built in the engine, so notebook users get it too, without changing what the engine already does by default
(a new setting, off unless asked for). OAK box keeps what only an app needs: screens, wording, the user's
choices turned into settings.

## Steps that run the engine

Every step that runs OpenAVMKit (Bring in data, Model groups, Check sales, Check my values, Prepare, the variable
tests, the models) is built on `steps.py`, not on another step's module: a `steps.Step` (its module, its receipt,
`key`: what it depends on now), and in its run `steps.workdir` / `steps.publish`, `steps.emit`, `steps.heartbeat()`,
`steps.engine_notes`, `steps.main`. Its routes come from `_step_routes` in `routes/steps.py` (each area of the API
is a router in `routes/`). A step that needs an earlier one done asks `<earlier>.STEP.accepted(...)` (cheap), never
builds the earlier step's view.

On screen, a step's state, run and calls come from `web/src/api/steps.ts` (`useStep`, `useStepAct`,
`useStepSetup`, `useStepNav`); after anything that changes a step, `stepChanged` asks it and every step after it
again (`NEXT`: the one table of which step starts from which).

## Shared helpers

A helper two modules or screens need lives in a shared place, never in one of them for the other to import:
`web/src/lib/format.ts` (numbers, money, dates, sizes, percentages), `web/src/lib/hooks.ts`, `web/src/components/`;
`cells.py` (a value read out of OpenAVMKit's tables), `steps.py` (the settings file, what a run wrote),
`fields.names()`. A step module's `_private` names are its own: what another module needs is made public, under a
name that says what it is.

## Screens

- **Width** (revised 2026-11-04): **tables** use all the width available (a minimum width is fine, never a
  maximum). **Everything else is as wide as what's in it**, not stretched to the page: a file's entry, a frame, a
  row of tests, a form (`width: fit-content; max-width: 100%`). Boxes in one list share the widest one's width
  (`.entry-list`), and its Add button sits at that right edge. Charts and maps are decided case by case (a chart
  that's read across time may want the width; a layer's map, opened in its entry, takes the page's width). Running text is capped for readability (`.project p`, `.cs-text`,
  `.wiz-lede`…), and a small chart that illustrates the paragraph above it (Check sales' sales per year) is as wide
  as that text.
- **Tables:** a table of results is `<table className="tbl">` (its own class only adds what's its own); every
  table has faint cell lines and alternate grey rows (the `:where(table)` rules in `styles.css`), its cells padded by
  the density (`--cell-y`); a numbers column's header has the column's class (`th.cs-n`) so it lines up with its
  numbers.
- **Pills and colours:** a short status word or mark is `.pill` (`pill-ok`, `pill-warn`, `pill-bad`, `pill-info`;
  grey without), or `components/Pill.tsx` for a verdict. Colours are the `:root` tokens (`--ok`, `--ok-tint`,
  `--ok-edge`, the same for warn, bad and info; `--select`, `--zebra`, `--cell-line`, `--rule`), never a hex in a
  rule; the buttons' and titlebar's bevels are the exception.
  A chart is drawn at its own width in pixels (a `ResizeObserver`), not scaled, so its text stays its size.
- **Funnels and other line lists** (a count, a phrase, a link): columns only as wide as their content, so a link
  sits beside its line, not at the far edge (`.cs-funnel`, `.bi-fn`: one grid, the lines on it by `subgrid`).
- **Adding something** (a file, a field, a test, a condition, a group, a step, a layer…) is always
  `components/AddButton.tsx`: a button with a plus and "Add …" in words (never a "+" typed into the label, a link,
  or a bare "+"). It opens what it adds (a menu, a popover, a new row) or adds it at once. A form's own submit
  button inside that popover is an ordinary button.
  It comes after the list it adds to, at that list's right edge: `<AddButton end>`, or a row of buttons in
  `.add-row`. Adding another item (a file, a layer, a value set) is outside the items' outlines; adding to one item
  (another ID, another copied field) is inside that item's outline, below its rows.
- **The style guide for files and items is `docs/style-guide.html`** (SPEC D47); open it before changing how a file
  or a removable item looks. In short:
  - **A file is always `components/FileEntry.tsx`** wherever it's added, picked or used (`StepFile` in the Data
    wizard): one thin outline (`--frame`, 3px); its first line its name in OAK box (mono, bold), its file name, its
    facts (`fileFacts`: rows, shapes), a short check, other actions as icons, then the ✕. What's set on the file goes
    in its body, inside the same outline: labels in one column, controls in the next (`.wiz-grid`, `.ly-grid`), so
    they line up like a two-column table. A step with no file yet is `FilePicker`: a dashed outline round
    [Add a file…] and "or use existing:". Read-only lists and choices of files use `FileLine` (the same first line,
    no outline, no ✕).
  - **A file's own name** (`parcels.csv`) is always `FileName` (`.file-name`): mono on a faint box, like code in a
    chat, cut short with the whole name on hover. Never plain or grey text.
  - **Taking something away is always `components/RemoveButton.tsx`:** a real button, red with a white ✕, raised
    and pressed like every button, last on its line at the right edge,
    labelled with what it removes. Never a "Remove" link, "(remove)", "drop", a grey X or a "(none)" option in a
    dropdown. On a file it takes the file off that step, never off disk. Deleting a project (from disk) keeps its own
    button and confirmation; closing a popup or a map isn't removing (its own close button).
  - **Anything that can be removed on its own has its own outline** (`--frame`, 3px): a file, an ID inside a file
    (`SubEntry`, on the body's columns), a test, a condition, a copied field, a location field. Its siblings in the
    same list get one too, even one that can't be removed. Every item's or group's outline is `--frame`; `--rule` is
    for lines (a table's, a hairline), not boxes.
  - **A thing you press is a raised button** (`.button`, `AddButton`, `RemoveButton`) unless it's in the style
    guide's list of flat ones (section 5: text links, icon buttons, pills, rows, cards, navigation). Flat is a
    deliberate choice, never the default: a new flat control is added to that list with what it does, or made a
    button.
  - **A file entry's first line is a faint warm band** (`--entry-head`), its body below a `--frame` line.
  - **A short choice (two or three options) inside an item** is a segmented control (`components/Seg.tsx`), not
    radio buttons; a reason an option can't be chosen is its title.
- **Loose rows get a frame:** rows of fields or widgets lying straight on the page (a step's fields) sit in a thin
  `.frame`; what belongs together shares one. Not inside a card or an entry, which is a frame already.
- **Picking fields or values from a list** is always `components/MultiPick.tsx`: a button listing what's chosen
  that opens a searchable checklist (a field's name with its column as a note, or a value with its count). Never
  a row of chips with ✕s, nor a row of loose ticks. Each chosen field that needs more (its column) gets a row
  below it in the wizard's grid (`.wiz-grid`: the name, its dropdown, ✕), as everywhere in the Data wizard.
- **Long explanations fold away:** a callout of more than a sentence or two (why rows don't match, what to do about
  it) is `components/Callout.tsx`: folded, one line (⚠ or ⓘ, its first sentence, "more"); open, the whole of it.
  The reader shows and hides it. A short status line stays plain text.
- **Short labels, the rest on demand:** a table cell says a short phrase; the fuller explanation goes in a tooltip
  (`components/Tip.tsx`: `InfoTip` shows an ⓘ beside the phrase), not in the cell. A column's header isn't repeated
  in its cells ("Pattern" over "Low price", not "Pattern 2: low price").
- **Values from the user's files can be any length** (a county export's 255-character "#####…" date, a 120-character
  column name): never let one size a table, a list or a dialog. In a table or a list, show it through
  `components/Val.tsx` (cut short, the whole value on hover) or `short()` from `lib/format.ts` when it's joined into
  text; a one-line cell can clip instead (`.clip`, `.rc-td`). Elsewhere `overflow-wrap: anywhere` on the body
  breaks a long word in its box, and a dialog never grows past the screen (it scrolls). Check new screens against
  a file with long values.

## Wording

Every word the UI shows is in `web/src/wording/en.json` (ICU MessageFormat, SPEC §6.6), imported as `t` from
`web/src/wording`; never a string literal in a screen. A message with arguments is called with them by name,
`t.x.plusOthers({ first, n })`; plurals and choices are the message's (`{n, plural, =1 {sale} other {sales}}`,
`{mode, select, move {…} other {…}}`), never a `?:` in the screen. What needs code first (joining a list, changing
case, arithmetic, picking between messages) is `say` in `wording/logic.ts`; a message never computes. After changing
`en.json`, `npm run wording:types` (CI checks `wording.gen.ts` is up to date). A lookup keyed by an id from the backend is
listed in `wording/records.json`. To edit wording in the running app: `edit-wording.bat` (Windows: the
app window, its page from the dev server), or `npm run dev:wording` with
`python -m oakbox --port 8765 --ui-url http://127.0.0.1:5173`; then Alt+click text. It writes `en.json`. A message may have line breaks (`\n`) and paragraph breaks (`\n\n`): show
wording in a `p`, `li`, `dd` or tooltip, which keep them. Nothing of the editor may reach other builds:
keep it behind `__WORDING_EDIT__`.

## Going online

- Downloads check certificates as the computer does: every process OAK box starts calls
  `oakbox.net.use_system_certificates()` first (a new entry point does too).
- Say who's asking: `oakbox.net.USER_AGENT`. Public services are shared (OpenStreetMap's Overpass is run by
  volunteers): keep rate limits on, cache and reuse, never retry in a loop, and send nothing to a service that
  didn't answer. Credit data as its licence asks ("© OpenStreetMap contributors", ODbL).

## Before pushing: what CI runs

Run all of it, not only the tests; CI fails on any of these.

```sh
uv run ruff check src tests && uv run ruff format --check src tests && uv run pyright && uv run pytest -q tests
PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 LC_ALL=C LANG=C uv run pytest -q tests
(cd web && npx biome check src && npx eslint src && npx tsc --noEmit && npm test)
# API types: regenerate and check nothing changed
uv run python -c "import json; from oakbox.app import create_app; print(json.dumps(create_app().openapi(), indent=1))" > web/openapi.json
(cd web && npm run -s api) && git diff --exit-code web/openapi.json web/src/api/schema.d.ts
```

A change to what the user sees is also checked in the real app (`run.bat`, or `uv run python -X utf8 -m oakbox`),
not only by tests.
