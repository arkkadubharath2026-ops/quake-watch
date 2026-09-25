/* Live Map (FR-07): viewport-aware loading, server/client clustering, filters, side panel. */
(function () {
  "use strict";
  const { h, api, load, fmt, magBadge, time, eventLink } = window.QW;

  const WINDOWS = { "1h": 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400 };
  const REFRESH_MS = 120000;

  let map;
  let layer;
  let controller = null;
  let debounce = null;
  let refreshTimer = null;

  function form() {
    return document.getElementById("map-filters");
  }

  function filters() {
    const f = form();
    const seconds = WINDOWS[f.window.value] || WINDOWS["24h"];
    return {
      start: new Date(Date.now() - seconds * 1000).toISOString().replace(/\.\d+Z$/, ".000Z"),
      min_magnitude: f.min_magnitude.value,
      status: f.status.value,
    };
  }

  /* URL state: ?window=&min_magnitude=&status=&lat=&lon=&z= (shareable views). */
  function readUrl() {
    const params = new URLSearchParams(location.search);
    const f = form();
    for (const name of ["window", "min_magnitude", "status"]) {
      const value = params.get(name);
      if (value !== null && [...f[name].options].some((o) => o.value === value)) f[name].value = value;
    }
    const lat = parseFloat(params.get("lat"));
    const lon = parseFloat(params.get("lon"));
    const z = parseInt(params.get("z"), 10);
    return Number.isFinite(lat) && Number.isFinite(lon) && Number.isFinite(z) ? { center: [lat, lon], zoom: z } : null;
  }

  function writeUrl() {
    const f = form();
    const c = map.getCenter();
    const params = new URLSearchParams();
    params.set("window", f.window.value);
    if (f.min_magnitude.value) params.set("min_magnitude", f.min_magnitude.value);
    if (f.status.value) params.set("status", f.status.value);
    params.set("lat", c.lat.toFixed(3));
    params.set("lon", c.lng.toFixed(3));
    params.set("z", String(map.getZoom()));
    history.replaceState(null, "", `?${params}`);
  }

  async function refresh() {
    if (controller) controller.abort();
    controller = new AbortController();
    const signal = controller.signal;
    const status = document.getElementById("map-status");
    const params = { ...filters(), bbox: QWMap.bboxParam(map) };
    writeUrl();
    status.textContent = "Loading events in view…";
    const [mapResult] = await Promise.all([
      api("/events/map", { params, signal }),
      load(document.getElementById("in-view"), "/events", renderList, {
        params: { ...params, sort: "magnitude", direction: "desc", page_size: 15 },
        signal,
        empty: "No events match these filters in this area. Try zooming out or widening the time window.",
        rows: 5,
      }),
    ]);
    if (mapResult.aborted) return;
    if (!mapResult.ok) {
      layer.clear();
      status.textContent = `Could not load map data: ${mapResult.error.message}`;
      return;
    }
    layer.render(mapResult.data);
    const d = mapResult.data;
    status.textContent = d.count === 0
      ? "No events in view for these filters."
      : d.mode === "clusters"
        ? `${fmt.num(d.count)} events in view, grouped into ${fmt.num(d.clusters.length)} areas. Zoom in for individual events.`
        : `${fmt.num(d.count)} events in view.`;
  }

  function scheduleRefresh() {
    window.clearTimeout(debounce);
    debounce = window.setTimeout(refresh, 300);
  }

  function renderList(data, el) {
    if (!data.results.length) return false;
    el.append(h("p", { class: "small text-body-secondary" }, `${fmt.num(data.total)} events in view; showing the ${data.results.length} strongest.`));
    el.append(h("ol", { class: "list-unstyled mb-0" }, data.results.map((e) =>
      h("li", { class: "d-flex gap-2 align-items-start py-2 border-bottom" },
        magBadge(e.magnitude, e.magnitude_type),
        h("div", { class: "flex-grow-1" },
          eventLink(e.key, e.place || e.key),
          h("div", { class: "small text-body-secondary" }, time(e.occurred_at), " · ", fmt.depth(e.depth_km)),
          h("button", { type: "button", class: "btn btn-link btn-sm p-0", onclick: () => select(e.key, [e.latitude, e.longitude]) },
            h("span", {}, "Show on map"), h("span", { class: "visually-hidden" }, `: ${e.place || e.key}`)))))));
    return true;
  }

  async function select(key, latlng) {
    const box = document.getElementById("selected");
    const body = document.getElementById("selected-body");
    box.hidden = false;
    if (latlng) map.setView(latlng, Math.max(map.getZoom(), 6));
    const result = await load(body, `/events/${encodeURIComponent(key)}`, (e) => {
      const s = e.source;
      body.append(
        h("div", { class: "d-flex gap-2 align-items-start mb-2" }, magBadge(s.magnitude, s.magnitude_type), h("strong", {}, s.place || e.key)),
        h("dl", { class: "qw-kv mb-2" },
          h("dt", {}, "Origin time"), h("dd", {}, fmt.utc(s.occurred_at)),
          h("dt", {}, "Depth"), h("dd", {}, fmt.depth(s.depth_km)),
          h("dt", {}, "Status"), h("dd", {}, s.status || "—"),
          h("dt", {}, "Revisions"), h("dd", {}, fmt.num(e.operational.revision_count)),
          h("dt", {}, "Tsunami flag"), h("dd", {}, s.tsunami ? "Yes (USGS flag, not a warning)" : "No")),
        h("a", { class: "btn btn-sm btn-primary", href: `/events/${encodeURIComponent(e.key)}/` }, "Full details"));
    }, { rows: 3 });
    if (result && result.ok) window.QW.announce(`Selected ${result.data.title}`);
  }

  function setAutoRefresh(on) {
    window.clearInterval(refreshTimer);
    if (on) refreshTimer = window.setInterval(refresh, REFRESH_MS);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const initial = readUrl();
    map = QWMap.create(document.getElementById("live-map"), initial || { center: [20, 0], zoom: 2 });
    layer = QWMap.eventLayer(map, { onSelect: (key) => select(key) });
    map.on("moveend", scheduleRefresh);
    form().addEventListener("change", (event) => {
      if (event.target.id === "f-refresh") setAutoRefresh(event.target.checked);
      else scheduleRefresh();
    });
    form().addEventListener("submit", (event) => event.preventDefault());
    setAutoRefresh(document.getElementById("f-refresh").checked);
    refresh();
  });

})();
