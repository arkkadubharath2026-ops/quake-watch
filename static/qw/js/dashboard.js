/* Dashboard (ESD §10): summary, 24 h map preview, recent events, daily activity, significant events. */
(function () {
  "use strict";
  const { h, load, fmt, magBadge, time, eventLink, api, state } = window.QW;

  function stat(label, value, extra) {
    return h("div", { class: "col-6 col-md-4 col-xl-2" },
      h("div", { class: "qw-card" },
        h("div", { class: "qw-stat" }, value),
        h("div", { class: "qw-stat-label" }, label),
        extra ? h("div", { class: "small mt-1" }, extra) : null));
  }

  function strongestCard(label, e) {
    return h("div", { class: "col-md-8 col-xl-4" },
      h("div", { class: "qw-card" },
        h("div", { class: "qw-stat-label mb-1" }, label),
        e ? h("div", { class: "d-flex gap-2 align-items-start" }, magBadge(e.magnitude),
          h("div", {}, eventLink(e.key, e.place || e.key), h("div", { class: "small text-body-secondary" }, time(e.occurred_at), " · depth ", fmt.depth(e.depth_km))))
          : h("p", { class: "mb-0 text-body-secondary" }, "No events in this window.")));
  }

  function renderSummary(s, el) {
    el.append(
      stat("Events, last 24 h", fmt.num(s.count_24h)),
      stat("Events, last 7 days", fmt.num(s.count_7d)),
      stat("M4.5+ in 7 days", fmt.num(s.m45_plus_7d)),
      stat("Reviewed share, 7 days", fmt.pct(s.reviewed_share_7d), "USGS review status"),
      strongestCard("Strongest in the last 24 h", s.strongest_24h),
    );
    renderSignificant(s.significant_7d);
  }

  function eventList(rows) {
    return h("ul", { class: "list-unstyled mb-2" }, rows.map((e) =>
      h("li", { class: "d-flex gap-2 align-items-start py-2 border-bottom" },
        magBadge(e.magnitude, e.magnitude_type),
        h("div", { class: "flex-grow-1" },
          eventLink(e.key, e.place || e.key),
          h("div", { class: "small text-body-secondary" }, time(e.occurred_at), " · depth ", fmt.depth(e.depth_km),
            e.status ? ` · ${e.status}` : "", e.tsunami ? " · tsunami flag" : "")))));
  }

  function renderSignificant(rows) {
    const el = document.getElementById("significant");
    if (!rows || !rows.length) return state(el, "empty", { message: "No significant events in the last 7 days." });
    el.replaceChildren(eventList(rows));
  }

  function isoDaysAgo(days) {
    return new Date(Date.now() - days * 86400000).toISOString().replace(/\.\d+Z$/, ".000Z");
  }

  async function renderMap() {
    const el = document.getElementById("preview-map");
    const status = document.getElementById("preview-map-state");
    const map = QWMap.create(el, { zoom: 1, scrollWheelZoom: false });
    const layer = QWMap.eventLayer(map);
    status.textContent = "Loading events…";
    const result = await api("/events/map", { params: { bbox: "-85,-180,85,180", start: isoDaysAgo(1) } });
    if (!result.ok) {
      status.replaceChildren(h("span", { class: "text-danger" }, "Could not load map data: ", result.error.message));
      return;
    }
    layer.render(result.data);
    status.textContent = result.data.count
      ? `${fmt.num(result.data.count)} events in the last 24 hours${result.data.mode === "clusters" ? " (grouped)" : ""}.`
      : "No events in the last 24 hours.";
  }

  // fixed band → ramp step (colour follows the band, not its position in the filtered list)
  const BAND_STEP = { "<2.5": 0, "2.5-4.5": 1, "4.5-6": 2, "6+": 3 };

  function renderActivity(data, el) {
    const since = isoDaysAgo(14).slice(0, 10);
    const rows = data.daily_by_band.filter((r) => r.day > since);
    if (!rows.length) return false;
    const days = [...new Set(rows.map((r) => r.day))].sort();
    const bands = ["<2.5", "2.5-4.5", "4.5-6", "6+", "unknown"].filter((b) => rows.some((r) => r.band === b));
    const count = (day, b) => (rows.find((r) => r.day === day && r.band === b) || { count: 0 }).count;
    const totals = days.map((d) => bands.reduce((sum, b) => sum + count(d, b), 0));
    const peak = days[totals.indexOf(Math.max(...totals))];
    QWCharts.figure(el, {
      summary: `Stacked daily event counts by magnitude band over ${days.length} days; busiest day ${peak} with ${fmt.num(Math.max(...totals))} events.`,
      config: {
        type: "bar",
        data: { labels: days, datasets: bands.map((b) => ({ label: `M ${b}`, data: days.map((d) => count(d, b)), qwToken: b === "unknown" ? "--qw-series-muted" : `--qw-mag-${BAND_STEP[b]}`, qwGap: true, backgroundColor: QWCharts.cssVar(b === "unknown" ? "--qw-series-muted" : `--qw-mag-${BAND_STEP[b]}`), borderColor: QWCharts.surface(), borderWidth: { top: 2 } })) },
        options: { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, title: { display: true, text: "Events" } } } },
      },
      columns: ["Day", ...bands.map((b) => `M ${b}`), "Total"],
      rows: days.map((d, i) => [d, ...bands.map((b) => fmt.num(count(d, b))), fmt.num(totals[i])]),
    });
    return true;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const significant = document.getElementById("significant");
    state(significant, "loading");
    load(document.getElementById("summary"), "/analytics/summary", renderSummary, { rows: 2 }).then((result) => {
      if (result && !result.ok) window.QW.errorState(significant, result);
    });
    load(document.getElementById("recent"), "/events", (data, el) => {
      if (!data.results.length) return false;
      el.append(eventList(data.results));
      return true;
    }, { params: { page_size: 8 }, empty: "No events have been ingested yet. The first sync runs within a few minutes of start-up." });
    load(document.getElementById("activity"), "/analytics/timeseries", renderActivity, { params: { days: 14 }, empty: "No activity recorded in the last 14 days." });
    renderMap();
  });
})();
