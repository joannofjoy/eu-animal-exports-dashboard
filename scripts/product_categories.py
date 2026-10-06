"""Groups the 35 CN8 product codes in fetch_at_history.py's PRODUCTS list
into leaf categories for the dashboards' category filter, each with its
official Eurostat name (from the CXT_NC codelist, English) alongside the
raw code -- so the filter UI can show exactly which codes each category
means, not just a label standing in for something opaque.

Seven leaf categories, which the reader-facing filter doesn't expose
directly -- instead it offers five single-select "views" (see VIEWS below:
All / Calves / For slaughter / For breeding / For production-rearing),
each summing whichever leaf categories answer that one question. A
checkbox tree letting someone combine leaves freely was tried first and
dropped: "Calves" and "For slaughter" aren't peers on the same axis (a
calf can itself be for slaughter), so checking both would silently
double-count every code that belongs to both.

- ZUCHTRINDER_ORIGINAL / ZUCHTRINDER_WEITERE ("Breeding cattle (pure-bred)"):
  unchanged from the original two-code scope of this project
  (01022110 heifers, 01022130 cows) plus 01022190 (breeding bulls). These
  codes carry no weight at all -- they're defined by trade *purpose*
  (genetics/herd replacement), not by size, so they sit outside the
  young/adult weight split below entirely. The four 010210xx codes that
  covered the same concept before a CN nomenclature revision are
  deliberately left out of PRODUCTS entirely (not just uncategorized) --
  confirmed via the live API to have zero AT export rows across all of
  2015-2025, since they were superseded by 010221/010231 before this data
  window starts.

- YOUNG_SLAUGHTER / YOUNG_OTHER ("Calves (<=300kg)") and
  ADULT_SLAUGHTER / ADULT_OTHER ("Adult cattle (>300kg)"): every other
  code splits along two independent axes -- weight (<=300kg vs >300kg)
  and declared trade purpose ("for slaughter" vs not). The weight line is
  a genuine age proxy (confirmed against Eurostat's own slaughter-weight
  statistics, apro_mt_pwgtm: Austria's white-veal-equivalent "Calf"
  category averages ~172kg live weight, comfortably under 300kg, while
  every adult category averages 590-700kg) -- but it's still a proxy, not
  an age field Comext actually reports, so these are labelled by weight,
  never as "veal"/"beef" outright. The slaughter/other split mirrors a
  real, separate legal distinction: EU intra-trade in live cattle requires
  a veterinary movement certificate, and there are exactly two models --
  BOV-Y for animals going straight to slaughter, BOV-X for animals bound
  for "further keeping" (breeding or production/fattening only; there is
  no EU livestock-movement category for anything like a companion animal).
  Keeping both axes selectable (rather than collapsing straight to
  "young"/"adult") means a user can still isolate e.g. just the
  slaughter-bound young codes if that's the more honest question for a
  given chart.

- OTHER_UNCLASSIFIED ("Other / unclassified"): codes that don't carry a
  clean weight bracket at all -- an exotic sub-genus code, the one
  non-cattle pure-bred-breeding code (01029020, kept out of the Zuchtrinder
  buckets since those are about *cattle* breeding specifically), a few
  residual "other bovine" codes, and four "weighing > 220 kg" codes
  (heifers/cows/bulls/steers under the generic "domestic bovines" series)
  whose open-ended upper bound straddles the 300kg line with no way to
  split it further -- confirmed via the live API to be zero-volume for
  every one of this project's 27 reporters across 2015-2026, so excluding
  them from the weight split costs nothing in practice.

Every code from PRODUCTS in fetch_at_history.py appears in exactly one of
the seven leaf dicts -- see tests/test_product_categories.py for a check
that enforces that stays true if PRODUCTS ever changes.
"""

import html
from collections.abc import Iterable

ZUCHTRINDER_ORIGINAL = {
    "01022110": "Pure-bred breeding heifers",
    "01022130": "Pure-bred breeding cows (excl. heifers)",
}

ZUCHTRINDER_WEITERE = {
    "01022190": "Pure-bred cattle for breeding (excl. heifers and cows)",
}

YOUNG_SLAUGHTER = {
    "01022921": "Cattle of a weight > 80 kg but <= 160 kg, for slaughter",
    "01022941": "Cattle of a weight > 160 kg but <= 300 kg, for slaughter",
    "01029021": "Domestic bovines of a weight > 80 kg and <= 160 kg, for slaughter",
    "01029041": "Domestic bovines of a weight > 160 kg and <= 300 kg, for slaughter",
}

YOUNG_OTHER = {
    "01022910": "Live cattle of a weight <= 80 kg (excl. pure-bred for breeding)",
    "01022929": (
        "Live cattle of a weight > 80 kg but <= 160 kg "
        "(excl. for slaughter, pure-bred for breeding)"
    ),
    "01022949": (
        "Live cattle of a weight > 160 kg but <= 300 kg "
        "(excl. for slaughter, pure-bred for breeding)"
    ),
    "01029005": "Live domestic bovines of a weight <= 80 kg (excl. pure-bred breeding animals)",
    "01029010": "Domestic bovines, weighing =< 220 kg (excl. pure-bred for breeding)",
    "01029029": (
        "Live domestic bovines of a weight > 80 kg and <= 160 kg "
        "(excl. for slaughter, pure-bred breeding animals)"
    ),
    "01029049": (
        "Live domestic bovines of a weight > 160 kg and <= 300 kg "
        "(excl. for slaughter, pure-bred breeding animals)"
    ),
}

ADULT_SLAUGHTER = {
    "01022951": "Heifers of a weight > 300 kg, for slaughter",
    "01022961": "Cows of a weight > 300 kg, for slaughter (excl. heifers)",
    "01022991": "Cattle of a weight > 300 kg, for slaughter (excl. heifers and cows)",
    "01029051": "Heifers of a weight > 300 kg, for slaughter",
    "01029061": "Cows of a weight > 300 kg, for slaughter (excl. heifers)",
    "01029071": "Domestic bovines of a weight > 300 kg, for slaughter (excl. heifers and cows)",
}

ADULT_OTHER = {
    "01022959": (
        "Live heifers of a weight > 300 kg (excl. for slaughter and pure-bred for breeding)"
    ),
    "01022969": (
        "Live cows of a weight > 300 kg (excl. for slaughter, pure-bred for breeding and heifers)"
    ),
    "01022999": (
        "Live cattle of a weight > 300 kg "
        "(excl. for slaughter, pure-bred for breeding, heifers and cows)"
    ),
    "01029059": (
        "Live heifers of a weight > 300 kg (excl. for slaughter, pure-bred breeding animals)"
    ),
    "01029069": (
        "Live cows of a weight > 300 kg "
        "(excl. for slaughter, pure-bred breeding animals and heifers)"
    ),
    "01029079": (
        "Live domestic bovines of a weight > 300 kg "
        "(excl. for slaughter, pure-bred breeding animals, heifers and cows)"
    ),
}

OTHER_UNCLASSIFIED = {
    "01022905": "Live cattle of the sub-genus Bibos or Poephagus (excl. pure-bred for breeding)",
    "01029020": "Bovine pure-bred breeding animals (excl. cattle and buffalo)",
    "01029031": "Live heifers, weighing > 220 kg (excl. pure-bred for breeding)",
    "01029033": "Live cows, weighing > 220 kg (excl. pure-bred for breeding)",
    "01029035": "Live bulls, weighing > 220 kg (excl. pure-bred for breeding)",
    "01029037": "Live steers, weighing > 220 kg",
    "01029090": "Live non-domestic bovines (excl. pure-bred for breeding)",
    "01029091": "Live domestic bovine animals (excl. cattle, buffalo and pure-bred for breeding)",
    "01029099": (
        "Live bovine animals (excl. cattle, buffalo, pure-bred for breeding and domestic species)"
    ),
}

# label = what shows in the filter UI; codes = {CN8 code: Eurostat name},
# shown alongside the label so the filter is transparent about exactly
# what it includes, not just a paraphrase of it.
CATEGORIES = {
    "zuchtrinder_original": {
        "label": "Original selection (heifers & cows)",
        "codes": ZUCHTRINDER_ORIGINAL,
    },
    "zuchtrinder_weitere": {
        "label": "Other breeding cattle",
        "codes": ZUCHTRINDER_WEITERE,
    },
    "young_slaughter": {"label": "For slaughter", "codes": YOUNG_SLAUGHTER},
    "young_other": {"label": "Rearing/store", "codes": YOUNG_OTHER},
    "adult_slaughter": {"label": "For slaughter", "codes": ADULT_SLAUGHTER},
    "adult_other": {"label": "Rearing/store", "codes": ADULT_OTHER},
    "other_unclassified": {
        "label": "Other / unclassified",
        "codes": OTHER_UNCLASSIFIED,
    },
}

# code -> leaf category key, built once here so other scripts can just do
# CODE_TO_CATEGORY[code] instead of searching all seven dicts every time.
CODE_TO_CATEGORY = {
    code: category for category, info in CATEGORIES.items() for code in info["codes"]
}


def validate_product_codes(product_codes: Iterable[str]) -> None:
    """Fail instead of silently dropping a newly added/unknown code.

    Pandas groupby drops NaN category keys by default, so mapping an
    uncategorized code and continuing would undercount dashboard totals.
    """
    unknown = {str(code) for code in product_codes if code not in CODE_TO_CATEGORY}
    if unknown:
        raise ValueError(f"Uncategorized product codes: {sorted(unknown)}")


# The reader-facing filter is a single-select "pick one lens" control, not
# a checkbox tree -- "Calves" and "For slaughter"/"For breeding"/"For
# production" aren't peers on the same axis (a calf can itself be for
# slaughter), so letting someone check several at once would silently
# double-count any code that belongs to two of them. Each entry's
# "categories" list is which of the seven leaf buckets above get summed
# for that view; "all" lists every one of them (including
# other_unclassified) so its total is the true grand total, not just
# whatever the other four views happen to add up to.
VIEWS = [
    {"key": "all", "label": "All", "categories": list(CATEGORIES.keys())},
    {
        "key": "calves",
        "label": "Calves (<=300kg)",
        "categories": ["young_slaughter", "young_other"],
    },
    {
        "key": "slaughter",
        "label": "For slaughter",
        "categories": ["young_slaughter", "adult_slaughter"],
    },
    {
        "key": "breeding",
        "label": "For breeding",
        "categories": ["zuchtrinder_original", "zuchtrinder_weitere"],
    },
    {
        "key": "production",
        "label": "For production/rearing",
        "categories": ["young_other", "adult_other"],
    },
]


def render_category_filter_html() -> str:
    """Build the HTML for the category-filter radio buttons, straight from
    VIEWS/CATEGORIES above -- the filter's structure is fixed (it doesn't
    depend on which year or country is selected), so this gets rendered
    once at build time instead of being reconstructed in JS on every page
    load. "All" starts selected.

    A <details> element under each option lists its underlying Eurostat
    codes and names -- collapsed by default (native, no JS needed), so the
    filter stays transparent about exactly what each view includes without
    the list itself being cluttered. A view spanning more than one leaf
    category (e.g. "Calves" = young_slaughter + young_other) merges both
    leaves' codes into one list here.
    """

    def codes_list(codes: dict[str, str]) -> str:
        items = "".join(
            f"<li><code>{code}</code> — {html.escape(name)}</li>" for code, name in codes.items()
        )
        return (
            f'<details class="filterCodes"><summary>{len(codes)} Eurostat codes</summary>'
            f"<ul>{items}</ul></details>"
        )

    parts = []
    for view in VIEWS:
        codes: dict[str, str] = {}
        for category in view["categories"]:
            codes.update(CATEGORIES[category]["codes"])
        checked = "checked" if view["key"] == "all" else ""
        label = html.escape(view["label"])
        parts.append(
            f'<div class="filterLeaf">'
            f'<label><input type="radio" name="view" class="viewRadio" '
            f'value="{view["key"]}" {checked}> {label}</label>'
            f"{codes_list(codes)}"
            f"</div>"
        )

    return "".join(parts)
