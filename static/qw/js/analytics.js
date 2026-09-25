/* Analytics (FR-09): one request per API section; each chart has a summary and a data table. */
(function () {
  "use strict";
  const { h, fmt, magBadge, eventLink, time, api, errorState } = window.QW;
  const $ = (id) => document.getElementById(id);

  function stats(items) {
    return h("div", { class: "row g-2" }, items.map(([label, value, note]) =>
      h("div", { class: "col-6" }, h("div", { class: "border rounded p-2 h-100" },
        h("div", { class: "qw-stat" }, value), h("div", { class: "qw-stat-label" }, label), note ? h("div", { class: "small" }, note) : null))));
  }

  function peak(labels, values) {
    const max = Math.max(...values);
    return { label: labels[values.indexOf(max)], value: max };
  }

  /* ---------------------------------------------------------------- sections */
  function timeseries(data) {
    const m = data.by_month;
    const mEl = $("monthly");
    if (!m.length) window.QW.state(mEl, "empty", { message: "No events in this window." });
    else {
      const labels = m.map((r) => r.month), values = m.map((r) => r.count);
      const p = peak(labels, values);
      QWCharts.bar(mEl, {
        labels, values, yTitle: "Events", xTitle: "Month",
        summary: `Event counts for ${labels.length} month(s); highest ${p.label} with ${fmt.num(p.value)} events.`,
      });
      mEl.querySelector("details").append(QWCharts.table(["Month", "Events", "Mean M", "Max M", "M4.5+"],
        m.map((r) => [r.month, fmt.num(r.count), fmt.mag(r.avg_magnitude), fmt.mag(r.max_magnitude), fmt.num(r.m45_plus)])));
      mEl.querySelector("details .qw-table-wrap").remove();
    }
    const w = data.significant_by_week;
    const wEl = $("weekly");
    if (!w.length) window.QW.state(wEl, "empty", { message: "No significant events in this window." });
    else {
      QWCharts.bar(wEl, {
        labels: w.map((r) => r.week), values: w.map((r) => r.count), yTitle: "Significant events", xTitle: "ISO week",
        summary: `Significant events (significance ≥ 600, PAGER alert or tsunami flag) in ${w.length} ISO weeks; total ${fmt.num(w.reduce((s, r) => s + r.count, 0))}.`,
      });
    }
  }

  function distributions(data) {
    const mag = data.magnitude;
    if (mag.length) {
      const labels = mag.map((r) => `${r.bin.toFixed(1)}–${(r.bin + 0.5).toFixed(1)}`), values = mag.map((r) => r.count);
      const p = peak(labels, values);
      QWCharts.bar($("mag-hist"), { labels, values, yTitle: "Events", xTitle: "Magnitude", summary: `Magnitude histogram; most common bin ${p.label} (${fmt.num(p.value)} events).` });
    } else window.QW.state($("mag-hist"), "empty");

    const depth = data.depth;
    if (depth.length) {
      const labels = depth.map((r) => `${r.bin}–${r.bin + 10}`), values = depth.map((r) => r.count);
      const p = peak(labels, values);
      QWCharts.bar($("depth-hist"), { labels, values, yTitle: "Events", xTitle: "Depth (km)", summary: `Depth histogram; most common bin ${p.label} km (${fmt.num(p.value)} events). Shallow < 70 km, intermediate 70–300 km, deep > 300 km.` });
    } else window.QW.state($("depth-hist"), "empty");

    const pts = data.magnitude_depth;
    if (pts.length) {
      QWCharts.figure($("scatter"), {
        summary: `${fmt.num(pts.length)} events plotted by magnitude (x) and depth (y, increasing downward).`,
        config: {
          type: "scatter",
          data: { datasets: [{ label: "Events", data: pts.map(([m, d]) => ({ x: m, y: d })), backgroundColor: QWCharts.series(), qwToken: "--qw-series-1", pointRadius: 3, pointHoverRadius: 6 }] },
          options: {
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `M ${fmt.mag(c.parsed.x)}, depth ${fmt.depth(c.parsed.y)}` } } },
            scales: { x: { title: { display: true, text: "Magnitude" } }, y: { reverse: true, title: { display: true, text: "Depth (km)" } } },
          },
        },
        columns: ["Magnitude", "Depth (km)"],
        rows: pts.slice(0, 200).map(([m, d]) => [fmt.mag(m), fmt.depth(d)]),
      });
      if (pts.length > 200) $("scatter").querySelector("details").append(window.QW.partialNotice(`Table shows the first 200 of ${fmt.num(pts.length)} points; export a research snapshot for the full data.`));
    } else window.QW.state($("scatter"), "empty");

    const st = data.status;
    const total = st.reduce((s, r) => s + r.count, 0);
    $("status").replaceChildren(total
      ? stats(st.map((r) => [r.status, fmt.num(r.count), `${Math.round((100 * r.count) / total)}% of events`]))
      : h("p", {}, "No events in this window."));
  }

  function breakdowns(data) {
    const r = data.regions.slice(0, 15);
    if (r.length) {
      QWCharts.bar($("regions"), {
        labels: r.map((x) => x.region || "Unassigned"), values: r.map((x) => x.count), horizontal: true, yTitle: "Events",
        summary: `Top ${r.length} regions by event count; most active ${r[0].region} (${fmt.num(r[0].count)}).`,
        columns: ["Region", "Events"],
      });
    } else window.QW.state($("regions"), "empty");
    $("networks").replaceChildren(data.networks.length
      ? QWCharts.table(["Network", "Events", "Mean M", "Max M", "Reviewed"],
        data.networks.map((n) => [`${n.name || n.network} (${n.network})`, fmt.num(n.count), fmt.mag(n.avg_magnitude), fmt.mag(n.max_magnitude), fmt.pct(n.reviewed_share)]))
      : h("p", {}, "No events in this window."));
  }

  function revisions(data) {
    const t = data.time_to_reviewed;
    $("ttr").replaceChildren(...(t.count
      ? [stats([
        ["Events reviewed", fmt.num(t.count)],
        ["Origin → review, median", `${fmt.mag(t.origin_p50_hours)} h`],
        ["First seen → review, median", `${fmt.mag(t.first_seen_p50_hours)} h`],
        ["Origin → review, 90th pct", `${fmt.mag(t.origin_p90_hours)} h`],
      ]), h("p", { class: "small text-body-secondary mt-2 mb-0" }, t.definition)]
      : [h("p", { class: "mb-0" }, "No automatic→reviewed transitions observed in this window yet. Only events QuakeWatch first saw as 'automatic' can be measured.")]));

    const f = data.field_frequency;
    if (f.length) {
      QWCharts.bar($("fields"), {
        labels: f.map((x) => x.field), values: f.map((x) => x.count), horizontal: true, yTitle: "Revisions changing the field",
        summary: `Fields changed across ${fmt.num(f.reduce((s, x) => s + x.count, 0))} field changes; most often ${f[0].field}.`, columns: ["Field", "Revisions"],
      });
    } else window.QW.state($("fields"), "empty", { message: "No revisions recorded in this window." });

    const most = data.most_revised;
    $("most-revised").replaceChildren(most.length
      ? h("ul", { class: "list-unstyled mb-0" }, most.map((e) => h("li", { class: "d-flex gap-2 py-1 border-bottom" }, magBadge(e.magnitude),
        h("div", {}, eventLink(e.key, e.place || e.key), h("div", { class: "small text-body-secondary" }, `${e.revision_count} revisions · `, time(e.occurred_at), ` · ${e.status}`)))))
      : h("p", { class: "mb-0" }, "No events have been revised in this window."));

    const mc = data.magnitude_changes;
    $("mag-changes").replaceChildren(mc.length
      ? QWCharts.table(["Event", "Before", "After", "Change"], mc.map((c) => [c.place || c.key, fmt.mag(c.before), fmt.mag(c.after), `${c.delta > 0 ? "+" : ""}${c.delta}`]))
      : h("p", { class: "mb-0" }, "No magnitude change of 0.3 or more in this window."));
  }

  function latency(data) {
    const l = data.first_observation_latency;
    $("latency").replaceChildren(
      l.count
        ? stats([["Events measured", fmt.num(l.count)], ["Median", fmt.duration(l.p50_s)], ["90th percentile", fmt.duration(l.p90_s)], ["99th percentile", fmt.duration(l.p99_s)]])
        : h("p", {}, "No latency measurements yet — they need events that occurred after live monitoring started."),
      h("p", { class: "small text-body-secondary mt-2 mb-0" }, data.definition, l.monitoring_start ? ` Monitoring started ${fmt.utc(l.monitoring_start)}.` : ""));
  }

  /* ---------------------------------------------------------------- loading */
  const SECTIONS = [
    ["timeseries", ["monthly", "weekly"], timeseries],
    ["distributions", ["mag-hist", "depth-hist", "scatter", "status"], distributions],
    ["breakdowns", ["regions", "networks"], breakdowns],
    ["revisions", ["ttr", "fields", "most-revised", "mag-changes"], revisions],
    ["latency", ["latency"], latency],
  ];

  async function loadSection(path, ids, render, days) {
    for (const id of ids) window.QW.state($(id), "loading");
    const result = await api(`/analytics/${path}`, { params: { days } });
    for (const id of ids) $(id).replaceChildren();
    if (!result.ok) {
      for (const id of ids) errorState($(id), result, () => loadSection(path, ids, render, days));
      return;
    }
    render(result.data);
  }

  function run() {
    const days = $("days").value;
    const url = new URL(location.href);
    url.searchParams.set("days", days);
    history.replaceState(null, "", url);
    for (const [path, ids, render] of SECTIONS) loadSection(path, ids, render, days);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const initial = new URLSearchParams(location.search).get("days");
    if (initial && [...$("days").options].some((o) => o.value === initial)) $("days").value = initial;
    $("days").addEventListener("change", run);
    $("window-form").addEventListener("submit", (e) => e.preventDefault());
    run();
  });
})();
