"""Main user flows in a real browser (ESD §16 End-to-End): dashboard, filters, event detail, alert
rule CRUD, research export, admin health, accounts, and the shared UI error states."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from apps.accounts.identity import ArangoUser
from tests.e2e.conftest import BrowserErrors, break_api, log_in, settle

MAGNITUDE = re.compile(r"-?\d+(?:\.\d+)?")


def magnitudes(page: Page) -> list[float]:
    cells = page.locator("#results tbody td.num .qw-mag").all_inner_texts()
    return [float(MAGNITUDE.findall(text)[-1]) for text in cells]


class TestPublicFlows:
    def test_dashboard_loads_every_region_without_errors(self, ui: Page) -> None:
        ui.goto("/")
        expect(ui.get_by_role("heading", level=1)).to_have_text("What is happening now")
        settle(ui)
        for region in ("#summary", "#recent", "#significant", "#activity"):
            expect(
                ui.locator(f"{region} [data-kind='server'], {region} [data-kind='error']")
            ).to_have_count(0)
        expect(ui.locator("[data-qw-freshness]").first).not_to_contain_text("Checking")

    def test_explorer_filters_sort_and_page_through_the_url(self, ui: Page) -> None:
        ui.goto("/explorer/")
        settle(ui)
        ui.get_by_label("Minimum magnitude").fill("2.5")
        ui.get_by_role("button", name="Apply filters").click()
        expect(ui).to_have_url(re.compile(r"min_magnitude=2\.5"))
        settle(ui)
        expect(ui.locator("#summary")).to_contain_text("37 events")
        assert all(m >= 2.5 for m in magnitudes(ui))
        expect(ui.locator("#results tbody tr")).to_have_count(25)

        ui.locator("#results thead").get_by_role("button", name="Magnitude").click()
        expect(ui).to_have_url(re.compile(r"sort=magnitude"))
        settle(ui)
        expect(ui.locator("th[aria-sort='descending']")).to_contain_text("Magnitude")
        shown = magnitudes(ui)
        assert shown == sorted(shown, reverse=True)

        ui.locator("#pager").get_by_role("button", name="Next page").click()
        expect(ui).to_have_url(re.compile(r"page=2"))
        settle(ui)
        expect(ui.locator("#results tbody tr")).to_have_count(12)

        ui.go_back()  # history restores the previous page of results
        settle(ui)
        expect(ui.locator("#results tbody tr")).to_have_count(25)

    def test_explorer_rejects_invalid_filters_with_field_messages(
        self, ui: Page, browser_errors: BrowserErrors
    ) -> None:
        browser_errors.allow("400")
        ui.goto("/explorer/?min_magnitude=99")
        settle(ui)
        expect(ui.locator("#results [data-kind='error']")).to_contain_text("min_magnitude")

    def test_event_detail_overview_and_tabs(self, ui: Page) -> None:
        ui.goto("/explorer/?min_magnitude=4.5")
        settle(ui)
        first = ui.locator("#results tbody tr").first.get_by_role("link")
        place = first.inner_text()
        first.click()
        expect(ui.get_by_role("heading", level=1)).to_contain_text(place.split(",")[0])
        expect(
            ui.get_by_text("Earthquake data courtesy of the U.S. Geological Survey")
        ).to_be_visible()
        for tab, pane in (
            ("Revision timeline", "#revisions"),
            ("Relationships", "#relationships"),
            ("Provenance", "#provenance"),
        ):
            ui.get_by_role("tab", name=re.compile(tab)).click()
            settle(ui)
            expect(ui.locator(pane)).to_be_visible()
            expect(
                ui.locator(f"{pane} [data-kind='server'], {pane} [data-kind='error']")
            ).to_have_count(0)
        expect(ui.locator("#revisions li").first).to_contain_text("Revision 1")

    def test_unknown_event_is_a_real_404(self, ui: Page, browser_errors: BrowserErrors) -> None:
        browser_errors.allow("404")
        response = ui.goto("/events/usgs_doesnotexist0/")
        assert response is not None
        assert response.status == 404
        expect(ui.get_by_role("heading", level=1)).to_have_text("Page not found")

    def test_analytics_charts_have_data_tables(self, ui: Page) -> None:
        ui.goto("/analytics/")
        settle(ui)
        charts = ui.locator("figure canvas[role='img']")
        expect(charts.first).to_be_visible()
        toggles = ui.locator("figure details > summary", has_text="Show data table")
        assert toggles.count() == charts.count() >= 3  # every chart has a table alternative
        toggles.first.click()
        expect(ui.locator("figure details table.qw-table").first).to_be_visible()

    def test_status_page_reports_health(self, ui: Page) -> None:
        ui.goto("/status/")
        settle(ui)
        expect(ui.locator("#health")).to_contain_text("ArangoDB")
        expect(ui.locator("#freshness [data-kind='server']")).to_have_count(0)

    def test_theme_toggle_persists(self, ui: Page) -> None:
        ui.emulate_media(color_scheme="light")
        ui.goto("/about/")
        html = ui.locator("html")
        expect(html).to_have_attribute("data-bs-theme", "light")
        ui.get_by_role("button", name="Dark theme").click()
        expect(html).to_have_attribute("data-bs-theme", "dark")
        ui.reload()
        expect(html).to_have_attribute("data-bs-theme", "dark")

    def test_mobile_navigation_collapses_and_opens(self, ui: Page) -> None:
        ui.set_viewport_size({"width": 390, "height": 844})
        ui.goto("/")
        explorer_link = ui.get_by_role("link", name="Explorer", exact=True)
        expect(explorer_link).to_be_hidden()
        ui.get_by_role("button", name=re.compile("navigation", re.I)).click()
        expect(explorer_link).to_be_visible()
        explorer_link.click()
        expect(ui).to_have_url(re.compile(r"/explorer/$"))


class TestUiStates:
    def test_server_failure_shows_reference_and_retry_recovers(
        self, ui: Page, browser_errors: BrowserErrors
    ) -> None:
        browser_errors.allow("500")
        break_api(ui, "**/api/v1/events?*", status=500)
        ui.goto("/explorer/")
        box = ui.locator("#results [data-kind='server']")
        expect(box).to_contain_text("Reference: e2e-corr-1")
        ui.unroute("**/api/v1/events?*")
        box.get_by_role("button", name="Retry").click()
        settle(ui)
        expect(ui.locator("#results tbody tr").first).to_be_visible()

    def test_network_failure_is_reported(self, ui: Page, browser_errors: BrowserErrors) -> None:
        browser_errors.allow("ERR_CONNECTION_REFUSED")
        browser_errors.allow("Failed to fetch")
        break_api(ui, "**/api/v1/events?*", status=0)
        ui.goto("/explorer/")
        expect(ui.locator("#results [data-kind='server']")).to_be_visible()
        expect(ui.locator("#results").get_by_role("button", name="Retry")).to_be_visible()

    def test_throttling_asks_the_user_to_wait(
        self, ui: Page, browser_errors: BrowserErrors
    ) -> None:
        browser_errors.allow("429")
        break_api(
            ui,
            "**/api/v1/events?*",
            status=429,
            body='{"error": {"code": "throttled", "message": "Request was throttled."}}',
        )
        ui.goto("/explorer/")
        expect(ui.locator("#results [role='alert']")).to_contain_text(
            re.compile("wait|try again", re.I)
        )

    def test_protected_pages_redirect_to_login(self, ui: Page) -> None:
        ui.goto("/alerts/")
        expect(ui).to_have_url(re.compile(r"/accounts/login/\?next=/alerts/"))


class TestAccountFlows:
    def test_signup_login_logout(self, ui: Page) -> None:
        ui.goto("/accounts/signup/")
        ui.get_by_label("Username").fill("e2e_new")
        ui.locator("#id_password1").fill("an-Unusual-passphrase-42")
        ui.locator("#id_password2").fill("an-Unusual-passphrase-42")
        ui.get_by_role("button", name="Create account").click()
        ui.wait_for_url("**/")
        account = ui.get_by_role("button", name=re.compile("e2e_new"))
        expect(account).to_be_visible()
        account.click()
        ui.get_by_role("button", name="Log out").click()
        expect(ui.get_by_role("link", name="Log in")).to_be_visible()

    def test_wrong_password_is_rejected_generically(self, ui: Page, user: ArangoUser) -> None:
        ui.goto("/accounts/login/")
        ui.get_by_label("Username").fill(user.username)
        ui.get_by_label("Password").fill("wrong-password")
        ui.get_by_role("button", name="Log in").click()
        expect(ui.locator("#login-errors")).to_contain_text("correct username and password")


class TestSignedInFlows:
    def test_alert_rule_create_preview_edit_delete(self, ui: Page, user: ArangoUser) -> None:
        log_in(ui, user.username)
        ui.goto("/alerts/")
        settle(ui)

        ui.get_by_role("button", name="Create rule").click()  # empty name: validation
        expect(ui.locator("#r-name")).to_have_attribute("aria-invalid", "true")

        ui.locator("#r-name").fill("Strong quakes")
        ui.locator("#r-minmag").fill("4.5")
        ui.get_by_role("button", name="Create rule").click()
        settle(ui)
        rules = ui.locator("#rules")
        expect(rules).to_contain_text("Strong quakes")
        expect(rules).to_contain_text("M ≥ 4.5")
        expect(ui.locator("#preview")).to_contain_text("Strong quakes")

        rules.get_by_role("button", name="Edit").click()
        expect(ui.locator("#r-name")).to_have_value("Strong quakes")
        ui.locator("#r-name").fill("Very strong quakes")
        ui.locator("#r-minmag").fill("6")
        ui.get_by_role("button", name="Save changes").click()
        settle(ui)
        expect(rules).to_contain_text("Very strong quakes")
        expect(rules).to_contain_text("M ≥ 6")

        ui.once("dialog", lambda dialog: dialog.accept())
        rules.get_by_role("button", name="Delete rule Very strong quakes").click()
        settle(ui)
        expect(rules).not_to_contain_text("Very strong quakes")

    def test_research_snapshot_manifest_and_csv_export(self, ui: Page, user: ArangoUser) -> None:
        log_in(ui, user.username)
        ui.goto("/research/")
        settle(ui)
        ui.locator("#s-title").fill("E2E strong events")
        ui.locator("#s-minmag").fill("4.5")
        ui.get_by_role("button", name="Freeze snapshot").click()
        expect(ui.locator("#snapshot-status")).to_contain_text("with 11 events")
        settle(ui)
        snapshots = ui.locator("#snapshots")
        expect(snapshots).to_contain_text("E2E strong events")

        snapshots.get_by_role("button", name="Show manifest").click()
        settle(ui)
        expect(snapshots.locator("dl.qw-kv")).to_contain_text("Content SHA-256")

        with ui.expect_download() as download_info:
            snapshots.get_by_role("link", name="CSV").click()
        download = download_info.value
        assert download.suggested_filename.endswith(".csv")
        lines = open(download.path(), encoding="utf-8").read().splitlines()  # noqa: SIM115
        assert len(lines) == 1 + 11  # header + one row per frozen event

    def test_saved_search_round_trip(self, ui: Page, user: ArangoUser) -> None:
        log_in(ui, user.username)
        ui.goto("/explorer/?min_magnitude=4.5")
        settle(ui)
        ui.get_by_role("button", name="Save search").click()
        ui.locator("#save-name").fill("M4.5+ today")
        ui.locator("#save-panel").get_by_role("button", name="Save").click()
        saved = ui.locator("#saved-list")
        expect(saved).to_contain_text("M4.5+ today")
        ui.goto("/explorer/")
        settle(ui)
        saved.get_by_role("link", name="M4.5+ today").click()
        expect(ui).to_have_url(re.compile(r"min_magnitude=4\.5"))
        settle(ui)
        expect(ui.locator("#summary")).to_contain_text("11 events")


class TestStaffFlows:
    def test_operations_is_staff_only(
        self, ui: Page, user: ArangoUser, browser_errors: BrowserErrors
    ) -> None:
        browser_errors.allow("403")
        log_in(ui, user.username)
        response = ui.goto("/operations/")
        assert response is not None
        assert response.status == 403
        expect(ui.get_by_role("heading", level=1)).to_have_text("Access denied")

    def test_operations_dashboard_for_staff(self, ui: Page, staff: ArangoUser) -> None:
        log_in(ui, staff.username)
        ui.goto("/operations/")
        settle(ui)
        expect(ui.get_by_role("heading", level=1)).to_have_text("Data operations")
        for region in ("#overview", "#runs", "#dead-letters", "#jobs", "#diagnostics", "#audit"):
            expect(
                ui.locator(f"{region} [data-kind='server'], {region} [data-kind='error']")
            ).to_have_count(0)
        # The seeded feed was ingested without a run record: the empty state, not an error.
        expect(ui.locator("#runs [data-kind='empty']")).to_be_visible()


@pytest.mark.parametrize("path", ["/", "/map/", "/explorer/", "/analytics/", "/status/", "/about/"])
def test_public_pages_have_no_console_or_csp_errors(ui: Page, path: str) -> None:
    ui.goto(path)
    settle(ui)
    expect(ui.locator("main h1")).to_have_count(1)
