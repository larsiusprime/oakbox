# us-nc-guilford-synth

A slice of Guilford County, NC: downtown Greensboro north to Buffalo Lake. It holds about 9,400 parcels, their
building cards, and 3,800 sales from 2015 to 2024. Everything starts from Guilford's own public data, as OpenAVMKit's
sample locality publishes it. That data is then altered so no record is the county's own, and problems are planted
for OAK box to catch (below).

The slice is small enough to run quickly. It still has a usable single-family model group: about 5,200 houses and
1,400 qualified house sales since 2018. There are also about 1,100 condos.

## How it was made

`make.py` builds it. On its first run it downloads Guilford's files (about 300 MB) from
`https://landeconomics.blob.core.windows.net/localities-public/us/nc/guilford/` into `.cache/`, which isn't committed.
It keeps the parcels whose centres fall in the window. Coordinates are in NC State Plane (EPSG:2264, US feet):
x 1,760,000–1,772,000, y 843,000–862,000.

- **Shapes:** Guilford's own parcel shapes, in place.
- **Parcel IDs:** new ones. They are plain numbers, as Guilford's are, but not Guilford's.
- **Addresses:** real street names, but the house numbers are shuffled among the parcels on each street.
- **Buildings:** each parcel keeps its own building cards, nudged as a whole so the fields still agree.
  - Year built moves by up to 3 years, and the effective year moves with it (never before the year built).
  - Heated area and footprint move by up to 5%, together.
  - A parcel with no building, such as vacant land, still has none. Bedrooms, baths, grade and condition stay with
    their building.
- **Sales:** the real deeds, with these changes:
  - dates moved by up to a month, and prices nudged by about 3%: a deed's sales together, so the 123 deeds that
    sold several parcels at once keep them on one day at one price;
  - qualified/unqualified and improved/vacant kept as Guilford coded them;
  - about 12% of unqualified deeds recorded at a nominal $10.
- **Assessed values:** the 2022 revaluation's, each nudged by about 4%.
- **Map layers:** Guilford's own, cut to the window. The flood zones are the exception: they are bands drawn along
  the real streams, because the FEMA maps aren't in the sample container.

These are real market patterns, not a formula: a model has real things to find, but there's no "true value" to score
it against.

## Files

| File | Rows | Key columns |
| --- | --- | --- |
| `in/geo/parcels.parquet` | 7,999 shapes | `GDV_REID` (parcel ID), `PIN_PLUS_EXT`, `TOTAL_ACRES` (land, in acres), `LOCATION_ADDR`, `PHYADDR_CITY`, `PHYADDR_ZIP`, `NEIGHBORHOOD`, `LAND_CLASS`, `ZONING`, 2022 assessed `TOTAL_LAND_VALUE_ASSESSED` / `TOTAL_BLDG_VALUE_ASSESSED` / `TOTAL_PROP_VALUE` |
| `in/condo_units.csv` | 1,360 condo units | The units without a shape of their own: the parcel file's columns (`REID` the plain parcel ID, `PIN_PLUS_EXT` with the unit's extension, `-001` and on), no geometry. Their building's parcel (`-000`) is in `parcels.parquet`. |
| `in/building.csv` | 6,864 building cards | `REID`, `BLDG_CARD`, `BLDG_DESC` / `BLDG_TYPE` (01-SFR, 04-CONDO…), `UNITS`, `HEATED_AREA` and `MB_FOOTPRINT_AREA` (sq ft), `STYLE`, `EXTERIOR`, `HEATING`, `AIR_COND`, `YEAR_BUILT`, `EFF_YEAR`, `BEDROOMS`, `BATH_FULL`, `BATH_HALF`; quality three ways, as Guilford writes it: `GRADE` (`B+5  130%`), `GRADE_LETTER` (AA–E), `GRADE_SCORE` (1.3); condition likewise: `CONDITION` (`A  12%`), `CONDITION_CODE`, `CONDITION_SCORE`; and as other systems combine them: `QC_RATING` (`Q3C2`, `Q3/C2`: UAD-style quality and condition in one value, 1 best) and `CDU` (EX … PR) |
| `in/sales.csv` | 3,804 sales | `REID`, `PIN`, `SALE_DATE`, `DEED_BOOK`, `DEED_PAGE`, `SALE_PRICE`, `SALE_STATUS` (QUALIFIED / UNQUALIFIED), `SALE_TYPE` (IMPROVED / VACANT, some blank), and `PRICE_*`: the same prices in other formats (below) |
| `in/permits.csv` | 2,140 permits | Made up: `PERMIT_NO`, `REID` (the plain parcel ID), `ISSUE_DATE` (2011–2025, year-month-day), `WORK_CLASS` (ALTERATION, REROOF, ADDITION, ELECTRICAL, NEW CONSTRUCTION, DEMOLITION, POOL), `VALUATION` |
| `in/geo/zoning.geojson` | 588 polygons | Zoning districts: `ZONING` (R-5, C-M…), `CLASSIFICATION` (RESIDENTIAL, COMMERCIAL…). In degrees (EPSG:4326), unlike the parcels. |
| `in/geo/school_districts.shp` | 4 polygons | School board districts: `DISTRICT`. Every parcel is in one. |
| `in/geo/flood_zones.shp` | 2 polygons | `FLD_ZONE` (AE: 1% annual chance, within 150 ft of a stream; X: 0.2%, to 400 ft), `ZONE_SUBTY`. 331 parcels are in one. |
| `in/geo/lakes.shp` | 1 polygon | Buffalo Lake: `MAJORLAKES`. For distances. |
| `in/geo/streams.shp` | 2 lines | North Buffalo Creek and Muddy Creek: `NAME`. Lines, so for distances only. |
| `in/geo/cbd.gpkg` | 1 polygon | Downtown Greensboro, the central business district, in a GeoPackage (layer `cbd`), in degrees. |
| `in/geo/universities.shp` | 6 points | UNCG, NC A&T and others: `name`. Points, so for distances only. |
| `in/geo/parks.shp` | 38 polygons | Parks: `name`. No `.prj` (below). |

## Problems planted on purpose

1. **Parcel IDs don't match as is.** 86% of `GDV_REID`s are zero-padded to 10 characters (`0000118003`). The sales
   and building files use the plain number (`118003`). Only 14% of sales find their parcel until leading zeros
   are removed from the parcel IDs; after that, 99.3% do.
2. **Trailing spaces.** 18 sales have a space after the `REID` (hand-keyed). Trimming takes the match to 99.8%.
3. **Sales of parcels that no longer exist.** 6 sales point at IDs combined away; they stay unmatched.
4. **One repeated parcel ID:** a parcel split on the map but not in the records (two shapes, one ID).
5. **4 blank parcel IDs:** Guilford's own right-of-way shapes with no ID.
6. **Several building cards per parcel.** 115 parcels have more than one card (Guilford's own, 124 extra rows),
   so the building file has more than one row for them. Keep card 1.
7. **No sale ID.** Make one from the parcel ID and date.
8. **Dates with a time**, as Guilford's exports write them: `8/8/2023 15:13`.
9. **Codes, not yes/no.** Valid and vacant sales are `SALE_STATUS` and `SALE_TYPE` codes, so they need rules.
   116 unqualified deeds are for $10. A `PIN` column is on the sales too, hyphenated (`7864-34-8966`), unlike the
   parcel file's `PIN_PLUS_EXT` (`7864348966-000`).
10. **Land in acres** (`TOTAL_ACRES`), building area in square feet.
11. **Prices written every which way.** The `PRICE_*` columns are `SALE_PRICE` again, as exports write it:

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
12. **Quality and condition written every which way.**
    - `GRADE` and `CONDITION` are a code and a percent in one value.
    - `CONDITION_SCORE` is % depreciation as a fraction (it rises with age), not % good.
    - `CONDITION_CODE` is "A" on every card.
    - `QC_RATING` holds quality and condition in one value, separated differently from row to row.
    - `CDU` mixes condition with desirability and utility.
13. **Map layers that differ from the parcels.**
    - Zoning is GeoJSON in degrees, and the CBD a GeoPackage in degrees; the parcels are in State Plane feet.
    - Flood zones cover only some parcels, so most are "in none".
    - Streams are lines and universities points, so they're for distances only.
    - `parks.shp` lost its `.prj`, so it has no coordinate system and can't be placed until one is supplied.
14. **Condo units on the roll, not on the map.** As many counties keep them, 1,360 condo units (and office condos) have
    no shape of their own: they're rows of `condo_units.csv`. Their building's parcel, the PIN's `-000` extension, is in
    `parcels.parquet`; a unit's PIN starts with its building's (`7865782948-030` is in `7865782948-000`). Until they're
    set up as units, their sales and building cards find no parcel. The four complexes without a `-000` parcel keep
    their units' shapes.
15. **Teardowns.** 40 improved, qualified sales are followed by a `DEMOLITION` permit 20 to 330 days later: the buyer
    bought the land. With the permits step set up, they're counted as vacant sales.
16. **Sales of several parcels on one deed.** 123 deeds (`DEED_BOOK`/`DEED_PAGE`) record two or more sales on the same
    day, Guilford's own: one transaction of several parcels, each given the whole price or a share. Sales scrutiny
    sets them aside once the Deeds step names the deed.
