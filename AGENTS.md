# Guidance for coding agents (OAK box)

OAK box is a desktop app, and **most of its users are on Windows**. Develop and test on Linux, but write for Windows
first. The product spec is docs/spec/, one file per area; SPEC.md is its index (where each numbered section, §3.5,
F9, D21, now is). Keep it in step with what's built, and keep a section's number when you move or change it: the
code cites them. docs/ARCHITECTURE.md is how the code is built (the modules, a run from button to receipt, a project
on disk): change it with the code it describes.

## Windows: text is always UTF-8 (non-negotiable)

Windows Python reads and writes text in the system code page (cp1252, "charmap") unless told otherwise. A "−", "é",
"²" or "✓" then stops a run on Windows that passes everywhere else (`UnicodeEncodeError: 'charmap' codec can't
encode character…`). Every time you touch I/O:

- **Every text read and write says `encoding="utf-8"`:** `open()`, `Path.read_text()` / `write_text()` / `.open()`,
  `importlib.resources` `read_text()`, `io.TextIOWrapper`, text-mode temp files, `subprocess` with `text=True`
  (also give `errors="replace"` when reading another program's output). Never rely on the default.
  `tests/test_encoding.py` fails on any that doesn't.
- **CSVs and other files the user brings** may not be UTF-8 (Excel writes cp1252, sometimes with a BOM). Read them
  as their files are, never as the computer's default; `utf-8-sig` drops a BOM. A CSV goes through
  `datafiles.csv_encoding(path)` (OpenAVMKit's `detect_encoding`: UTF-8, UTF-16 or cp1252), which `data.load` names too,
  so the run reads it as the previews do.
- **Every Python process OAK box starts runs in UTF-8 mode** (`-X utf8`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`:
  `steps.child_env()`), so OpenAVMKit's own reads, writes and prints are UTF-8 too. The launchers
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

Every step that runs OpenAVMKit (Bring in data, Model groups, Check sales and its time adjustment preview, Check my
values, Prepare the fields, the variable tests, Try them, Finalize) is built on `steps.py`, not on another step's module: a `steps.Step` (its module, its receipt,
`key`: what it depends on now), and in its run `steps.workdir` / `steps.publish`, `steps.emit`, `steps.heartbeat()`,
`steps.engine_notes`, `steps.main`. Its routes come from `_step_routes` in `routes/steps.py` (each area of the API
is a router in `routes/`). A step that needs an earlier one done asks `<earlier>.STEP.accepted(...)` (cheap), never
builds the earlier step's view.

On screen, a step's state, run and calls come from `web/src/api/steps.ts` (`useStep`, `useStepAct`,
`useStepSetup`, `useStepNav`); after anything that changes a step, `stepChanged` asks it and every step after it
again (`NEXT`: the one table of which step starts from which).

## Shared helpers

A helper two modules or screens need lives in a shared place, never in one of them for the other to import:
`web/src/lib/format.ts` (numbers, money, dates, sizes, percentages), `web/src/lib/hooks.ts`, `web/src/lib/route.ts`
(the address: `navigate`, the tabs), `web/src/lib/colours.ts`, `web/src/components/`;
`cells.py` (a value read out of OpenAVMKit's tables), `steps.py` (the settings file, what a run wrote, and where
each is: `out_dir`, `settings_path`, `handoff`, `look`),
`fields.names()`. A step module's `_private` names are its own: what another module needs is made public, under a
name that says what it is.

A route that changes a project changes it inside `with editing(project_id) as project:` (`routes/common.py`; with
`settings=True` when settings.json follows from the change), or holds `projects.lock(project_id)` from loading it to
saving it. The page can send two changes at once, and without the lock the second save undoes the first.
OAK box's own settings (appsettings.py) change the same way: `with appsettings.changing() as s:`, never
`load()` then `save()`.

What a request names and isn't there raises `errors.NotFound` (404); an earlier step that has to run first raises
`errors.NotReady` (409), its message saying which. Routes catch those, never `LookupError` itself, so a `KeyError`
from a bug stays a 500 with its traceback.

## Screens

- **Every action is acknowledged at once (non-negotiable, 2026-11-07).** Whatever the user does (a click, a key, a
  drop, a choice) shows a visible change *instantly*, before any answer comes back, so it's never unclear whether it
  was taken: the button pressed and busy, the row added, the choice shown made. When the result takes a moment, show
  a **cancellable** spinner or progress bar where the result will appear, and say **how long it should take**
  (from a measure: the file's size, the last run's time) or, when that can't be known, **how long it's been**
  ("Reading parcels.csv · 0:12"). Never a click that seems to do nothing while the server works: large counties
  (Guilford, NC: a 220 MB parcel file) make every slow path visible. Applies to adding a file, picking a field,
  opening a preview, every step's run and every mutation.
  **The shared pieces** (`components/Activity.tsx`, `components/Waiting.tsx`): every mutation and query already
  shows in the corner pill from its first moment (what, how long, Stop for a read), and the control pressed gets
  `data-busy` while the change it started is saved; nothing to add for that. A screen's first load uses
  `<Loading q qkey doing>` (its clock, Stop, Try again; the pill then leaves it out); anything else slow, `<Waiting>`
  where its result will appear. A query or mutation showing its own progress (polling, a run, a progress bar) takes
  `meta: { quiet: true }`; one that can say more than "Saving your change", `meta: { doing: "…" }`.
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
  `--ok-edge`, the same for warn and bad; info has `--info-tint` and `--info-edge`; `--select`, `--zebra`, `--cell-line`, `--rule`, a chart's `--chart-bar`), never a hex in a
  rule; the buttons' and titlebar's bevels are the exception. What's drawn in SVG or on a map, where the tokens
  don't reach, takes its colours from `lib/colours.ts` (`CHART`, `TRIMMED`, `PICKED`…), never a hex in the screen.
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
- **The style guide is `docs/style-guide.html`** (SPEC D47): buttons, files, removable items, and every control
  kept flat, each with its reason. Open it (it's one HTML page; open it in a browser to try each piece) before
  adding or changing a button, a file's entry, a list of items or a settings row. In short:
  - **A file is always `components/FileEntry.tsx`** wherever it's added, picked or used (`StepFile` in the Data
    wizard): one thin outline (`--frame`, 3px); its first line its name in OAK box (mono, bold), its file name, its
    facts (`fileFacts`: rows, shapes), a short check, other actions as icons, then the red −. What's set on the file goes
    in its body, inside the same outline: labels in one column, controls in the next (`.wiz-grid`, `.ly-grid`, `.set-grid` outside a file), so
    they line up like a two-column table. Not a sentence with a blank in it ("A sale demolished within [365] days…"),
    which stays a sentence, nor a question with its answers below it (a radio group). A step with no file yet is `FilePicker` (`screens/WizardFiles.tsx`): a dashed outline round
    [Add a file…] and "or use existing:". Read-only lists and choices of files use `FileLine` (the same first line,
    no outline, no ✕).
  - **A file's own name** (`parcels.csv`) is always `FileName` (`.file-name`): mono on a faint box, like code in a
    chat, cut short with the whole name on hover. Never plain or grey text.
  - **Taking something off a list or a step is always `components/RemoveButton.tsx`:** a raised red button with a
    white − (the pair of AddButton's +), last on its line at the right edge. `what` names what it removes: its
    label ("Remove parks") shows on hover and is read aloud. Pass `undo` (how to put it back): "Removed parks · Undo"
    shows for a few seconds (`lib/undo.ts`, `components/UndoToast.tsx`); a remove that can't be undone isn't a
    remove. With words, it's the same red button, its white − then its words (`RemoveTextButton`, "− Remove group",
    offering Undo itself). Never a
    "Remove" link, "(remove)", "drop", an ✕ or a "(none)" option in a dropdown. On a file it takes the file off that
    step, never off disk.
  - **Deleting for good is `DeleteButton`** (`components/Buttons.tsx`): a danger button with a trash can and its
    words ("Delete set", "Delete project"), which asks first. Never a trash can on something that can be undone.
  - **Closing is `CloseButton`:** a grey ✕, only at the top right of a popup, panel or dialog. Taking away a row or
    an entry that isn't saved yet (a new ID row, the import form, an "add a file" slot) is the red −, like any item.
  - **Boxes inside the same file stack flush** (`SubEntry`): no space between them, one border line where they
    meet.
    Nothing is lost; never for removing. Close and remove never share a look.
  - **The button family** (style guide, section 1): `.button`, `.button-primary` (one per view), `DeleteButton`,
    `AddButton`, `SmallButton` (an action beside a line of text: "Reconcile…", "Options ˅", "4 values ˅"),
    `ToolButton` (an icon; with `pressed`, a toggle that stays pressed in), `CloseButton`, `RemoveButton`. Unfolding in
    place is `Disclose` (a chevron), a link that leaves the app is `ExternalLink` (↗), and going somewhere in the app
    is a link (`.wiz-link`). Choosing is a dropdown, `Seg`, radio cards (`.cu-choice`) or a selectable row.
  - **A file's name in a sentence** is set off too: `NamesFile` (a file name like code, a name in OAK box in mono),
    the wording's sentence whole. A dropdown of files gives each option its file name (`Choice`'s third element).
  - **Anything that can be removed on its own has its own outline** (`--frame`, 3px): a file, an ID inside a file
    (`SubEntry`, on the body's columns), a test, a condition, a copied field, a location field. Its siblings in the
    same list get one too, even one that can't be removed. A table's rows are boxed already (its lines): a removable row ends in its −, no box of its own. Every item's or group's outline is `--frame`; `--rule` is
    for lines (a table's, a hairline), not boxes.
  - **A thing you press is a raised button** unless it's kept flat in the style guide's section 3 (navigation,
    list rows, sortable headers, disclosures, swatches), each with its reason. Flat is a deliberate choice, never
    the default: a new flat control is added there with its reason, or made a button. A pressable table row or chart
    is only a shortcut to a link or button in it (the chart shows its enlarge icon).
  - **A file entry's first line is a faint warm band** (`--entry-head`), its body below a `--frame` line, tinted a
    third of the way from white to that band (`--entry-body`); the rows inside it (`SubEntry`) stay white.
  - **A short choice (two or three options) inside an item** is a segmented control (`components/Seg.tsx`), not
    radio buttons; a reason an option can't be chosen is its title. What the chosen option does, when it needs saying, is one
    line under it in the same column (`.set-note`, the control level with its label), not words in brackets on each
    option.
  - **A form in an entry has a fixed width** (`FileEntry form`, the import form): it grows downward as text wraps,
    never sideways as what's typed or chosen changes.
  - **The buttons that do what a form, dialog or step is for** (Import, Save, Start, Delete…) sit at its right
    edge, the main one first (`.form-actions`).
- **Loose rows get a frame:** rows of fields or widgets lying straight on the page (a step's fields) sit in a thin
  `.frame`; what belongs together shares one. Not inside a card or an entry, which is a frame already.
- **Picking fields or values from a list** is always `components/MultiPick.tsx`: a button listing what's chosen
  that opens a searchable checklist (a field's name with its column as a note, or a value with its count). Never
  a row of chips with ✕s, nor a row of loose ticks. Each chosen field that needs more (its column) gets a row
  below it in the wizard's grid (`.wiz-grid`: the name, its dropdown, ✕), as everywhere in the Data wizard.
- **Long explanations fold away:** a callout of more than a sentence or two (why rows don't match, what to do about
  it) is `components/Callout.tsx`: folded, one line (⚠ or ⓘ, its first sentence, "more"); open, the whole of it.
  The reader shows and hides it. A short status line stays plain text.
- **A warning inside a row of settings keeps the row one line high:** `components/WarnChip.tsx`, ⚠ and a title of a
  few words ("777 sales off the map", from the backend's `title`), a button; the whole explanation and what to do
  open in a popup beside it. A check's own words are short too ("93% match"). Callout is for explanations on a
  line of their own.
- **A field's reading is its button** (style guide, 2B): "$270K median ▾", "year-month-day ▾", "true = yes ▾" opens
  how the column is read, in a column of one width on every row (`.field-tools`), the values button after it. No
  ✓ on a reading; one that needs a look is amber with ⚠. A reading with nothing to change is plain words in the
  same column.
- **Short labels, the rest on demand:** a table cell says a short phrase; the fuller explanation goes in a tooltip
  (`components/Tip.tsx`: `InfoTip` shows an ⓘ beside the phrase), not in the cell. A column's header isn't repeated
  in its cells ("Pattern" over "Low price", not "Pattern 2: low price").
- **Values from the user's files can be any length** (a county export's 255-character "#####…" date, a 120-character
  column name): never let one size a table, a list or a dialog. In a table or a list, show it through
  `components/Val.tsx` (cut short, the whole value on hover) or `short()` from `lib/format.ts` when it's joined into
  text; a one-line cell can clip instead (`.clip`, `.rc-td`). Elsewhere `overflow-wrap: anywhere` on the body
  breaks a long word in its box, and a dialog never grows past the screen (it scrolls). Check new screens against
  a file with long values.

- **State outside React (a module-level store):** the build memoizes with React Compiler, which can't see a mutable
  `Map` or `Set` change. Keep such state as one immutable snapshot, replaced on every change, read with
  `useSyncExternalStore(subscribe, () => snapshot)` and computed from the snapshot it returns (as
  `screens/FieldHistogram.tsx` does); never read a mutable module variable during render.

## Wording

Every word the page shows is in `web/src/wording/en.json` (ICU MessageFormat, SPEC §6.6), imported as `t` from
`web/src/wording`; never a string literal in a screen. (Words that come from Python, such as receipts, checks, errors and the report, are still
written in Python, in plain English: SPEC §6.6 has moving them as the next step. Write new ones as the ones beside
them are.) A message with arguments is called with them by name,
`t.x.plusOthers({ first, n })`; plurals and choices are the message's (`{n, plural, =1 {sale} other {sales}}`,
`{mode, select, move {…} other {…}}`), never a `?:` in the screen. What needs code first (joining a list, changing
case, arithmetic, picking between messages) is `say` in `wording/logic.ts`; a message never computes. After changing
`en.json`, `npm run wording:types` (CI checks `wording.gen.ts` is up to date). A lookup keyed by an id from the backend is
listed in `wording/records.json`. To edit wording in the running app: `edit-wording.bat` (Windows: the
app window, its page from the dev server), or `npm run dev:wording -- --host 127.0.0.1` with
`python -m oakbox --port 8765 --ui-url http://127.0.0.1:5173`; then Alt+click text. It writes `en.json`. A message may have line breaks (`\n`) and paragraph breaks (`\n\n`): show
wording in a `p`, `li`, `dd` or tooltip, which keep them. Nothing of the editor may reach other builds:
keep it behind `__WORDING_EDIT__`.
**The two datasets, by name (non-negotiable, 2026-11-08):** always **Parcel universe** (every parcel, sold or not,
as it is now: what's valued) and **Sales record** (every sale: what the models learn from), with their symbols:
🌐 Parcel universe, 💰 Sales record. "In the parcel universe", "in the sales record"; never "today's", "as it is
today", "the parcels'", "at the sale", "as sold", "in the sale" or other loose stand-ins. A box, column or heading
that's one of them is headed by its name and symbol ("🌐 Parcel universe", "💰 Sales record"). The files are still
named as files (`sale.csv`); the dataset is named as the dataset.
**Dates (non-negotiable, 2026-11-08):** every date shown is **YYYY-MM-DD**, however the file writes it: read with its
column's format (`oakbox/dates.py`: `iso_day`, `date_format_of`; the page's `day`, `isoDay`, `when` in
`lib/format.ts`), never a file's own way ("12/15/1988 0:01") or the computer's locale. The one exception is a date
field's reading table, whose "As written" side is there to show the file's own way beside YYYY-MM-DD.
**Naming the steps:** a step is its tab's short name (Inputs, Model groups, Sales, Evaluate, Variables, Models,
Report): its page's title, "Looks right › Sales", "Press Looks right on Sales first". Its run keeps a verb (Bring in data,
Check sales, Check my values), on its Run button and wherever the run is meant ("applies on the next Check sales").
**Formatting:** `**bold**` and `*italic*` (`\*` for an asterisk). A message with any unescaped `*` is rich: its type
in `wording.gen.ts` is `ReactNode` (or a function returning one), so it can only be shown, never used as text (a
`title`, a placeholder, an `aria-label`, a template string); tsc says where. A prop that only ever shows wording
(a step's lede, a landing page's lists) takes `ReactNode`, so its message can be formatted.

## Optional engines (XGBoost, CatBoost)

Not in the bundle; OAK box downloads them when asked (`oakbox/engines.py`, SPEC §6). So:

- Never import `xgboost` or `catboost` at module level, in OAK box or the engine: inside the function that uses
  them (OpenAVMKit's `utilities/optional.py` helpers raise a clear error when one is missing).
- A new process entry point calls `oakbox.engines.activate()` after `use_system_certificates()`, or the
  downloaded engines aren't importable there.
- A new dependency that's only needed by one of them goes in that OpenAVMKit extra, never the base: the bundle
  build fails if xgboost or catboost become base dependencies again.
- A checkout has both (`uv sync` installs the dev group, which has `oakbox[xgboost,catboost]`).

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
