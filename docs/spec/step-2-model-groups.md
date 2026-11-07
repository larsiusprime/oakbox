# Step 2, Model groups

As built (F5), then the builder as first specified (§3.5).

## F5. Step 2, Model groups (its own tab, **2. Model groups**; §3.5 as built so far)
- **One task at a time,** in the Data wizard's frame (steps on the left, ✅ ⚠ ❌ marks, Back and Next at the bottom
  right): **How to start** › **Build the groups** › **Check them** › **Tag and write** › **What each group got**. Each
  tab will work this way (Bring in data and Check sales next): the run is a step whose button is where Next is, its
  progress fills that step, and when it's done the results open by themselves; the results are steps, not dialogs;
  **Looks right › Check sales** is the last step's Next. The tab opens on the first step not done (on the results when
  they're up to date).
  - **How to start:** the two choices; once started, starting again asks first ("This replaces your 6 groups").
  - **Build the groups:** the builder below, filling the step. Next saves unsaved changes (**Save and continue ›**).
  - **Check them:** each saved group's parcels and sales with its checks, Unassigned last; ⚠ on the step when any needs
    a look. None stops the run.
    - **Model it** (first column, a tick per group; added 2026-10-31): what to do with each group. Ticked by default
      only with enough improved sales to model (15). A group not ticked is greyed, "Not modeled", with nothing left to
      look at, here and after: in Check sales' time adjustment (no choice; never borrowed from), Check my values (not
      offered), the variable tests (skipped) and Model values (every model skipped: OpenAVMKit
      `instructions.main.skip.<group>`; "Not modeled" in its tables). Saved with the groups (`modeled`); the
      tag-and-write run doesn't depend on it.
  - **Tag and write:** the formats, then **Tag and write ›** (**Tag and write again ›** when out of date); progress
    while it runs, with **Stop**; then the results. Up to date, it says when it was written, with **Tag and write
    again** beside **Next ›**.
  - **What each group got:** what the receipt dialog showed; **Looks right › Check sales** marks notebook 1 done and
    opens Check sales.
- **Land use & building type on Data.** A Data wizard step under More details asks for **Land use** (`land_class`) and
  **Building type** (`bldg_type`), with building description, class, units and stories under More. Both are guessed from
  common column names (`LAND_USE`, `LUC`, `PROP_CLASS`, `BLDG_TYPE`…). Model groups are made from these, so they need to
  be in the parcel universe.
  - **Your own fields:** any other column of a parcel file (the parcel universe or a file joined to it), loaded under a
    name the user chooses. The name can be one of OpenAVMKit's own input fields that nothing else sets (zoning,
    bldg_rooms_bed, bldg_style…: 51 of them), loaded under OpenAVMKit's name so it's treated as OpenAVMKit treats it.
    Refused, saying why: the IDs, geometry and polar coordinates, and what OpenAVMKit works out itself ("OpenAVMKit
    works out sale_year itself"); what's filled in as Bring in data runs (condo_group, census_*, dist_to_*; and true_*,
    synthetic data's answer key); and a field with its own row in the wizard ("land_class has its own row in the wizard
    (Land use): pick its column there"). Each one has a class, **Land/location**, **Improvement** or **Other**, and
    whether it's **a category** or **a number** (guessed from the column). This writes OpenAVMKit's
    `field_classification` (`land` / `impr` / `other`, `categorical` / `numeric`), and the field can be tested in model
    group rules. The line for a new one has **Add field** and, once anything is filled in, **×** to empty it without
    adding anything.
  - Names use lowercase letters, digits and underscores. OpenAVMKit's own field names, location fields' names and names
    already used are refused, with the reason shown. A refused add keeps what was typed.
  - Your own fields are one table: column, name, class, kind, values (the **N values** button, and a warning when there
    is one, such as how many values of a number aren't numbers and will be blank), and remove. Its last row adds one.
    Changing them puts Bring in data out of date ("your own fields").
- **How to start:** the first time, the user chooses **Start with suggested groups** or **Define my own from scratch**.
  Suggested groups are made from the values of land use, building type, building description and building class, by the
  words in them: condos and townhomes, small multi-family, apartments, manufactured homes, commercial and industrial,
  agricultural, public and exempt, then single-family. The specific kinds come first, so a duplex on residential land
  lands in small multi-family. A group is suggested only if some value matches, and suggesting needs one of those fields
  (otherwise it says to add one on Data).
- **Layout:** the ordered group list (left); the selected group's editor (middle); a full-height map (right) that can be
  **Docked**, **Full** (filling the editor's place) or hidden.
  - **List:** colour, name, parcels, improved and vacant sales, the worst check, and how many parcels moved in or out
    since the last save (+161, −161). Up/down buttons change the order. **Unassigned** is last, in grey; pressing it
    shows only those parcels on the map (every group switched off in the legend), and pressing it again, a legend square
    or **Show all** brings the rest back.
  - **Map legend:** each colour's square is a checkbox, filled while its parcels are shown and hollow when they're
    hidden (not drawn, and not clickable). By changes, the squares are where parcels move to, Unassigned, and no change.
    **Show all** appears while anything is hidden.
  - **Editor:** name, colour, parcels (vacant), improved sales, vacant sales, median sale price; the rule ("any of" /
    "all of" these conditions). Each condition is one line: the field (by name), the test, the values, ×. The values are
    one dropdown that lists what's chosen ("CONDO, TOWNHOUSE, TWINHOME  3 ▾") and opens a searchable checklist with each
    value's parcel count, **All** (or **All shown** while searching) and **Clear**; a value not listed can be typed in
    when the list is cut short. what moved since the last save, with **Show them on the map**; the checks; Delete group.
  - **Start from a field…:** pick a category field (land use first) and send each value (with parcels, vacant parcels
    and valid sales) to a group, or to a new one. Each group gets a condition on that field and keeps its others.
- **Live preview:** every edit is re-run (after a 200 ms pause) with OpenAVMKit's own filter code on the parcel universe
  Bring in data wrote, in order, first match wins, as its model-group tagging does; about 30 ms on the sample. Sales
  follow their parcel's group. Changes stay a draft until **Save groups**, which writes `modeling.model_groups` (`{id:
  {name, filter}}`, the id kept when renamed); **Undo changes** goes back to the saved groups. Saving doesn't put Bring
  in data out of date.
- **Checks per group:** its rule isn't finished; no parcel meets it; every parcel it meets is in a group above; under 15
  improved sales: too few to model; under 20: too few for a vertical-equity test; over 80% of its parcels look vacant
  (no building size), so building data may be missing for them. Unassigned: "N parcels in no group: they won't be
  valued".
- **Map:** the parcel shapes on OpenStreetMap tiles when online, plain background offline. Coloured by **Group**, or by
  **Changes** (parcels in a different group than when saved, coloured by their new group; the rest grey). The shapes are
  made once from Bring in data's results (`out/oakbox/groups/shapes.bin`, simplified to about half a metre, in
  degrees) and recoloured, not redrawn, on each preview.
- **Inspect:** clicking a parcel shows its key fields (address, land use, building type and description, units, size,
  year built, land size, zoning, neighbourhood, assessed value, and every field a rule tests), its valid sales, and why
  it's in its group: each group in order, with the values it was tested on, ✓ for the group it's in (and the conditions
  it met), and any later group it also meets. It also counts the parcels like it (the same values in the category fields
  the rules test) and how many sold, with **Show them on the map**.
- **Checked against OpenAVMKit:** a test runs OpenAVMKit's own `tag_model_groups` on the saved settings and gets the
  preview's counts.
- **The end of notebook 1 (assemble): Tag and write.** The **Tag and write** step runs OpenAVMKit's own
  `tag_model_groups_sup` and `write_notebook_output_sup("1-assemble")` on what Bring in data loaded
  (`out/oakbox/bring_in/sup.pickle`, so nothing is loaded again), in a process of its own (`python -m oakbox.assemble
  <project>`), like Bring in data. It runs on the saved groups: unsaved changes, no groups, or Bring in data out of date
  stop it, saying which.
  - **Written:** `out/1-assemble-sup.pickle` (what notebook 2, clean, starts from) and, in `out/look/`, the parcel
    universe, the sales and the hydrated sales as Parquet. **Formats** adds GeoPackage, zipped Shapefile or CSV, for map
    viewers and spreadsheets.
  - **What each group got** (a step): per model group, parcels, vacant parcels, improved and vacant sales (the sales get
    their parcel's group, as OpenAVMKit hydrates them), then Unassigned (`UNKNOWN`, not valued); whether every count
    matches the builder's preview (the preview's column shows when one doesn't); the files written, their size and what
    each is; **Show in folder**; OpenAVMKit's own warnings, folded.
  - **Looks right** marks notebook 1 done. Changing the groups or the formats, or running Bring in data again, puts it
    out of date (and un-done) until it runs again; a change on Data makes it wait for Bring in data (§6.4).
  - **Left out of notebook 1:** cloud sync (a desktop app's files are on the desktop), and street frontages
    (`enrich_sup_streets`: the street network is deferred, D29). Its "examine" cells are Bring in data's receipt;
    "examine in ridiculous detail" is each field's details (click its name).
- **Not yet:** common areas (deferred), hand edits (map lasso), nested AND/OR, undo/redo, export/import, and a map for
  very large counties (the shapes are sent whole: fine at 10k parcels, too much at 500k; vector tiles then).

## 3.5 Model group builder
Model groups are parcels valued together, for example single-family, condos, commercial and agricultural. **Vacant land
is not a model group of its own.** Vacant parcels stay in their model group and are valued by its main model. Vacant
sales are flagged (`vacant_sale`), so reports can break results out by improved/vacant. The builder shows
improved/vacant counts per model group.

**Layout:**
- **Left:** the ordered model group list, with colour, parcel count, and sale count split improved/vacant. "Unassigned"
  is always shown in grey.
- **Center:** a map coloured by model group. Clicking a parcel shows its attributes and *why* it landed in its model
  group ("matched rule 2 of Commercial"). A table toggle shows the same parcels as rows.
- **Right:** the rule editor for the selected model group.

**Ways to define a model group:**
1. **From a field.** Pick a field, such as land-use code. Oakbox lists the distinct values with counts, and the user
   assigns each value to a model group.
2. **Rule builder.** Conditions of the form *field / operator / value*, with AND/OR and nesting. It compiles to
   OpenAVMKit's filter lists.
   - On fields with blanks, it uses in-list/not-in-list, because `==`/`!=` silently send blank rows to Unassigned.
3. **Hand edits.** Lasso or click parcels on the map. These are saved as an explicit parcel list, and reports list them.

**Behavior:**
- **First match wins,** as in OpenAVMKit. Model groups can be dragged to reorder.
- **Unassigned parcels are not modeled.** OpenAVMKit labels them `UNKNOWN`. The health panel makes this loud.
- **Sales follow their parcel's model group.**
- **Live preview.** Each edit is re-evaluated against a cached parcel table, reproducing first-match-wins, common-area
  reassignment and the `UNKNOWN` fallback exactly. The target is under 2 seconds at 500k parcels.
- **Apply** writes the settings and warns that steps 3–5 will re-run, because fills, clusters, time adjustment, scrutiny
  and models are all per model group.
- **Health checks per model group:**
  - "Only 12 sales — too few to model reliably" (model warning under 15 sales)
  - "Too few sales for a vertical-equity test" (under 20)
  - "3,104 parcels unassigned"
  - "This rule matches nothing"
- **Advanced:** common areas.
  - Condo handling is *not* here. It runs at the start of step 1 and changes the row set, so it lives in the step 1
    settings.
- **Undo/redo.** Definitions can be exported and imported, to reuse across years or share with a neighbouring
  jurisdiction.

**Parcels put in a group by hand** (2026-11-07, from Models › Outliers: "it's in the wrong group"): a group keeps them
(`ModelGroup.keys`); they're in it whatever the rules say, and in no other (its filter `["or", ["isin", "key", …], rule]`,
every other group's `["and", ["notin", "key", …], rule]`). The map and checks count them (`groups.assign`). Not yet
listed on this page.
