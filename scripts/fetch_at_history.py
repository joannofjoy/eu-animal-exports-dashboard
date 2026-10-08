"""Fetch a reporter country's live cattle exports (2015-latest full year)
from Eurostat Comext dataset DS-045409, and aggregate to yearly totals.
Defaults to Austria (--reporter AT), the country this whole project started
with, but works for any Comext reporter -- Comext only accepts the 27 EU
member states as reporters (a non-EU country never *reports* to Eurostat,
it can only appear as a *partner* in another country's own declarations),
confirmed against the CXT_FREE_ISO codelist and against the 09.07.2026
project meeting notes ("reporting country -- only 27 EU the API EUROSTAT
that we will use").

Covers every CN8 code under heading 0102 (live bovine animals) except
buffalo (010231/010239 -- a different species under the same heading) and
except the four 010210xx codes (pure-bred breeding bovines under the
pre-2002-ish nomenclature, superseded by 010221/010231) -- confirmed via
the live API to have zero rows for AT across the entire 2015-2025 window,
so they're left out rather than kept as dead weight in the query and the
category filter. What's covered: pure-bred breeding cattle (01022110
heifers, 01022130 cows, 01022190 other) and ordinary/slaughter cattle by
weight class (the 010229xx and 01029xxx codes). An earlier version of
this project only tracked the two pure-bred breeding codes; checking the
full breakdown showed that's only about a quarter of Austria's actual
live cattle export volume, so PRODUCTS below now covers the whole heading
(see docs/progress_notes.md).

Flow=2 (export). Pulls two indicators in the same query:
SUPPLEMENTARY_QUANTITY (head count -- confirmed to exist for the
non-breeding codes too, not just the pure-bred ones) and VALUE_IN_EUROS
(the trade value in euros, for "how much money is that" alongside the
animal counts). Comext's SDMX key allows joining multiple indicator codes
with "+", the same way PRODUCTS below joins multiple product codes, so
this is one request per year, not two -- confirmed live: a query for
SUPPLEMENTARY_QUANTITY+VALUE_IN_EUROS returns both, tagged by an
"indicators" column in the response, at no extra cost over asking for one.
See docs/eurostat_comext_api.md for why DS-045409 is the dataset used
(confirmed by Eurostat user support).

This is the first step of the data pipeline: it talks to the internet and
writes CSV files. The second step, scripts/build_dashboard.py, reads those
CSVs and turns them into the actual webpage -- it never talks to the
internet itself, so re-running the dashboard build doesn't need this script
to run again unless the underlying data should be refreshed.

Writes (each processed CSV now has both a "quantity" column, head count,
and a "value_eur" column, trade value in euros -- see aggregate()). The
reporter code (lowercased) prefixes every filename, so Austria's own files
keep the exact names the rest of this project already expects -- adding a
new reporter never touches Austria's files, it just adds a parallel set:
  data/raw/comext_bovine_export_<REPORTER>_<start>-<end>.csv   raw monthly rows
  data/processed/<reporter>_bovine_exports_yearly_by_product.csv
                                                                year,product,quantity,value_eur
  data/processed/<reporter>_bovine_exports_yearly_by_partner.csv
                                                                year,partner,quantity,value_eur
  data/processed/<reporter>_bovine_exports_yearly_by_partner_product.csv
                                                                year,partner,product,quantity,value_eur
                                                                (keeps both breakdowns at once,
                                                                for the dashboards' category
                                                                filter -- see product_categories.py)
  data/processed/<reporter>_bovine_exports_monthly_by_partner_product.csv
                                                                month,partner,product,quantity,value_eur
                                                                (same idea, but keeps the month
                                                                instead of collapsing to year --
                                                                for public/monthly.html)

Run it from the command line, e.g.:
  python scripts/fetch_at_history.py --reporter AT --start-year 2015 --end-year 2025
  python scripts/fetch_at_history.py --reporter DE --start-year 2015 --end-year 2025
"""

import argparse
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"

# Kept as the default reporter (see main()'s --reporter argument) rather
# than removed -- this project started as Austria-only, and every existing
# processed CSV, build script, and template still assumes Austria's files
# exist under their original (unprefixed-by-choice, i.e. "at_"-prefixed)
# names, so AT stays the default everywhere a reporter isn't specified.
REPORTER = "AT"

# Every CN8 code under heading 0102 (live bovine animals), excluding buffalo
# (010231/010239) and excluding the four 010210xx codes (pure-bred breeding
# bovines under the pre-2002-ish nomenclature -- verified to have zero AT
# export rows in 2015-2025, since they were superseded by 010221/010231
# before this data window starts). Grouped here by sub-heading to match the
# official nomenclature structure -- see the CXT_NC codelist for the full
# names.
PRODUCTS = [
    # 010221 -- pure-bred cattle for breeding (current nomenclature)
    "01022110",
    "01022130",
    "01022190",
    # 010229 -- live cattle, excl. pure-bred for breeding, by weight class
    "01022905",
    "01022910",
    "01022921",
    "01022929",
    "01022941",
    "01022949",
    "01022951",
    "01022959",
    "01022961",
    "01022969",
    "01022991",
    "01022999",
    # 010290 -- other live bovine animals, excl. cattle/buffalo, by weight class
    "01029005",
    "01029010",
    "01029020",
    "01029021",
    "01029029",
    "01029031",
    "01029033",
    "01029035",
    "01029037",
    "01029041",
    "01029049",
    "01029051",
    "01029059",
    "01029061",
    "01029069",
    "01029071",
    "01029079",
    "01029090",
    "01029091",
    "01029099",
]
FLOW = "2"  # export
# Head count and trade value, requested together (Comext lets you join
# multiple indicator codes with "+", same as PRODUCTS does) -- the
# response comes back with one row per (period, partner, product,
# indicator) combination, tagged in the "indicators" column, rather than
# needing two separate requests.
INDICATORS = ["SUPPLEMENTARY_QUANTITY", "VALUE_IN_EUROS"]

# Aggregate/grouping partner codes to exclude from per-partner and per-product
# totals (these overlap with real country codes and would double-count).
# A set (curly braces, like a dict but with no values) is used instead of a
# list because checking "is this code in here?" is what this collection is
# for, and sets do that check faster than lists do.
AGGREGATE_PARTNERS = {
    "WORLD",
    "EXT_EA",
    "EXT_EA21",
    "EXT_EU",
    "EXT_EU27_2020",
    "INT_EA",
    "INT_EA21",
    "INT_EU",
    "INT_EU27_2020",
    # Not a double-counting rollup like the ones above -- QV/QW are
    # Eurostat's own "destination not specified" catch-all codes (per the
    # CXT_FREE_ISO codelist: "Countries and territories not specified
    # within the framework of intra-/extra-Union trade"). Only ever
    # showed up once reporters other than Austria were added -- excluded
    # here so this trade doesn't show up as a fake, unnamed "country" row
    # in the per-partner breakdowns.
    "QV",
    "QW",
    # QS is another Eurostat catch-all, not a country: "Stores and
    # provisions within the framework of extra-Union trade" (per the
    # CXT_FREE_ISO codelist) -- found once the 27-reporter rollout turned
    # up a reporter with trade recorded under it.
    "QS",
    # QU/QX/QY/QZ are confidentiality-suppression placeholders -- "...not
    # specified [for commercial or military reasons]" per CXT_FREE_ISO --
    # distinct from QV/QW above (which mean "destination genuinely
    # unknown"), these mean Eurostat deliberately withheld the real
    # partner to avoid identifying individual traders. Found "QY" showing
    # up as a literal partner value once meat-trade fetching started
    # (fetch_meat_imports.py); the other three are the same family and
    # excluded pre-emptively rather than waiting to find each one by
    # accident. See validate_api_response() below for the related case of
    # this showing up as a *blank* partner instead of one of these codes.
    "QU",
    "QX",
    "QY",
    "QZ",
}

# __file__ is this script's own path. .resolve() turns it into a full,
# unambiguous path; .parent.parent walks up two folders (scripts/ -> project
# root), so ROOT_DIR always points at the project root regardless of which
# folder you happened to run this script from.
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"


def fetch_year(year: int, reporter: str = REPORTER) -> bytes:
    """Download one year of monthly export rows from the Eurostat API and
    return the raw response bytes (not yet parsed). reporter defaults to
    Austria but accepts any of the 27 EU member state codes.
    """
    # The API expects a single "key" string that packs all the filters
    # together, dot-separated, in a fixed order (reporter.partner.product.
    # flow.indicator). Leaving the partner segment empty (the ".." below)
    # means "all partner countries", which is what we want here.
    key = f"M.{reporter}..{'+'.join(PRODUCTS)}.{FLOW}.{'+'.join(INDICATORS)}"
    params = {
        "startPeriod": f"{year}-01",
        "endPeriod": f"{year}-12",
        "format": "SDMX-CSV",
    }
    # requests.get() makes the actual HTTP request. timeout=60 means "give
    # up and raise an error if the server hasn't responded within 60
    # seconds" rather than hanging forever. raise_for_status() then checks
    # the HTTP status code and raises an exception if it wasn't a success
    # (2xx) -- so a failed request stops the script here with a clear
    # error, instead of silently continuing with no data.
    response = requests.get(f"{BASE_URL}/{key}", params=params, timeout=60)
    response.raise_for_status()
    return response.content


def validate_api_response(
    df: pd.DataFrame,
    year: int,
    reporter: str,
    flow: str,
    indicators: list[str] = INDICATORS,
    products: list[str] = PRODUCTS,
) -> pd.DataFrame:
    """Reject a successful HTTP response if its observations don't match
    the requested slice or if values/indicator pairs are incomplete.

    Missing one of the paired measures must not silently become a zero in
    _pivot_indicators(): an absent euro value is not evidence of zero value.
    Returning the numeric OBS_VALUE column also keeps later sums from
    depending on pandas' type inference.
    """
    required = {
        "freq",
        "reporter",
        "partner",
        "product",
        "flow",
        "indicators",
        "TIME_PERIOD",
        "OBS_VALUE",
    }
    missing_columns = required - set(df.columns)
    if missing_columns:
        raise ValueError(f"Eurostat response is missing columns: {sorted(missing_columns)}")
    if df.empty:
        # A genuinely empty year is a real possibility for a low-volume
        # reporter (e.g. Cyprus, Malta) or for a year still in progress --
        # confirmed live against the API for Sweden's 2022 imports, which
        # really is just a header row with zero observations, not a
        # broken request. Treating this as fatal would discard every
        # *other* year's real data too, since fetch() only concatenates
        # after validation succeeds for all years. So this returns the
        # empty frame as-is (pd.concat later just contributes zero rows)
        # instead of raising.
        print(f"  Note: Eurostat returned no observations for {reporter}, flow {flow}, {year}")
        return df

    # A blank partner field (not one of the explicit QU/QX/QY/QZ
    # confidentiality codes in AGGREGATE_PARTNERS, an actually-empty
    # value) is a real, if infrequent, Eurostat quirk -- confirmed live
    # for several reporters' meat-import data (e.g. Germany 2023: a
    # handful of rows for one product/month with freq/product/flow/
    # indicators/value all present and correct, but partner blank).
    # These are a handful of low-value rows, consistent with the same
    # confidentiality suppression QY etc. represent explicitly elsewhere
    # -- filled in with QX (Eurostat's generic "not specified for
    # commercial or military reasons" code) rather than raising, since
    # the alternative is discarding an entire year's real data (same
    # fetch()-wide-concatenation reasoning as the empty-year case above).
    # The specific choice of QX over its intra-/extra-EU-specific
    # siblings (QY/QZ) is an inference, not something Eurostat's response
    # states outright -- it doesn't matter for this project's purposes,
    # since AGGREGATE_PARTNERS excludes all four the same way.
    df = df.copy()
    df["partner"] = df["partner"].fillna("QX")

    key_columns = ["freq", "reporter", "partner", "product", "flow", "indicators", "TIME_PERIOD"]
    if df[key_columns].isna().any().any():
        raise ValueError("Eurostat response contains a missing observation dimension")
    if set(df["freq"].astype(str)) != {"M"}:
        raise ValueError("Eurostat response contains a frequency other than monthly")

    if set(df["reporter"].dropna().astype(str)) != {reporter}:
        raise ValueError(f"Eurostat response contains a reporter other than {reporter}")
    if set(df["flow"].dropna().astype(str)) != {flow}:
        raise ValueError(f"Eurostat response contains a flow other than {flow}")
    if not df["TIME_PERIOD"].astype(str).str.startswith(f"{year}-").all():
        raise ValueError(f"Eurostat response contains observations outside {year}")
    unexpected_products = set(df["product"].dropna().astype(str)) - set(products)
    if unexpected_products:
        raise ValueError(
            f"Eurostat response contains unrequested products: {sorted(unexpected_products)}"
        )
    if set(df["indicators"].dropna().astype(str)) != set(indicators):
        raise ValueError("Eurostat response does not contain exactly the requested indicators")

    values = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    if values.isna().any() or values.isin([float("inf"), float("-inf")]).any():
        raise ValueError("Eurostat response contains missing or non-numeric observation values")

    observation_key = ["freq", "reporter", "partner", "product", "flow", "TIME_PERIOD"]
    duplicate_mask = df.duplicated([*observation_key, "indicators"], keep=False)
    if duplicate_mask.any():
        raise ValueError("Eurostat response contains duplicate observation keys")

    indicator_sets = df.groupby(observation_key, dropna=False)["indicators"].agg(set)
    expected_indicators = set(indicators)
    if not indicator_sets.map(lambda found: found == expected_indicators).all():
        raise ValueError("Eurostat response has observation keys missing a requested indicator")

    cleaned = df.copy()
    cleaned["OBS_VALUE"] = values
    return cleaned


def fetch(start_year: int, end_year: int, reporter: str = REPORTER) -> pd.DataFrame:
    """Download every year from start_year to end_year and return them
    combined as one pandas DataFrame (a table you can filter/group/sum,
    similar to a spreadsheet).

    One request per year, not one big request for the whole range: with
    this many product codes (see PRODUCTS above), a multi-year request is
    large enough that Eurostat's API switches to an asynchronous job queue
    instead of answering directly -- it returns a "SUBMITTED" status with
    no data, which would need separate polling to retrieve. Splitting by
    year keeps each individual request small enough to get an immediate,
    synchronous response, matching the pattern scripts/download_data.py
    already uses.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"comext_bovine_export_{reporter}_{start_year}-{end_year}.csv"

    # Collect each year's DataFrame in this list, then glue them together
    # at the end with pd.concat -- simpler than appending rows one at a
    # time to a growing DataFrame.
    years_data = []
    for i, year in enumerate(range(start_year, end_year + 1)):
        content = fetch_year(year, reporter)
        # dtype=str tells pandas "treat these two columns as plain text,
        # don't try to guess a numeric type for them." Without it, pandas
        # notices that partner/product codes are made of digits (e.g.
        # "01022110") and silently converts them to numbers, which strips
        # the leading zero and turns "01022110" into 1022110 -- a real bug
        # that happened earlier in this project.
        year_df = pd.read_csv(BytesIO(content), dtype={"product": str, "partner": str})
        year_df = validate_api_response(year_df, year, reporter, FLOW)
        years_data.append(year_df)

        # Save the first year's raw response with the header row, and
        # every subsequent year without one, appending to the same file --
        # so the combined raw_path file ends up as one normal CSV with a
        # single header, matching what a single big request would have
        # produced.
        mode = "wb" if i == 0 else "ab"
        with open(raw_path, mode) as f:
            if i == 0:
                f.write(content)
            else:
                # Drop the header line (everything up to the first
                # newline) before appending, so it isn't repeated.
                f.write(content.split(b"\n", 1)[1])

    return pd.concat(years_data, ignore_index=True)


INDICATOR_COLUMNS = {"SUPPLEMENTARY_QUANTITY": "quantity", "VALUE_IN_EUROS": "value_eur"}


def _pivot_indicators(
    df: pd.DataFrame,
    group_cols: list[str],
    indicator_columns: dict[str, str] = INDICATOR_COLUMNS,
) -> pd.DataFrame:
    """Shared helper for aggregate()'s three tables: group by group_cols
    (e.g. ["year", "product"]) AND the "indicators" column together, sum
    OBS_VALUE within each group, then pivot "indicators" from being extra
    rows into being extra columns -- so a (year, product) pair that used
    to be two rows (one SUPPLEMENTARY_QUANTITY row, one VALUE_IN_EUROS
    row) becomes one row with both a "quantity" and a "value_eur" column.

    This pivot step matters because summing OBS_VALUE directly (ignoring
    which indicator each row is) would add head counts and euro amounts
    together into one meaningless number -- grouping by "indicators" too
    keeps them apart until the very end, when pivot() lays them out side
    by side instead of stacked as separate rows.

    indicator_columns maps each raw Eurostat indicator code to the output
    column name it should become -- defaults to this project's original
    live-cattle shape (head count + euro value), but fetch_meat_imports.py
    passes a different mapping, since meat's quantity indicator is
    QUANTITY_IN_100KG (there's no per-animal head count for meat), not
    SUPPLEMENTARY_QUANTITY.
    """
    grouped = (
        df.groupby([*group_cols, "indicators"])["OBS_VALUE"]
        .sum()
        .reset_index()
        # pivot() takes the long "indicators" column (one row per
        # indicator) and spreads its distinct values out into their own
        # columns, using "OBS_VALUE" to fill them in -- the inverse of
        # groupby/stack. index=group_cols keeps one output row per
        # original group instead of per (group, indicator) pair.
        .pivot(index=group_cols, columns="indicators", values="OBS_VALUE")
        .reset_index()
        .rename(columns=indicator_columns)
    )
    # pivot() leaves a leftover label ("indicators") on the column index
    # itself (not a real column, just metadata) that would otherwise show
    # up if this DataFrame's columns were ever inspected or reset again --
    # clearing it keeps the result a plain, unlabelled column list.
    grouped.columns.name = None

    # A (year, product) combination might have only ever had one of the
    # two indicators reported (rare, but possible for a brand-new or
    # about-to-disappear product/partner pairing) -- pivot() leaves those
    # as NaN (pandas' "missing value" marker) rather than 0. Treating "no
    # value reported" as zero matches how every other missing-data case in
    # this codebase is handled, and avoids NaN leaking into the CSV as the
    # literal text "nan".
    for col in indicator_columns.values():
        if col not in grouped.columns:
            grouped[col] = 0
        grouped[col] = grouped[col].fillna(0)

    return grouped


def aggregate(
    df: pd.DataFrame, indicator_columns: dict[str, str] = INDICATOR_COLUMNS
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Take the raw monthly rows and produce three yearly summaries: one
    totalled by product code, one totalled by partner country, and one
    keeping both breakdowns at once (partner AND product, not collapsing
    either) -- the last one is what lets the dashboards' category filter
    work, since it can't be reconstructed from the other two once they've
    each summed away one of the two dimensions. Returns all three as a
    tuple (a fixed-size, ordered sequence) so the caller gets them back
    together in one line: `by_product, by_partner, by_partner_product =
    aggregate(df)`.

    Each table has both a quantity column and a "value_eur" column (trade
    value) -- see _pivot_indicators() above for how the raw rows (one per
    indicator) turn into that shape, and for what indicator_columns is.
    """
    # df["partner"].isin(AGGREGATE_PARTNERS) gives True/False for every
    # row depending on whether its partner code is one of the aggregate
    # codes; the leading ~ flips every True/False, so this line keeps only
    # the rows whose partner is NOT an aggregate code. .copy() makes an
    # independent copy of that filtered table -- without it, pandas would
    # sometimes warn that later edits are ambiguous (editing the filtered
    # view vs. the original table).
    df = df[~df["partner"].isin(AGGREGATE_PARTNERS)].copy()

    # TIME_PERIOD looks like "2023-04" (year-month); slicing characters
    # 0 to 4 keeps just the year part, "2023".
    df["year"] = df["TIME_PERIOD"].str.slice(0, 4)

    quantity_col = next(iter(indicator_columns.values()))

    by_product = _pivot_indicators(df, ["year", "product"], indicator_columns).sort_values(
        ["year", "product"]
    )

    # Same idea, but grouped by (year, partner) instead of (year, product),
    # and sorted so the biggest exporters come first within each year.
    by_partner = _pivot_indicators(df, ["year", "partner"], indicator_columns).sort_values(
        ["year", quantity_col], ascending=[True, False]
    )

    # Same idea again, but grouped by (year, partner, product) -- neither
    # dimension summed away, so this is the one build_dashboard.py needs
    # to answer "how much did partner X send in category Y in year Z".
    by_partner_product = _pivot_indicators(
        df, ["year", "partner", "product"], indicator_columns
    ).sort_values(["year", "partner", "product"])

    return by_product, by_partner, by_partner_product


def aggregate_monthly(
    df: pd.DataFrame, indicator_columns: dict[str, str] = INDICATOR_COLUMNS
) -> pd.DataFrame:
    """Like aggregate()'s by_partner_product table, but keeping the full
    "YYYY-MM" month instead of collapsing to just the year -- this is what
    public/monthly.html needs for its month-by-month chart, which none of
    the yearly-granularity tables can answer since the month information
    is thrown away as soon as aggregate() groups by year. Also has both a
    quantity column and a "value_eur" column, same as aggregate()'s
    tables -- see _pivot_indicators().

    Kept as a separate function (rather than adding a fourth return value
    to aggregate()) so the three existing, already-yearly tables and their
    callers don't need to change at all -- this is purely additive.
    """
    df = df[~df["partner"].isin(AGGREGATE_PARTNERS)].copy()

    return (
        _pivot_indicators(df, ["TIME_PERIOD", "partner", "product"], indicator_columns)
        .rename(columns={"TIME_PERIOD": "month"})
        .sort_values(["month", "partner", "product"])
    )


def main() -> None:
    # argparse reads command-line arguments (the words typed after
    # "python scripts/fetch_at_history.py"). description=__doc__ reuses
    # this file's own top docstring as the help text shown by --help.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reporter",
        default=REPORTER,
        help="Comext reporter country code, e.g. AT, DE, IE, ES, FR, NL (default: AT)",
    )
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    reporter = args.reporter.upper()

    df = fetch(args.start_year, args.end_year, reporter)
    by_product, by_partner, by_partner_product = aggregate(df)
    monthly = aggregate_monthly(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    prefix = reporter.lower()
    by_product_path = PROCESSED_DIR / f"{prefix}_bovine_exports_yearly_by_product.csv"
    by_partner_path = PROCESSED_DIR / f"{prefix}_bovine_exports_yearly_by_partner.csv"
    by_partner_product_path = (
        PROCESSED_DIR / f"{prefix}_bovine_exports_yearly_by_partner_product.csv"
    )
    monthly_path = PROCESSED_DIR / f"{prefix}_bovine_exports_monthly_by_partner_product.csv"
    by_product.to_csv(by_product_path, index=False)
    by_partner.to_csv(by_partner_path, index=False)
    by_partner_product.to_csv(by_partner_product_path, index=False)
    monthly.to_csv(monthly_path, index=False)

    print(f"Saved {by_product_path} ({len(by_product)} rows)")
    print(f"Saved {by_partner_path} ({len(by_partner)} rows)")
    print(f"Saved {by_partner_product_path} ({len(by_partner_product)} rows)")
    print(f"Saved {monthly_path} ({len(monthly)} rows)")


# This file can be *imported* (e.g. `from fetch_at_history import aggregate`
# in a test, or from build_dashboard.py) without actually running main() --
# __name__ is only equal to "__main__" when the file is run directly
# (`python scripts/fetch_at_history.py`), not when it's imported elsewhere.
if __name__ == "__main__":
    main()
