# ADR-011: Server-rendered pages with API-driven islands

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
The ESD fixes the frontend stack as HTML5, CSS3, JavaScript and Bootstrap 5, with no SPA framework.
The pages need live data (maps, charts, feeds) that the versioned JSON API (`/api/v1`) already
serves, validates and throttles. The CSP is strict: `script-src 'self' 'nonce-…'`, `style-src 'self'`,
and no CDN (ADR vendored assets). Every flow must render loading, empty, partial, validation,
permission, not-found and server-failure states consistently.

## Decision
1. **Django renders every page shell** (`apps/web`, URL namespace `pages`): layout, navigation,
   attribution, safety text, forms and headings. Auth gating is done on the server
   (`login_required`, staff check → 403), so protected pages never flash for anonymous users.
2. **Event Detail renders its overview on the server** from `EventQueryService.detail`. Missing
   events are real HTTP 404s, historical/raw USGS ids redirect (302) to the canonical URL, and the
   core facts are readable without JavaScript. The lazily loaded tabs use the API.
3. **Interactive regions are "islands"**: one static script per page under `static/qw/js/` calls
   the same `/api/v1` endpoints external clients use (session cookie + CSRF header). No second
   data path exists for the UI, so API validation, throttling, object-level authorization and audit
   apply to UI traffic unchanged.
4. **One runtime (`qw.js`) owns UI states.** `QW.load()` maps every response to exactly one state
   (loading skeleton, success, empty, validation with field details, auth → login link, permission,
   not found, throttled, server failure with retry and correlation id, network failure). Data is
   inserted only through a DOM builder that uses `textContent` — never `innerHTML` — so API content
   cannot inject markup. Links built from upstream data are scheme/host-checked on the server
   (`safe_usgs_url`).
5. **URLs carry state**: the Explorer query string *is* the canonical filter set (the same shape as
   saved searches and snapshot definitions), and the map keeps its view in the URL, so any view can
   be shared or bookmarked.
6. **No inline script except the nonce'd theme bootstrap**; page data for scripts is passed with
   `json_script` (not executed). Chart.js and Leaflet only set styles through the CSSOM, which the
   `style-src 'self'` policy allows.

## Alternatives considered
- **SPA (React/Vue) with a build step** — rejected: outside the ESD stack, adds a toolchain and a
  second rendering model for a data-exploration app whose pages are mostly independent.
- **Fully server-rendered pages (no API calls)** — rejected: the map, charts and feeds would need
  duplicate server-side query paths and full reloads for every pan or filter change.
- **htmx-style HTML fragments** — rejected: a new dependency and a second set of endpoints to
  secure; the JSON API already exists and is tested.

## Consequences
- Page views stay thin (no business logic); view tests pin routing, gating, CSP and the page
  contract; browser behaviour is covered by Playwright end-to-end tests (L6).
- A page's script depends on the API contract; API changes must update the matching island.
- Accessibility is designed in once (skip link, landmarks, live regions, keyboard-operable
  controls, data tables behind every chart, text alternatives for the maps).
