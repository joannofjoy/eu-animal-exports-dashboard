"""Renders the top-of-page navigation shared by the reader-facing pages.
navigate between them -- a shared component (like product_categories.py's
render_category_filter_html()) so the six pages' navigation can't drift
out of sync with each other one page at a time, the way the old per-page
row of arrow-and-text links (e.g. "<- Yearly exports * Destination map ->")
could.

These aren't JS-driven tabs -- each "tab" points at a separate static HTML
file, not a view within one page, so clicking one is a normal full-page
navigation. The tab *look* (rather than a plain list of links) is just a
styling choice, borrowed from the in-page view-tabs already used on
dashboard.html (Yearly Exports/Map) and monthly.html (year picker) so the
whole site reads consistently.
"""

import html

# Internal analysis pages are deliberately not included here.
PAGES = [
    ("index.html", "Yearly Exports"),
    ("map.html", "Map"),
    ("monthly.html", "Monthly"),
    ("trade_pairs.html", "Export vs. Import"),
    ("beef_vs_cows.html", "Live vs. Meat"),
    ("methodology.html", "Methodology"),
]


def render_site_tabs_html(active_page: str) -> str:
    """active_page is one of the filenames in PAGES (e.g. "index.html").
    That page's tab renders as plain text with the "active" styling
    instead of a link -- there's no point linking a page to itself, and
    it matches the .tabBtn.active convention already used for the in-page
    tabs elsewhere on this site.
    """
    parts = []
    for filename, label in PAGES:
        safe_label = html.escape(label)
        classes = "siteTabBtn"

        if filename == active_page:
            parts.append(f'<span class="{classes} active">{safe_label}</span>')
        else:
            parts.append(f'<a class="{classes}" href="{filename}">{safe_label}</a>')

    return "".join(parts)
