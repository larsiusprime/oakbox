# Step 7, Report, and what goes in and out

As built (F10), then import, export and reports as first specified (§4).

## F10. Step 7, Report (its own tab, **7. Report**; built 2026-11-01, `report.py`, `ReportTab.tsx`)
Opens once Model values has had Looks right (the tab waits for it, as the others do). Reads Finalize's output; runs
nothing. Two steps:
- **Export:** every parcel, one row each: key, model group, model value, the roll's value, change from the roll (%),
  value per finished area, why there's no value (not modeled, left unvalued, below zero…), the latest sale in the study
  window (price, date) and the ratio of the value as made to it, latitude and longitude. **Format** (a switch): CSV,
  GeoPackage, Excel, Shapefile, GeoParquet; GIS formats carry each parcel's shape (Bring in data's), or a point where
  there's none (said). Written to `out/oakbox/report/export/<project>_<year>_model_values.<ext>`, with **Show in
  folder**. Shapefile: names cut to 10 characters with a `_fields.csv` key, a warning over 2 GB. Excel: split across
  sheets past 1,048,575 rows. On the synthetic sample (9,354 parcels): CSV 0.1 s, Excel 1.3 s, GeoPackage 1.4 s (7 MB).
- **Report:** a printable HTML page (settled 2026-11-01: HTML first, as good-looking as it can be made; Typst only if it
  falls short), previewed in the step, **Open in browser to print** (print, or save as PDF), and written to
  `out/oakbox/report/`. Calls: its **Title** (made from the project's name to start) and **Judge the values on** (the
  user decides: out of fold, held out, as valued; all three to start; at least one), saved as `project.report`. Its
  parts:
  - **In brief** (a board member's page): how many parcels got a value, then per model group a sentence with the figures
    and targets ("Single-family: values sit at 0.945 of sale prices at the median (low; target 0.95 to 1.10), COD 13.2
    (uniform; target 5 to 15), dearer and cheaper alike (VEI −2.1%); 158 sales. The roll on the same sales: 0.843, COD
    14.1."), groups with too few sales or none said so, and the groups with no model value and why. A set chosen with no
    sales is said, not dropped.
  - **Judged on … sales**, one per set chosen: per group, model values and the roll's on the same sales (in italics):
    sales, median ratio and its 90% interval, COD, PRD, PRB, VEI, CHD, vertical equity in words; marks that read in
    black and white (✓ met, ✗ missed, none: not judged).
  - **Across prices:** the median ratio by fifths of the sales by price, per group, against the target band (SVG).
  - **On the map:** each sale of the first set, by its ratio (SVG, no tiles: it prints).
  - **What every parcel got:** as on Model values.
  - **How the values were made:** the files, the sales kept and set aside, time adjustment, the ratio study's window and
    trimming, the standards, each group's models (and their variable lists), the variables, and what each statistic
    means.
  - Letter pages, a page break before the long sections, system fonts; the footer names OpenAVMKit's version and when
    the values were finalized.
- Not yet: picking sections, a logo and header text, filtering by location or class, saved presets and editable
  templates (§4.3).

## 4. Inputs, outputs and reports

## 4.1 Import and export
- **Import:** Shapefile (loose or zipped), GeoPackage, GeoJSON, Parquet/GeoParquet, CSV, Excel, and fixed-width text
  with a layout. Oakbox ships layouts for the PACS appraisal export versions it has been tested on (Travis CAD first);
  other layouts can be supplied as a simple field/start/width table. Zipped exports are opened in place, without
  unpacking by hand. Large exports are read straight from the zip as a stream, never unpacked to disk: the Travis CAD
  export is 0.5 GB zipped and 17.8 GB unpacked. Quick checks read only the columns they need (Travis: IDs from the 4.9
  GB property file in 20 s). Oakbox stores everything as GeoParquet in the project's `in/` folder; OpenAVMKit itself
  only reads CSV/Parquet. The parcel layer is loaded as OpenAVMKit's `geo_parcels`.
- **Export:** per-parcel values, flags and ratios as Parquet/GeoParquet, GeoPackage, Shapefile, CSV and Excel.
  - **Default format:** GeoPackage for GIS users, CSV for everyone else.
  - **Shapefile limits:** field names are cut to 10 characters, and files are capped at 2 GB. Oakbox warns and writes a
    field-name key.
  - **Excel limit:** about 1,048,576 rows. Larger exports are split across sheets, or CSV is suggested.

## 4.3 Reports and customization
- **Standard reports** (the model-values report is built, F10; the others are planned):
  - ratio study
  - equity studies
  - sales scrutiny
  - variables
  - model summary
- **Rendering:** printable HTML (built 2026-11-01, F10): the browser prints it or saves it as PDF. Typst (open source, a
  Python wheel with no system install) remains the fallback if HTML can't do what a report needs.
- **For everyone:** pick sections, filter by location or class, add a logo and header text, choose a standards profile.
  Saved as a per-project report preset.
- **For power users and consultants (planned):** editable report templates. **Open template folder** copies them into
  the project. Edited templates are validated, with a fallback to the stock template on error. Jurisdiction packs ship
  as template sets. (Written when reports were to be Typst; with reports in HTML, the template format is open.)
