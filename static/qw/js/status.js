/* System Status: public freshness + service health. /system/health answers 503 when the
 * database is down, so a failed request is rendered as "down" rather than a generic error. */
(function () {
  "use strict";
  const { h, api, load, state, fmt } = window.QW;
  const $ = (id) => document.getElementById(id);
  const LABEL = { fresh: "Live", degraded: "Degraded", stale: "Stale", unknown: "Unknown" };

  function badge(ok, text) {
    return h("span", { class: `badge ${ok ? "text-bg-success" : "text-bg-danger"}` },
      h("i", { class: `bi bi-${ok ? "check-circle" : "x-circle"}`, "aria-hidden": "true" }), " ", text);
  }

  function renderFreshness(f, el) {
    el.append(
      h("p", { class: "qw-freshness fs-5 mb-2", "data-status": f.status }, h("span", { class: "qw-dot", "aria-hidden": "true" }), h("strong", {}, LABEL[f.status] || f.status), " — ", f.message),
      h("dl", { class: "qw-kv" },
        h("dt", {}, "Last successful sync"), h("dd", {}, f.last_success_at ? [fmt.utc(f.last_success_at), " (", fmt.ago(f.last_success_at), ")"] : "never"),
        h("dt", {}, "USGS feed generated"), h("dd", {}, fmt.utc(f.source_generated_at)),
        h("dt", {}, "Last attempt"), h("dd", {}, f.last_attempt ? `${f.last_attempt.status} at ${fmt.utc(f.last_attempt.started_at)}` : "—",
          f.last_attempt && f.last_attempt.error ? h("div", { class: "small text-danger" }, f.last_attempt.error.message || String(f.last_attempt.error)) : null),
        h("dt", {}, "USGS circuit breaker"), h("dd", {}, f.circuit.status === "closed" ? "closed (normal)" : `${f.circuit.status} after ${f.circuit.consecutive_failures} consecutive failures`)));
    return true;
  }

  async function renderHealth() {
    const el = $("health");
    state(el, "loading");
    const r = await api("/system/health");
    const data = r.ok ? r.data : r.status === 503 ? { status: "degraded", database: "down", cache: "unknown", checked_at: null } : null;
    if (!data) return window.QW.errorState(el, r, renderHealth);
    window.QW.fill(el, h("dl", { class: "qw-kv" },
      h("dt", {}, "Overall"), h("dd", {}, badge(data.status === "ok", data.status === "ok" ? "operational" : "degraded")),
      h("dt", {}, "Database (ArangoDB)"), h("dd", {}, badge(data.database === "up", data.database)),
      h("dt", {}, "Shared state and job queue"), h("dd", {}, badge(data.cache === "up", data.cache)),
      h("dt", {}, "Checked"), h("dd", {}, data.checked_at ? fmt.utc(data.checked_at) : "—")));
  }

  document.addEventListener("DOMContentLoaded", () => {
    load($("freshness"), "/system/freshness", renderFreshness);
    renderHealth();
  });
})();
