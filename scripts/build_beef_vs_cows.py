"""Build the "live exports vs. meat imports" comparison page
(public/beef_vs_cows.html) from the processed Eurostat data.

Puts a reporter's own live cattle *exports* (heading 0102, already
fetched by fetch_at_history.py for every reporter this project tracks)
next to that same reporter's beef & veal meat *imports* (headings
0201/0202, fetch_meat_imports.py) -- the "calves leave live, meat comes
back" question from docs/llm_agent_handoff.md section 6/6.1. The two
sides use different units on purpose (animals vs. tonnes) and are shown
side by side rather than converted into one shared number -- there's no
reliable live-animal-to-meat-weight conversion that isn't itself an
estimate (see section 6's carcass-weight research), and this page's job
is to show the two real, independently reported figures, not to invent a
combined one. It's also import-only on the meat side and export-only on
the live side: that direction is what the original investigative question
is about, not a full four-way export/import breakdown.

Much simpler than build_dashboard.py's page: no category or geography
filter, since there's no sub-category to filter by on the meat side (see
scripts/meat_products.py) and keeping the live-cattle side as a plain
total keeps both panels directly comparable in scope.

Run it after both fetch_at_history.py and fetch_meat_imports.py, any time
the underlying processed CSVs change:

    python scripts/build_beef_vs_cows.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from countries import REPORTERS
from site_nav import render_site_tabs_html

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PUBLIC_DIR = ROOT_DIR / "public"
TEMPLATE_PATH = PUBLIC_DIR / "beef_vs_cows.template.html"
OUTPUT_PATH = PUBLIC_DIR / "beef_vs_cows.html"
REPORTER_DATA_DIR = PUBLIC_DIR / "data" / "beef_vs_cows"


def load_live_exports_by_year(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, dict[str, int]]:
    """Read <reporter>_bovine_exports_yearly_by_product.csv and collapse
    it to one {quantity, valueEur} total per year, summed across every
    product code -- this page shows the reporter's whole live-cattle
    export total, not a category breakdown.
    """
    prefix = reporter.lower()
    path = processed_dir / f"{prefix}_bovine_exports_yearly_by_product.csv"
    df = pd.read_csv(path, dtype={"year": str})
    totals = df.groupby("year")[["quantity", "value_eur"]].sum()
    return {
        year: {"quantity": int(round(row["quantity"])), "valueEur": int(round(row["value_eur"]))}
        for year, row in totals.iterrows()
    }


def load_meat_imports_by_year(
    processed_dir: Path = PROCESSED_DIR, reporter: str = "AT"
) -> dict[str, dict[str, float]]:
    """Read <reporter>_beef_imports_yearly_by_product.csv and collapse it
    to one {quantityTonnes, valueEur} total per year. The raw column is
    quantity_100kg (Eurostat's own reporting unit, see
    fetch_meat_imports.py); dividing by 10 turns it into tonnes, the unit
    this page and public/methodology.html actually show readers.
    """
    prefix = reporter.lower()
    path = processed_dir / f"{prefix}_beef_imports_yearly_by_product.csv"
    df = pd.read_csv(path, dtype={"year": str})
    totals = df.groupby("year")[["quantity_100kg", "value_eur"]].sum()
    return {
        year: {
            "quantityTonnes": round(row["quantity_100kg"] / 10, 1),
            "valueEur": int(round(row["value_eur"])),
        }
        for year, row in totals.iterrows()
    }


def render(
    template: str,
    live_exports_by_year: dict[str, dict[str, int]],
    meat_imports_by_year: dict[str, dict[str, float]],
    reporters: list[tuple[str, str]] = REPORTERS,
) -> str:
    """Fill in the __PLACEHOLDER__ tokens in `template` with real data and
    return the finished HTML as a string. Same plain str.replace()
    approach as build_dashboard.py's render() -- see its docstring for why
    a full template engine isn't needed here either.
    """
    all_years = sorted(set(live_exports_by_year) | set(meat_imports_by_year))
    year_range = f"{all_years[0]}–{all_years[-1]}" if all_years else "no data yet"

    replacements = {
        "__YEAR_RANGE__": year_range,
        "__LIVE_EXPORTS_BY_YEAR_JSON__": json.dumps(live_exports_by_year, ensure_ascii=False),
        "__MEAT_IMPORTS_BY_YEAR_JSON__": json.dumps(meat_imports_by_year, ensure_ascii=False),
        "__REPORTERS_JSON__": json.dumps(
            [{"code": code, "name": name} for code, name in reporters], ensure_ascii=False
        ),
        "__SITE_TABS_HTML__": render_site_tabs_html("beef_vs_cows.html"),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)

    return template


def main() -> None:
    # Austria is always baked directly into the page, same reasoning as
    # build_dashboard.py: it's the default view, no reason to make every
    # visitor's first load wait on an extra fetch() just to see it.
    live_exports_by_year = load_live_exports_by_year(reporter="AT")
    meat_imports_by_year = load_meat_imports_by_year(reporter="AT")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = render(template, live_exports_by_year, meat_imports_by_year)

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH} "
        f"({len(live_exports_by_year)} live-export years, "
        f"{len(meat_imports_by_year)} meat-import years)"
    )

    # Every other reporter gets its own small *.js* file, loaded on demand
    # via a dynamically-injected <script src> tag -- same reasoning as
    # build_dashboard.py's REPORTER_DATA_DIR loop (fetch() of a relative
    # path is blocked under file://, see that script's comment for the
    # confirmed details).
    REPORTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for code, name in REPORTERS:
        if code == "AT":
            continue
        try:
            other_live = load_live_exports_by_year(reporter=code)
        except FileNotFoundError:
            print(f"Skipping {name} ({code}): no live-export data yet")
            continue
        try:
            other_meat = load_meat_imports_by_year(reporter=code)
        except FileNotFoundError:
            print(
                f"Skipping {name} ({code}): no meat-import data yet -- "
                f"run fetch_meat_imports.py --reporter {code}"
            )
            continue
        data_path = REPORTER_DATA_DIR / f"{code.lower()}.js"
        payload = json.dumps(
            {"liveExportsByYear": other_live, "meatImportsByYear": other_meat},
            ensure_ascii=False,
        )
        data_path.write_text(f"window.REPORTER_DATA['{code}'] = {payload};", encoding="utf-8")
        print(
            f"Wrote {data_path} "
            f"({len(other_live)} live-export years, {len(other_meat)} meat-import years)"
        )


if __name__ == "__main__":
    main()
