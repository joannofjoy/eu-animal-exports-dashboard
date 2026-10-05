# EU Animal Exports Dashboard

Dashboards visualizing live-cattle exports from six EU countries, built
from Eurostat Comext trade data. See `docs/eurostat_comext_api.md` for
why dataset `DS-045409` is the one used, and `docs/llm_agent_handoff.md`
for the fuller history behind the current design — both are worth reading
before making non-trivial changes here.

## Scope

Every CN8 code under heading `0102` (live bovine animals) except buffalo
and four pre-2002-nomenclature codes confirmed to carry zero trade (see
`scripts/product_categories.py`'s module docstring for the full
breakdown). Reporter is selectable in every page's header: Austria (`AT`,
the default), Germany, Ireland, Spain, France, or Netherlands — see
`scripts/countries.py`'s `REPORTERS`. Both export and import flows are
fetched; both head count and trade value in euros are available
throughout (a toggle in the header switches every chart/map/legend
between them).

## Data pipeline

**One command, refreshes everything:**

```
python scripts/refresh_all.py
```

Re-fetches every reporter's export and import data (2015 through the
current year, computed fresh each run — nothing to bump by hand annually)
from the live Eurostat API, then rebuilds every page. This is also what
runs automatically: see `.github/workflows/refresh.yml`, which runs this
same script on a schedule and deploys the result to GitHub Pages, so the
live site stays current without anyone needing to run anything by hand.

**Individual steps**, if you only need one piece:

```
python scripts/fetch_at_history.py --reporter AT --start-year 2015 --end-year 2025
python scripts/fetch_at_imports.py --reporter AT --start-year 2015 --end-year 2025
python scripts/fetch_world_boundaries.py   # one-time; boundaries don't change
python scripts/fetch_mirror_data.py        # Austria only, feeds mirror.html
```

`--reporter` accepts any of `AT`/`DE`/`IE`/`ES`/`FR`/`NL`. Raw monthly
rows land in `data/raw/` (gitignored — large, easily regenerated);
aggregated CSVs land in `data/processed/` (also gitignored, same reason).

## Dashboards (`public/`)

Plain HTML/CSS/JS, no server, no framework. Every page works by opening
the `.html` file directly in a browser (`file://`) *and* when hosted as
static files — both are treated as real requirements, not just the
former: several real cross-browser bugs (documented in
`docs/llm_agent_handoff.md`) came from assuming `file://` behavior would
match a normal hosted page. Chart.js and Leaflet load from free CDNs; the
map basemap is Esri's free "Dark Gray Canvas" tiles (no API key).

Data is baked into each page at build time as embedded JSON — nothing
calls the Eurostat API when someone actually opens a page. Every other
reporter besides the one baked in (Austria) loads its own small JS data
file on demand when picked from the dropdown, via a dynamically-injected
`<script src>` tag rather than `fetch()` (`fetch()` of a relative path is
blocked under `file://`; `<script src>` isn't).

| Page | Template → build script | What it shows |
|---|---|---|
| `index.html` | `index.template.html` → `build_dashboard.py` | Yearly totals + top destination countries, click a bar to select a year |
| `map.html` | `map.template.html` → `build_map.py` | Leaflet choropleth by destination, quantile-colored per year, year slider |
| `monthly.html` | `monthly.template.html` → `build_monthly.py` | Within-year month-by-month breakdown, alongside the same partner list and map |
| `trade_pairs.html` | `trade_pairs.template.html` → `build_trade_pairs.py` | One reporter's own exports vs. imports with a single chosen partner country |
| `dashboard.html` | `dashboard.template.html` → `build_site.py` | Both `index` and `map` combined on one page, tab-switchable — built but not linked in the site nav |
| `mirror.html` | `mirror.template.html` → `build_mirror.py` | Internal QA tool: Austria's own declarations vs. partner countries' mirrored declarations (see `docs/mirror_tool_explained.md`) — Austria only, not part of the multi-reporter rollout |

All six pages share one filter panel (`scripts/product_categories.py`):
a single-select view — All / Calves (≤300kg) / For slaughter / For
breeding / For production-rearing — never a "veal"/"beef" label outright,
since Comext has no age field and the weight brackets don't map onto the
EU's legal veal/beef age line cleanly (see `docs/llm_agent_handoff.md`
section 6 for the research behind that call).

**Never edit a `.html` file in `public/` directly** — the next build
silently overwrites it. Edit the matching `.template.html` instead.

## Dev setup (linting & tests)

```
pip install -r requirements-dev.txt
ruff check .
ruff format .
pytest
```

Both must be clean before any change is considered done. Tests cover the
pure data-transformation logic (CSV aggregation, GeoJSON joining,
category coverage, template rendering) — not the network-calling `fetch_*`
functions, which would just be testing that the internet works.

## Automated refresh / hosting

`.github/workflows/refresh.yml` runs `scripts/refresh_all.py` on the 1st
and 15th of each month and deploys straight to GitHub Pages via the
official deploy-pages action — nothing gets committed back to the repo on
a scheduled run, it just re-fetches fresh and republishes. Requires, one
time, in this repo's GitHub settings: **Settings → Pages → Source →
GitHub Actions**.

## Sharing a snapshot directly (not via the live link)

```
python scripts/make_share_bundle.py
```

Copies the finished pages (everything except `*.template.html` source
files and `mirror.html`, the internal QA tool) plus their data files into
`public_share/` — a clean, self-contained folder. Zip it and send it;
every page still works opened directly (double-click `index.html`), no
server or live link needed on the recipient's end. Regenerate it after
every data refresh you want to share — it's disposable build output
(gitignored), not something to keep committed.
