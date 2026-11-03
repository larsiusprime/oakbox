"""Download-only fetch of a public OpenAVMKit sample locality (M0 spike).

Usage: python fetch_sample.py <base_dir> <cc/st/name> <slug>

Never uses cloud_sync (which can upload). Skips anything that isn't data or
settings: the container also holds PDFs, .py scripts and .pyc files.
"""

import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

CONTAINER = "https://landeconomics.blob.core.windows.net/localities-public"
ALLOWED = (".csv", ".parquet", ".geoparquet", ".json")


def main() -> None:
    base, prefix, slug = Path(sys.argv[1]), sys.argv[2].strip("/") + "/", sys.argv[3]
    listing = urllib.request.urlopen(f"{CONTAINER}?restype=container&comp=list&prefix={quote(prefix)}").read().decode("utf-8-sig")
    names = re.findall(r"<Name>(.*?)</Name>", listing)
    in_dir = base / "data" / slug / "in"
    total = 0
    for name in names:
        rel = name[len(prefix):]
        if not rel.lower().endswith(ALLOWED) or "__pycache__" in rel:
            print(f"skip {rel}")
            continue
        dest = in_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(f"{CONTAINER}/{quote(name)}").read()
        dest.write_bytes(data)
        total += len(data)
        print(f"got  {rel} ({len(data) // 1024} KB)")
    print(f"downloaded {total / 2**20:.1f} MB to {in_dir}")


if __name__ == "__main__":
    main()
