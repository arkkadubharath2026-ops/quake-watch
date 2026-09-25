"""WCAG 2.2 AA audit in a real browser (axe-core rules + keyboard behaviour axe cannot check).

axe-core is run on every page, signed out and in, in the light and dark themes and at phone
width, after every data region has finished loading (so the audited DOM includes rendered data,
charts, tables and maps). Manual-only criteria are recorded in docs/ACCESSIBILITY.md.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from axe_playwright_python.sync_playwright import Axe
from django.contrib.auth.models import User
from playwright.sync_api import Page, expect

from tests.e2e.conftest import log_in, settle

WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
PUBLIC = ["/", "/map/", "/explorer/?min_magnitude=2.5", "/analytics/", "/status/", "/about/"]
ACCOUNT = ["/accounts/login/", "/accounts/signup/"]
SIGNED_IN = ["/alerts/", "/research/"]
axe = Axe()


MARKERS = ".leaflet-marker-pane"


def _violations(page: Page, context: Any, options: dict[str, Any]) -> list[dict[str, Any]]:
    result = axe.run(page, context=context, options={**options, "resultTypes": ["violations"]})
    return [
        {
            "rule": v["id"],
            "impact": v["impact"],
            "help": v["help"],
            "targets": [n["target"] for n in v["nodes"]][:5],
        }
        for v in result.response["violations"]
    ]


def audit(page: Page) -> list[dict[str, Any]]:
    """All WCAG 2.2 A/AA rules on the settled page.

    Map markers are audited separately without ``target-size``: overlapping markers are exempt
    under 2.5.8's "equivalent" exception because every map has a text list offering the same
    events (Live Map side panel, Explorer table, Dashboard recent list) - see ACCESSIBILITY.md.
    """
    settle(page)
    tags = {"runOnly": {"type": "tag", "values": WCAG_TAGS}}
    found = _violations(page, {"exclude": [[MARKERS]]}, tags)
    if page.locator(MARKERS).count():
        found += _violations(
            page, {"include": [[MARKERS]]}, {**tags, "rules": {"target-size": {"enabled": False}}}
        )
    return found


def event_path(page: Page) -> str:
    page.goto("/explorer/?min_magnitude=4.5")
    settle(page)
    href = page.locator("#results tbody tr a").first.get_attribute("href")
    assert href
    return href


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("path", PUBLIC + ACCOUNT)
def test_public_pages_pass_axe(ui: Page, path: str, theme: str) -> None:
    ui.emulate_media(color_scheme=theme)
    ui.goto(path)
    assert audit(ui) == []


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_event_detail_passes_axe_on_every_tab(ui: Page, theme: str) -> None:
    ui.emulate_media(color_scheme=theme)
    ui.goto(event_path(ui))
    assert audit(ui) == []
    for tab in ("Revision timeline", "Scientific products", "Relationships", "Provenance"):
        ui.get_by_role("tab", name=tab, exact=False).first.click()
        assert audit(ui) == [], tab


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("path", SIGNED_IN)
def test_signed_in_pages_pass_axe(ui: Page, user: User, path: str, theme: str) -> None:
    ui.emulate_media(color_scheme=theme)
    log_in(ui, user.username)
    ui.goto(path)
    assert audit(ui) == []


def test_operations_passes_axe(ui: Page, staff: User) -> None:
    log_in(ui, staff.username)
    ui.goto("/operations/")
    assert audit(ui) == []


@pytest.mark.parametrize("path", ["/", "/explorer/?min_magnitude=2.5", "/analytics/"])
def test_reflow_width_passes_axe_without_horizontal_scroll(ui: Page, path: str) -> None:
    ui.set_viewport_size({"width": 320, "height": 780})  # 1.4.10: 320 CSS px
    ui.goto(path)
    assert audit(ui) == []
    overflow = ui.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0  # 1.4.10 Reflow: no two-dimensional scrolling for page content


def test_error_states_pass_axe(ui: Page, browser_errors: Any) -> None:
    browser_errors.allow("500")
    ui.route(
        "**/api/v1/events?*",
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body='{"error": {"code": "internal_error", "message": "x", "correlation_id": "c"}}',
        ),
    )
    ui.goto("/explorer/")
    expect(ui.locator("#results [data-kind='server']")).to_be_visible()
    assert audit(ui) == []


class TestKeyboard:
    def test_skip_link_is_first_and_moves_focus_to_main(self, ui: Page) -> None:
        ui.goto("/explorer/")
        ui.keyboard.press("Tab")
        skip = ui.locator(":focus")
        expect(skip).to_have_text("Skip to main content")
        expect(skip).to_be_visible()  # 2.4.7 Focus visible: shown when focused
        ui.keyboard.press("Enter")
        expect(ui).to_have_url(re.compile(r"#main$"))
        ui.keyboard.press("Tab")
        in_main = ui.evaluate(
            "() => document.getElementById('main').contains(document.activeElement)"
        )
        assert in_main

    def test_focus_ring_is_visible_on_controls(self, ui: Page) -> None:
        ui.goto("/explorer/")
        ui.locator("#f-minmag").focus()
        ui.keyboard.press("Tab")
        # 1.4.11: a solid brand-coloured ring (not a translucent tint) around the focused control;
        # waited for because Bootstrap animates box-shadow on form controls
        ui.wait_for_function(
            "() => getComputedStyle(document.activeElement).boxShadow.includes('rgb(11, 92, 173)')"
        )

    def test_sortable_headers_and_tabs_work_from_the_keyboard(self, ui: Page) -> None:
        ui.goto("/explorer/?min_magnitude=2.5")
        settle(ui)
        ui.locator("#results thead").get_by_role("button", name="Depth").focus()
        ui.keyboard.press("Enter")
        expect(ui.locator("th[aria-sort='descending']")).to_contain_text("Depth")
        expect(ui.locator("#qw-live")).to_contain_text("Sorted by Depth")  # announced

    def test_theme_toggle_reports_its_state(self, ui: Page) -> None:
        ui.emulate_media(color_scheme="light")
        ui.goto("/about/")
        toggle = ui.locator("[data-qw-theme-toggle]")
        expect(toggle).to_have_attribute("aria-pressed", "false")
        toggle.focus()
        ui.keyboard.press("Enter")
        expect(toggle).to_have_attribute("aria-pressed", "true")

    def test_reduced_motion_disables_skeleton_animation(self, ui: Page) -> None:
        ui.emulate_media(reduced_motion="reduce")
        ui.route("**/api/v1/events?*", lambda route: None)  # hold the request: stay loading
        ui.goto("/explorer/")
        skeleton = ui.locator("#results .qw-skeleton").first
        expect(skeleton).to_be_attached()
        assert skeleton.evaluate("e => getComputedStyle(e).animationName") == "none"
