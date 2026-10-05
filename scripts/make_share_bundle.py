"""Copies the finished, reader-facing pages into one clean, self-contained
folder ready to zip and send directly to the team -- a different
distribution channel from the live GitHub Pages URL
(scripts/refresh_all.py + .github/workflows/refresh.yml), for sharing a
snapshot by email/Slack/Drive instead of (or alongside) pointing people at
the live link. The folder is self-contained on purpose: every page still
works opened directly as a local file (double-click), the same as
anywhere else in this project -- nobody receiving it needs to run
anything or have Python installed.

Deliberately leaves two things out of the bundle:

- Every `*.template.html` file -- these are build *sources*, not pages
  meant to be opened directly (open one and you'll see literal
  `__PLACEHOLDER__` tokens instead of real numbers, which would look
  broken to someone who doesn't know what a template is).
- `mirror.html` -- an internal data-quality/QA tool, not a finished
  reader-facing dashboard (its own tab in the site nav is styled
  muted/italic and literally tooltips "not intended for publication").
  Everything else built from `public/*.template.html` is reader-facing
  and gets included.

Run it any time after a data refresh (scripts/refresh_all.py), once the
`public/` folder it reads from is up to date:

    python scripts/make_share_bundle.py

Writes to `public_share/` at the project root -- cleared and rebuilt
fresh every run, not meant to be committed to git (same reasoning as
`public/data/*.js` already being build output: regenerating it is cheap
and keeping an old copy around would just go stale).
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "public"
OUTPUT_DIR = ROOT_DIR / "public_share"

# Every reader-facing page this project builds, except mirror.html (see
# the module docstring above for why). Each one's own "data/<page>/"
# folder (the other five reporters' lazily-loaded JS files) gets copied
# alongside it automatically, since the pages themselves reference those
# by a relative path like "data/map/de.js" -- the bundle has to keep that
# same folder layout intact for the links between tabs and the reporter
# picker to keep working once this is unzipped somewhere else.
PAGES = ["index.html", "map.html", "monthly.html", "trade_pairs.html", "dashboard.html"]


def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for page in PAGES:
        source = PUBLIC_DIR / page
        if not source.exists():
            print(f"Skipping {page}: not found in {PUBLIC_DIR} -- run the build scripts first.")
            continue
        shutil.copy2(source, OUTPUT_DIR / page)

    data_source = PUBLIC_DIR / "data"
    if data_source.exists():
        shutil.copytree(data_source, OUTPUT_DIR / "data")

    copied_pages = [p for p in PAGES if (OUTPUT_DIR / p).exists()]
    print(f"Wrote {OUTPUT_DIR} ({len(copied_pages)} pages: {', '.join(copied_pages)})")
    print(f"Zip the '{OUTPUT_DIR.name}' folder and send it -- open index.html first.")


if __name__ == "__main__":
    main()
