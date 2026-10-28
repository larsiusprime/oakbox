"""Robustness check for the wizard's reading of sales that find no parcel (SPEC F3d): IDs written differently
(Reconcile), parcels missing from the parcel universe, another numbering, keying slips.

8 parcel ID schemes x 7 situations, 10,000 parcels and 6,000 sales each, run through OAK box's own wizard via its
API. About 25 seconds:

    OAKBOX_HOME=$(mktemp -d) uv run python tools/id_robustness.py $(mktemp -d)

Prints one JSON line per run and writes results.json; every run's "got" should equal its "expect" (F: "missing"
with a keying-slips line)."""

import json
import random
import string
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from fastapi.testclient import TestClient
from shapely.geometry import box

from oakbox.app import create_app

OUT = Path(sys.argv[1])
N = 10_000
SALES = 6_000
R = random.Random(7)
D = string.digits


def digits(r, n):
    return "".join(r.choice(D) for _ in range(n))


# ---------- 8 schemes: (name, make(r) -> canonical id, how a sales file might write it differently) ----------
SCHEMES = {
    # 1 Guilford-style: plain integer account; the parcel file zero-pads to 10
    "plain_int_padded": (lambda r: str(r.randint(100_000, 999_999)), "parcel file pads to 10"),
    # 2 NC PIN: 10 digits, written hyphenated 4-2-4 in other files
    "nc_pin": (lambda r: digits(r, 10), "hyphenated 7865-74-3125"),
    # 3 Arizona book-map-parcel with optional letter suffix
    "az_bmp": (
        lambda r: (
            f"{r.randint(100, 999)}-{r.randint(1, 99):02d}-{r.randint(1, 999):03d}"
            + (r.choice("ABC") if r.random() < 0.15 else "")
        ),
        "no dashes 10123045A",
    ),
    # 4 Texas PACS property ID: variable-length integer, 1 to 7 digits
    "tx_pacs_varlen": (lambda r: str(int(10 ** r.uniform(0, 7))), "zero-padded to 8"),
    # 5 Cook County 14-digit PIN, written 17-04-321-012-0000
    "cook_pin14": (
        lambda r: (
            f"{r.randint(1, 33):02d}-{r.randint(1, 36):02d}-{r.randint(100, 999)}-{r.randint(1, 99):03d}-"
            f"{r.choice(['0000', '1001', '1002', '8001'])}"
        ),
        "digits only 17043210120000",
    ),
    # 6 California APN 3-3-2, some files with spaces
    "ca_apn": (
        lambda r: f"{r.randint(1, 999):03d}-{r.randint(1, 999):03d}-{r.randint(1, 99):02d}",
        "spaces 123 456 78",
    ),
    # 7 Denver-style schedule number with letter prefix: R0123456 (M for mobile homes)
    "letter_prefix": (lambda r: r.choice("RRRRRM") + digits(r, 7), "lower case r0123456"),
    # 8 Tennessee-style dotted map/group/parcel: 045.07-02-019.000
    "tn_dotted": (
        lambda r: (
            f"{r.randint(1, 150):03d}{r.choice(['', '.' + str(r.randint(1, 20)).zfill(2)])}-"
            f"{r.choice(['', 'A', 'B'])}{r.randint(1, 30):02d}-{r.randint(1, 99):03d}.{r.choice(['00', '000'])}"
        ),
        "county prefix 081-",
    ),
}


def universe_ids(make, r):
    s = set()
    while len(s) < N:
        s.add(make(r))
    return sorted(s)


def fresh(make, r, avoid, n):
    out = set()
    while len(out) < n:
        v = make(r)
        if v not in avoid:
            out.add(v)
    return list(out)


# ---------- How a sales file can differ (the "written differently" transforms) ----------
def tidy(scheme, v):  # the scheme's typical alternate writing, fixable or not
    if scheme == "plain_int_padded":
        return v  # handled by padding the parcel side
    if scheme == "nc_pin":
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    if scheme == "az_bmp":
        return v.replace("-", "")
    if scheme == "tx_pacs_varlen":
        return v.zfill(8)
    if scheme == "cook_pin14":
        return v.replace("-", "")
    if scheme == "ca_apn":
        return v.replace("-", " ")
    if scheme == "letter_prefix":
        return v.lower()
    if scheme == "tn_dotted":
        return "081-" + v


def base_written(scheme, v, differently):  # how the parcel file writes its own IDs
    return v.zfill(10) if differently and scheme == "plain_int_padded" and R.random() < 0.86 else v


# ---------- Scenarios: what the sales file holds, and what the right answer is ----------
# expect: "missing" (parcels missing), "reconcile" (IDs written differently), "wrong_id" (not the same IDs at all),
# "fine" (>= 95% match: nothing to say)
def scenarios(scheme, make, ids):
    r = random.Random(hash(scheme) & 0xFFFF)
    sold = [r.choice(ids) for _ in range(SALES)]
    extra = fresh(make, r, set(ids), 1_500)
    out = {}
    # A: 20% of sales are of parcels kept off the map (condo units): same scheme, new IDs
    a = sold[: int(SALES * 0.8)] + [r.choice(extra) for _ in range(int(SALES * 0.2))]
    out["A_missing_20pct"] = (a, "missing", extra)
    # B: every sale written the scheme's other way (fixable or not)
    out["B_written_differently"] = ([tidy(scheme, v) for v in sold], "reconcile", None)
    # C: written differently AND 20% missing
    out["C_both"] = ([tidy(scheme, v) for v in a], "reconcile", extra)
    # D: wrong ID column: same-looking IDs from another numbering (disjoint)
    other = fresh(make, r, set(ids), 3_000)
    out["D_wrong_column"] = ([r.choice(other) for _ in range(SALES)], "wrong_id", None)
    # E: a few trailing spaces (3%) and 15% missing
    e = [v + " " if r.random() < 0.03 else v for v in sold[: int(SALES * 0.85)]] + [
        r.choice(extra) for _ in range(int(SALES * 0.15))
    ]
    out["E_spaces_and_missing"] = (e, "reconcile", extra)

    # F: 8% hand-keyed typos (one digit changed): look like parcel IDs but aren't
    def typo(v):
        i = [k for k, c in enumerate(v) if c.isdigit()]
        k = r.choice(i)
        return v[:k] + str((int(v[k]) + 1) % 10) + v[k + 1 :]

    out["F_typos_8pct"] = ([typo(v) if r.random() < 0.08 else v for v in sold], "missing_or_typos", None)
    # G: only 3% missing: under the 5% that's worth a word
    out["G_missing_3pct"] = (
        sold[: int(SALES * 0.97)] + [r.choice(extra) for _ in range(int(SALES * 0.03))],
        "fine",
        None,
    )
    return out


c = TestClient(create_app())


def put(pid, n, **b):
    body = {
        "holds": None,
        "universe": False,
        "match": None,
        "id_column": None,
        "extra_field": None,
        "extra_column": None,
        "dupes": None,
        "dupes_sort": None,
        "dupes_desc": False,
        "blank_ok": None,
        **b,
    }
    return c.put(f"/api/projects/{pid}/wizard/files/{n}", json=body)


rows = []
for scheme, (make, _how) in SCHEMES.items():
    ids = universe_ids(make, random.Random(len(scheme)))
    shapes = len({__import__("re").sub(r"[A-Za-z]", "A", __import__("re").sub(r"\d", "9", v)) for v in ids})
    for name, (sales, expect, extra) in scenarios(scheme, make, ids).items():
        d = OUT / scheme / name
        d.mkdir(parents=True, exist_ok=True)
        gpd.GeoDataFrame(
            {"PID": [base_written(scheme, v, name[0] in "BC") for v in ids]},
            geometry=[box(i % 100, i // 100, i % 100 + 1, i // 100 + 1) for i in range(N)],
            crs=2264,
        ).to_parquet(d / "parcels.parquet")
        pd.DataFrame({"PID": sales, "SALE_PRICE": 100_000, "SALE_DATE": "2024-01-02"}).to_csv(
            d / "sales.csv", index=False
        )
        files = [("parcels", "parcels.parquet"), ("sales", "sales.csv")]
        if extra is not None:  # the file that has the missing parcels, in the project but not joined
            pd.DataFrame({"PID": extra, "UNIT_AREA": 900}).to_csv(d / "units.csv", index=False)
            files.append(("units", "units.csv"))
        pid = c.post(
            "/api/projects",
            json={
                "name": f"{scheme}-{name}",
                "country": "US",
                "region": "NC",
                "jurisdiction": "X",
                "tax_year": 2026,
                "valuation_date": "2026-01-01",
            },
        ).json()["id"]
        for n, f in files:
            assert (
                c.post(f"/api/projects/{pid}/files", json={"path": str(d / f), "mode": "copy", "name": n}).status_code
                == 200
            )
        put(pid, "parcels", universe=True, id_column="PID")
        t = time.time()
        w = put(pid, "sales", holds="sales", id_column="PID").json()
        secs = time.time() - t
        sf = next(f for f in w["files"] if f["name"] == "sales")
        share = sf["id_check"]["share"]
        miss = sf["not_in_universe"]
        sug = (
            c.post(
                f"/api/projects/{pid}/wizard/files/sales/reconcile",
                json={"file_steps": [], "base_steps": [], "view": "unmatched", "seed": 0, "suggest": True},
            )
            .json()
            .get("suggestion")
        )

        def verdict(share, miss):
            if share >= 0.95:
                return "fine"
            if miss:
                return "wrong_id" if miss["kind"] == "other_id" else "missing"
            return "reconcile"

        got = verdict(share, miss)
        slips = bool(miss and any("keying slips" in line for line in miss["lines"]))
        got2 = None
        if sug and name.startswith("C"):  # apply the suggested clean-up, then ask again
            c.put(
                f"/api/projects/{pid}/wizard/files/sales/reconcile",
                json={"file_steps": sug["file_steps"], "base_steps": sug["base_steps"]},
            )
            w2 = c.get(f"/api/projects/{pid}/wizard").json()
            f2 = next(f for f in w2["files"] if f["name"] == "sales")
            got2 = (
                verdict(f2["id_check"]["share"], f2["not_in_universe"]),
                round(f2["id_check"]["share"], 3),
                bool(f2["not_in_universe"] and any(" are in units " in x for x in f2["not_in_universe"]["lines"])),
            )
        holder = bool(miss and any(" are in units " in line for line in miss["lines"]))
        rows.append(
            dict(
                scheme=scheme,
                scenario=name,
                expect=expect,
                got=got,
                share=round(share, 3),
                suggestion=(sug or {}).get("text"),
                sug_share=round((sug or {}).get("share", 0), 3),
                holder=holder,
                slips=slips,
                after_cleanup=got2,
                shapes=shapes,
                secs=round(secs, 2),
                first=(miss or {}).get("lines", [""])[0][:90],
            )
        )
        print(json.dumps(rows[-1]), flush=True)
json.dump(rows, open(OUT / "results.json", "w"), indent=1)
