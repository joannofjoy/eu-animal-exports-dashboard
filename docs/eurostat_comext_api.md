# Eurostat Comext API notes

## What the API can do

Comext (detailed international trade in goods) is served from a separate
endpoint from the main Eurostat API:

```
https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/
```

It's a standard SDMX 2.1 REST API:

- `datastructure/ESTAT/{dataset}` — dimensions and their codelists for a dataset
- `data/{dataset}/{key}?startPeriod=...&endPeriod=...&format=SDMX-CSV` — the actual data

The `{key}` is a dot-separated value per dimension, in the dataset's declared
dimension order (e.g. `freq.reporter.partner.product.flow.indicators`).
Multiple codes for one dimension are joined with `+`; an empty segment
means "all values" for that dimension. `format=SDMX-CSV` returns a flat CSV,
which is much easier to work with than the default SDMX-ML/JSON-stat.

**Full, unfiltered dataset downloads are disabled** — every query must be
filtered (reporter/partner/product/flow/etc.), unlike the old bulk `.dat`
download service. This is why `download_data.py` builds a narrow key instead
of pulling everything and filtering client-side.

Each dataset also has its own codelist versions, so the same-looking
dimension (e.g. `product`, `indicators`) can allow different codes in
different datasets — always worth checking `datastructure` for the specific
dataset before assuming a code carries over.

## Official dataset names (from ALL_DATAFLOWS.xml)

Eurostat's own dataflow catalog confirms the distinction found by testing:

- **`DS-045409`**: *"EU trade since 1988 by HS2-4-6 and CN8"* — EU-only,
  CN8 detail included.
- **`DS-059341`**: *"International trade of EU and non-EU countries since
  2002 by HS2-4-6"* — wider reporter scope, but stops at HS6 (no CN8).

(Correction: `DS-045409` covers data back to 1988, not 2002 as stated
earlier in this doc.)

## Why DS-045409 is the dataset we use

We need: CN8 product codes (`01022110`, `01022130`) and a head-count
indicator (the API's equivalent of the old bulk file's `SUP_QUANTITY`
column). Three candidate dataset codes were checked:

| Dataset | Status | Problem |
|---|---|---|
| **DS-045409** | ✅ Works | CN8 products + `SUPPLEMENTARY_QUANTITY` indicator, both intra- and extra-EU partners in one query |
| DS-059341 | Live, but wrong granularity | Product codelist only goes to CN6 (e.g. `0102`, `010221`); no head-count indicator, only `QUANTITY_KG`/`VALUE_EUR`/`VALUE_NAC`. Querying CN8 codes or `SUPPLEMENTARY_QUANTITY` returns `INVALID_QUERY_DIMENSION_VALUE` |
| DS-059322 | Retired | Structure endpoint responds, but the data endpoint returns `ERR_NOT_FOUND_2: DATA_SET is not available for dissemination` — a 404, not a query problem |

So `DS-045409` isn't an arbitrary pick — it's the only one of the three that
is both currently live and structurally capable of returning CN8-level
live-animal head counts. This was confirmed by cross-checking its 2022
figures against a locally held official bulk file (`fullxixu202252.dat`,
restricted to `XI`/`XU` UK partner codes) — the quantities matched exactly.

## Other differences between DS-045409 and DS-059341

Both datasets share the same underlying codelist versions (reporter/partner
`CXT_FREE_ISO` v10.0, product `CXT_NC` v11.0, indicators `CXT_INDICATORS`
v31.0) — the gap isn't stale reference data, it's what each dataset actually
has populated:

- **Reporter scope.** `DS-045409` only has the 27 EU Member States (plus
  `EU`/`EU27_2020`/`EA`/`EA21` aggregates) as reporters. `DS-059341` is
  considerably wider: EU Member States **plus** EFTA (`CH`, `IS`, `LI`,
  `NO`) **plus** candidate / potential-candidate / Eastern Partnership
  countries reporting their own trade (`AL`, `BA`, `GE`, `MD`, `MK`, `TR`,
  `UA`, `XK`, `XS`) **plus** Northern Ireland as its own reporter (`XI`).
  So `DS-059341` looks like it's meant for EU-vs-wider-Europe comparisons,
  not just Member State self-reported trade.
- **Product depth.** `DS-045409` resolves down to CN8 (`01022110`).
  `DS-059341` tops out at HS6 (`010221`) — the CN8 codes exist in the
  shared codelist but aren't populated for this dataset, which is why the
  earlier query for `01022110` against `DS-059341` failed.
- **Indicators.** `DS-045409` carries `SUPPLEMENTARY_QUANTITY` (head count)
  alongside value/weight. `DS-059341` only has `QUANTITY_KG`, `VALUE_EUR`,
  `VALUE_NAC` — weight and value, no head count.

Net effect: `DS-059341` would be the better choice if the analysis ever
needs to include non-EU European reporters (e.g. Ukraine, Turkey, Norway
exporting live animals) at HS6/weight level — but for EU Member State
exports by head count at CN8, it can't substitute for `DS-045409`.
