# Handoff notes for future LLM agents

Last updated: 2026-10-05

This is a working-session log, not user-facing documentation — it exists so
an agent picking this project up cold (no conversation history) can
understand *why* things are built the way they are, not just what the code
currently does. The code itself and its own comments are the source of
truth for *what*; this file is for decisions, dead ends, and research that
isn't obvious from reading the final state alone.

If something here contradicts the current code, trust the code — this file
describes the reasoning at the time of writing, and the project moves fast.

See also, for earlier/narrower context:
- `docs/progress_notes.md` — the original PHP prototype (now fully
  replaced by the Python/static-site pipeline described below; kept for
  history only, don't take its file paths as current).
- `docs/eurostat_comext_api.md` — Comext SDMX API mechanics, dataset
  choice (`DS-045409`), key format.
- `docs/croatia_2024_anomaly.md`, `docs/mirror_tool_explained.md` —
  mirror-statistics tooling (Austria's own declarations vs. partner
  countries' mirrored declarations).

## 1. Architecture, in one paragraph

Pure static site. `scripts/fetch_*.py` fetch data from Eurostat and write raw CSVs to `data/raw/`; `scripts/build_*.py` read `data/processed/` CSVs without network access and generate the dashboard HTML from matching templates. `public/methodology.html` is maintained directly as a static reader page. No server or database is required. Dashboard pages are intended to work both hosted and opened through `file://`; the selected reporter is loaded from a relative JavaScript data file to preserve that support.

Reader dashboards: `index` (Yearly Exports), `map`, `monthly`, and `trade_pairs` (Export vs. Import). `dashboard` is a combined view that is built but not linked in reader navigation. `mirror` is an internal QA tool and is not linked in reader navigation or copied into share bundles. `methodology.html` is the reader-facing page for source, definitions and caveats. Keep technical history and exploratory findings in `docs/`.
Multi-reporter support: Austria (`AT`) plus five more EU countries
(`DE`, `IE`, `ES`, `FR`, `NL`) — see `scripts/countries.py`'s `REPORTERS`.
Austria's data is baked directly into each page at build time; every other
reporter gets its own `public/data/{page}/{code}.js` file, loaded via a
dynamically-injected `<script src>` tag when picked from the dropdown —
**not** `fetch()`. This is load-bearing, not a style choice: a plain
`fetch()` of a relative path is blocked under `file://` (confirmed live,
throws "Failed to fetch" — Chromium treats `file://` as an opaque CORS
origin). A `<script src>` tag isn't subject to that restriction.

## 2. Reporter-country persistence across tabs — a real debugging saga

The request was simple ("keep my selected country when I click between
tabs"); getting it right took three rounds because each fix passed my own
testing and then failed differently in the user's hands. Worth reading in
full if touching this code, since the failure modes are non-obvious:

1. **First attempt: `localStorage`.** Worked perfectly in my own
   Chromium/Edge CDP tests. Failed for the user in real Firefox. Root
   cause: Firefox treats every `file://` page as its own isolated origin —
   `localStorage` set on `index.html` is invisible to `map.html` even in
   the same folder. Chromium is lenient about this in a way Firefox isn't.
   This was *not* caught by automated testing because the test browser was
   Chromium both times.

2. **Second attempt: carry the country in the URL instead**
   (`map.html?reporter=IE`), rewritten onto every tab link live via JS
   (`updateTabLinksForReporter()`), with `localStorage` kept only as a
   fallback for a bare retyped URL. This is browser-agnostic — it doesn't
   depend on storage at all. But it still broke: the tab links were only
   updated *after* a newly-picked country's data finished loading
   (inside `applyReporterData()`), which is asynchronous for any country
   not yet cached. Clicking a tab in that gap (very easy to do right after
   a first pick) still carried the *old* value. Fixed by moving the link
   update to the top of `switchReporter()`, called synchronously and
   optimistically the instant a switch starts, not after the data arrives.
   Also added a `pendingReporter` guard so a late-arriving response for an
   earlier, superseded pick can't clobber a newer selection.

3. **Third bug, the real culprit for most of the user's actual reports:**
   when the selected reporter was **Austria** (the default), the code
   deliberately *omitted* `?reporter=` from the tab links to keep URLs
   "clean." That meant a destination page got no instruction from the URL
   at all and fell back to its own `localStorage` — which, on any page
   previously tested with a different country (by me or the user), still
   held that stale value with nothing to override it. Picking Austria
   never actually reached the destination page's state. Fixed by **always**
   stamping `?reporter=<code>` onto every tab link, Austria included —
   confirmed by deliberately planting a stale value in one page's storage
   and verifying Austria still overrides it correctly.

The lesson that generalizes: **a persistence mechanism that falls back to
storage must never have a "no instruction" state** — if the primary
channel (the URL, here) can go silent for *any* selection including the
default, the fallback will eventually surface stale data with nothing to
tell the user why. Always propagate state explicitly, even for the "this
is the default, nothing to see here" case.

Current mechanism (stable, in all 6 templates' JS): `switchReporter(code)`
calls `updateTabLinksForReporter(code)` synchronously first (always
includes `?reporter=`, no exceptions), then loads data (sync if cached,
async `<script src>` otherwise, guarded by `pendingReporter`).
`applyReporterData()` is the single place `currentReporter` actually
changes, and it also re-stamps the links and writes `localStorage` as a
secondary channel.

## 3. €/Animals unit toggle

Request: show trade value in € alongside animal counts. The underlying
data already had both (`value_eur` was fetched alongside quantity from day
one of the multi-indicator Comext query, see `eurostat_comext_api.md`) —
this was purely a presentation gap, not a data gap. `byCategoryValueEur`
sits alongside `byCategory` in every page's embedded JSON (same category
keys, same shape), so a page that never reads it keeps working unchanged.

UI went through two rounds:
- **v1**: radio buttons buried in the sidebar filter panel, next to the
  geo filter. Technically worked but the user didn't notice it existed for
  a while (reasonably — it wasn't near anything else "important").
- **v2 (current)**: moved to a real two-segment pill toggle
  (`.unitToggleGroup` / `.unitToggleBtn`) in the page header, right next
  to the reporter picker — both control *how the whole page reads*, so
  they're peers, not one being a "filter." This is the pattern to follow
  for any future global-view toggle: header, not sidebar.

`formatUnit()`/`formatUnitShort()` per page pick `fmtEur` vs. plain `fmt`
based on `unitMode`; every chart axis/tooltip/legend/CSV column routes
through these rather than hardcoding "animals" anywhere.

## 4. Sticky/click-to-pin info boxes

Original ask: hover-only tooltips disappear when you move the mouse,
making screenshots for a school assignment hard. Pattern (map.html,
monthly.html, originally; later ported to trade_pairs.html too): clicking
a country keeps its tooltip open via Leaflet's `layer.openTooltip()` +
`bringToFront()`, tracked in a `selectedCountryCode`/`selectedCountry`
variable; clicking elsewhere (or the same country again, on map/monthly)
closes it. Works reliably even though Leaflet tooltips default to
`permanent: false` — calling `.openTooltip()` manually doesn't get
silently undone by Leaflet's own hover-close behavior, at least on the
Leaflet version pinned here (1.9.4).

When this was ported to `trade_pairs.html`, its map tooltip had never
shown anything but the country *name* — no trade figures at all, unlike
the other pages' choropleths. Added `totalsForCountry()`/`tooltipFor()`
to show real export/import totals (honoring the unit toggle), which
surfaced a real bug worth knowing about if adding more map logic to that
page: **both `tooltipFor()` and the map-build code run synchronously at
initial page load**, before the later "Filter / selection state" section
of the script has executed — so any `let` variable that section declares
(it declared `selectedCategories` and, at the time, `unitMode`) throws
`ReferenceError: Cannot access '...' before initialization` the instant
the map tries to use it. Fix was to move those declarations up next to
`selectedCountry`, which already had this exact problem solved with a
comment explaining why. If you add a new `let` that the map section reads
immediately, it needs to live up there too, not down in its "natural"
section.

## 5. Basemap: CARTO → Esri

`map.html`, `monthly.html`, `trade_pairs.html`, and `dashboard.html` all
used CARTO's free "dark_all" tiles (`{s}.basemaps.cartocdn.com`). At some
point CARTO started requiring an API key for free/anonymous tile
requests — but **the tile endpoint still returns HTTP 200** with a valid
PNG; it's just a watermarked "API KEY REQUIRED / carto.com/basemaps/apikey"
placeholder image instead of real map data. This means a network-level
check (status code, content-type) will *not* catch the regression — only
actually looking at the rendered tile (screenshot) reveals it. Worth
remembering for any future "is this still working" check on an external
tile/image service: status 200 is not proof of correct content.

Replaced with Esri's free "Dark Gray Canvas" basemap
(`server.arcgisonline.com/.../Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`
— note the `{z}/{y}/{x}` order, row before column, that's Esri's own
convention, not a typo if you see it elsewhere in this codebase). No API
key, no signup. `maxZoom: 16` (Esri's actual tile availability; CARTO's
was 18 but this project never needs street-level zoom for a
country-choropleth). Attribution text pulled from Esri's own service
metadata (`?f=json` → `copyrightText`), not guessed.

## 6. The veal vs. beef research thread

Original colleague ask (from a Marker meeting, "Shades of White" research
reference): does Eurostat distinguish veal from general beef, for a
live-export-vs-meat-import comparison? Answer, arrived at over several
research passes, each verified against a primary source rather than
assumed:

**Comext (the live-trade dataset this whole project is built on) has no
age field at all.** CN8 codes under heading `0102` split live cattle by
*weight bracket* (`<=80kg`, `80-160kg`, `160-300kg`, `>300kg`) and
declared trade purpose (`for slaughter` / not), never by age or a
veal/beef label. This was confirmed directly against the actual CN8
codelist (`CXT_NC`), not assumed from code names alone.

**The EU does have a real legal veal/beef age line — just not in this
dataset.** Regulation (EU) No 1308/2013 Annex IV + the older Commission
Regulation (EC) No 566/2008 define: **Class V** (<8 months, "white veal")
and **Class Z** (8–12 months, "rosé veal") = legally veal; **12 months and
older = beef**, split into Category A (young bulls, 12–24mo), B (bulls,
24mo+), C (steers), D (cows, have calved), E (heifers). This is almost
certainly what the colleague's "Shades of White" reference was pointing
at (white vs. rosé veal is a real, named EU distinction).

**Attempted to bridge weight → age using Eurostat's own slaughter
statistics** (`apro_mt_pwgtm`, a *different* Eurostat dataset — not
Comext, the main dissemination API instead — reports animals
slaughtered + their weight, split into exactly the Calf/Young
cattle/Bull/Cow/Heifer/Bullock categories that mirror the legal classes).
Found real, weighted-average **carcass** weights for Austria (2021-2025):
Calf ~103kg, Young cattle ~233kg, adult categories 319-400kg. Converting
to an *estimated* live weight (carcass weight ÷ a dressing-percentage
estimate — calves ~60%, adults ~51-57%, commonly-cited industry figures,
**not** one single verified-exact number per category) put Calf at
~172kg live and Young cattle at ~409kg live — i.e. **even a true Class-V
calf is right in the middle of Comext's 160-300kg bracket, and Class-Z
"young cattle" (still legally veal) is already past the >300kg line**,
mixed in with full adult bulls/cows at 590-700kg. Conclusion: **the
weight brackets don't cleanly separate veal from beef** — they were
designed for customs/transport purposes, not nutrition labeling, and this
was confirmed empirically rather than assumed.

This finding directly shaped the category redesign in section 7 below:
the dashboards label everything by weight bracket and declared purpose,
**never** as "veal" or "beef" outright, and the user explicitly agreed
this was the right call after seeing the numbers.

### 6.1 Extending the question to meat trade (not livestock) — 2026-10-06

User follow-up, explicit correction after an initial misread: *"I mean
meat trade, not livestock trade"* — i.e. not this project's own live
cattle data, but processed beef/veal product imports/exports, and how
animal-rights/welfare organizations track that side. Research done via
live web search + direct primary-source verification, not assumption:

**The same gap exists on the meat side, confirmed directly against
Eurostat's live codelist.** DS-045409 (this project's own dataset — a
general goods-trade dataset, not cattle-specific; the project just
filters it to heading `0102`) also carries headings `0201` (fresh/chilled
bovine meat) and `0202` (frozen bovine meat). Fetched `CXT_NC`
(Eurostat's CN8 product codelist) live and checked every code under both
headings (32 total): every single one splits by **cut type** (carcass,
quarters, boneless) and **weight band**, exactly like the live-animal
side — not one mentions veal, age, or a Class V/Z label. A web search
summary claimed specific "veal CN codes" (e.g. `0201.10.10.10`) exist,
but that 10-digit format and the "190kg carcass" threshold it cited don't
match the EU's actual 8-digit CN system or any code in the real codelist
response — almost certainly a different country's tariff schedule
(e.g. US HTS) surfaced by the search, not an EU one. Flagging this
explicitly since it's a case of a plausible-sounding but unverified claim
that a live primary-source check actually contradicted.

**So: meat *trade* statistics (Comext/CN, which is what customs
authorities and Eurostat's trade dashboards report) cannot distinguish
veal from beef at all, in or out of the EU.** The real EU legal
veal/beef line (Class V/Z = veal vs. 12mo+ = beef, per Reg 1308/2013 —
see above) is a **carcass grading classification applied at the
slaughterhouse**, not a customs classification. It only exists in
production statistics, not trade statistics — the distinction is lost
the moment meat crosses a border and gets classified under CN/HS codes
for customs purposes.

**What orgs/the EU itself actually use instead:**
- **Production, not trade**: the EU's own Meat Market Observatory
  (`agriculture.ec.europa.eu/.../market-observatories/meat`) sources its
  veal-specific numbers from `apro_mt_pwgtm` — the same Eurostat
  slaughterhouse dataset already used and verified earlier in this
  section (section 6, "Attempted to bridge weight → age...") — which
  reports animals *slaughtered*, split into the real Calf/Young
  cattle/Bull/Cow/Heifer categories. This is domestic production data
  (how many calves a country slaughtered for veal), not an import/export
  figure.
- **Live animal movements, not meat**: Eurogroup for Animals' 2019 report
  *"Towards a meat and carcasses only trade"* (the report advocating for
  a *shift* from live to meat trade — directly relevant context, not just
  a tangent) explicitly lists its data sources (Annex I): **Comext** (the
  same dataset/API this project uses) for recent trends, plus **TRACES**
  (the EU's animal-movement control system) for longer time series and
  journey-duration detail Comext doesn't carry. Notably, the report
  itself flags that even TRACES — the system specifically built to track
  live consignments — has known data-quality problems (citing CIWF 2018:
  "logs are often incomplete/unrealistic on times, and lack follow-up
  actions"). The report's own "beef and veal" trade references are
  high-level advocacy framing, not a worked veal-specific trade dataset.
- **The EU Commission's own "beef and veal" trade dashboard**
  (same market-observatory page) appears to report beef and veal
  *together* as one commodity group rather than as a split line — its
  methodology page doesn't claim a veal/beef breakdown, consistent with
  the CN-code finding above (there's no code to split on).
- **User pushback ("aren't NGOs and journalists using *some* data for
  this?") led to a stronger, more specific finding.** Read EuroVeal/
  FEFAC's "Vision of the European Veal Sector" (2021) directly — the
  actual EU veal-sector industry federation's own paper, the body with
  the strongest incentive to have good trade figures if they existed.
  It states outright: **"Veal trade with Third Countries is very
  limited, hence consumption is almost equivalent to production"** —
  i.e. even the industry itself doesn't track cross-border veal trade;
  it substitutes national *production* totals as a proxy for national
  *consumption* instead. Its own per-capita consumption figure is
  footnoted **"Source: Eurostat, Agreste, PVE — 2014 (Data are lacking
  since 2014)."** PVE (Productschap Vee en Vlees) was a Dutch public
  sectoral board that used to collect detailed EU livestock/meat
  sector statistics; it was dissolved around 2014, and per this
  industry paper written in 2021, nothing has fully replaced it since
  for veal specifically. Also confirmed directly in a French national
  agricultural-statistics sheet (FranceAgriMer, sourced from French
  customs): beef import/export figures carry an explicit **"*Including
  veal"** footnote — veal is folded into "beef" even at national
  customs-statistics level, not just at the EU/Comext level.
  Company-level veal export figures that *do* circulate in trade press
  (e.g. VanDrie Group, the dominant Dutch veal producer, self-reporting
  "exports to 60+ countries") are self-disclosed corporate figures, not
  government statistics; genuine cross-border veal-specific volumes
  otherwise live behind paid industry market-intelligence subscriptions
  (e.g. GIRA Meat Club), not in any public dataset found so far.

**Bottom line for a future "meat trade" feature**: a live-export-vs-
meat-import comparison *by volume* (total heading-0102 live exports vs.
total 0201/0202 meat imports) is buildable with the existing
fetch_at_history.py-style pipeline pointed at different CN8 codes — same
dataset, same API, same reporter/partner/flow dimensions, genuinely
little new infrastructure needed. But a *veal-specific* version of that
comparison — "how much of what's imported as meat could be traced back
to the calves that left live" — is not something published trade
statistics can answer at all, from any source found so far. That would
need either a sourcing assumption (e.g. applying a country's known
veal-share-of-production ratio to its meat exports) or a different kind
of evidence entirely (certification/traceability records, not trade
statistics). Not started — this was scoping research only, nothing built.

## 7. Product category system — three generations, current state

`scripts/product_categories.py` groups the 35 CN8 codes
`fetch_at_history.py`'s `PRODUCTS` list tracks. This went through three
designs across the project's life; **only the third is current**:

1. **Original**: `SCHLACHTRINDER` ("for slaughter") /
   `SONSTIGE` ("everything else") — two flat buckets, a checkbox filter.
2. **Intermediate** (briefly, mid-session): split further into
   `young_slaughter` / `young_other` / `adult_slaughter` / `adult_other` /
   `other_unclassified` (7 leaves total, including the unchanged breeding
   pair), grouped under 4 parent checkboxes in a tree
   (`"Breeding cattle"`, `"Calves (<=300kg)"`, `"Adult cattle (>300kg)"`,
   `"Other / unclassified"`). This was a real, working, tested design —
   but it was a checkbox tree, and checking multiple boxes at once could
   silently double-count (e.g. "Calves" + "For slaughter" both include
   `young_slaughter`).
3. **Current**: the same 7 leaf categories still exist
   (`CODE_TO_CATEGORY` → 7 keys, used by every `build_*.py` script to
   produce `byCategory`/`byCategoryValueEur` JSON — this part is stable
   and build-script-facing, don't touch lightly), but the **reader-facing
   filter is now a single-select, five-option radio control** (`VIEWS` in
   `product_categories.py`): **All / Calves (≤300kg) / For slaughter /
   For breeding / For production-rearing**. Each view sums whichever leaf
   categories answer that one question (`"calves"` = `young_slaughter` +
   `young_other`; `"slaughter"` = `young_slaughter` + `adult_slaughter`;
   etc.) — `"all"` includes every leaf, including `other_unclassified`,
   so its total is the true grand total, not just whatever the other four
   happen to add up to. The old `GROUPS` constant and checkbox-tree
   rendering are gone entirely, replaced by `render_category_filter_html()`
   emitting `<input type="radio" name="view" class="viewRadio">`.

   **Why single-select, not checkboxes:** "Calves" is an *age/weight*
   axis; "For slaughter"/"For breeding"/"For production" is a *purpose*
   axis. A calf can itself be for slaughter. These aren't peers on one
   dimension, so letting someone check several at once would silently
   double-count any code belonging to two selected views. This was an
   explicit, considered tradeoff, not an oversight — if a future request
   wants to combine axes (e.g. "slaughter-bound calves only"), that's a
   sixth *named* view with its own explicit category list, not a
   checkbox combination.

   JS side: every page declares `const VIEWS = __VIEWS_JSON__;` (passed
   from Python the same way `REPORTERS` is) and
   `selectedCategories` is a `Set` rebuilt by `recomputeCategories()`
   reading `document.querySelector('#categoryFilter .viewRadio:checked')`
   and looking up its `VIEWS` entry — not from DOM checkbox state
   directly. All the downstream summing code
   (`quantityForPartner`/`valueFor`/`sumCategories`) was untouched by this
   change; only how `selectedCategories` gets *constructed* changed.

   `trade_pairs.template.html` needs `VIEWS` declared **before** its early
   `selectedCategories` initialization (see section 4's note on the same
   page) — this bit twice during the rewrite and is worth double-checking
   if this file changes again.

## 8. Data-quality findings worth knowing before adding more codes

- **17 of the 35 tracked CN8 codes are completely empty** — zero trade,
  all six reporters, all years 2015-2025. All 17 are from the generic
  `0102 90 xx "domestic bovines"` series; every one has a `0102 29 xx`
  "cattle"-specific twin code with the *same* weight bracket that **does**
  carry real volume. Conclusion: none of the six reporter countries ever
  declare live cattle trade under the generic series — confirmed live via
  the API, not assumed. These 17 codes are harmless to keep (they just
  contribute zero) but could be dropped from `PRODUCTS` if ever trimming
  the query; not done so far since it doesn't change any output.
- **`01022905`** ("Bibos or Poephagus" subgenus) is real, not a data
  artifact — Bibos covers gaur/gayal/banteng (Asian wild/semi-domesticated
  cattle), Poephagus covers yak. The ~15k animals over 11 years/6
  reporters are almost certainly ordinary European yak farming (confirmed
  present in Austria, Germany, France specifically; domestic yak is IUCN
  "Least Concern," not endangered — the wild relatives in this taxonomic
  group mostly are, but aren't what's being traded here).
- **`01029091`/`01029099`** ("domestic"/other bovine excl. cattle/buffalo)
  carry real, substantial volume (273k / 569k over 11yr/6 reporters) —
  almost certainly **bison** (genus *Bison*, American + European/wisent),
  which the EU's own CN explanatory notes group here specifically (along
  with genus *Syncerus*, African buffalo) because they share the same
  14-rib anatomical classification bovine, buffalo, and Bibos/Poephagus
  don't.

## 9. Explicit user decisions / standing constraints

- **No paid services, ever** — this shaped the CARTO→Esri switch (needed
  a genuinely free alternative, not "free tier"), the `<script src>`
  pattern over any server-based data API, and Chart.js/Leaflet both being
  loaded from free CDNs.
- **Must work opened directly via `file://`** — no dev server assumed.
  This is the root cause behind nearly every cross-browser bug found this
  session (sections 2 and 5 above) and should be treated as a hard
  constraint, not revisited without being asked.
- **Not pushed to GitHub / no git commits made this session** — explicit:
  "im not sure we need to put it up to github." Don't `git commit`/`push`
  without being asked again, even though the repo is git-initialized.
- Every live-API or live-browser claim in this document and in the
  codebase's own comments was verified against the real Eurostat API, a
  real browser (via Chrome DevTools Protocol), or a primary legal/
  taxonomic source — not assumed. If you're tempted to state something
  about Comext's structure, a browser's behavior, or a regulation's exact
  text without checking, that's inconsistent with how this project has
  been built so far; check first.

## 10. Still open / explicitly parked

- **Veal-vs-beef €/kg price comparison** — real numbers were pulled once
  (Austria, 2021-2025: lightest live-export weight brackets command
  roughly 2-3x the €/kg of heaviest adult brackets) but this was
  superseded by the deeper research in section 6 and never written up as
  a final deliverable. If resumed, section 6's findings on weight-bracket
  imprecision should temper how confidently any veal/beef framing is
  applied to it.
- Automated refresh/deploy now exists in `.github/workflows/refresh.yml`;
  it runs `scripts/refresh_all.py` twice monthly, stages reader-facing
  files with `scripts/make_deploy_site.py`, and publishes `site_dist/` to
  GitHub Pages. First publication still requires Pages to be configured in
  repository settings. This supersedes the PHP-era manual-refresh note in
  `progress_notes.md`.
- Reader-facing “Project notes (work in progress)” have been removed from
  the dashboards. Use `public/methodology.html` for published definitions
  and caveats; keep investigations and implementation history in `docs/`.
- The internal mirror tool remains buildable for QA but is omitted from the
  reader navigation and sharing bundle.
- Only tested in Chromium/Edge (via CDP) and, for the persistence bug
  specifically, debugged against real user reports from Firefox. Safari
  is untested.

## 11. Handoff checkpoint — 2026-10-05

The user asked to modernize the public dashboard UI, remove internal notes from reader pages, retain The Marker colors, prepare it for deployment, and audit the data pipeline. Work is staged locally for handoff; **nothing has been committed, pushed, or published**.

- Preserved the existing palette (`#E64980`, `#6FB2A5`, `#31688F`, `#6D3D83`, near-black/off-white). Added CSS polish in all `public/*.template.html` files and matching styling to hand-maintained `public/methodology.html`: clearer card grouping, navigation and control hierarchy, spacing, rounded surfaces, responsive mobile layout, visible keyboard focus and reduced-motion support. Generated pages have been rebuilt. No visual browser screenshot review has been done in this last UI turn; next agent should inspect in a browser at desktop and mobile sizes before treating the design as final.
- Reader methodology is at `public/methodology.html`; internal/research notes remain in `docs/`. Deployment staging output is `site_dist/` (5 reader pages plus 4 data folders); share bundle output is `public_share/` (6 HTML pages and data). Both were regenerated after the UI changes. They are generated/ignored output, not source.
- The prior data audit checked cached raw data for six reporters (AT/DE/IE/ES/FR/NL), both trade flows, 2015–2026. No duplicate raw coordinates, null observation values, measure-pair gaps, or unexpected product codes were found; recomputed yearly/monthly aggregates matched processed outputs. This was a cached-data audit, **not a fresh live Eurostat retrieval**. Latest cached period reached July 2026 with reporter/flow availability varying.
- Fixes from that audit: API response validation now catches empty/incomplete/malformed observations in `scripts/fetch_at_history.py`; category validation prevents silent omission of unrecognized CN8 codes in `scripts/product_categories.py` and the build loaders; `scripts/build_map.py` maps Natural Earth `RS` geometry to Eurostat partner code `XS` (Serbia); missing partner names were filled in `scripts/countries.py`. Small destinations without separate polygons in the Natural Earth 110m layer cannot be individually shaded, noted for readers in methodology.
- The previous full test run completed with **44 passed** and Ruff reported clean. Those checks preceded the CSS-only UI turn. In that turn all builders completed, all generated reader pages were checked for style insertion and unresolved navigation placeholders, and `git diff --check` passed. No tests were run during the CSS turn.
- Existing working tree includes a mix of this earlier UI/methodology/data-audit work and previously requested note cleanup/deployment preparation. Inspect `git status` and `git diff` before staging any subset; do not assume all modified generated/data JS files are UI-only. The user's earlier instruction was not to commit or push without being asked. No paid services; direct `file://` support remains a requirement.

Useful rebuild commands from the project root:

```
python scripts/build_dashboard.py
python scripts/build_map.py
python scripts/build_monthly.py
python scripts/build_trade_pairs.py
python scripts/build_site.py
python scripts/make_deploy_site.py
```

`public/methodology.html` is hand-maintained. `scripts/refresh_all.py` performs a live API fetch, so do not use it merely to rebuild UI output.

## 12. Handoff checkpoint — 2026-10-05 (resuming after the above)

Picked this project back up after the agent whose checkpoint is section 11
worked on it. Reviewed their changes file-by-file before touching anything
further (don't just trust a handoff note's self-description — verify):

- **`validate_api_response()`** (`fetch_at_history.py`) and
  **`validate_product_codes()`** (`product_categories.py`): legitimate,
  well-reasoned defensive checks. Kept as-is.
- **Serbia RS/XS map fix** (`build_map.py`): verified independently rather
  than trusting the claim -- confirmed Austria's own processed data has
  real `XS` rows (`grep` count: 11) and Natural Earth's boundary file uses
  `RS` for Serbia's `ISO_A2`/`ISO_A2_EH`. Real bug, correct fix.
- **`methodology.html` replacing the per-page "Project notes" footer**:
  a good simplification -- one dedicated page instead of the same
  collapsible blob repeated on six pages. Content is accurate.
- **CSS duplication**: the UI-polish pass left every touched file (all
  four main templates plus `methodology.html`) with its style block
  effectively written *twice* -- a base layer followed by a full second
  layer re-declaring `:root`, `body`, `.wrap`, `nav`, etc. with additional/
  overriding properties, concatenated rather than merged. Harmless (CSS
  cascade resolves it fine, confirmed via screenshots -- nothing was
  visually broken), but a real maintainability smell. **Fully consolidated
  in `methodology.html`** (it was small, 103 lines, already being read in
  detail for an unrelated check) into one definition per selector, keeping
  every effective value unchanged. **Not yet done for the four main
  templates** (`index`/`map`/`monthly`/`trade_pairs.template.html`) --
  each has materially more of this duplication (100+ lines), and doing it
  for all four safely needs the same careful one-property-at-a-time
  reconciliation, not a quick pass. Worth doing, but it's real effort;
  flagged to the user rather than silently taken on.
- **Mobile tab bar**: at narrow widths the site-nav tab strip overflows
  horizontally with no visual affordance (fade, partial-next-tab peek,
  etc.) hinting that it scrolls -- verified via CDP that it's genuinely
  scrollable and every tab (including the new "Methodology") is reachable,
  so nothing is actually lost, but a first-time mobile reader has no cue
  to try swiping. Minor, not fixed, flagged to the user.
- **Retired `scripts/make_share_bundle.py`**, which I'd written in an
  earlier session, in favor of this checkpoint's `make_deploy_site.py` --
  the two had become near-duplicates (same job, different output folder
  name and a slightly different page list) once `methodology.html`
  existed. Keeping one unambiguous script beats maintaining two that could
  silently drift apart. Updated its docstring to cover both the CI-deploy
  and share-with-team use cases explicitly, and updated the README and
  `.gitignore` accordingly.
- Full lint + test suite verified clean after the other agent's changes
  (44 passed) and again after the above (same). All five reader pages
  plus `methodology.html` screenshotted at desktop and mobile widths,
  zero console errors.
- Mid-session, also expanded `REPORTERS` (`scripts/countries.py`) from six
  reporters to all 27 EU member states (Comext only accepts EU members as
  reporters at all, so this is the real ceiling, not an arbitrary round
  number) -- verified live that Greece's Comext reporter code is `GR`, not
  `EL` (which some other Eurostat datasets use for Greece), before adding
  it. Data fetch for the 21 new reporters was in progress when this note
  was written; if you're picking this up and don't see ~27 reporters'
  worth of `public/data/*/XX.js` files, the fetch likely didn't finish --
  rerun `fetch_at_history.py`/`fetch_at_imports.py --reporter <code>` for
  whichever are missing, then the four `build_*.py` scripts.
- **Explicitly flagged by the user as "for later," not yet done:**
  - `map.html`'s reporting-country styling only gives it a pink outline
    (`fillColor: NO_DATA_COLOR`, i.e. dark) -- `monthly.html`'s map
    instead fills it with translucent pink
    (`fillColor: PINK, fillOpacity: 0.55`). User wants `map.html` to match
    `monthly.html`'s version. Small, well-scoped fix in `map.template.html`'s
    `styleFor()` once picked back up.
  - User wants research into how animal-rights/welfare organizations
    themselves gather per-country **meat** trade data (processed beef/veal
    product imports and exports -- CN/HS headings like 0201/0202, fresh
    or frozen bovine meat) for the veal-vs-beef question. Explicitly
    *not* livestock/live-animal trade (this project's own DS-045409
    pipeline, heading 0102, already covers that side) -- the open
    question is specifically how the *meat* side of the original
    "live calves exported vs. meat imported" comparison gets tracked,
    and whether meat-trade data (unlike live-animal Comext data) carries
    any veal/beef or age distinction that heading 0102 doesn't. Not
    started; would likely need its own new fetch pipeline against a
    different Comext heading, not an extension of the existing one.

## 13. Handoff checkpoint — 2026-10-06 (27-reporter fetch completed, real bugs found)

Picked up where section 12 left off: the 21 new reporters' fetch was
running in the background. It finished, but with real failures worth
understanding, not just re-running blindly.

- **First pass: 10 fetches failed with `requests.exceptions.ReadTimeout`**
  (Cyprus export+import, Finland export+import, Greece import, Hungary
  export, Malta export+import, Sweden export+import). Re-running the exact
  same 10 fetches immediately: 2 succeeded on bare retry (Greece import,
  Hungary export -- genuinely transient), but **8 failed again, with a
  different error**: `validate_api_response()` raising `ValueError:
  Eurostat returned no observations for <reporter>, <flow>, <year>`.
- **Root cause, confirmed live against the API, not assumed**: these
  reporters genuinely have zero observations for specific years -- e.g.
  queried Sweden's 2022 imports directly and got HTTP 200 with just the
  CSV header row, no data rows. Small/low-volume reporters (Cyprus,
  Malta) and specific quiet years (Sweden 2022, current-year-so-far 2026)
  are a real possible state, not a broken request. The bug: section 11's
  `validate_api_response()` treated `df.empty` as unconditionally fatal,
  which aborted the *entire* multi-year `fetch()` call for that
  reporter/flow -- discarding every other year's real data too, since
  years only get concatenated after all of them validate successfully.
  **Fixed** in `fetch_at_history.py`'s `validate_api_response()`: an empty
  year now prints a note and returns the empty frame as-is (contributes
  zero rows via `pd.concat`) instead of raising. `fetch_at_imports.py`
  imports this same function, so one fix covers both. Re-ran the 8
  affected reporter/flow fetches after the fix -- all succeeded, several
  with multiple genuinely-empty years logged as notes (Malta's export side
  is 0 rows for *every* year 2015-2026 -- Malta apparently exports no live
  cattle at all under heading 0102, imports only).
- **New partner codes from the wider reporter set**: cross-checked every
  partner code appearing in any reporter's processed CSVs against
  `countries.py`'s `COUNTRY_NAMES`, live against Eurostat's `CXT_FREE_ISO`
  codelist (not guessed) -- 13 were missing. 12 were real countries, added
  to `COUNTRY_NAMES` (Argentina, Brazil, Bahamas, Congo, Faroe Islands,
  Iceland, Madagascar, Malaysia, Nigeria, Occupied Palestinian Territory,
  Uganda, Vietnam). The 13th, `QS`, is Eurostat's own aggregate code
  ("Stores and provisions within the framework of extra-Union trade"),
  the same class as the existing `QV`/`QW` entries in
  `AGGREGATE_PARTNERS` -- added there instead, then re-ran Belgium's
  export fetch (the only reporter whose data actually contained a `QS`
  row) to purge it from the aggregated output.
- **Re-verified the `OTHER_UNCLASSIFIED` zero-volume claim**
  (`product_categories.py`'s docstring, flagged in section 10/pending list
  as scoped to "six reporters"): checked the four `>220kg` generic
  "domestic bovines" codes (`01029031/33/35/37`) against all 27 reporters'
  full processed data -- still genuinely zero volume everywhere. Docstring
  updated from "six reporters... 2021-2025" to "27 reporters...
  2015-2026"; the underlying claim held, just needed the count corrected.
- **Three real front-end bugs found via live CDP checks on Malta**
  (the zero-export-data edge case), not from reading the code alone:
  1. `index.template.html`: `selectedYear = years[years.length - 1]` is
     `undefined` when `years` is empty, rendering "Top destination
     countries, undefined" above a meaningless empty 0-1-axis chart.
     Fixed with a `noDataNote`/`updateNoDataState()` pair that hides both
     chart panels and shows "No export data has been reported for Malta
     in this period" instead, wired into both the initial page load and
     `renderAll()`.
  2. `map.template.html` and `monthly.template.html` (independent copies
     of the same logic, no shared module between templates): their
     `quantileBreaks()` returned `bucketCount - 1` entries of `undefined`
     for empty input instead of `[]`, because `sortedValues[-1]` silently
     reads as `undefined` rather than erroring -- so `updateLegend()`'s
     existing `if (!breaks.length)` "No data for this selection" guard
     never triggered (length was 4, just full of `undefined`), and the
     legend rendered "< NaN", "NaN – NaN" etc. instead. Fixed by returning
     `[]` immediately when `sortedValues` is empty, in both files --
     this is the actual root cause, and the already-correct "no data"
     message now reaches the screen as originally intended. Also fixed
     `map.template.html`'s title (`years[yearSlider.value]` → "undefined"
     when `years` is empty) to show "no data for this reporter" instead.
  3. `monthly.template.html`: the year-tab buttons (2015/2016/.../2026)
     were built **once**, from a bare top-level `years.forEach(...)`, and
     never rebuilt on reporter switch -- so Malta kept showing Austria's
     full 12-tab row even though Malta's own `years` array is `[]`,
     misleadingly implying 12 years of data exist to click through.
     `applyReporterData()` also never reset `selectedYear`, so it stayed
     pinned to whatever the previously-viewed reporter's last year was.
     Fixed by extracting tab-building into `buildYearTabs()` (clears and
     rebuilds the tab row), called both at initial load and from
     `applyReporterData()`, which now also resets `selectedYear` to
     `years.length ? years[years.length - 1] : undefined` on every
     switch.
  Verified all three fixes live via CDP: Malta now shows a clear
  "no data" state with zero console errors on `index.html`, `map.html`,
  and `monthly.html`; re-verified Austria (the server-baked default) and
  Poland (a normal, full-data reporter) still render identically to
  before on all three pages, so the fixes don't regress the common case.
  `trade_pairs.html` was already fine without any fix -- it blends export
  and import data per partner and shows explicit "Exported: 0 animals"
  rather than relying on a possibly-empty `years` array.
- Full lint + test suite clean throughout (44 passed, ruff clean) --
  checked after every substantive change, not just once at the end.
- All six `build_*.py` scripts re-run after every fetch/code change
  (`build_dashboard.py`, `build_map.py`, `build_monthly.py`,
  `build_trade_pairs.py`, `build_site.py`, `build_mirror.py`) --
  `public/` now reflects all 27 reporters with validated data and the
  three front-end fixes above.
- Not yet done: none of this session's changes (the 27-reporter data, the
  `validate_api_response()`/`AGGREGATE_PARTNERS`/`COUNTRY_NAMES` fixes, or
  the three front-end empty-data fixes) have been committed to git yet.

**Update, same day**: both "for later" items above were picked back up
and finished. The section-13 commit covers everything through the
27-reporter expansion; the map.html pink fill and the meat-trade
research (and the new page it led to) are documented below in sections
14 and 6.1 respectively.

## 14. New page: public/beef_vs_cows.html ("Live vs. Meat") — 2026-10-06

User's own framing, verbatim: *"i think lets build an additional view
that will be beef vs cows comparison"* -- clarified via two quick
questions before building anything (given the real scope: a whole new
fetch pipeline, not a UI tweak) into: a reporter's own live cattle
**exports** next to that same reporter's beef/veal meat **imports**,
shown side by side in each side's native unit (animals vs. tonnes) with
no shared-unit conversion -- both the user's explicit, "(Recommended)"
picks.

**Why import-only/export-only, and why no conversion**: directly follows
section 6.1's research -- "live calves leave, meat comes back" is the
actual investigative question, and there's no single verified live-
weight-to-meat-weight conversion factor (dressing percentage varies by
animal type; section 6 already found this out the hard way for the
veal/beef weight-bracket question). Showing both numbers as Eurostat
actually reported them, rather than inventing a blended figure, was the
deliberate choice.

**New fetch pipeline (`scripts/fetch_meat_imports.py`,
`scripts/meat_products.py`)**: meat (CN headings 0201/0202, 24 CN8 codes,
the same set already verified live in section 6.1) needed its own fetch
script, not just a new category on the existing one, because its
quantity indicator is different -- **confirmed live that meat CN8 codes
return no `SUPPLEMENTARY_QUANTITY` rows at all** (only `VALUE_IN_EUROS`);
the real quantity indicator is `QUANTITY_IN_100KG` (found by testing
every plausible-sounding candidate from the generic `CXT_INDICATORS`
codelist against the live API one at a time -- most returned HTTP 400,
only `QUANTITY_IN_100KG` actually worked for this dataset). This is a
real, structural difference from every other fetch in this project
(live cattle, always head counts), not a naming inconsistency to paper
over.

Rather than duplicate `fetch_at_history.py`'s `validate_api_response()`/
`aggregate()`/`_pivot_indicators()`, generalized them (this is the
genuine "second concrete case" the project's own stated convention asks
for before adding an abstraction):
- `validate_api_response()` gained a `products` parameter (was hardcoded
  to the module-level live-cattle `PRODUCTS`), defaulting to `PRODUCTS`
  so every existing call site is unaffected.
- `_pivot_indicators()`/`aggregate()`/`aggregate_monthly()` gained an
  `indicator_columns` parameter (was hardcoded to
  `{"SUPPLEMENTARY_QUANTITY": "quantity", "VALUE_IN_EUROS": "value_eur"}`),
  same defaulting approach. `fetch_meat_imports.py` passes
  `{"QUANTITY_IN_100KG": "quantity_100kg", "VALUE_IN_EUROS": "value_eur"}`
  -- the deliberately different column name (`quantity_100kg`, not
  `quantity`) is intentional, so a future bug that accidentally mixed up
  which side's data went where would throw a KeyError instead of
  silently plotting tonnes as animals.
- `fetch_year()`/`fetch()` were **not** shared (duplicated in
  `fetch_meat_imports.py` instead) -- this matches the *already-existing*
  pattern (`fetch_at_imports.py` already duplicates these two rather than
  importing them, since the SDMX key needs different PRODUCTS/FLOW baked
  in each time), not a new inconsistency introduced here.

**Two real data-quality findings from the live 27-reporter meat fetch**,
both confirmed against the live API before fixing, not guessed:
1. **A blank/NaN `partner` field** on a handful of rows (confirmed live
   for Germany 2023: 10 rows, one product/month combination, every other
   column present and valid) -- crashed `validate_api_response()`'s
   "missing observation dimension" check, which aborted the *entire*
   multi-year fetch for that reporter (same failure shape as the
   empty-year bug from section 13). Affected 8 of 27 reporters (CY, DK,
   FR, DE, GR, IT, MT, NL). Fixed by filling blank `partner` with `QX`
   (Eurostat's own "not specified for commercial or military reasons"
   code, confirmed to exist in `CXT_FREE_ISO`) before that check runs --
   the specific choice of QX over its intra-/extra-EU-specific siblings
   (QY/QZ) is an inference (blank rows don't say which), but doesn't
   matter here since `AGGREGATE_PARTNERS` excludes all of them the same
   way.
2. **`QY` itself showing up as a literal (non-blank) partner value**,
   confirmed in Estonia's 2018 meat-import data -- it's a real Eurostat
   confidentiality code (`CXT_FREE_ISO`: "...not specified for commercial
   or military reasons..."), the same family as `QV`/`QW` already in
   `AGGREGATE_PARTNERS` but not previously seen, since those only cover
   "destination genuinely unknown," a different concept. Added `QU`,
   `QX`, `QY`, `QZ` to `AGGREGATE_PARTNERS` together, pre-emptively
   covering the rest of the family rather than waiting to hit each one by
   accident across future refreshes.
- Re-ran just the 8 affected reporters after the fix -- all succeeded.
  All 27 reporters confirmed present (`data/processed/<code>_beef_
  imports_yearly_by_product.csv`) before building.
- **27 more partner-country codes** turned up once meat data existed for
  all 27 reporters (meat ships much further than live cattle does) --
  checked live against `CXT_FREE_ISO` the same way as every other
  `COUNTRY_NAMES` addition in this project, all real countries (Chile,
  Hong Kong, New Zealand, Taiwan, Uruguay, etc. -- see `countries.py` for
  the full list), none needed exclusion.

**The page itself** (`public/beef_vs_cows.template.html` ->
`scripts/build_beef_vs_cows.py`): deliberately simpler than
`index.template.html` -- no category or geography filter sidebar (there's
no sub-category to filter by on the meat side, see `meat_products.py`'s
docstring for why; keeping the live-cattle side a plain total too keeps
both panels directly comparable in scope), no unit toggle (units are
fixed per panel, €/animals-style toggling doesn't apply the same way
when the two panels are already in different units). Two independent
Chart.js bar charts, each with its own independent "no data" state --
**tested live with Malta, which turns out to be a genuinely interesting
real finding, not just an edge case**: Malta has zero live-cattle exports
(already known, section 13) but real, substantial beef/veal meat imports
(3,000-7,000+ tonnes/year) -- i.e. Malta imports meat but has no live
cattle export industry at all. The page shows this correctly: "No live
cattle export data has been reported for Malta in this period" on the
left, a real populated chart on the right, independently. Verified live
via CDP on Austria (default), Poland (normal reporter, confirmed only
failed once before the full 27-reporter build finished -- expected
fallback-to-Austria behavior, not a bug, re-verified clean after
rebuilding), Malta (the edge case), and at a 390px mobile viewport --
zero console errors throughout, panels stack correctly on mobile.
Added to `scripts/site_nav.py`'s `PAGES` ("Live vs. Meat", between
"Export vs. Import" and "Methodology"), `scripts/refresh_all.py` (fetch +
build steps), and `README.md`'s page table.
New tests: `tests/test_build_beef_vs_cows.py` (load/render functions,
same tmp_path-CSV approach as every other `test_build_*.py`), plus two
new tests in `tests/test_fetch_at_history.py` for the `products`/
`indicator_columns` generalization specifically. 51 tests passing, ruff
clean.

Not yet done: none of this is committed to git yet (same as section 13's
work -- nothing in this session has been committed/pushed).
Not scoped/not asked for: a fresh/chilled (0201) vs. frozen (0202) split
on the meat side would be real and verifiable (unlike a veal split,
there's a genuine CN-code line to split on) but wasn't requested -- the
page currently shows combined meat.
