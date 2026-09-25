/* Explorer (FR-05/06/12): URL-driven filters, sortable paginated table, map view, query summary,
 * saved searches and snapshot export. The URL query string *is* the canonical filter set, so
 * views are shareable and saved searches simply link back here. */
(function () {
  "use strict";
  const { h, api, load, state, fmt, magBadge, eventLink, formToParams, showFieldErrors, errorState, announce } = window.QW;

  const FILTER_KEYS = ["q", "start", "end", "min_magnitude", "max_magnitude", "min_depth_km", "max_depth_km",
    "status", "alert", "tsunami", "network", "lat", "lon", "radius_km", "event_type", "bbox"];
  const COLUMNS = [
    { key: "occurred_at", label: "Origin time (UTC)", sort: "occurred_at" },
    { key: "magnitude", label: "Magnitude", sort: "magnitude", num: true },
    { key: "place", label: "Place" },
    { key: "depth_km", label: "Depth", sort: "depth", num: true },
    { key: "status", label: "Status" },
    { key: "revision_count", label: "Revisions", sort: "revisions", num: true },
    { key: "significance", label: "Significance", sort: "significance", num: true },
  ];
  const PAGE_SIZE = 25;
  const authenticated = document.body.dataset.authenticated === "true";

  let params = new URLSearchParams(location.search);
  let view = "table";
  let map = null;
  let layer = null;
  let radiusCircle = null;

  const $ = (id) => document.getElementById(id);

  /* ---------------------------------------------------------------- state ↔ form */
  function filtersFromParams() {
    const out = {};
    for (const key of FILTER_KEYS) if (params.get(key)) out[key] = params.get(key);
    out.sort = params.get("sort") || "occurred_at";
    out.direction = params.get("direction") || "desc";
    return out;
  }

  function fillForm() {
    const form = $("filters");
    for (const el of form.elements) {
      if (!el.name || el.type === "submit") continue;
      const value = params.get(el.name) || "";
      el.value = el.type === "date" ? value.slice(0, 10) : value;
    }
    if (params.get("lat") || params.get("network")) form.querySelector("details").open = true;
  }

  function readForm() {
    const form = $("filters");
    const next = new URLSearchParams();
    const values = formToParams(form);
    for (const [key, value] of Object.entries(values)) {
      // keep full timestamps from saved searches when the date part was not edited
      const previous = params.get(key);
      next.set(key, previous && (key === "start" || key === "end") && previous.slice(0, 10) === value ? previous : value);
    }
    next.set("sort", params.get("sort") || "occurred_at");
    next.set("direction", params.get("direction") || "desc");
    return next;
  }

  function navigate(next, { push = true } = {}) {
    params = next;
    if (push) history.pushState(null, "", `?${params}`);
    run();
  }

  /* ---------------------------------------------------------------- table */
  function headerCell(col, filters) {
    if (!col.sort) return h("th", { scope: "col" }, col.label);
    const active = filters.sort === col.sort;
    const ariaSort = active ? (filters.direction === "asc" ? "ascending" : "descending") : null;
    return h("th", { scope: "col", class: col.num ? "num" : null, "aria-sort": ariaSort },
      h("button", {
        type: "button",
        class: "qw-sort",
        onclick: () => {
          const next = new URLSearchParams(params);
          next.set("sort", col.sort);
          next.set("direction", active && filters.direction === "desc" ? "asc" : "desc");
          next.delete("page");
          navigate(next);
          announce(`Sorted by ${col.label}, ${next.get("direction") === "asc" ? "ascending" : "descending"}`);
        },
      }, col.label));
  }

  function cell(col, e) {
    switch (col.key) {
      case "occurred_at": return h("td", {}, h("time", { datetime: e.occurred_at }, fmt.utc(e.occurred_at)));
      case "magnitude": return h("td", { class: "num" }, magBadge(e.magnitude, e.magnitude_type), e.magnitude_type ? h("span", { class: "small text-body-secondary ms-1" }, e.magnitude_type) : null);
      case "place": return h("td", {}, eventLink(e.key, e.place || e.key), e.tsunami ? h("span", { class: "badge text-bg-info ms-1" }, "tsunami flag") : null, e.alert ? h("span", { class: "badge text-bg-warning ms-1" }, `PAGER ${e.alert}`) : null);
      case "depth_km": return h("td", { class: "num" }, fmt.depth(e.depth_km));
      case "revision_count": return h("td", { class: "num" }, fmt.num(e.revision_count));
      case "significance": return h("td", { class: "num" }, fmt.num(e.significance));
      default: return h("td", {}, e[col.key] || "—");
    }
  }

  function renderTable(data, el) {
    $("summary").textContent = `${fmt.num(data.total)} events · ${data.query.summary}`;
    renderPager(data);
    if (!data.results.length) return false;
    const filters = filtersFromParams();
    el.append(h("div", { class: "qw-table-wrap" },
      h("table", { class: "table table-hover qw-table align-middle" },
        h("caption", { class: "visually-hidden" }, `Earthquakes matching: ${data.query.summary}. Page ${data.page} of ${data.total_pages}.`),
        h("thead", {}, h("tr", {}, COLUMNS.map((c) => headerCell(c, filters)))),
        h("tbody", {}, data.results.map((e) => h("tr", {}, COLUMNS.map((c) => cell(c, e))))))));
    return true;
  }

  function renderPager(data) {
    const pager = $("pager");
    pager.replaceChildren();
    if (data.total_pages <= 1) return;
    const go = (page) => {
      const next = new URLSearchParams(params);
      next.set("page", String(page));
      navigate(next);
      $("summary").focus?.();
    };
    const item = (label, page, { disabled = false, current = false, srLabel } = {}) =>
      h("li", { class: `page-item${disabled ? " disabled" : ""}${current ? " active" : ""}` },
        h("button", { type: "button", class: "page-link", disabled, "aria-current": current ? "page" : null, "aria-label": srLabel || null, onclick: () => go(page) }, label));
    const pages = new Set([1, data.total_pages, data.page - 1, data.page, data.page + 1].filter((p) => p >= 1 && p <= data.total_pages));
    const sorted = [...pages].sort((a, b) => a - b);
    const items = [item("‹", data.page - 1, { disabled: data.page === 1, srLabel: "Previous page" })];
    sorted.forEach((p, i) => {
      if (i && p - sorted[i - 1] > 1) items.push(h("li", { class: "page-item disabled" }, h("span", { class: "page-link" }, "…")));
      items.push(item(String(p), p, { current: p === data.page, srLabel: `Page ${p}` }));
    });
    items.push(item("›", data.page + 1, { disabled: data.page === data.total_pages, srLabel: "Next page" }));
    pager.append(h("ul", { class: "pagination pagination-sm flex-wrap mb-0" }, items));
  }

  function run() {
    fillForm();
    const query = { ...filtersFromParams(), page: params.get("page") || 1, page_size: PAGE_SIZE };
    load($("results"), "/events", renderTable, {
      params: query,
      rows: 8,
      empty: "No events match these filters. Try widening the date range or lowering the minimum magnitude.",
      messages: { validation: "Some filters are not valid — see the details below." },
    }).then((result) => {
      if (result && !result.ok) {
        $("summary").textContent = "";
        if (result.status === 400) showFieldErrors($("filters"), result.error);
      } else {
        showFieldErrors($("filters"), null);
      }
    });
    if (view === "map") refreshMap();
  }

  /* ---------------------------------------------------------------- map view */
  async function refreshMap() {
    if (!map) {
      map = QWMap.create($("explorer-map"));
      layer = QWMap.eventLayer(map);
      map.on("moveend", () => { if (!radiusMode()) refreshMap(); });
    }
    map.invalidateSize();
    const filters = filtersFromParams();
    const status = $("map-status");
    if (radiusCircle) { radiusCircle.remove(); radiusCircle = null; }
    if (radiusMode()) {
      // The map endpoint takes a viewport box; a radius query is shown from the paginated list instead.
      const lat = parseFloat(filters.lat), lon = parseFloat(filters.lon), km = parseFloat(filters.radius_km);
      radiusCircle = L.circle([lat, lon], { radius: km * 1000, fill: false, color: "#0b5cad", dashArray: "6 4" }).addTo(map);
      map.fitBounds(radiusCircle.getBounds(), { animate: false });
      const result = await api("/events", { params: { ...filters, page_size: 200 } });
      if (!result.ok) { status.textContent = `Could not load map data: ${result.error.message}`; return; }
      const d = result.data;
      layer.render({ mode: "points", points: d.results.map((e) => [e.key, e.latitude, e.longitude, e.magnitude, e.depth_km, e.occurred_at]) });
      if (d.total > d.results.length) {
        status.replaceChildren(window.QW.partialNotice(`Partial view: showing the first ${fmt.num(d.results.length)} of ${fmt.num(d.total)} events in the radius (current sort order). Use the table for all results.`));
      } else {
        status.textContent = `${fmt.num(d.total)} events within ${fmt.num(km)} km.`;
      }
      return;
    }
    status.textContent = "Loading…";
    const { bbox: _ignored, ...withoutBbox } = filters;
    const result = await api("/events/map", { params: { ...withoutBbox, bbox: QWMap.bboxParam(map) } });
    if (!result.ok) { status.textContent = `Could not load map data: ${result.error.message}`; return; }
    layer.render(result.data);
    status.textContent = result.data.count
      ? `${fmt.num(result.data.count)} matching events in view${result.data.mode === "clusters" ? " (grouped; zoom in for detail)" : ""}.`
      : "No matching events in view.";
  }

  function radiusMode() {
    return Boolean(params.get("lat") && params.get("lon") && params.get("radius_km"));
  }

  function setView(next) {
    view = next;
    for (const btn of document.querySelectorAll("[data-view]")) {
      const on = btn.dataset.view === next;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-pressed", String(on));
    }
    $("table-view").hidden = next !== "table";
    $("map-view").hidden = next !== "map";
    if (next === "map") refreshMap();
  }

  /* ---------------------------------------------------------------- saved searches */
  function loadSaved() {
    const el = $("saved-list");
    if (!el) return;
    load(el, "/saved-searches", (data) => {
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled mb-0 small" }, data.results.map((s) =>
        h("li", { class: "d-flex justify-content-between align-items-start gap-2 py-1 border-bottom" },
          h("div", {},
            h("a", { href: `?${new URLSearchParams(s.filters)}` }, s.name),
            h("div", { class: "text-body-secondary" }, s.summary)),
          h("button", {
            type: "button", class: "btn btn-sm btn-link text-danger p-0", "aria-label": `Delete saved search ${s.name}`,
            onclick: async () => {
              if (!window.confirm(`Delete the saved search "${s.name}"?`)) return;
              const r = await api(`/saved-searches/${encodeURIComponent(s.id || s.key)}`, { method: "DELETE" });
              if (r.ok) { announce(`Deleted ${s.name}`); loadSaved(); } else window.alert(r.error.message);
            },
          }, h("i", { class: "bi bi-trash", "aria-hidden": "true" }))))));
      return true;
    }, { empty: "No saved searches yet.", rows: 2 });
  }

  async function saveSearch(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = form.name.value.trim();
    if (!name) return showFieldErrors(form, { details: { fields: { name: "Enter a name." } } });
    const filters = filtersFromParams();
    const result = await api("/saved-searches", { method: "POST", body: { name, filters } });
    if (result.ok) {
      showFieldErrors(form, null);
      form.reset();
      bootstrap.Collapse.getOrCreateInstance(form).hide();
      announce(`Saved search "${name}"`);
      loadSaved();
    } else if (!showFieldErrors(form, result.error)) {
      showFieldErrors(form, { details: { fields: { name: result.error.message } } });
    }
  }

  async function freezeSnapshot(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const out = $("snapshot-result");
    const title = form.title.value.trim();
    if (!title) return showFieldErrors(form, { details: { fields: { title: "Enter a title." } } });
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    state(out, "loading", { message: "Freezing snapshot…", rows: 1 });
    const result = await api("/research/snapshots", { method: "POST", body: { title, notes: form.notes.value.trim(), filters: filtersFromParams() } });
    button.disabled = false;
    if (!result.ok) {
      if (result.status === 400) showFieldErrors(form, result.error);
      return errorState(out, result, null, { throttled: "Snapshot limit reached for this hour. Please try again later." });
    }
    showFieldErrors(form, null);
    const s = result.data;
    const id = encodeURIComponent(s.id || s.key);
    out.replaceChildren(h("div", { class: "alert alert-success mb-0", role: "status" },
      `Snapshot frozen with ${fmt.num(s.row_count)} events. Download: `,
      h("a", { href: `/api/v1/research/snapshots/${id}/export?format=csv` }, "CSV"), " · ",
      h("a", { href: `/api/v1/research/snapshots/${id}/export?format=json` }, "JSON"), " · ",
      h("a", { href: `/api/v1/research/snapshots/${id}/export?format=zip` }, "ZIP with manifest"), " — or open the ",
      h("a", { href: "/research/" }, "Research Lab"), "."));
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("filters").addEventListener("submit", (event) => {
      event.preventDefault();
      navigate(readForm());
    });
    window.addEventListener("popstate", () => {
      params = new URLSearchParams(location.search);
      run();
    });
    for (const btn of document.querySelectorAll("[data-view]")) btn.addEventListener("click", () => setView(btn.dataset.view));
    if (authenticated) {
      $("save-panel").addEventListener("submit", saveSearch);
      $("snapshot-panel").addEventListener("submit", freezeSnapshot);
      loadSaved();
    }
    run();
  });
})();
