# Croatia 2024: what's weird, and how it was checked

> **Scope note:** everything in this doc uses only the two original CN8
> codes -- `01022110` (pure-bred breeding heifers) and `01022130` (pure-bred
> breeding cows) -- i.e. the **"Ursprüngliche Auswahl"** category in the
> dashboards' filter. This investigation predates the later widening of the
> project's scope to all 35 CN8 codes under heading 0102 (live cattle,
> excl. buffalo). If you're looking at a dashboard with "Alle Kategorien"
> selected, the totals there won't match the numbers quoted below --
> select "Ursprüngliche Auswahl" only to see the same figures this doc is
> built on.

Tobi flagged that Croatia's number for 2024 looks large. It is:

| Year | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| Quantity | 318 | 498 | **4,813** | 728 |

A ~10x jump for one year, then back down. This doc walks through how that
number was checked, and a real problem it turned up.

## Step 1 — is it a pipeline bug? (No.)

```python
import pandas as pd

raw = pd.read_csv(
    "data/raw/comext_bovine_export_AT_2015-2025.csv",
    dtype={"product": str, "partner": str},
)
hr_2024 = raw[(raw.partner == "HR") & (raw.TIME_PERIOD.str.startswith("2024"))]

print(hr_2024.duplicated(subset=["TIME_PERIOD", "product"]).sum())  # 0 -- no duplicate rows
print(hr_2024.OBS_VALUE.sum())                                       # 4813 -- matches exactly
```

19 distinct monthly rows, zero duplicates, sum to exactly 4,813. Whatever
this number is, it isn't a double-count in the aggregation code.

## Step 2 — is it stale/cached data? (No.)

Re-querying Eurostat's live API directly (not the cached file) returns the
same 19 rows, identical values. Not a caching artifact either.

## Step 3 — where's the spike, within the year?

```python
print(hr_2024.groupby("TIME_PERIOD").OBS_VALUE.sum())
```

```
2024-01      33
2024-02      18
2024-03      60
2024-04      23
2024-05      33
2024-06      46
2024-08     492
2024-09      64
2024-10    1261
2024-11    1408
2024-12    1375
```

Jan–Jun is normal (~35/month, in line with other years). The entire spike
is Aug and Oct–Dec — 4,044 of the 4,813 total in just three months
(Oct–Dec). Almost all of it is one product code, `01022110` (heifers), not
`01022130` (cows).

A single mis-keyed row (e.g. a misplaced decimal) usually shows up as one
odd month, not three consecutive months holding steady around 1,300–1,400.
That pattern argues *against* a simple typo.

## Step 4 — the actual red flag: mirror statistics don't match

Eurostat doesn't just have Austria's declarations — every EU country
reports its own trade too. So Croatia's own reported *imports from
Austria* should roughly match what Austria says it *exported to Croatia*.
They don't:

```python
import requests

url = (
    "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1"
    "/data/DS-045409/M.HR.AT.01022110+01022130.1.SUPPLEMENTARY_QUANTITY"
)
resp = requests.get(url, params={
    "startPeriod": "2024-01", "endPeriod": "2024-12", "format": "SDMX-CSV",
})
print(resp.text)
```

This returns **zero rows.** Croatia's own customs/statistics office
reported *no imports from Austria at all* in this product category for
2024 — not a small number, literally no data. (Broadening the query to
all flow directions turns up a handful of small `HR → AT` rows instead —
the reverse direction, totalling under 300 head across the year — nothing
resembling Austria's reported 4,813 in the other direction.)

So: Austria says ~4,800 head went to Croatia in 2024. Croatia's own
records show essentially nothing arriving from Austria that year. That's
a genuine mismatch, not just rounding or timing noise. Eurostat has a
name for this kind of reporter-vs-partner gap — an **asymmetry** — and a
formal process for investigating it, covered in Step 6 below.

## Step 5 — one specific hypothesis: did monthly figures that should have
been reported separately get added up cumulatively toward year-end?

This is testable two ways.

**A. If Oct/Nov/Dec were cumulative running totals mistakenly reported as
monthly figures, each month would have to be ≥ the previous one** — a
running total can't go down. It doesn't:

```python
q4 = hr_2024[hr_2024.TIME_PERIOD.isin(["2024-10", "2024-11", "2024-12"])]
print(q4.groupby("TIME_PERIOD").OBS_VALUE.sum())
```

```
2024-10    1261
2024-11    1408
2024-12    1375   <- lower than November
```

Dec is lower than Nov. A true cumulative-total mixup can't produce that
dip, so this specific mechanism doesn't fit.

**B. Is the Q4-heavy shape even unusual for Croatia, or is 2024 just a big
year with the same shape as always?**

```python
hr["year"] = hr.TIME_PERIOD.str.slice(0, 4)
hr["month"] = hr.TIME_PERIOD.str.slice(5, 7)

yearly = hr.groupby("year").OBS_VALUE.sum()
q4 = hr[hr.month.isin(["10", "11", "12"])].groupby("year").OBS_VALUE.sum()
for y in sorted(yearly.index):
    print(y, "Q4 share:", round(100 * q4.get(y, 0) / yearly[y], 1), "%")
```

```
2015: 59.5%   2019: 53.4%   2023: 28.9%
2016:  0.0%   2020: 23.1%   2024: 84.0%
2017: 16.9%   2021: 13.6%   2025: 52.6%
2018: 88.2%   2022: 30.5%
```

2018 was *more* Q4-concentrated than 2024 (88.2% vs 84.0%), and half the
other years also lean majority-Q4. So the backloaded shape isn't the
anomaly — that's just how Croatia's AT-import reporting (or the real
trade) normally runs. What's actually unusual about 2024 is purely the
**magnitude**, not the timing.

One honest limitation: the `LAST UPDATE` field in the raw data is
identical, down to the second, across every 2024 row for Croatia —
that's a dataset-wide sync timestamp from Eurostat's side, not a per-row
original-submission date, so this data doesn't give visibility into
revision history fine-grained enough to fully rule out a batch backfill
some other way. But the specific "monthly figures got summed cumulatively
into one month" mechanism is not supported by the evidence available.

## Step 6 — how unusual is Croatia's mismatch, really? Checking five more partners

Eurostat's own methodology guide for this dataset — the *Compilers guide
on European statistics on international trade in goods* (2017 edition,
[KS-02-17-333](https://ec.europa.eu/eurostat/documents/3859598/8021340/KS-02-17-333-EN-N.pdf)),
Section 7.1 "Asymmetries" (p. 185) — confirms this kind of reporter-vs-
partner mismatch is a known, actively monitored issue, not something
unique to this dataset or this trade lane:

> §816: "For trade in goods statistics, comparability across countries is
> a more visible quality dimension than for most other statistical
> domains. Once asymmetries are identified and measured through a mirror
> analysis, further analytical work should be initiated to identify their
> causes. [...] data corrections and/or changes in methodologies and
> practices require the Member States involved to perform the analysis
> jointly, to agree on the asymmetry causes and on the corrections to be
> done in their respective data. This is called a 'reconciliation
> exercise'."

Chapter 12 ("Tools for reconciliation", p. 222) gives the formula Eurostat
itself uses to measure how big an asymmetry is:

```
Relative Asymmetry = (Reporter − Mirror) / ((Reporter + Mirror) / 2)
```

This ranges from 0% (perfect match) to ±200% (one side reports a real
number, the other reports nothing at all — Croatia's case). Applying that
formula to Austria's five other biggest 2024 partners in this same
product category, using the same live cross-check as Step 4:

| Partner | AT says (export) | Partner says (import) | Relative asymmetry |
|---|---:|---:|---:|
| 🇭🇷 Croatia | 4,813 | 0 | **200.0%** |
| 🇩🇪 Germany | 2,499 | 13 | **197.9%** |
| 🇷🇴 Romania | 224 | 25 | 159.8% |
| 🇭🇺 Hungary | 2,940 | 889 | 107.1% |
| 🇮🇹 Italy | 4,516 | 5,403 | −17.9% |
| 🇪🇸 Spain | 149 | 129 | 14.4% |

(Türkiye, Austria's single biggest partner in this category at 8,382 head,
can't be checked this way — Turkey doesn't report into Eurostat's
intra/extra-EU trade system, so DS-045409 has no Turkish-side mirror data
to compare against.)

This reframes the finding. **Croatia isn't uniquely broken — it's the most
extreme point on a pattern that shows up across several of Austria's
partners in this specific, low-volume product category.** Germany's
mismatch is nearly as extreme in relative terms (197.9%, vs. Croatia's
theoretical-maximum 200%), and Romania and Hungary both show large,
one-sided gaps too. Only Italy and Spain come close to matching Austria's
numbers. Croatia does still stand out on two dimensions at once — it's
both the largest mismatch in absolute head count *and* one of the two
fully one-sided cases (0 reported, not just "much smaller") — which is
why it was the one flagged in the first place, but it isn't an isolated
glitch.

That several partners show large asymmetries specifically in this
low-volume, pure-bred-breeding product category (rather than across
Austria's trade generally) points toward a *systematic* rather than a
one-off cause — see the discussion below.

## Step 7 — is Croatia's side missing just the head count, or the whole declaration?

One specific, testable hypothesis: maybe Croatia's importer(s) *did*
declare this trade — value, partner, everything — and only the
`SUPPLEMENTARY_QUANTITY` (head count) field specifically was left out
under a simplification rule. If so, querying the same reporter/partner/
product/period combination for the *value* indicator instead of quantity
should turn up real numbers even though quantity came back empty.

```python
url = (
    "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1"
    "/data/DS-045409/M.HR.AT.01022110+01022130.1.VALUE_IN_EUROS"
)
resp = requests.get(url, params={
    "startPeriod": "2024-01", "endPeriod": "2024-12", "format": "SDMX-CSV",
})
print(resp.text)
```

**Also zero rows.** Croatia's side has no value declared for this trade
either — not a partial declaration with the quantity field dropped, but a
total absence of any matching record. Checked against a country with real
mirror data as a sanity check on the query itself (Italy: real monthly
`VALUE_IN_EUROS` rows come back, e.g. €93,388 for January 2024), so this
isn't a wrong-indicator-name problem.

Germany's mirror, checked the same way, tells a related but distinct
story: a *single* `VALUE_IN_EUROS` row for the entire year (€6,105, June
2024) against Austria's claimed 2,499 head sent to Germany across the
year. So Germany's importers filed *something* — one small, presumably
fully-compliant transaction — while the rest of the year's trade is
absent from Germany's own statistics too, not partially reported.

This changes which mechanism from the next section best fits the data: a
"quantity field omitted, but the transaction otherwise declared"
simplification would leave a value trail. What's actually observed —
nothing at all, on both the value and quantity side — points more toward
either the trade never triggering an Intrastat obligation on the partner's
side at all (see the exemption threshold, below), or the goods being
recorded under a different partner-country code entirely (see
quasi-transit/triangular trade, also below).

## Is this a COMEXT data-entry error?

Can't say for certain from the data alone, but Eurostat's Compilers guide
(Chapter 12, "Tools for reconciliation") maintains two standard checklists
of known asymmetry causes — Table 16 ("types of errors") and Table 17
("methodological causes") — and several entries from those tables line up
with what's been found here, roughly most to least likely:

1. **Full exemption from Intrastat reporting on the partner's side
   (Compilers guide §5.1 "Exemption threshold", p. 179, §776–786).** This
   was the first hypothesis tested here, and it's worth being precise
   about which mechanism actually fits, because an earlier draft of this
   doc got it wrong: the exemption threshold is **not** about any single
   shipment being cheap — it's an *annual* threshold, set per member
   state, below which a trading company is exempted from filing *any*
   Intrastat declaration for the whole year, based on that company's
   *total* trade value across all products and all EU partners combined
   (§776: "expressed in annual values [...] at least 97% of total
   dispatches and at least 93% of total arrivals [...] is covered" — the
   remaining traders below that line file nothing at all). A single
   pure-bred breeding animal is genuinely not cheap, which rules out the
   guide's separate, much smaller **individual transaction threshold**
   (§5.3, p. 181, §794–797) — that one explicitly only covers
   transactions under €200 each, "the artificial division of a
   transaction into shares below EUR 200 is not allowed" — cattle
   shipments essentially never qualify. But the annual exemption
   threshold doesn't care how expensive any one shipment is: a small or
   irregular livestock importer in Croatia could deal in genuinely
   valuable animals and *still* fall under the country's annual exemption
   line if livestock trade is a small part of (or all of) a small
   company's yearly turnover. That would explain Step 7's finding
   directly — no value, no quantity, nothing at all, because the
   declaration was never required in the first place. Germany's one
   real transaction alongside an otherwise-empty year is consistent with
   the same mechanism at the level of individual traders: some of
   Austria's German buyers file, some don't, depending on their own
   annual totals.
2. **Simplification threshold for small/medium traders (§5.2, p. 180,
   §787–789).** A related but distinct mechanism, for traders *above*
   the exemption line but still small: they may be allowed to skip
   reporting "the quantity of the goods (net mass and/or supplementary
   unit)" specifically while still filing everything else. This one
   *would* leave a value trail — which Step 7 didn't find for Croatia,
   making it a weaker fit there than full exemption, but it may explain
   partial cases like Germany's, or partners not in the six-country
   comparison above.
3. **Quasi-transit (Table 16, §12.4.1).** The guide describes two named
   sub-cases: goods cleared for import in one member state before being
   immediately re-dispatched to another ("indirect imports"), and goods
   received from one member state before immediately being re-exported
   ("indirect exports"). Either can produce exactly this shape of
   mismatch — one side records the movement, the other doesn't, because
   the customs clearance and the "real" destination happened in different
   countries. This would also explain Step 7's "nothing at all, not even
   value" finding: the goods may be genuinely recorded by Croatia, just
   attributed to whichever country actually cleared customs, not Austria.
   Related: **triangular trade (§12.4.2)** — a three-country deal
   (contract with country B, physical goods movement A→C) where one side
   reports the contracting partner instead of the physical one.
4. **Product misclassification (Table 16, §12.4.7).** An actual
   classification or entry error on the Austrian side — e.g. a
   consignment coded to the wrong partner country. The guide notes this
   is "considered to be a major reason for asymmetries in detailed
   statistics" generally, though the multi-month sustained pattern here
   (vs. one isolated row) makes a simple one-off typo less likely than
   the systematic explanations above.
5. **Not a cumulative-reporting mixup** — ruled out in Step 5: the monthly
   values aren't monotonically increasing the way a running total would
   have to be, and the Q4-heavy shape recurs in most other years too, so
   it isn't something unique to how 2024 got reported.

None of these can be confirmed without either Statistics Austria/Croatia's
input or someone with domain knowledge of a specific 2024 deal — that's
exactly what the guide's own "reconciliation exercise" process (Chapter
12.3) is for, and it requires the two national statistical authorities to
cooperate directly; it isn't something resolvable from public API data
alone. What *can* be said confidently: this number is unusually
well-supported on Austria's side (real rows, no duplicates, matches the
live API) and unusually *unsupported* on Croatia's side (no matching
import declarations at all) — and that same one-sided pattern, to varying
degrees, shows up across several of Austria's other partners in this same
low-volume product category, which points toward a systematic reporting-
threshold effect rather than a one-off data-entry mistake specific to
Croatia.

## References

- Eurostat, *Compilers guide on European statistics on international
  trade in goods* — 2017 edition, product code KS-02-17-333.
  [Landing page](https://ec.europa.eu/eurostat/web/products-manuals-and-guidelines/-/KS-02-17-333) ·
  [Full PDF](https://ec.europa.eu/eurostat/documents/3859598/8021340/KS-02-17-333-EN-N.pdf)
  · local copies saved in this repo at
  `docs/references/eurostat_compilers_guide_KS-02-17-333.pdf` (full text,
  ~6.2 MB) and `docs/references/eurostat_compilers_guide_KS-02-17-333_TOC.pdf`
  (table of contents only), in case the Eurostat URL ever moves or the
  document gets superseded by a newer edition
  — Chapter 5 "Thresholds within the Intrastat system" (p. 178–181,
  §770–797, incl. 5.1 "Exemption threshold" and 5.3 "Individual
  transaction threshold"), Section 7.1 "Asymmetries" (p. 185, §816–818),
  and Chapter 12 "Tools for reconciliation" (p. 222–236, incl. Table 16
  "Types of errors causing mirror discrepancy" and Table 17
  "Methodological causes for mirror discrepancies", both p. 227–228). All
  page/paragraph numbers above were read directly from this PDF, not
  taken on trust from a secondary source.
- `docs/eurostat_comext_api.md` and the two Eurostat User Support reply
  `.docx` files in this project's root folder — confirm DS-045409 as the
  correct dataset. One reply also quotes "the compilers' guide, page 207"
  on a *different* threshold value (traders declaring consignments under
  €1,000 exempted from quantity reporting) than what this project's own
  copy of the 2017 edition shows at a similarly-numbered paragraph range
  (which covers the Quality Handbook, not thresholds, around p. 184) —
  most likely a newer edition with renumbered/updated paragraphs and a
  since-raised threshold value, not a contradiction. Left uncited above
  since it couldn't be verified directly against this project's own copy
  of the guide; the €200 individual-transaction threshold and the annual
  exemption threshold, both used above, were.
