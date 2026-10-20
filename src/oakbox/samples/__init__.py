"""Public sample counties: where to download them, and the pre-filled guided build for each.

Samples are fetched download-only from OpenAVMKit's public Azure container.
Only data and settings files are kept; anything else there (PDFs, scripts) is
skipped and never executed.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from oakbox.setup import Setup, StageId

CONTAINER = "https://landeconomics.blob.core.windows.net/localities-public"
DATA_SUFFIXES = (".csv", ".parquet", ".geoparquet")


@dataclass(frozen=True)
class Sample:
    id: str
    name: str
    description: str
    prefix: str
    files: tuple[str, ...]

    def _data(self) -> dict:
        return json.loads(resources.files("oakbox.samples").joinpath(f"{self.id}.json").read_text())

    def setup(self) -> Setup:
        """The sample's decisions. File paths are relative to the project's in/ folder."""
        return Setup.model_validate(self._data()["setup"])

    def notes(self) -> dict[StageId, str]:
        """Walkthrough notes shown on each stage (SPEC §3.2)."""
        return self._data()["notes"]


SAMPLES = {
    "us-va-petersburgcity": Sample(
        id="us-va-petersburgcity",
        name="City of Petersburg, Virginia",
        description="About 14,500 parcels. A small city that runs quickly.",
        prefix="us/va/petersburgcity/",
        files=("parcels.geoparquet", "petersburg-dbo-cama-fix.parquet"),
    ),
}


def list_remote(prefix: str) -> list[tuple[str, int]]:
    """Names and sizes of the blobs under ``prefix``."""
    url = f"{CONTAINER}?restype=container&comp=list&prefix={quote(prefix)}"
    xml = urllib.request.urlopen(url, timeout=60).read().decode("utf-8-sig")
    names = re.findall(r"<Name>(.*?)</Name>", xml)
    sizes = [int(s) for s in re.findall(r"<Content-Length>(\d+)</Content-Length>", xml)]
    return list(zip(names, sizes, strict=True))


def download(
    sample: Sample,
    in_dir: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> int:
    """Download the sample's data files into ``in_dir``. Returns bytes written."""
    wanted = {sample.prefix + f for f in sample.files}
    blobs = [(n, s) for n, s in list_remote(sample.prefix) if n in wanted and n.lower().endswith(DATA_SUFFIXES)]
    missing = wanted - {n for n, _ in blobs}
    if missing:
        raise FileNotFoundError(f"Sample files not found on the server: {sorted(missing)}")
    total = sum(s for _, s in blobs)
    done = 0
    in_dir.mkdir(parents=True, exist_ok=True)
    for name, _ in blobs:
        rel = name[len(sample.prefix) :]
        dest = in_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(f"{CONTAINER}/{quote(name)}", timeout=120) as resp, tmp.open("wb") as fh:
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if on_progress:
                    on_progress(done, total, rel)
        tmp.replace(dest)
    return done
