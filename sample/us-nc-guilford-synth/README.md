# us-nc-guilford-synth

A made-up county laid out like Guilford County, NC's exports: about 5,100 parcels in eight neighborhoods
(Greensboro, High Point, Jamestown, Summerfield), 2,000 sales from 2019 to 2025, and a CAMA file of
building cards. Shapes are in NC State Plane (EPSG:2264, US feet). Values come from a simple formula
(land, building size, grade, condition, age, a 6.5% a year market trend) plus noise, so a model has
something real to find.

## Files

| File | Rows | Key columns |
| --- | --- | --- |
| `in/geo/parcels.parquet` | 5,135 shapes | `GDV_REID` (parcel ID), `PIN_PLUS_EXT`, `ACRES` (land, in acres), address, `NBHD`, 2022 assessed `LAND_VALUE` / `BLDG_VALUE` / `TOTAL_VALUE` |
| `in/cama.csv` | 4,959 building cards | `REID`, `CARD_NUM`, `HEATED_AREA` (sq ft), `YEAR_BUILT`, `EFF_YEAR`, `GRADE` (A–E), `COND` (EX–PR), `STORIES`, `BEDROOMS`, `FULL_BATHS`, `HALF_BATHS`; quality and condition again as `GRADE_PLUS` (B+, C-), `QUALITY_NUM` (1–10), `COND_DESC` (Average, Good…), `COND_NUM` (1–6) |
| `in/geo/school_zones.shp` | 8 polygons | School attendance zones: `ZONE_ID`, `ZONE_NAME`, `GRADES`. Every parcel is in one. |
| `in/geo/flood_zones.shp` | 8 polygons | Flood zones along creeks: `FLD_ZONE` (AE: 1% annual chance, X: 0.2%), `ZONE_SUBTY`. 400 parcels are in one. |
| `in/geo/zoning.geojson` | 16 polygons | Zoning districts: `ZONE_CODE`, `ZONE_DESC`. In degrees (EPSG:4326), unlike the rest. |
| `in/geo/lakes.shp` | 3 polygons | Lakes: `NAME`, `TYPE`. For distances (and the largest by area, by name). |
| `in/geo/rivers.shp` | 2 lines | Rivers and creeks: `NAME`, `TYPE`. Lines, so for distances only. |
| `in/geo/cbd.gpkg` | 1 polygon | Downtown Greensboro, the central business district, in a GeoPackage (layer `cbd`). |
| `in/geo/schools.shp` | 16 points | Schools: `SCHOOL`, `LEVEL`. Points, so for distances only. |
| `in/sales.csv` | 2,002 sales | `REID`, `PIN`, `DEED_DATE`, `SALE_PRICE`, `QUALIFIED` (Q/U), `VACANT_LOT` (Y/blank), and `PRICE_*`: the same prices in other formats (below) |

## Problems planted on purpose

1. **Parcel IDs don't match as is.** 86% of `GDV_REID`s are zero-padded to 10 characters (`0000118003`);
   the sales and CAMA files use the plain number (`118003`). Only about 12% of sales find their parcel until
   leading zeros are removed from the parcel IDs (then 98.8%).
2. **Trailing spaces.** 18 sales have a space after the `REID` (hand-keyed). Trimming takes the match to 99.7%.
3. **Sales of parcels that no longer exist.** 6 sales point at IDs combined away; they stay unmatched.
4. **One repeated parcel ID:** a parcel split on the map but not in the records (two shapes, one ID).
5. **14 blank parcel IDs:** right-of-way and common-area slivers.
6. **Several building cards per parcel.** About 3% of built parcels have a second card (`CARD_NUM` 2: a garage
   apartment, a barn), so the CAMA file has more than one row for them; keep card 1.
7. **No sale ID.** Make one from the parcel ID and date.
8. **Dates with a time**, as `DEED_DATE` exports do: `10/15/2019 0:00`.
9. **Nominal and unqualified deeds.** About 12% of sales are `U`; some are $10 deeds. A `PIN` column is on
   the sales too, hyphenated (`7802-07-0848`) unlike the parcel file's `PIN_PLUS_EXT` (`7802070848 000`).
10. **Prices written every which way.** The `PRICE_*` columns are `SALE_PRICE` again, as exports write it:

    | Column | Looks like | |
    | --- | --- | --- |
    | `PRICE_DOLLARS` | `$250,000.00` | |
    | `PRICE_COMMAS` | `250,000` | |
    | `PRICE_DECIMAL` | `250000.00` | |
    | `PRICE_PADDED` | `$   250,000.00 ` | fixed-width report |
    | `PRICE_EURO` | `250.000,00` | decimal comma |
    | `PRICE_THOUSANDS` | `250` | in $1,000s |
    | `PRICE_CENTS` | `25000000` | whole cents |
    | `PRICE_EXCEL` | `1.11E+06` over $1M | Excel rounded them: the exact price is lost |
    | `PRICE_SHORT` | `$250K`, `$1.11M` | |
    | `PRICE_MIXED` | all of the above, some blank, a few `N/A`, `-`, `TBD`, `0` | hand-kept |
    | `PRICE_NEGATIVE` | `(10)` for the $10 deeds | accounting negatives |
11. **Map layers for the Shapefiles section.** The `geo/` layers above: two polygon shapefiles to stamp onto
    parcels (school zones cover all of them; flood zones only some, so most parcels are "in none"), zoning as
    GeoJSON in a different coordinate system from the parcels, and lakes, rivers, the CBD and school points to
    measure distances to. Sale prices don't depend on these distances: they were drawn before the layers existed.
