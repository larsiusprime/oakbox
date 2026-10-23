"""Writes src/oakbox/locales.json: per country, its currency and how it writes numbers, from Unicode CLDR.

Run when CLDR changes (babel is only needed here, not in the app):

    uv run --with babel python packaging/make_locales.py
"""

import json
from pathlib import Path

from babel import Locale, numbers
from babel.languages import get_official_languages

ROOT = Path(__file__).resolve().parent.parent
countries = [c["code"] for c in json.loads((ROOT / "src/oakbox/iso3166.json").read_text())["countries"]]
# OAK box's number styles: how the decimal mark and thousands separator are written.
STYLES = {
    (".", ","): "1,234.56",
    (",", "."): "1.234,56",
    (",", " "): "1 234,56",
    (".", "'"): "1'234.56",
    (".", " "): "1 234.56",
}
SPACES = {" ", " ", " "}
IMPERIAL = {"US", "LR", "MM"}  # countries that measure land in feet and acres


def locale_for(country: str) -> Locale | None:
    for lang in [*get_official_languages(country, de_facto=True), "en"]:
        try:
            return Locale.parse(f"{lang}_{country}")
        except Exception:  # noqa: BLE001 - no CLDR data for that pair
            continue
    return None


out = {}
for code in countries:
    loc = locale_for(code)
    currencies = numbers.get_territory_currencies(code, tender=True)
    style = "1,234.56"
    if loc is not None:
        dec, grp = numbers.get_decimal_symbol(loc), numbers.get_group_symbol(loc)
        grp = " " if grp in SPACES else "'" if grp in ("'", "’") else grp
        style = STYLES.get((dec, grp), "1,234.56")
    out[code] = {
        "currency": currencies[0] if currencies else "USD",
        "numbers": style,
        "units": "imperial" if code in IMPERIAL else "metric",
    }

en = Locale("en")
used = sorted({v["currency"] for v in out.values()} | {"USD", "EUR", "GBP", "JPY", "CNY", "INR", "CAD", "AUD"})
currencies = [
    {"code": c, "name": en.currencies.get(c, c), "symbol": numbers.get_currency_symbol(c, "en")} for c in used
]
(ROOT / "src/oakbox/locales.json").write_text(
    json.dumps({"countries": out, "currencies": currencies}, indent=1, ensure_ascii=False) + "\n"
)
print(len(out), "countries,", len(currencies), "currencies")
