"""Tests for scripts/site_nav.py."""

from site_nav import PAGES, render_site_tabs_html


def test_active_page_renders_as_span_not_a_link():
    html = render_site_tabs_html("monthly.html")

    assert '<span class="siteTabBtn active">Monthly</span>' in html
    # The active page's own filename should not appear as an href anywhere
    # -- there's no reason to link a page to itself.
    assert 'href="monthly.html"' not in html


def test_every_other_page_renders_as_a_link():
    html = render_site_tabs_html("index.html")

    for filename, _label in PAGES:
        if filename == "index.html":
            continue
        assert f'href="{filename}"' in html


def test_all_pages_appear_exactly_once():
    html = render_site_tabs_html("map.html")

    assert html.count('class="siteTabBtn') == len(PAGES)


def test_methodology_is_in_reader_navigation_and_mirror_is_not():
    assert PAGES[-1][0] == "methodology.html"

    html = render_site_tabs_html("index.html")
    assert 'href="methodology.html"' in html
    assert 'href="mirror.html"' not in html
