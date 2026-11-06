# Step 1, Inputs: Bring in data

## F4. Step 1, Inputs: Bring in data (its own tab, **1. Inputs**)
- **One task at a time** (the frame of F5): **What runs** (❌ when Data has something to fix, with what changed since the
  last run) › **Bring in data** (the run: **Bring in data ›** where Next is, progress with Skip, then the results open)
  › **The parcel universe** › **The sales** (each with its funnel and fields) › **Public data and checks** (⚠ when
  public data was skipped or a check differs), whose Next is **Looks right › Model groups**.
- **Terms:** the joined parcel table is always the **parcel universe** and the joined sales table the **sales record**,
  here and in every message (the wizard's messages name the files holding them that way too).
- **Ready:** what will run (the parcel universe, the sales record, the files joined to them, the map layers, how many
  fields). It can't run while Data has a problem; the first is shown, with a link to Data.
- **Run:** OpenAVMKit's 1-assemble up to model groups (`load_dataframes`, `process_dataframes`), which needs no model
  groups and no engine change. It runs in a process of its own (`python -m oakbox.bring_in <project>`), so the app stays
  responsive and **Stop** ends it. It reports its steps; the page shows them, time so far, and time left from the last
  run. Results are written to `out/oakbox/bring_in/` via a temporary folder, so a stopped or failed run leaves the last
  receipt. A failure shows the last line of its log (`out/oakbox/bring_in.log`).
- **Receipt:** the counts, for the parcel universe and the sales record alike:
  - **Where the rows came from:** for the parcel universe, its file's rows, those without a parcel ID, repeated IDs, the
    parcels; for each file joined to it, its rows, blank IDs, extra rows, rows for parcels not in the parcel universe,
    and the parcels with and without a row from it (with a note when it holds the building size: OpenAVMKit treats a
    parcel without one as vacant land, building fields 0). For the sales record: its file's rows, those not valid by the
    valid-sale rule or column (OpenAVMKit leaves them out as it loads, so these are counted from the file), repeated
    sale IDs, valid sales, improved and vacant, and those that don't find a parcel.
  - **Fields:** every field (helpers left out), grouped as from your files, from map layers, and worked out by
    OpenAVMKit: how many have it, a summary (numbers: lowest, median, highest; years without a thousands comma;
    categories: how many values and the commonest; dates: the range; yes/no: the counts; IDs: "all different"), where it
    came from (file and column, "cleaned up", "your valid-sale rule", "made from the parcel ID and sale date"), and
    notes (0 for no building; measured from the shape; only parcels in a layer's shapes; farther than the distance limit
    is blank).
  - **Checked against Data:** what the wizard predicted (parcels, valid sales, share finding a parcel, parcels in each
    stamped layer) beside what OpenAVMKit got.
  - OpenAVMKit's own warnings, folded away; the libraries' notices only counted. Under the hood: the calls and their
    times, and what was written.
- **Each field in detail:** each field's name is a link with a faint magnifier, and its whole row highlights on hover;
  clicking either opens its details (notebook 1's "examine in ridiculous detail", one field at a time): for a number,
  its count, zeros, lowest, 10th/25th/50th/75th/90th percentiles, highest and mean; for everything else (and a number
  too), every value with its count, most common first and searchable (dates by year). Read from the one column, not the
  whole table.
- **Rows:** each count with rows behind it has **see them**, and each table **View all rows**: a dialog that reads one
  page (50 rows) at a time from Parquet written in 1,000-row groups, so a large parcel universe is never loaded whole,
  with **Export CSV**, streamed a row group at a time. Dropped rows show as written in their file.
- **Out of date:** when the settings it depends on (`data`, `field_classification`, `locality`) change, the step says
  what changed (a file added or removed, how a file is read, how the files join, map layers, the centre, location
  fields) and greys the last receipt until it runs again.
- **Looks right** is required: **2 Model groups** opens only once it's pressed on an up-to-date receipt, and closes
  again when Data changes.
