"""Download world country boundaries (Natural Earth, public domain) for the
map dashboard's choropleth.

This is the same underlying data source the old R/Shiny version of this
project used (the R package `rnaturalearth` just wraps Natural Earth's
files) -- 110m resolution, i.e. simplified enough for a whole-world view,
which keeps the file small since this ends up embedded directly in a
webpage later.

Boundaries basically never change, so unlike scripts/fetch_at_history.py
(re-run whenever export data should refresh) this only needs re-running if
the cached file goes missing or a newer/different resolution is wanted.

Writes:
  data/raw/ne_110m_admin_0_countries.geojson

Run it directly:
  python scripts/fetch_world_boundaries.py
"""

from pathlib import Path

import requests

URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector"
    "/master/geojson/ne_110m_admin_0_countries.geojson"
)

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
OUTPUT_PATH = RAW_DIR / "ne_110m_admin_0_countries.geojson"


def main() -> None:
    response = requests.get(URL, timeout=60)
    response.raise_for_status()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(response.content)
    print(f"Saved {OUTPUT_PATH} ({len(response.content) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
