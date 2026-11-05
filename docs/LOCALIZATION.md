# Localization: plan and spec

**Status:** planned, not started (written 2026-11-05). Nothing here is built. When work starts, each part that's built
moves into SPEC.md (a new §6.7, "Languages and countries"), as SPEC.md is the product spec.

Marks used below: **Decided** is a choice this plan makes (change it here first if it's wrong). **Ask** is a fact a
local advisor must confirm before it's built into a preset; the plan's guess is given so the work can start.
**Engine** marks work in OpenAVMKit (our fork, then upstream, off unless asked for, as AGENTS.md says).

---

## 0. Scope

| Locale | Language | Market | Why it fits |
|---|---|---|---|
| `en` | English | (source, and the fallback for anything missing) | |
| `fr-CA` | Canadian French | Quebec | Municipal rolls at market value (*valeur réelle*), three-year rolls; the province publishes a *proportion médiane* and *facteur comparatif* per roll: a ratio study in official form. French may be required to sell there (Charter of the French Language, Bill 96). |
| `nl-NL` | Dutch | The Netherlands | WOZ: every municipality values every property at market value every year, supervised by the Waarderingskamer. |
| `ko-KR` | Korean | South Korea | Official prices (공시가격, 공시지가) are mass appraisals with 1 January as the reference date. |

**Not in scope:** France, Belgium, other French or Dutch markets (a French- or Dutch-speaking computer elsewhere gets
`fr-CA` or `nl-NL`); OpenAVMKit's documentation, its Markdown reports and the notebooks (they stay English); census-like
data for Canada, the Netherlands and Korea (listed in §6 as later work).

**Size:** about 26,000 English words to translate per language, about 78,000 in all:

| Source | Words |
|---|---|
| `web/src/wording/en.json` (2,335 messages) | 14,930 |
| OAK box's Python wording (checks, receipts, errors, progress, the report) | ~5,600 |
| The field dictionary (166 fields, from OpenAVMKit) | ~2,500–3,000 |
| OpenAVMKit's warnings that OAK box shows (139 `warn` calls) | ~2,300 |
| Menus, installer messages, README, release notes | ~1,200 |

---

## 1. Decisions

**L1. Files.** One catalog per locale beside the English one: `web/src/wording/en.json` (the source),
`fr-CA.json`, `nl-NL.json`, `ko-KR.json`, with the same nesting. A message missing from a locale's catalog shows in
English. `wording.gen.ts` stays generated from `en.json` only: English defines the keys, their arguments and their
types.

**L2. Choosing the language.** A new app setting, `AppSettings.language`: `"auto"` (the default), `"en"`, `"fr-CA"`,
`"nl-NL"` or `"ko-KR"`. `auto` takes the computer's display language: any `fr-*` → `fr-CA`, any `nl-*` → `nl-NL`,
any `ko-*` → `ko-KR`, anything else → `en`. Chosen under View › Language (native menu) and in the app's settings;
changing it redraws the app (nothing open is lost: work saves as it's made).

**L3. Formatting follows the language, plural rules too.** Messages are formatted in the UI's language: its plural
rules and its way of writing numbers, money and dates (`fr-CA`: `1 234,56 $`, `2026-11-05`; `nl-NL`: `€ 1.234,56`,
`5-11-2026`; `ko-KR`: `₩1,234`, `2026. 11. 5.`). An English UI keeps today's behaviour: the computer's own region
(en-US, en-CA, en-GB…). One place says which locale formats (`wording/locale.ts`); nothing else passes `undefined` to
`Intl` or `toLocaleString`.

**L4. The data's country is not the UI's language.** How a project's files are read (number style, CSV delimiter,
encoding, date order, units, currency, ID schemes) follows the project's country and region, never the UI language.
An English UI reading a Quebec file reads `1 234,56` correctly; a Korean UI can open a US county.

**L5. Python sends codes, the screen says them.** Anything the backend wants shown is a `Said`
(`{"key": "server.check.datesFailed", "args": {"words": "…", "n": 12}}`), never an English sentence. The screen
looks the key up in the catalog and formats it. Numbers go as numbers, never preformatted. Receipts written before
this hold English strings: those are shown as they are (a field is `str | Said`).

**L6. What Python still writes itself goes through the same catalogs.** The printable report, export labels, the
native menus and any dialog shown before the page loads are written by Python. A small module, `oakbox/wording.py`,
reads the same catalog files and formats the subset of ICU MessageFormat the catalogs use (arguments, `plural` with
`=n` and `#`, `select`, `number`, `date`), with plural rules and number formats from Babel (Unicode CLDR, pure Python,
small). CI renders every message with sample arguments in both FormatJS and `oakbox/wording.py` and requires the same
text (as §6.6 did for the move to `en.json`). *Considered:* drawing the report in the page instead of Python: one
formatter, but a much bigger change to how the report is printed. Not now.

**L7. OpenAVMKit's text stays English; its warnings get codes.** **Engine:** every warning OpenAVMKit raises carries a
stable code and its values; the English text is unchanged, so notebooks see no difference. OAK box shows a known
code from its catalog (`engine.<code>`) and an unknown one in English, marked "from OpenAVMKit" (as now). OpenAVMKit's
errors (a run that stops) stay English in this round.

**L8. The field dictionary is translated in OAK box.** A script copies the pinned OpenAVMKit's
`data_dictionary.json` names and descriptions into `en.json` (`dictionary.<key>.name`, `.description`), with
`{jurisdiction}` as an ICU argument instead of a text replacement. CI checks the copy matches the pinned engine.
Field keys (`land_area_sqm`) are never translated: they're names in the data.

**L9. Data stays in English keys.** Column names in exports, `settings.json`, file names OAK box writes and
OpenAVMKit's keys are unchanged in every language. Only labels meant for people are translated (the report, the
headers of the Excel export's readable sheet if it has one).

**L10. Korean particles.** Translators write around particles that depend on a value (은/는, 이/가, 을/를), or use the
usual `을(를)` form. No particle helper in this round; add one to `say` only if the translators ask for it.

**L11. Fonts.** IBM Plex Sans KR (OFL, the same family) is bundled for Hangul, after IBM Plex Sans in `--font`, and
after IBM Plex Mono in `--mono` (Plex Mono has no Hangul: Korean file and column names otherwise fall back to an
unrelated font). Its subsets load by `unicode-range`, so a non-Korean screen loads none of it.

**L12. Countries get presets.** One data file per supported country, `src/oakbox/countries/<CC>.json` (US, CA, NL,
KR), with regional overrides (CA › QC). It says what `locales.json` can't: the valuation date rule, the standards
presets, ID schemes, date order, CSV delimiter and encoding to try first, number style by region, the area
definitions to ask about, sale-type filters, the currency's magnitude, plausible sizes, and which enrichments work
there. Other countries keep today's `locales.json` defaults.

**L13. Terminology is per market.** One glossary (`docs/l10n/glossary.csv`) with, per term: the English, a
definition, where it shows, do-not-translate (COD, PRD, PRB, VEI…), and the `fr-CA`, `nl-NL`, `ko-KR` terms. Quebec
terms are Quebec's (*rôle d'évaluation*, *évaluateur*, *valeur uniformisée*, *proportion médiane*; the OQLF's *Grand
dictionnaire terminologique*), never France's.

**L14. When a locale ships.** A locale ships when every message that existed at the English freeze is translated
and reviewed in the app. A message added after that may show in English for one release.

---

## 2. Phase A: correct for non-US projects (no translation; English users get it too)

These are bugs for any project outside the US today. Each lands on its own.

### A1. CSV delimiter and encoding

- **Engine:** `data.load.<name>` takes `csv: {"sep": ";", "encoding": "cp949"}`; without it, today's behaviour
  (`data.py` reads CSVs with a bare `pd.read_csv` at the load, ~line 4324, and for column names, ~line 4502). GIS files take
  `encoding` too, passed to `gpd.read_file` / pyogrio (a `.dbf` without a `.cpg`).
- **OAK box:** one reader for every CSV it reads itself (`datafiles.py`, `wizard/files.py:43`, `clean.py:231`…), in
  `datafiles.py`. It guesses the delimiter (`,` `;` tab `|`) and the encoding (UTF-8, UTF-8 with BOM, then the
  country's: cp949 for KR, cp1252 for CA and NL), shows both on the file's entry, and lets the user change them; the
  choice is written to the file's `csv` block.
- **Done when:** three test files load in the wizard and in an engine run, also in CI's non-UTF-8 pass: a Quebec CSV
  (`;`, decimal comma, cp1252, accented headers), a Korean CSV (cp949, Hangul headers and values), and a shapefile
  whose `.dbf` is cp949 with no `.cpg`.

### A2. Dates

- Add `%d-%m-%Y` (Dutch), `%d.%m.%Y`, `%Y.%m.%d` and `%Y. %m. %d.` (Korean) to `fields.DATE_FORMATS`, with their
  words in `DATE_WORDS`.
- The order formats are tried in comes from the country (L12): day before month for NL; for CA both readings stay
  and an ambiguous column is always pointed out (`rules._also` already finds it). Today `%m/%d/%Y` is always tried
  first.
- Month names in French, Dutch and Korean (`janv.`, `mrt`, `3월`) are read from a table, not `%b` (English only).
- **Engine:** a date built from parts (a calc taking a year-month column like `202503` and a day column like `4`):
  Korea's official sales data writes dates that way (**Ask**: column layout of the current 국토교통부 실거래가 files).
- **Done when:** a test reads each new format, each month-name table, and a date from parts; an ambiguous column on
  a CA project is flagged.

### A3. Money: magnitudes and scales

- `wizard/money.py` judges amounts in currency units: `NOMINAL = 1_000` (a token price), `TOO_BIG = 50_000_000`
  ("probably cents"). In won, every ordinary sale is over 50 million and a ₩1,000 deed is about 70 cents. Both become
  multiples of the currency's magnitude (a power of ten against the dollar, in the country file: KRW 3, JPY 2, EUR
  and CAD 0). **Engine:** OAK box sets `analysis.sales_scrutiny.nominal_price.below` from it (default 1,000, as now).
- The scale guesser (`money.py:224`) knows thousands and cents; add **×10,000**: Korean official data gives prices
  in 만원 (`85,000` = ₩850,000,000). On a KR project, an amount column whose median looks like 만원 says so.
- `PLAUSIBLE_SQFT` and the other plausibility ranges come from the country file.
- **Done when:** a KR sample with prices in 만원 is read as won with the right scale, nothing flagged "probably
  cents", and ₩1,000 deeds flagged nominal.

### A4. Area

- **Korea:** apartment area is one of three: 전용면적 (the unit's own), 공급면적 (plus shared halls and stairs),
  계약면적 (plus parking and other common areas). On a KR project, an area field asks which; mixing them in one
  model group is pointed out. Price per area can also be shown per 평 (3.3058 m²) beside per m² (a setting, on by
  default for KR): Koreans quote 평당가, though official papers use m².
- **Quebec:** column names with `pi2`, `pi²`, `pc`, `pieds` read as square feet; `m2`, `m²`, `mc` as square metres.
- **Netherlands:** a volume field (m³, *inhoud*), a size measure Dutch valuation uses. **Engine:** a dictionary
  field for it, named as the dictionary's others are.
- **Elevation below sea level:** check that elevation, slope and their fills work with negative values (most of the
  western Netherlands).

### A5. Sales: what counts as a market sale

Per-country sale filters on Check sales, from the country file, each one explained and off by default where unsure:

- **NL:** *kosten koper* (resale: the buyer pays costs) and *vrij op naam* (new builds: price includes them) aren't
  comparable: new builds marked, or adjusted (**Ask**: what the Waarderingskamer expects). *Erfpacht* (leasehold
  ground) flagged as a location or parcel field.
- **KR:** lease deals (전세, 월세) never loaded as sales; direct deals (직거래) as against brokered (중개거래)
  pointed out; cancelled contracts (해제) excluded (**Ask**: the columns that mark them).
- **QC:** **Ask**: how Quebec offices mark valid sales and which exclusions are standard.

### A6. Parcel IDs

- Add to ID cleaning and to `tools/id_robustness.py` (8 US schemes today): Korea's 19-digit PNU; the Netherlands'
  16-digit BAG ids and the cadastral reference (*kadastrale aanduiding*: municipality code, section, parcel number,
  apartment index); Quebec's 7-digit lot numbers written with spaces (`2 345 678` is `2345678`) and the roll's
  *matricule*.
- Leading zeros always kept (IDs are text).
- **Done when:** `id_robustness.py` passes on 12 schemes.

### A7. Country and region defaults

- **Regions:** the region picker gets Canada's provinces (ISO 3166-2:CA) beside the US states (`projects.py:74`: free
  text for every other country).
- **Region overrides:** QC: number style `1 234,56`, CSV `;` tried first.
- **Valuation date by country** (the default, still changeable):

  | Country | Rule |
  |---|---|
  | US | 1 January of the tax year (today) |
  | NL | 1 January of the year before (WOZ 2026 is valued at 2025-01-01) |
  | KR | 1 January of the year |
  | CA (QC) | 1 July two years before the roll's first year (the 2026–2028 roll at 2024-07-01) (**Ask**) |

- **"Tax year"** is the US name; each country's is wording (roll year in Quebec, the WOZ year, the 공시 year).

### A8. Features that only work in the US

- **Census** (ACS, `counties.json`, FIPS): shown only for US projects; elsewhere its card says it's US-only.
- **Elevation:** OpenAVMKit's only source is USGS 3DEP (`utilities/dem.py`: the US and its territories). **Engine:** a
  global source as well (Copernicus GLO-30, ~30 m), chosen when the parcels are outside 3DEP; finer national sources
  later (AHN for the Netherlands, HRDEM for Canada) (**Ask** each advisor which their offices use).
- **Frontage:** `utilities/somers.py` works in `frontage_ft` only; metric projects get metres. **Engine.**
- **Maps:** OpenStreetMap is thin in places in Korea; note it on KR projects' distance card. VWorld (the official
  Korean map service) is later work.

### A9. Exports a local Excel can open

- CSV exports use the region's delimiter and decimal mark (QC and NL: `;` and `,`), changeable on the export.
- Numbers are always written as numbers, never formatted (French spacing uses U+202F, which breaks re-import).
- **Done when:** checked by hand in Excel set to French (Canada) and Dutch (Netherlands): the export opens in columns
  with numbers as numbers.

### A10. Typing, search and sorting

- **Korean typing:** pressing Enter while a Korean syllable is being composed confirms the syllable, but OAK box
  reads it as Enter. `Combo.tsx` then picks the first match early, and WebView2 may double the last syllable. No
  handler in `web/src` checks for this. Fix: one shared helper in `lib/hooks.ts` that ignores keys while
  `isComposing` (or `keyCode === 229`), used by every Enter and Escape handler (about ten screens and components).
- **Unicode normalization:** file names, column names and values compared or searched are normalized to NFC, in
  Python on reading and in the page on searching (Mac-made Korean file names arrive decomposed).
- **Search** ignores accents and case through one helper (`lib/format.ts` or a new `lib/text.ts`): "ecully" finds
  "Écully". **Sorting** uses `Intl.Collator` in the UI's language.
- **Shortcuts** use `event.key`, never `event.code` (AZERTY and other layouts). None use `code` today; keep it so.
- **Done when:** tests for the matcher and the composition helper; checked by hand with Microsoft's Korean IME on
  Windows in a Combo, a MultiPick search and a text field.

### A11. Standards presets

The Standards step gets presets per country beside the IAAO's (`ratio.py`, `iaao_standards`). The mechanism is built
now; the numbers come from advisors:

- **QC:** the province's rules for the *proportion médiane* and related figures (**Ask**).
- **NL:** the Waarderingskamer's quality measures (**Ask**: which figures and limits).
- **KR:** the level target is deliberately below 1 (현실화율, set by government policy and changed over the years);
  the preset takes the current year's target by property type (**Ask**).

---

## 3. Phase B: ready to receive translations (no translated words needed)

### B1. Loading the catalogs

- `wording/catalog.ts` loads `en.json` and, lazily, the active locale's file, and lays the locale's messages over the
  English (L1). `t` keeps its shape and types.
- The live editor (`npm run dev:wording`) edits the active locale's file: it shows the English beside the message, and
  writes to `fr-CA.json`, `nl-NL.json` or `ko-KR.json` (`scripts/wording-edit-plugin.mjs` takes the target file).
  The editor's other rules stay (same arguments, same types, no overwriting a newer change).
- `<html lang>` is set to the UI's language (it's `en` in `web/index.html`): it decides Hangul glyphs and line breaking.

### B2. CI checks for the catalogs (`scripts/wording-check.mjs`, in CI and `npm run build`)

For each locale file:
- no key that `en.json` lacks;
- each message parses as ICU and has the same argument names and kinds as its English;
- each `plural` has every category the locale needs (`Intl.PluralRules(locale).resolvedOptions().pluralCategories`,
  plus `other`), and no `=n` the English doesn't have unless it's an addition;
- each list has the English list's length (lists are options in order);
- `**` and `*` balanced; a message is rich exactly when its English is (its type is fixed by `wording.gen.ts`);
- it prints how much is translated, per top-level section (not a failure: L14 decides when a locale ships).

### B3. The language setting

- `AppSettings.language` (L2): its route, View › Language in the native menus (`menus.py`, `winmenu.py`,
  `qtmenu.py`), and the app's settings.
- The window title follows the language.

### B4. Remove English-only formatting

- `wording/locale.ts`: the formatting locale (L3), exported. Used by `catalog.ts` (instead of
  `new Intl.NumberFormat().resolvedOptions().locale`) and every `lib/format.ts` helper (instead of `undefined`).
- `lib/format.ts`:
  - `when()`'s `"today at"` becomes a message;
  - `amount()`'s `K`/`M` becomes `Intl.NumberFormat`'s compact notation (which writes 억/만 in Korean);
  - `pct()` and `signed()` go through the locale (`12,5 %` in French).
- `wording/logic.ts`:
  - `list()` and every `join("; ")` become `Intl.ListFormat`;
  - `lower()` and the capitalizing replace are dropped or done only for `en`;
  - each `say` helper is reviewed for English word order.
- **Nested messages** (a message inside another, "‹Model groups› waits for ‹Bring in data›"): list every one, and
  check each can be translated in French with its gender and agreement. Reword where it can't.

### B5. Python sends codes (L5): the largest item

- `oakbox/wording.py`:
  - `Said` (a pydantic model: `key`, `args`);
  - `said("server.…", **args)`, which checks at call time in tests that the key exists.
- Every English sentence the API returns becomes a `Said` in `en.json`'s `server` section (~5,600 words):
  - `Check.text` and `Issue` text (`wizard/models.py`), and every `wizard/*` check;
  - receipt notes, including OAK box's own dropped-rows notes;
  - errors (`HTTPException` details, `LookupError("Finalize first: …")`);
  - progress labels (`steps.emit`, e.g. `"Writing notebook 2's output"`);
  - `DATE_WORDS`, `UNIT_WORDS`, `report.FORMATS`' labels.
- Numbers in them go as arguments, never as `f"{n:,}"`.
- **The page:** `say.said(s)` renders a `Said` (or an old English string as it is). `wording.gen.ts` also writes the
  union of `server.*` keys, so a `Said` from the API schema is type-checked.
- **Tests:**
  - every `said(...)` call in `src/oakbox` names a key that exists, with the arguments its message has (a test
    reading the code's syntax tree);
  - a test fails on new English sentences in API response models, outside an allowed list (logs, docstrings,
    developer-only errors).
- **Order:** module by module, biggest first: `report.py` (through B8), `model.py`, `clean.py`,
  `wizard/models.py`, `datafiles.py`, `ratio.py`, `bring_in.py`, `enrichments.py`, `wizard/*`.
- This also moves the Python wording within reach of the live editor, which helps the English clean-up (SPEC §6.6
  says it's "the next bite").

### B6. Warning codes (L7) **Engine**

- `openavmkit/utilities/warnings.py`:
  - `class OpenAVMKitWarning(UserWarning)` with `code` and `params`;
  - `warn(code, message, **params)` that raises it with today's English message.
- All 139 `warnings.warn` calls move to it.
- One upstream PR, no behaviour change; tests that every call site has a unique, stable code.
- **OAK box:** `steps.engine_notes` and the receipts (`model.py:1481`, `vartest.py:286`, `assemble.py:153`,
  `final.py:373`, `enrichments.py:555`) keep the code and params and store a `Said` (`engine.<code>`); an unknown
  code is kept as English text.
- The catalog's `engine` section is written from the engine's codes by a script, its English the engine's.

### B7. The field dictionary (L8)

- `tools/dictionary_wording.py` writes `en.json`'s `dictionary` section from the pinned engine.
- CI checks it's current after a pin changes.
- `fields.dictionary()` still sends English names (for the API's English users and old clients); the page shows the
  catalog's.

### B8. Python's formatter and the report (L6)

- `oakbox/wording.py` reads the catalogs:
  - **in a checkout:** from `web/src/wording/`;
  - **in the bundle:** from package data, copied there by the build (a test checks the copy is current).
- It formats the ICU subset with Babel.
- The parity test renders every message the Python side uses with sample arguments in FormatJS and in Python, and
  requires the same text.
- `report.py`:
  - every word through it;
  - `_num` and `_money` replaced by Babel's number and currency formatting in the formatting locale (₩, `$`
    after the amount in `fr-CA`, compact amounts);
  - `<html lang>` set;
  - the print styles' fonts include Plex Sans KR.
- `menus.py`'s labels through it, with translated mnemonics (`&Fichier`), given by translators.

### B9. Fonts and line breaking (L11)

- Add `@fontsource/ibm-plex-sans-kr` (check the package name and licence when adding it). Add it to `--font` and
  `--mono`.
- `:lang(ko) { word-break: keep-all; }` and `line-break: strict`.
- Check the bundle's size before and after.
- French spacing (a space before `:` and around « »; Quebec's rules differ from France's, **Ask** the translator)
  is typed into the messages as non-breaking spaces: no code.

### B10. Pseudo-locale and test catalogs (development only)

- `npm run wording:pseudo` writes `en-XA.json`:
  - every message with accented letters, 35% longer, and in brackets (`[Ádd fíéld ·····]`);
  - arguments and ICU untouched;
  - a few Hangul syllables mixed in.
- Text missing its brackets on screen is a string that isn't in the catalog. A message cut short is a layout that
  can't grow.
- Machine-translated test catalogs for `fr-CA` and `ko-KR` (and `nl-NL`), to check real lengths, Hangul line breaks
  and fonts:
  - they're never shipped and never given to translators as drafts unless the vendor asks for that;
  - they live outside `src` (`web/l10n-test/`, ignored by the build).
- Both load only in a development mode (`__L10N_TEST__`); the release build fails if any of it is in the bundle
  (alongside `scripts/no-wording-edit.mjs`).

### B11. A layout pass on every screen

- The screenshot run used for §6.6 (97 screens, every step of every tab) gets a locale option.
- Run it in `en-XA` and in the Korean test catalog, and fix every clipped label, overflowing table header, wrapped
  `Seg` and tab that no longer fits.
- Add the locale runs to the screenshot checks.
- **Done when:** the 97 screens show no clipped or overflowing text in `en-XA` and in Korean.

### B12. The installer

- `packaging/oakbox.iss` gets a `[Languages]` section:
  - English;
  - French (Inno Setup's `French.isl` is France's French; its few lines suit Quebec, **Ask** the translator);
  - Dutch;
  - Korean (check whether `Korean.isl` ships with the Inno Setup version used or comes from its community
    translations).
- OAK box's own installer messages (`[CustomMessages]`) are written from the catalog by the build.

### B13. Translation management

- **Tool:** Weblate (open source, can be self-hosted, a natural fit for an AGPL project); Crowdin or Lokalise if a
  vendor brings its own.
- **Files:** `en.json` as the source, nested ICU JSON; the three locale files written back by pull request. The
  CI checks in B2 run on those pull requests.
- **Context for translators:** `web/src/wording/context.json`, a note per message where it isn't obvious: where it
  shows, how long it may be (a tab, a button, a column header), what each argument is, with an example. The examples
  come from the live editor (it already keeps the values each message was last shown with). The B11 screenshots are
  uploaded as context.
- **The glossary** (C2) is loaded into the tool, so its terms are enforced.

---

## 4. Phase C: people, no translators yet

- **C1. Freeze the English.** Finish the wording clean-up (SPEC §6.6), including the Python wording once B5 brings it
  into the catalog. Shorten the long explanations where they can be shorter: every word cut is saved three times.
  Set a freeze date; after it, English changes are batched per release and marked for translation.
- **C2. Glossary, English side.** Pick 150–300 terms (the IAAO's, OAK box's own: model group, holdout, parcel
  universe, roll, valuation date, set aside…) with definitions and where they show, into
  `docs/l10n/glossary.csv` (L13). Mark what isn't translated (COD, PRD, PRB, VEI, MAPE, file formats).
- **C3. A style guide per language**, settled with each translator:
  - **Formality:** Korean 합쇼체 or 해요체; Dutch *je* or *u* (software usually says *je*); French *vous*.
  - **Tone:** OAK box's plain voice ("what you decide", "what you end with").
  - Unit abbreviations (m², pi², 평), punctuation and spacing, how numbers and dates look.
- **C4. A brief for translators:** ICU syntax, arguments, plural categories per language, `**bold**`, line and
  paragraph breaks, the particle rule (L10), length limits.
- **C5. An advisor per market** (assessment practice, not translation): confirms every **Ask** (§5), gives the
  standards presets' values, reviews the glossary's terms, says which data sources offices use.

---

## 5. Questions for local advisors (the Ask list)

| # | Market | Question | Plan's guess |
|---|---|---|---|
| Q1 | QC | The roll's reference date | 1 July two years before the roll's first year |
| Q2 | QC | Rules for the *proportion médiane*, *facteur comparatif* and other quality figures | (none) |
| Q3 | QC | How sales are validated, standard exclusions | (none) |
| Q4 | QC | Typography: spaces before `: ; ! ?` | OQLF's rules (fewer spaces than in France) |
| Q5 | QC | The matricule's format(s) | segmented digits with dashes |
| Q6 | NL | The Waarderingskamer's quality figures and limits | (none) |
| Q7 | NL | How new builds (*vrij op naam*) and *erfpacht* are treated | marked, user decides |
| Q8 | NL | Elevation source offices use | AHN |
| Q9 | NL | Which floor-area and volume measures offices model on | GBO (NEN 2580) and *inhoud* |
| Q10 | KR | Current 현실화율 targets by property type | (from policy, per year) |
| Q11 | KR | Columns of the current 실거래가 files: date parts, 만원, deal type, cancellations | as in A2, A3, A5 |
| Q12 | KR | Which area definition the official prices model on | 전용면적 |
| Q13 | KR | Map and elevation sources offices use | VWorld; Copernicus |
| Q14 | All | Who the first users are (assessment offices, consultants, researchers) | assessment offices |

---

## 6. Later (not this round)

- Census-like data for each country: Statistics Canada dissemination areas; CBS *wijken en buurten*; Korea's
  statistical output areas (집계구).
- National map and elevation services (VWorld, AHN, HRDEM).
- Importers for national data: BAG/WOZ files; 국토교통부 실거래가; Quebec roll extracts.
- A Korean particle helper (L10), if translators want it.
- OpenAVMKit's errors and Markdown reports in other languages.

---

## 7. Phase D: translation (after the go-ahead)

1. **Pilot:** one tab (Check my values) in `ko-KR` and `fr-CA`; reviewed in the app; brief and glossary adjusted.
2. **Full translation:** about 26,000 words per language.
3. **Review in the app:** the translator and the market's advisor go through every screen with the live editor
   (about a week per language).
4. **Testing with real data:** a Korean Windows machine (Korean display language, Microsoft Korean IME) with Korean
   official data; Windows in French (Canada) with a Quebec roll; Windows in Dutch with WOZ and BAG data.
5. **Release** by L14. After that, English changes are batched before each release and sent to the tool.

---

## 8. Order and rough sizes (engineering only)

| Work | Size | Needs |
|---|---|---|
| A1 CSV delimiter and encoding (with **Engine**) | 1–1.5 weeks | |
| A2 dates (with **Engine** date from parts) | 3–5 days | |
| A3 money magnitudes and 만원 | 2–3 days | |
| A4 area questions, 평, volume | 3–5 days | |
| A5 sale filters | 2–4 days | Ask answers |
| A6 ID schemes | 3–4 days | |
| A7 region list and defaults | 2–3 days | Q1 |
| A8 US-only features, global elevation (**Engine**) | 1 week | |
| A9 exports | 1–2 days | |
| A10 typing, search, sorting | 3–4 days | |
| A11 standards presets (mechanism) | 2–3 days | values from advisors |
| B1–B4 catalogs, checks, setting, formatting | 1.5–2 weeks | |
| B5 Python sends codes | 3–5 weeks | |
| B6 warning codes (**Engine**) | 1–1.5 weeks | |
| B7–B8 dictionary, Python formatter, report | 1.5–2 weeks | |
| B9–B12 fonts, pseudo-locale, layout pass, installer | 1.5–2 weeks | |
| B13 translation tool and context | 3–5 days | |

**Order:** A1, A2, A3 first (real bugs, some in the engine); then B10's pseudo-locale and B1–B2, so everything after
can be checked as it's built; then B5 (the biggest), with the rest of A and B beside it. C runs alongside. About
10–14 weeks of engineering in all, before translation starts.

## 9. Risks

- **Translating before the English is frozen** pays for the same words twice. C1 comes first.
- **Wrong terms for the market** (France's French in Quebec, US assessment terms carried into WOZ or 공시가격 work)
  make the product look foreign to the users who matter. Mitigated by C2, C5 and the review in step D3.
- **B5 is wide:** it touches most backend modules. Done module by module, each a separate change, with English
  output unchanged (tested as §6.6 was).
- **Bundle size:** Plex Sans KR and Babel add to the bundle; measure and report it with B9.
- **Facts not yet confirmed:** everything marked **Ask** is the plan's best guess. Build the mechanisms now; fill in
  the values after advisors confirm.
