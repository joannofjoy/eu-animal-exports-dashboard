"""Renders the top-of-page tab bar used on all six dashboard pages to
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

# (filename, label) for every page, in the order the tabs should appear.
# Mirror Statistics sits last and gets the "dev" treatment below -- it's a
# data-quality/reconciliation view for working on this project, not one of
# the six polished reader-facing dashboards.
PAGES = [
    ("index.html", "Yearly Exports"),
    ("map.html", "Map"),
    # "Combined View" (dashboard.html) is left out of the nav for now --
    # the page and its build script still exist, it's just not linked from
    # the tab bar at the moment.
    ("monthly.html", "Monthly"),
    ("trade_pairs.html", "Export vs. Import"),
    ("mirror.html", "Mirror Statistics"),
]

# Pages that are internal/development views rather than finished reader-facing
# dashboards -- their tab renders muted and gets a "(dev)" suffix plus an
# explanatory title tooltip instead of looking like just another normal tab.
DEV_PAGES = {"mirror.html"}
DEV_TOOLTIP = "Internal data-quality view for development use -- not intended for publication."


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
        if filename in DEV_PAGES:
            classes += " siteTabBtnDev"
            safe_label += " (dev)"

        if filename == active_page:
            parts.append(f'<span class="{classes} active">{safe_label}</span>')
        else:
            title = f' title="{html.escape(DEV_TOOLTIP)}"' if filename in DEV_PAGES else ""
            parts.append(f'<a class="{classes}" href="{filename}"{title}>{safe_label}</a>')

    return "".join(parts)
