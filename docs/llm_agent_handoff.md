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

Pure static site. `scripts/fetch_*.py` hit the live Eurostat Comext SDMX
API and write raw CSVs to `data/raw/`; `scripts/build_*.py` read
`data/processed/` CSVs, do zero network I/O, and fill `__PLACEHOLDER__`
tokens in `public/*.template.html` to produce the real `public/*.html`
files. Never edit a `.html` file directly — it gets silently overwritten
next build. No server, no database; pages are meant to work opened
directly via `file://` (double-click), which has shaped several decisions
below. Run `.venv/Scripts/python.exe -m ruff check .` and `-m pytest -q`
before considering any change done — both must be clean.

Six reader-facing-ish pages, all built from their own `build_*.py` +
`*.template.html` pair: `index` (Yearly Exports), `map`, `monthly`,
`trade_pairs` (Export vs. Import), `dashboard` (Combined View — built but
deliberately **not linked** in the site nav, see `site_nav.py`), `mirror`
(Mirror Statistics — internal dev/QA tool, styled as muted/italic in the
nav, not a finished reader-facing dashboard).

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
- No automated data refresh exists (same gap `progress_notes.md` flagged
  in the PHP era) — `fetch_at_history.py`/`fetch_at_imports.py` are manual
  runs, one per reporter. 2026's figures aren't in yet as of this writing.
- Only tested in Chromium/Edge (via CDP) and, for the persistence bug
  specifically, debugged against real user reports from Firefox. Safari
  is untested.
