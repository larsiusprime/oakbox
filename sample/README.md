# Sample data

Made-up counties to try OAK box on. Nothing here is real data. Each folder has its files under `in/`,
a `README.md` saying what's in them, and the `make.py` that built them (deterministic: rerun it and you get
the same files).

| Folder | What it's for |
| --- | --- |
| [us-nc-guilford-synth](us-nc-guilford-synth/) | Guilford County-style files with the problems real exports have: IDs that don't match between files, a repeated and some blank parcel IDs, several building cards per parcel. |

To try one: **New project**, then in the Data wizard add the files from the folder's `in/` (copy them, so the sample
stays as it is): the parcel file on **Parcel universe**, the sales on **Sales**, and the rest (a CAMA file, say) on
**More files**.
