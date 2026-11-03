# Sample data

Counties to try OAK box on, built from public data and then altered, so no record is anyone's own. Each folder
has its files under `in/`, a `README.md` saying what's in them and how they were altered, and the `make.py` that
built them (deterministic: rerun it and you get the same files).

| Folder | What it's for |
| --- | --- |
| [us-nc-guilford-synth](us-nc-guilford-synth/) | A slice of Guilford County, NC (9,400 parcels around downtown Greensboro), with the problems real exports have: IDs that don't match between files, a repeated and some blank parcel IDs, several building cards per parcel, coded sale fields, prices in odd formats, and map layers to join or measure to. |

To try one: **New project**, then in the Data wizard add the files from the folder's `in/` (copy them, so the sample
stays as it is): the parcel file on **Parcel universe**, the sales on **Sales**, and the rest (a building file, say) on
**More files**.
