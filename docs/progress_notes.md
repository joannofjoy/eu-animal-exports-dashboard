# Progress notes — Austrian bovine exports dashboard

Last updated: 2026-07-15

> **Update (2026-07-29):** the "combined heifers + cows" scope described
> below has since been widened to all live cattle (every CN8 code under
> heading `0102` except buffalo), not just the two pure-bred-breeding
> codes — that subset turned out to be only about a quarter of Austria's
> actual live cattle export volume. The specific numbers and code
> references in this entry describe the narrower scope that was current
> as of this session; see the README for the current scope.

## Background / decisions made this session

- **Product scope:** the Eurostat dataset only has head-count data for two
  CN8 codes, `01022110` (heifers) and `01022130` (cows), both under the
  "pure-bred breeding cattle" subheading (`010221`). You chose to combine
  them into one total rather than show a heifers/cows breakdown — so the
  dashboard title says "cattle exports" in spirit, but the underlying data
  is specifically this pure-bred-breeding-cattle subset, not all live
  cattle. This caveat is stated in the "Hinweis" line on the page but kept
  short; the CN8 code numbers themselves were removed from the visible
  copy per your later request.
- **View for this draft:** chart-only, no map — you picked this over a
  Leaflet map so we could get something working end-to-end first. The data
  layer (per-partner yearly totals with country codes) is already built so
  a map is an additive step later, not a rebuild.
- **Language:** German, matching your three reference samples exactly
  (`sample map code.txt`, `code leaflet sample.txt`, `sample code 2.txt`) —
  same dark palette, kicker/header/panel structure, Chart.js.
- **Wording:** "Stück" and "Kopfzahl" replaced with "Tiere" throughout
  (tooltips, axis titles, dataset labels, source line) — your stance that
  cows are individuals, not units.
- **Color:** originally the yearly chart used pink/turquoise to distinguish
  heifers vs. cows and the destination-country chart used blue. Once the
  breakdown was dropped, you asked for a single consistent blue-green
  (`--turq`, `#6FB2A5`) across both charts instead of introducing a new
  accent for "selected."
- **Year selection:** originally a `<select>` dropdown; you asked to
  replace it with clicking directly on a bar in the top chart instead. The
  clicked bar highlights (full opacity vs. `rgba(turq, 0.35)` for the
  rest) and the destination-country panel updates and retitles.

## Data pipeline

**`scripts/fetch_at_history.py`** (pandas-based, matches the style of the
existing `scripts/download_data.py`):

- Calls `https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409/M.AT..01022110+01022130.2.SUPPLEMENTARY_QUANTITY`
  with `startPeriod=2015-01`, `endPeriod=2025-12`, `format=SDMX-CSV`.
  Reporter = Austria only, flow = export (`2`).
- Dataset choice (`DS-045409` over `DS-059341`/`DS-059322`) was already
  established and confirmed by Eurostat's own user support before this
  session — see `docs/eurostat_comext_api.md` and the two Eurostat reply
  `.docx` files in the parent folder. `DS-045409` is the only
  API-accessible dataset with both CN8 product detail and head-count
  (`SUPPLEMENTARY_QUANTITY`); `DS-059341` stops at HS6 and has no head
  count, and `DS-059322` is retired (404 on the data endpoint).
- Writes raw monthly data to
  `data/raw/comext_bovine_export_AT_2015-2025.csv`.
- Aggregates to two processed files, excluding aggregate/grouping partner
  codes (`WORLD`, `EXT_EA*`, `INT_EA*`, `EXT_EU*`, `INT_EU*`) so they don't
  double-count against the real country rows:
  - `data/processed/at_bovine_exports_yearly_by_product.csv` —
    `year,product,quantity` (22 rows: 11 years × 2 product codes)
  - `data/processed/at_bovine_exports_yearly_by_partner.csv` —
    `year,partner,quantity` (301 rows: up to 49 real partner countries ×
    11 years)
- Data confirmed complete for all 11 years, including 2025 (all 12 months
  present, verified against the raw API response directly).
- One bug caught and fixed during this session: pandas' default CSV
  reading inferred the `product` column as an integer, dropping the
  leading zero (`01022110` → `1022110`). Fixed by reading `product` and
  `partner` columns with explicit `dtype=str`.

**Sanity numbers** (combined heifers + cows, for spot-checking): 2015 →
29,006; 2017 (peak) → 36,085; 2022 (low) → 18,614; 2025 → 11,076.
Top destination in most years is Türkei or Italien.

## Dashboard files (`public/`)

- **`index.php`** — the whole page: markup, inline `<style>` (Marker color
  tokens, panel/kicker/header patterns copied from your samples), and the
  `<script>` block with both Chart.js configs and the click-to-select-year
  logic. Chart.js itself is loaded from the jsdelivr CDN (same as your
  samples) — free, no paid service, matches your "no external paid
  service" requirement.
- **`includes/data.php`** — `getYearlyByProduct()` (year → heifers/cows/
  total) and `getTopPartnersByYear()` (year → top N partners, sorted
  descending). Reads the two processed CSVs directly with `fgetcsv`, no
  dependencies.
- **`includes/countries.php`** — ISO2 → German country name lookup for the
  ~49 real partner codes in the data (pulled from Eurostat's own
  `CXT_FREE_ISO` codelist, German locale, historical parenthetical notes
  stripped, e.g. `DE` → "Deutschland").
- Data is embedded server-side as JSON directly into the page's `<script>`
  block (`json_encode(..., JSON_UNESCAPED_UNICODE)`) — no client-side AJAX
  calls, since the dataset is small enough (11 years, 10 partners/year) to
  just ship inline.

## Environment notes (in case they matter later)

- This machine didn't have PHP installed. I installed **PHP 8.3** via
  `winget install --id PHP.PHP.8.3` so I could actually run the dashboard
  rather than just review the code — it's now available at `php` in new
  shells (PATH was updated by the installer).
- Early on, `pandas`/`numpy` were being blocked by Windows **Smart App
  Control** (a reputation-based code-integrity feature that silently
  flipped from "evaluation" to "enforced" sometime after this machine's
  2/27/2026 clean install — confirmed via the Code-Integrity event log).
  It resolved itself once SAC's reputation check caught up with the
  installed packages; no OS settings were changed. If pandas/numpy ever
  fail to import again on this machine with a `DLL load failed` /
  "Application Control policy" error, that's almost certainly the same
  mechanism, not a corrupted install.

## Verification performed

- `php -l` syntax-checked all three PHP files after every edit.
- Ran the real page via `php -S localhost:8000 -t public` and fetched it
  with `Invoke-WebRequest` to catch runtime errors `php -l` can't see —
  this is how a real bug got caught: `array_keys()` on a PHP array
  auto-casts numeric-string keys like `"2025"` to `int`, which then made
  `htmlspecialchars()` throw under `declare(strict_types=1)`. Fixed by
  casting years to strings explicitly.
- Screenshotted the rendered page (Edge headless) after each round of
  changes to confirm it visually matches intent.
- Simulated an actual mouse click via Chrome DevTools Protocol (not just
  code review) — clicked the 2017 bar and confirmed, from the live page
  state: `selectedYear` updated to `"2017"`, the panel title updated to
  "Wichtigste Zielländer, 2017", the destination-country values matched a
  hand-aggregated check of the raw Eurostat CSV (Türkei 18,823, Italien
  7,720, Ungarn 2,193, ...), and the bar-color array showed only index 2
  at full opacity with the rest dimmed.
- The dev server from this session is still running in the background at
  `localhost:8000` if you want to keep clicking around without restarting
  anything.

## What's still to do

**Map (deferred by your choice this round)**
- Add lat/lon centroids for the ~49 partner country codes (names are
  already in `includes/countries.php`; coordinates are not).
- Decide layout: replace the destination-country bar chart with the map,
  or show both side by side.
- Circle sizing/color scale for export volume, popups on hover/click
  (your `sample map code.txt` already has a working pattern to copy).

**Known gap: keyboard accessibility**
- Removing the `<select>` dropdown in favor of clicking chart bars means
  there's currently no keyboard-operable way to change the selected year
  — canvas click targets aren't keyboard-reachable by default in Chart.js.
  Worth a decision: is this acceptable for an internal/editorial tool, or
  does it need a fallback (e.g. arrow-key support, or a visually-hidden
  select kept in sync with the chart)?

**Getting this into production**
- Currently a standalone page under `public/`, not wired into The
  Marker's actual CMS/site template, hosting, or URL structure.
- No automated data refresh — `fetch_at_history.py` is a manual run.
  2025's figures will keep getting revised by Eurostat, and 2026 will need
  adding once that year closes out. Worth deciding on a refresh cadence
  (manual re-run before publishing updates, vs. a scheduled job).
- German copy was written by me this session — needs an editorial pass
  before anything public-facing.
- Only tested in Edge (headless) at desktop width; the mobile breakpoint
  CSS (`@media max-width:760px`) is written but unverified on an actual
  phone or in Firefox/Safari.
- No favicon/branding beyond the color palette — irrelevant for a
  standalone draft, but worth remembering once this moves into the real
  site shell.
