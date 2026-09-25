# Accessibility audit (WCAG 2.2 AA)

- **Date:** 2026-09-25 · **Scope:** every page of the web UI (ADR-011), signed out, signed in and staff.
- **Standard:** WCAG 2.2 level A and AA.
- **Method:** automated rules in a real browser, keyboard and motion checks written as tests, and a
  manual review of the criteria no tool can decide.

## How it is tested

`tests/e2e/test_accessibility.py` runs in Chromium (Playwright) against the live Django app and
the real ArangoDB test database, seeded from the recorded USGS feed:

| Check | Coverage |
|---|---|
| axe-core 4.12 rules tagged `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` | 8 public/account pages × light + dark; Event Detail (all 5 tabs) × light + dark; Alerts and Research Lab signed in × light + dark; Operations as staff; 3 pages at 320 px; the server-failure state |
| 1.4.10 Reflow | no horizontal page scroll at 320 CSS px, i.e. 400 % zoom (Dashboard, Explorer, Analytics) |
| 1.4.11 Non-text contrast (focus) | the focused control has the solid two-tone brand ring |
| 2.4.1 Bypass blocks, 2.4.7 Focus visible | skip link is the first tab stop, is visible when focused, moves focus into `main` |
| 2.1.1 Keyboard, 4.1.3 Status messages | sortable headers operate with Enter; the sort change is announced in `#qw-live` |
| 4.1.2 Name, role, value | theme toggle exposes `aria-pressed` |
| 2.3.3 Animation from interactions | `prefers-reduced-motion` stops the loading skeleton animation |

axe is run only after every data region has finished loading, so it audits rendered data: tables,
charts, maps, forms and error states. It does not audit empty shells. `tests/e2e/test_flows.py` also
fails any page that logs a console error or CSP violation.

Run: `python -m pytest tests/e2e -m e2e` (needs `python -m playwright install chromium`).

## Findings and fixes

The first automated run failed 18 of 32 checks; A7 came from the flow tests and A9 from the manual review. Every finding was fixed in the design system or
shared runtime, not per page, and all checks now pass.

| # | Criterion | Finding | Fix |
|---|---|---|---|
| A1 | 1.4.3 Contrast | Bootstrap's `.btn-outline-primary` keeps `#0d6efd` in dark mode (3.42:1 on `#212529`) | Primary and outline buttons use the theme's brand token (`--qw-brand`) with an `--qw-on-brand` text colour per theme |
| A2 | 1.4.3 Contrast | `.btn-outline-secondary`, the account menu and "Mark all read" use `#6c757d` (3.3–3.7:1 dark, 4.32:1 on the light muted surface) | Secondary outline buttons use `--qw-text-muted` (5.9:1 light, ≥ 7:1 dark) |
| A3 | 1.4.3 Contrast | Tabs and links used Bootstrap's `#0d6efd` on the muted surface (4.15:1) | `--bs-link-color` set to the brand token in both themes; tabs and pagination follow it |
| A4 | 2.5.8 Target size | Pager buttons 22.4 px wide | `.page-link` minimum width 2 rem |
| A5 | 2.5.8 Target size | Stacked source links on About were 19 px tall | Link list rows are at least 28 px tall |
| A6 | 2.1.1 Keyboard | Wide tables and raw JSON scroll horizontally but could not be focused, so keyboard users could not scroll them | `QW.scrollRegion()`: scroll containers are focusable, named regions; the raw payload and manifest `<pre>` blocks likewise |
| A7 | 4.1.2 / 4.1.3 | Regions filled by hand after a loading state (System Status health, Dashboard significant events, Analytics sections, snapshot, refresh and admin-action results) kept `aria-busy="true"` after rendering, so assistive tech treated them as still loading | `QW.fill()` replaces content and ends the busy state; used by every manual loading state |
| A8 | 2.3.3 Motion | Under reduced motion the skeleton shimmer ran as a 0.01 ms *infinite* animation, effectively a flicker | Reduced motion caps iterations at 1 and disables the skeleton animation |
| A9 | 1.4.11 Non-text contrast | Focus ring was a 45 % translucent blue (~1.9:1 on white) | Solid two-tone ring from the brand token (found in manual review) |

A7 was found by the end-to-end suite, not axe. The tests wait until no region is busy, and
Status never got there.

## Exceptions (documented, not violations)

- **Map markers and clusters (2.5.8):** markers can overlap when zoomed out, so they cannot
  always keep 24 px of spacing. WCAG 2.5.8's *equivalent* exception applies: every map has a
  text alternative with the same events and actions:
  - Live Map: the side panel list.
  - Explorer: the table view.
  - Dashboard: the recent events list.
  - Event Detail: the coordinates in text.

  Markers stay keyboard-focusable and are audited for every other rule. Only `target-size` is
  disabled inside `.leaflet-marker-pane`.
- **Map tiles (1.4.5 / 1.1.1):** OpenStreetMap tiles are decorative context. Each map has an
  `aria-label` that points to its text equivalent.

## Manual review (criteria tools cannot decide)

| Criterion | Result |
|---|---|
| 1.1.1 Non-text content | Charts: `role="img"`, the summary sentence as the name, a caption and a data table. Icons are `aria-hidden`; icon-only buttons have labels |
| 1.3.1 Info and relationships | Landmarks (`header/nav`, `main`, `aside`, `footer`), one `h1` per page, sequential headings, `th scope`, `<dl>` for key–value data, label↔input pairs |
| 1.4.1 Use of colour | Magnitude badges show the number, markers also scale in size, and freshness and status badges carry words |
| 1.4.11 Non-text contrast | Focus ring: 2 px surface gap + 2 px solid brand ring (≥ 6.6:1 against the adjacent surfaces in both themes); it was a 45 % translucent tint (~1.9:1), fixed as A9 |
| 1.4.4 Resize text | rem-based type scale; reflow at 320 px (tested) covers 400 % zoom |
| 2.4.3 Focus order | DOM order follows the visual order; filters come before results |
| 2.4.11 Focus not obscured (2.2) | No sticky headers or overlays cover focused controls. The mobile menu pushes content down rather than covering it |
| 2.5.7 Dragging movements (2.2) | The map can be panned with the keyboard and the zoom buttons; no feature needs dragging |
| 3.2.6 Consistent help (2.2) | The footer links (About, data attribution, disclaimer) sit in the same place on every page |
| 3.3.1 / 3.3.3 Error identification and suggestion | Invalid fields get `aria-invalid`, a message linked with `aria-describedby`, and focus moves to the first invalid field; API validation messages name the field and the allowed range |
| 3.3.7 Redundant entry (2.2) | The Explorer query becomes the snapshot and saved-search definition, so the user never retypes it |
| 3.3.8 Accessible authentication (2.2) | Username and password with `autocomplete` attributes; paste is allowed; no cognitive test |
