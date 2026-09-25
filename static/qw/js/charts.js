/* Chart.js wrappers. Each chart is a <figure> with: a canvas (role="img" + summary label), a
 * visible caption, and a collapsible data table — the accessible equivalent of the chart. */
(function () {
  "use strict";
  const { h, fmt } = window.QW;
  const charts = new Set();

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function themeDefaults() {
    const dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
    Chart.defaults.color = dark ? "#c9d1d9" : "#3d4852";
    Chart.defaults.borderColor = dark ? "rgba(240,246,252,0.12)" : "rgba(0,0,0,0.1)";
    Chart.defaults.font.family = cssVar("--qw-font-sans") || "system-ui";
  }

  const PALETTE = ["--qw-mag-0", "--qw-mag-1", "--qw-mag-2", "--qw-mag-3", "--qw-mag-4"];
  function palette(i) {
    return cssVar(PALETTE[i % PALETTE.length]);
  }

  function table(columns, rows) {
    return h("div", { class: "qw-table-wrap" },
      h("table", { class: "table table-sm qw-table" },
        h("thead", {}, h("tr", {}, columns.map((c, i) => h("th", { scope: "col", class: i ? "num" : null }, c)))),
        h("tbody", {}, rows.map((r) => h("tr", {}, r.map((v, i) => (i ? h("td", { class: "num" }, v) : h("th", { scope: "row" }, v))))))));
  }

  /**
   * figure(container, {summary, config, columns, rows})
   *   summary: one-sentence description used as the canvas label and caption.
   *   columns/rows: the data table (first column = row header).
   */
  function figure(container, { summary, config, columns, rows }) {
    for (const old of charts) {
      if (!old.canvas.isConnected) { old.destroy(); charts.delete(old); }
    }
    themeDefaults();
    const canvas = h("canvas", { role: "img", "aria-label": summary });
    const fig = h("figure", { class: "mb-0" },
      h("div", { class: "qw-chart" }, canvas),
      h("figcaption", { class: "small text-body-secondary mt-2" }, summary),
      h("details", { class: "small mt-1" }, h("summary", {}, "Show data table"), table(columns, rows)));
    container.append(fig);
    config.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: matchMedia("(prefers-reduced-motion: reduce)").matches ? false : undefined }, config.options || {});
    const chart = new Chart(canvas, config);
    charts.add(chart);
    return chart;
  }

  document.addEventListener("qw:theme", () => {
    themeDefaults();
    for (const chart of charts) {
      // datasets carry the CSS token they were coloured from, so dark mode gets its own steps
      for (const ds of chart.data.datasets) {
        if (ds.qwToken) ds.backgroundColor = cssVar(ds.qwToken);
        if (ds.borderColor && ds.qwGap) ds.borderColor = surface();
      }
      chart.update("none");
    }
  });

  function series() {
    return cssVar("--qw-series-1");
  }

  function surface() {
    return cssVar("--qw-surface") || "#fff";
  }

  /** Single-series bar chart: one colour, no legend (the heading names the series). */
  function bar(container, { labels, values, yTitle, xTitle, summary, columns, horizontal = false, format = fmt.num }) {
    return figure(container, {
      summary,
      config: {
        type: "bar",
        data: { labels, datasets: [{ label: yTitle, data: values, backgroundColor: series(), qwToken: "--qw-series-1", borderRadius: 4, borderSkipped: "start", maxBarThickness: 36 }] },
        options: {
          indexAxis: horizontal ? "y" : "x",
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${yTitle}: ${format(ctx.parsed[horizontal ? "x" : "y"])}` } } },
          scales: {
            [horizontal ? "x" : "y"]: { beginAtZero: true, title: { display: Boolean(yTitle), text: yTitle }, grid: { color: Chart.defaults.borderColor } },
            [horizontal ? "y" : "x"]: { title: { display: Boolean(xTitle), text: xTitle }, grid: { display: false } },
          },
        },
      },
      columns: columns || [xTitle || "", yTitle],
      rows: labels.map((l, i) => [String(l), format(values[i])]),
    });
  }

  window.QWCharts = { figure, palette, table, fmt, bar, series, surface, cssVar };
})();
