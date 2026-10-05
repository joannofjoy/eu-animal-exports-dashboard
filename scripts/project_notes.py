"""Renders the "Project notes" block embedded at the bottom of every
dashboard page -- a running log of the choices made so far about scope,
terminology, and known data-quality issues, so anyone looking at the page
mid-project (a colleague, an editor, future-us) can see what's already been
decided without having to ask.

This is meant as a working note, not permanent page content -- most or all
of it should come back out once the dashboards are finalized for
publication. Keeping it as one shared, collapsed <details> block (rather
than writing it out on every page) means there's exactly one place to
trim later.
"""

import html

# Each entry is one bullet point. Kept as plain text (escaped at render
# time) rather than pre-built HTML, so this list stays easy to read and
# edit as decisions change.
NOTES = [
    (
        "Animals, not units: quantities are consistently described as "
        "“animals,” not “head” or “units” -- "
        "cattle are living creatures, not piece goods."
    ),
    (
        "Product scope: 35 CN8 codes under heading 0102 (live cattle), "
        "excluding buffalo (010231/010239) and excluding the four "
        "010210xx codes (pre-2002 nomenclature, confirmed to have zero "
        "AT data for 2015-2025). An earlier version covered only the two "
        "original breeding-cattle codes (see next point) -- that was "
        "roughly a quarter of the actual export volume."
    ),
    (
        "Category filter: the 35 codes are grouped into four categories "
        "(Original selection, Other breeding cattle, Slaughter cattle, "
        "Other cattle). “Original selection” stays separately "
        "selectable so old and new figures can be compared directly."
    ),
    (
        "Geography filter: All countries / EU only / Non-EU only, "
        "combinable independently of the category filter."
    ),
    (
        "Aggregate partner codes (WORLD, EXT_EU, INT_EU, EXT_EA, INT_EA "
        "etc.) are excluded from all totals to avoid double-counting."
    ),
    (
        "Known data issue: Croatia's 2024 figure (original selection) is "
        "unusually high and doesn't match Croatia's own import "
        "declarations -- see docs/croatia_2024_anomaly.md for the full "
        "investigation."
    ),
    (
        "Source: Eurostat Comext, dataset DS-045409, confirmed by "
        "Eurostat support as the correct/current dataset for CN8 detail "
        "with head counts (see docs/eurostat_comext_api.md)."
    ),
]


def render_project_notes_html() -> str:
    """Build the collapsed <details> block listing NOTES above. Collapsed
    by default (native <details>, no JS needed) so it doesn't compete with
    the actual charts/map for attention, but is there for anyone who opens
    it.
    """
    items = "".join(f"<li>{html.escape(note)}</li>" for note in NOTES)
    return (
        '<details class="notes">'
        "<summary>Project notes (work in progress)</summary>"
        f"<ul>{items}</ul>"
        "</details>"
    )
