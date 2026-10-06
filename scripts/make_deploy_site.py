"""Stage only reader-facing files, for either of two purposes: static
hosting, or sending a snapshot directly to the team.

The generated `public/` directory also contains templates (unfilled
`__PLACEHOLDER__` tokens -- not meant to be opened directly) and
`mirror.html`, an internal QA tool, not a finished reader-facing
dashboard. Never upload or share that directory as-is: this script
creates a clean copy with just the linked dashboard pages, their
lazy-loaded reporter data, and the reader methodology page.

Two callers use this same output:

- `.github/workflows/refresh.yml` runs it after every data refresh and
  uploads `site_dist/` straight to GitHub Pages.
- Run it yourself (`python scripts/make_deploy_site.py`) any time you want
  a folder to zip and send to the team directly instead of (or before)
  pointing people at the live link -- every page in it still works opened
  directly (double-click `index.html`), no server needed on their end.
  (An earlier, separate `make_share_bundle.py` did this same job with a
  slightly different page list; retired in favor of this one script so
  there's a single, unambiguous "what actually gets shared/published"
  answer instead of two scripts that could silently drift apart.)
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "public"
OUTPUT_DIR = ROOT_DIR / "site_dist"
PAGES = ["index.html", "map.html", "monthly.html", "trade_pairs.html", "methodology.html"]
DATA_PAGES = ["index", "map", "monthly", "trade_pairs"]


def main() -> None:
    missing = [name for name in PAGES if not (PUBLIC_DIR / name).is_file()]
    missing.extend(
        f"data/{page}" for page in DATA_PAGES if not (PUBLIC_DIR / "data" / page).is_dir()
    )
    if missing:
        raise FileNotFoundError(
            "Build the dashboard pages before staging deployment; missing: " + ", ".join(missing)
        )

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for page in PAGES:
        shutil.copy2(PUBLIC_DIR / page, OUTPUT_DIR / page)

    (OUTPUT_DIR / "data").mkdir()
    for page in DATA_PAGES:
        shutil.copytree(PUBLIC_DIR / "data" / page, OUTPUT_DIR / "data" / page)

    print(f"Staged {len(PAGES)} reader pages and {len(DATA_PAGES)} data folders in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
