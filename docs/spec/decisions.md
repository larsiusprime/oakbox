# Decisions

Every product decision, numbered (D1, D2…). Code and the rest of the spec cite them by number.

## 2. Decisions

- **D1 · Scope.** Both checking values and producing values. Checking values ships first.
- **D2 · Configuration.** The guided build and builders write fully resolved `settings.json`. Users never have to edit
  JSON; Under the hood shows it read-only (§3.2). Hand-made settings, including `$$` references and `!`/`+` keys, can be
  imported.
- **D3 · Jurisdictions.** Generic, not Texas-specific. Test with OpenAVMKit's public sample localities. Non-disclosure
  states come later.
- **D4 · Data model.** GIS-first. A parcel geometry layer is required.
- **D5 · Scale.** 500k+ parcels supported on suitable hardware. Small jurisdictions run on the low-end floor (§5).
- **D6 · Platform.** Windows 10 64-bit minimum is the primary target. **Linux x86_64 is also supported** (glibc 2.34+:
  Ubuntu 22.04+, Debian 12+, RHEL/Rocky 9+), from the same codebase and CI. Installs per user, with no admin rights. A
  later macOS version must stay possible (§6.1).
- **D7 · Network.** Works offline. Internet is only needed for optional enrichment, the map background, update checks
  and the sample download.
- **D8 · Updates.** The user approves each update. IT-managed deployment comes later.
- **D9 · Input/output.** In: Shapefile, GeoPackage, GeoJSON, (Geo)Parquet, CSV, Excel, fixed-width text with a layout
  (PACS exports). Out: (Geo)Parquet, GeoPackage, Shapefile, CSV, Excel. Polished PDF reports. Custom reports.
- **D10 · Engine.** OpenAVMKit changes are real commits on the `openavmkit-oakbox` branch, pinned by commit, later
  upstreamed (§7).
- **D11 · Licensing.** Oakbox's own code is MIT. OpenAVMKit, including our `openavmkit-oakbox` commits, stays
  AGPL-3.0/commercial. The installer ships OpenAVMKit under AGPL with a source link. Every other dependency must be
  free/open-source and AGPL-compatible (§6.2).
- **D12 · Privacy.** No parcel data leaves the machine. No telemetry.
- **D13 · Localization.** Deferred. All UI strings go in a string table from day one.
- **D14 · Code signing.** Deferred; the maintainer will handle it.
- **D15 · UI tech.** Strict TypeScript + React 19 (SPA, React Compiler, React Aria Components), built with Vite. No
  Next.js/SSR. Runs in a native window on a FastAPI backend whose API types are generated into TypeScript, so the whole
  stack type-checks (§6.5).
- **D16 · Checking values.** The user names the total-value field(s) to check. No particular field is required. Land
  values are out of scope: a separate land-value tool is planned.
- **D17 · Online notices.** Anything that goes online says what it sends, in a calm one-time notice (§3.11).
- **D18 · CAMA export.** v1 is a generic CSV/Excel file: parcel ID plus new columns. It carries total value only. Land
  values are left out; a separate land-value tool is planned. Vendor layouts come later.
- **D19 · Sample county.** **No sample in the app for now** (F3); it may be rebuilt on the new flow later. A synthetic
  county to add by hand is in the repository ([`sample/`](../../sample/README.md)). CI still runs OpenAVMKit end to end on
  `us-va-petersburgcity`, outside the app (§8 smoke test).
- **D20 · Model choice.** Each model group has its own models (LightGBM, MRA and Multi-MRA to start), each taking a
  named variable list (F9; revised 2026-10-31 from "Choose for me").
- **D21 · Name and look.** "OAK box" (written "Oakbox" in code and folder names). The look is a dense desktop tool
  (D43). The look (settled 2026-11-01): **an oak box**, and inside it **Manila folders and white paper**. The box: the
  inside is dark, low-contrast oak boards (`assets/oak-planks.svg`); a frame of light oak runs round the window
  (`OakFrame`): its top piece is the lid, the sides run grain down (`oak-v.svg`), the bottom rail grain across
  (`oak-h.svg`), mitred at 45° at the bottom corners, flat against the lid at the top. Every piece is pinned to the
  window's edges and its grain tiles seamlessly (stitched noise), so the frame stretches with any window, no script;
  it never takes a click. The lid (`OakBand`) is polished oak, staying at the top as the page scrolls, with the brass
  plate on it: **no text sits on the bare wood: what's said is on the plate**, and **the plate is the main
  navigation** (revised 2026-11-02, `OakBand`, `lib/place.ts`): "OAK box" is the name, not a link; then a trail of
  where you are, Projects › project › tab › step ("Projects › G2 · 2026 › 6 Model values › **Finalize**"), each crumb
  above you a link, the one you're on in bold. Each crumb in a project opens a list of the others at its level, each
  saying where it will open: the projects (each with its last place, "3 Check sales › Sales set aside", "running" when
  a run is going, "here"), the tabs (each with the step it opens on, ✓ when done, "waits" when locked), the steps (✓,
  "here"). Choosing an earlier crumb replaces the trail after it with that choice's own: **every project and every tab
  remembers where you last were** (kept on this computer), so going back opens there; nothing stops or is lost (work
  saves as it's made, runs keep going). **Back** (Alt+←, or the mouse's back button) retraces the path you took, steps
  included. No "Next" on the plate: moving on is each step's own Next. The folder tabs and step lists stay. Inside:
  **a container with a heading, lying on the wood or in a folder, is a Manila folder** (creamy but still Manila,
  `--manila`), its heading the folder's tab, one piece with it (no line between), the heading larger; what it holds is
  **crisp white paper** (`--paper`). **On paper already, a container with a heading is a titled section** of the
  document (its heading over a hairline), never a folder inside a document. The project is one folder lying in the
  box, its tabs along its top edge on the wood; a step's list of steps lies on the Manila, the step itself is a sheet.
  **Pop-ups (revised 2026-11-01): anything that blocks the screen is part of the box**: a dialog over a dimmed screen
  has a light oak frame, its title on a brass plate on the frame, what it says on one white sheet inside. **Anything
  attached to something on the page belongs to the papers**: a value list, a picker, the parcel inspector on the map
  are Manila, their heading on the Manila with no line under it, their list or table on white paper. Plain dropdown
  lists are controls, unchanged. Tables' alternate and highlighted rows are very light blue (`--zebra`, `--head`), not
  grey. Buttons and controls are unchanged. Print: no wood, no lid, no frame. | Projects" at home, "OAK box | New
  project", "OAK box | G2 · Tax year 2026" in a project; it takes you home (there is no separate back link). Inside a
  project the folder tabs stand on the band's bottom edge, paper on wood, and the open one runs into the page; they're
  always one row (revised 2026-11-03): wider than the window (a narrow window, a high zoom), the row scrolls, with ‹ ›
  at its ends as sheet tabs and browser tab strips have (each greyed when its end is showing), the wheel over the row
  scrolls it, and the open tab is kept in view (`components/TabStrip.tsx`); a tab that waits on an earlier step says
  so at the top of the page, under the tabs. Print leaves the band out. Type is IBM Plex Sans and Plex Mono (OFL),
  bundled, with Noto Sans as the fallback for other scripts. **Landing pages** (settled 2026-11-02): every tab, and
  every major step with parts (Data › More details, Data › Condo units), opens on a landing page before its first
  step: the step's number and name and, in a few lines, why it exists, then **Start: ‹first step› ›** (revised
  2026-11-04: no *What happens* / *What you decide* / *What you end with* columns, no *Needs* line; a step that waits
  on another says so at the top of the page, as before). A tab's is **Overview** (◆, never ✓ or !) at the top of its
  step list and in the plate's; it opens on its own only the first time the tab is opened in the project (kept on the
  computer), after that the tab opens where it was left, and Overview is always one click away. A major step's parts
  are reached through its landing page: its row opens it, and Back and Next pass through it. Metadata is a step list
  too, with no Overview (revised 2026-11-04): just Project details, whose Next opens Data. The text is `landing` in
  `wording/en.json`.
- **D22 · Model groups.** A dedicated builder with live map feedback (§3.5).
- **D23 · Sale validity.** Office codes and OpenAVMKit scrutiny together. The assessor can overrule any sale. **A sale
  flagged invalid never enters the modeling pipeline.** Review happens in Oakbox's separate sales register (§3.6).
- **D24 · Years.** One project per jurisdiction per tax year (§3.7).
- **D25 · Users.** Single user, one PC, for now.
- **D26 · Help.** Built-in help pages plus a link to the Discord. An AI helper comes later (§3.8).
- **D27 · Bad input data.** Data health and a Field profile, with plain-language problems and safe one-click fixes
  (§3.9).
- **D28 · Ratio study.** IAAO statistics with pass/fail against editable standards profiles (§4.2).
- **D29 · Enrichment.** A dedicated Enrichment screen exposing OpenAVMKit's real options, with cost estimates,
  small-area trial runs and coverage results (§3.12). v1 covers map-layer joins, footprints, census (configurable
  variables), distances (OpenAVMKit's defaults plus the user's own layers), elevation, permits and missing-value
  estimation. The street network is deferred.
- **D30 · Variables.** "Plow forward" or "Test variables first" (§3.10).
- **D31 · Map background.** Offline: parcels only. Online: an OpenStreetMap-based background. Every map has a **Street
  map** box in its corner to take the background away (a plain one, to see only the colours). Each map starts as
  Settings › Performance › Street map says (revised 2026-11-06, §5); the box changes that map. The user's own imagery
  comes later (§3.11).
- **D32 · Custom reports.** Sections and branding for everyone; editable templates for power users (§4.3; their format
  is open now that reports are HTML, F10).
- **D33 · Staleness.** Oakbox tracks which settings feed which step and re-runs exactly what changed. OpenAVMKit's
  checkpoints don't self-invalidate (§6.4).
- **D34 · Derived fields.** Typed "transforms" in Match columns, plus an Advanced formula builder, compile to OpenAVMKit
  `calc`. Per-parcel corrections compile to `tweak` (§3.13).
- **D35 · Vacancy.** Default: a blank finished area means vacant land (OpenAVMKit's rule), stated clearly. Users opt out
  per project and supply an explicit vacancy signal instead (§3.9).
- **D36 · Vacant land.** Main (total-value) models only. No separate vacant-stage run within a model group
  (`run_vacant=False`). Vacant sales are still flagged correctly (`vacant_sale`), and vacant land is not a model group
  of its own. May be revisited.
- **D37 · Guided build.** No up-front wizard. The project screen is the guide: setup stages, then steps, each with
  Decide → Check → Run → Receipt, and done only after **Looks right** (§3.2).
- **D38 · Datasets.** Any number of input files, each declared as one of seven kinds, stitched by an explicit,
  user-confirmed plan with match rates and ID fixes (§3.2).
- **D39 · Show the work.** Every stage shows what it will do and what it did, with counts and reasons. **Under the
  hood** (collapsed, open to everyone) shows the settings it wrote.
- **D40 · Sample.** Superseded by D19: no sample in the app for now.
- **D41 · Mirror OpenAVMKit.** OAK box is a GUI for OpenAVMKit, not logic on top of it. Every screen maps to something
  OpenAVMKit does or a setting it reads, and the user's choices are written as OpenAVMKit settings. When OpenAVMKit
  can't do something a user needs, the change goes upstream (§7), not into OAK box. OAK box's own logic is limited to
  presentation: previews, explanations, defaults and checks that read data without changing it.
- **D42 · Help on hover.** Explanations go in hover tooltips (also shown on keyboard focus), not in lines of text on the
  screen. Screens carry only labels and what the user needs to act. Applies to new screens and to screens as they are
  revised.
- **D43 · Dense by default.** Compact, information-dense presentation, after mid-2000s desktop software (Mac OS X
  Tiger): 14 px text, about 24 px controls and table rows, a light grey window, softly rounded panels and tabs, buttons
  with a classic two-step bevel (two rings of light and shadow, swapped when pressed; grey, blue for the main action,
  red for danger; hovered icon buttons share it); every dropdown, pick-list or searchable, is a classic combo box: a
  sunken white field with a bevelled arrow button inside its right edge, folder tabs that touch, the first flush with
  the panel, slightly rounded inputs, little padding. Tables keep full outlines: an outer border, a gradient header bar,
  column lines and row lines, with a blue alternate-row tint. **Density** (revised 2026-11-03), View → Density, kept in
  OAK box's settings: **Default** is the look above. **Compact** is a Windows 2000 dialog's density: every padding,
  margin and gap is a multiple of one spacing unit (`--sp`: 1rem in Default, 0.2rem in Compact), so all spacing shrinks
  to a fifth; nothing sits between a box's edge and what's in it; table rows are as tall as their tallest control and no
  taller; controls are about 20 px. Gaps between things side by side never go below about 3 px (`--gap-min`), lists keep
  their bullets' indent (`--indent-min`), folder tabs their own height (`--tab-h`), and the plate's ends clear its
  screws. Default draws exactly as it did before Compact existed (checked pixel for pixel). Comfortable (touch screens)
  was removed; a saved Comfortable reads as Default. **Zoom** (settled 2026-11-03), View → Zoom in (Ctrl+=), Zoom out
  (Ctrl+-), Actual size (Ctrl+0), and Ctrl+mouse wheel as in a browser (a level a notch; a trackpad's small movements
  added up): 67, 75, 80, 90, 100, 110, 125, 150, 175 or 200%, kept in OAK box's settings, the level shown for a moment
  at the top right. It scales the text (`--zoom` on `<html>`), and with it everything sized in rem, which is nearly all
  the layout; 1px lines stay 1px and maps keep their own scale. It replaced Large text (a saved Large text opens at
  125%); 100% draws exactly as before. **Typing in a dropdown** (settled 2026-11-02): a dropdown of 7 or more choices,
  and the column picker always, can be typed in (`components/Combo.tsx`). It looks like any dropdown until clicked; a
  click opens the whole list; typing keeps the choices whose names hold what was typed, anywhere in the name, case aside
  (names only, not a column's sample values), the letters marked, with "N of M match" under the list; the first match is
  highlighted, so Enter picks it; Esc or leaving puts back what was chosen. In the column picker a file's heading goes
  when none of its columns match; "(none)" and the picker's other choices (In another file…, Assumed) stay. Fewer than 7
  choices: a plain dropdown.
- **D44 · Native window.** The app's name and place are in the native title bar ("Travis County 2026 – OAK box"; "OAK
  box" on the home screen), not on the page. Menus are native (Win32 on Windows, Qt on Linux) and hold only what exists
  (§3.14). Browser mode has no menus; everything in them is also reachable on the page.
- **D45 · Fields wizard.** Fields are chosen in a guided wizard over all of a project's files, one small question at a
  time (F3d), (the per-file table, F3c, was the Advanced view until it was removed on 2026-10-31). Guesses are
  preselected only on a name match that passes the field's check.
- **D46 · Tables use the width.** Tables use all the width there is (a minimum width, never a maximum); only running
  text is capped for reading. Everything else that isn't a table (a file's entry, a frame of fields, a form) is as wide
  as what's in it, not the page (revised 2026-11-04: stretched boxes were mostly empty and moved their ✕ far from what
  it removes); boxes in one list share the widest one's width. Charts and maps are decided case by case; a layer's map,
  opened in its entry, takes the page's width. Every table has faint cell lines and alternate gray rows, and a numbers
  column's header lines up with its numbers. A cell says a short phrase; the fuller explanation is in a tooltip on an ⓘ
  (D42), and a column's header isn't repeated in its cells.
- **D47 · Files and items look one way.** Settled 2026-11-04, the style guide `docs/style-guide.html`. **A file**,
  wherever it's added, picked or used, is one thin outline: its first line a faint warm band (revised 2026-11-04), its
  name in OAK box (mono, bold), its file name (set off like code: mono on a faint box), its facts ("4,712 rows ·
  shapes"), a short check, other actions as icons, then a **red −** at the right edge (centred on a one-line entry,
  top right on a tall one). What's set on the file (its IDs, what it's about, how it's used) is inside the same
  outline, labels in one column and controls in the next. − takes the file off that step (the file stays in the
  project and can be picked again; Undo puts it back). A step with no file yet shows a dashed outline: [Add a file…]
  or use existing: [Choose…]. The import form is an entry too (its path, its format and size; its red − takes it away,
  instead of Cancel). Lists and choices that only show files (what Bring in data runs, the Condo units file) use the
  same first line without outline or −. **Anything removable on its own** (an ID inside a file, a test, a condition, a
  copied field, a location field) has its own outline, siblings too, and the same red − (a real button, raised like
  every button, a white − on it: the pair of Add's +; revised 2026-11-04), its label on hover, and **Undo** for a few
  seconds after it; every "Remove" link, "(remove)", "drop" and grey X is gone. **Deleting for good** is a danger
  button with a trash can and its words, and asks first; **closing** a popup, panel or dialog is a grey ✕ at its top
  right (a row or entry not saved yet is taken away with the red −, like any item); the three never share a look.
  Adding to an item (another ID) is inside it, at its bottom right; adding another item is after the list. A short
  choice inside an item is a segmented control, not radio buttons. Every item's outline is the same colour
  (`--frame`). **Anything pressed is a raised button** (the family: button, primary, delete, add, small, tool, close,
  remove) unless the style guide keeps it flat, with its reason (navigation, list rows, sortable headers, disclosures
  with a chevron, swatches); flat is never the default. Text links that did something are small buttons; links that go
  somewhere stay links, and ones that leave the app carry ↗. No page opens with a "Step 5 of 10 · …" line over its
  title: the step list and the plate's trail say where you are (revised 2026-11-04).
