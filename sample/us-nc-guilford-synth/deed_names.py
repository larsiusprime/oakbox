"""Made-up buyers and sellers for the sample's sales (GRANTOR, GRANTEE), the way a recorder writes them: SURNAME GIVEN
in capitals, couples joined with &, companies, banks and trusts. Some sales are between family (a shared surname),
some buyers buy several parcels within a year (investors, builders). Its own random stream, so nothing else changes.

make.py adds them; `python deed_names.py` adds them to in/sales.csv as it is.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SURNAMES = (
    "SMITH JOHNSON WILLIAMS BROWN JONES GARCIA MILLER DAVIS RODRIGUEZ MARTINEZ HERNANDEZ LOPEZ GONZALEZ WILSON "
    "ANDERSON THOMAS TAYLOR MOORE JACKSON MARTIN LEE PEREZ THOMPSON WHITE HARRIS SANCHEZ CLARK RAMIREZ LEWIS "
    "ROBINSON WALKER YOUNG ALLEN KING WRIGHT SCOTT TORRES NGUYEN HILL FLORES GREEN ADAMS NELSON BAKER HALL RIVERA "
    "CAMPBELL MITCHELL CARTER ROBERTS PATEL O'NEAL MCALLISTER DAWSON-REID OKAFOR"
).split()
GIVEN = (
    "JAMES MARY ROBERT PATRICIA JOHN JENNIFER MICHAEL LINDA DAVID ELIZABETH WILLIAM BARBARA RICHARD SUSAN JOSEPH "
    "JESSICA THOMAS SARAH CHARLES KAREN DANIEL LISA MATTHEW NANCY ANTHONY BETTY MARK SANDRA DONALD ASHLEY"
).split()
COMPANIES = (
    "TRIAD HOMES LLC",
    "GATE CITY PROPERTIES LLC",
    "PIEDMONT INVESTMENTS INC",
    "OPENDOOR PROPERTY J LLC",
    "FIRST NATIONAL BANK",
    "WELLS FARGO BANK NA",
    "SECRETARY OF HOUSING AND URBAN DEVELOPMENT",
    "CITY OF GREENSBORO",
    "D R HORTON INC",
    "HABITAT FOR HUMANITY OF GREATER GREENSBORO INC",
)
BUILDERS = COMPANIES[:4] + COMPANIES[8:9]  # buy several parcels in a year


def _person(rng: np.random.Generator, surname: str | None = None) -> str:
    s = surname or rng.choice(SURNAMES)
    given = rng.choice(GIVEN)
    middle = f" {rng.choice(list('ABCDEJKLMRSTW'))}" if rng.random() < 0.6 else ""
    if rng.random() < 0.35:  # a couple: SMITH JOHN A & MARY
        return f"{s} {given}{middle} & {rng.choice(GIVEN)}"
    return f"{s} {given}{middle}"


def add(sales: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(777)
    n = len(sales)
    sellers, buyers = [], []
    for _ in range(n):
        r = rng.random()
        if r < 0.04:  # between family: the same surname on both sides
            s = rng.choice(SURNAMES)
            sellers.append(_person(rng, s))
            buyers.append(_person(rng, s))
            continue
        sellers.append(rng.choice(COMPANIES) if rng.random() < 0.12 else _person(rng))
        buyers.append(rng.choice(BUILDERS) if r < 0.12 else _person(rng))
    trusts = rng.random(n) < 0.03
    for i in np.flatnonzero(trusts):
        sellers[i] = f"{rng.choice(SURNAMES)} FAMILY TRUST"
    out = sales.copy()
    out["GRANTOR"] = sellers
    out["GRANTEE"] = buyers
    return out


if __name__ == "__main__":
    path = Path(__file__).parent / "in" / "sales.csv"
    sales = pd.read_csv(path, dtype=str, keep_default_na=False)
    add(sales.drop(columns=["GRANTOR", "GRANTEE"], errors="ignore")).to_csv(path, index=False)
