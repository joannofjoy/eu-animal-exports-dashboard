# EU Animal Exports Dashboard

Static dashboards visualizing live bovine-animal trade reported by all 27
EU member states, using Eurostat Comext data. Reader-facing definitions and caveats
are on [`public/methodology.html`](public/methodology.html). Technical
decisions, data investigations and agent handoff notes remain under `docs/`
and are not part of the published site; [`docs/README.md`](docs/README.md)
explains what each document is for.

## Scope

Every CN8 code under heading `0102` (live bovine animals) except buffalo
and four pre-2002-nomenclature codes confirmed to carry zero trade (see
`scripts/product_categories.py`'s module docstring for the full
breakdown). Reporter is selectable in every page's header: all 27 EU
member states, Austria (`AT`) the default — see `scripts/countries.py`'s
`REPORTERS`. Both export and import flows are
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
python scripts/fetch_meat_imports.py --reporter AT --start-year 2015 --end-year 2025
python scripts/fetch_world_boundaries.py   # one-time; boundaries don't change
python scripts/fetch_mirror_data.py        # Austria only, feeds mirror.html
```

`--reporter` accepts any of the 27 EU member-state codes in
`scripts/countries.py`'s `REPORTERS`. Raw monthly
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
| `beef_vs_cows.html` | `beef_vs_cows.template.html` → `build_beef_vs_cows.py` | One reporter's own live cattle exports (heading 0102) next to its beef & veal meat imports (headings 0201/0202) — shown side by side in native units (animals vs. tonnes), not converted into one number |
| `dashboard.html` | `dashboard.template.html` → `build_site.py` | Both `index` and `map` combined on one page, tab-switchable — built but not linked in the site nav |
| `mirror.html` | `mirror.template.html` → `build_mirror.py` | Internal QA tool: Austria's own declarations vs. partner countries' mirrored declarations (see `docs/mirror_tool_explained.md`) — Austria only, not part of the multi-reporter rollout |
| `methodology.html` | Maintained directly | Reader-facing source, definitions and limitations; linked from the dashboards |

The reader dashboards share one product view (`scripts/product_categories.py`):
All / Calves (≤300 kg) / For slaughter / For breeding / For
production-rearing. “Calves” is a weight grouping, not an age label;
Comext does not report age. See `public/methodology.html` for the reader
explanation and the handoff notes for the research behind the decision.

Generated dashboard pages in `public/` are built from their matching
`.template.html` files. `methodology.html` is the exception: it is a
hand-maintained static page, not build output.

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
and 15th of each month, then stages the reader-facing pages in `site_dist/`
with `scripts/make_deploy_site.py` and deploys that clean folder to GitHub
Pages. Templates and the internal QA page are left out of the hosted
artifact. Before the first publication, configure **Settings → Pages →
Source → GitHub Actions** and confirm the intended public repository and
URL. Scheduled refreshes publish new output without committing generated
data to the repository. Review workflow runs and the published pages after
the first deployment.

## Sharing a snapshot directly (not via the live link)

```
python scripts/make_deploy_site.py
```

Same script and output (`site_dist/`) the CI workflow uses to publish —
run it yourself any time you want a folder to zip and send to the team
directly, instead of (or before) pointing people at the live link. Every
page in it still works opened directly (double-click `index.html`), no
server or live link needed on the recipient's end. Regenerate it after
every data refresh you want to share — it's disposable build output
(gitignored), not something to keep committed.
