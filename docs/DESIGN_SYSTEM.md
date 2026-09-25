# QuakeWatch design system

Bootstrap 5.3 (vendored) plus a thin token layer in `static/qw/css/qw.css`. Pages never hard-code
colours or spacing; they use these tokens or Bootstrap utilities. Light and dark themes are selected
by `data-bs-theme` (OS preference on first visit, then the toggle, remembered in `localStorage`).

## Tokens

| Group | Tokens | Notes |
|---|---|---|
| Typography | `--qw-font-sans`, `--qw-font-mono`, `--qw-text-xs … --qw-text-2xl` | System font stack; 1.2 type scale |
| Spacing | `--qw-space-1 … --qw-space-8` | 4 px grid |
| Shape | `--qw-radius`, `--qw-radius-sm`, `--qw-focus-ring` | Two-tone focus ring (surface gap + solid brand) on every `:focus-visible` |
| Surfaces | `--qw-surface`, `--qw-surface-muted`, `--qw-border`, `--qw-text-muted` | Redefined per theme |
| Brand | `--qw-brand`, `--qw-on-brand` | Links, tabs, pagination, primary/outline buttons (Bootstrap's fixed `#0d6efd`/`#6c757d` miss AA on our surfaces) |
| Freshness | `--qw-fresh`, `--qw-degraded`, `--qw-stale`, `--qw-unknown` | Always paired with a text label |
| Magnitude | `--qw-mag-0 … --qw-mag-4`, `--qw-mag-ink-0 … 4` | Ordinal ramp, see below |
| Charts | `--qw-series-1`, `--qw-series-muted` | Single-series colour; "unknown/other" |

### Magnitude ramp

Magnitude bands (< 2.5, 2.5–4.5, 4.5–6, 6–7, ≥ 7) are **ordered**, so they use one warm hue
from light to dark, not categorical colours. Both theme variants were checked with the dataviz
palette validator (`--ordinal`): lightness is monotone, adjacent steps differ by ΔL ≥ 0.06, hue
spread ≤ 40°, and the lightest step clears 2:1 against the surface. Badge text colours
(`--qw-mag-ink-*`) meet WCAG AA 4.5:1 on every step in both themes. Magnitude is never
encoded by colour alone: map markers also scale in size, and every badge shows the number.

| Band | Light | Dark |
|---|---|---|
| < 2.5 | `#e8a33a` | `#efa955` |
| 2.5–4.5 | `#e0712c` | `#e8883f` |
| 4.5–6 | `#c9432a` | `#dd6a33` |
| 6–7 | `#962430` | `#c2462b` |
| ≥ 7 | `#5e1538` | `#a2352a` |

Chart datasets record the token they were coloured from (`qwToken`), so switching theme recolours
them with that theme's steps. The colour follows the band, not its position in a filtered list.

## Components

| Component | Class / helper | Contract |
|---|---|---|
| Page header | `.qw-page-header` | `h1` + one-line purpose |
| Card | `.qw-card` | Equal height only when alone in a grid column |
| Stat tile | `.qw-stat`, `.qw-stat-label` | Number + label; no colour-only meaning |
| Magnitude badge | `QW.magBadge()` / `.qw-mag[data-band]` | Screen-reader prefix "Magnitude" |
| Freshness badge | `[data-qw-freshness]` | Dot + status word + time; polls every 60 s |
| Key–value list | `.qw-kv` (`<dl>`) | Source vs derived values in separate lists |
| Table | `.qw-table` in `QW.scrollRegion(label, table)` | Numeric columns right-aligned, tabular figures; sortable headers are buttons with `aria-sort`; the scroll container is a focusable, named region |
| Chart | `QWCharts.figure()` / `.bar()` | Canvas `role="img"` + summary caption + "Show data table" |
| Map | `QWMap.create()` / `.eventLayer()` | Legend control; the page always has an equivalent text list |
| Timeline | `.qw-timeline` | Ordered list, newest first |
| Form field | `partials/field.html` | Label↔input, required marker, `aria-describedby` for help and errors |

## UI states (every data region)

`QW.load(el, path, render, opts)` renders exactly one of the states below. Code that sets a
loading state by hand must finish with `QW.fill(el, …)` (or `QW.errorState`), which also ends the
region's `aria-busy` period.


| State | Trigger | Presentation |
|---|---|---|
| Loading | request in flight | skeleton rows, `aria-busy`, hidden "Loading…" status |
| Success | 2xx with data | `render()` output |
| Empty | `render()` returns `false` | inbox icon + page-specific guidance |
| Partial | page-specific (for example, clustered map, truncated table) | inline warning notice |
| Validation error | 400 | message + per-field list; forms mark fields `aria-invalid` and focus the first |
| Auth required | 401, or 403 while signed out | "Please log in" + login link with `next` |
| Permission error | 403 while signed in | lock icon + message |
| Not found | 404 | message from the API |
| Throttled | 429 | wait message + retry |
| Server failure | 5xx | fixed public message, retry button, correlation id |
| Network failure | fetch rejected | connection message + retry |

Full-page errors use `templates/400|403|404|503.html` (layout + next steps) and a standalone
`500.html` that needs no context processors.

## Accessibility checklist (WCAG 2.2 AA)

Audited automatically and manually; findings, fixes and exceptions are in [ACCESSIBILITY.md](ACCESSIBILITY.md).

- Skip link to `#main`; landmarks (`header/nav`, `main`, `aside`, `footer`); one `h1` per page, sequential headings.
- All controls are native elements (buttons, links, inputs); icon-only buttons have `aria-label`.
- Live regions: `#qw-live` for announcements (sort changes, saves, deletions); map/result status lines use `role="status"`.
- Charts: summary sentence as the accessible name and caption, plus a data table.
- Maps: text list of the same events (Live Map side panel, Explorer table, Dashboard recent list).
- `prefers-reduced-motion` disables animations (skeleton shimmer, Chart.js animation).
- Colour is never the only carrier of meaning (magnitude, freshness, status badges all have text).
- Responsive down to 320 px (tested): navigation collapses below `xl`; tables scroll horizontally inside a focusable region.
- Targets are at least 24 px (pager buttons 32 px; link lists 28 px rows); map markers use 2.5.8's equivalent-control exception.
