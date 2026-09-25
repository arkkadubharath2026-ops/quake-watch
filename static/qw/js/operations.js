/* Operations (FR-14, staff): overview, runs, dead letters, audit, diagnostics, admin actions. */
(function () {
  "use strict";
  const { h, api, load, fmt, errorState, announce, showFieldErrors, formToParams, time } = window.QW;
  const $ = (id) => document.getElementById(id);
  let runsPage = 1;

  const STATUS_CLASS = { succeeded: "text-bg-success", partial: "text-bg-warning", failed: "text-bg-danger", running: "text-bg-info", queued: "text-bg-secondary" };
  const OUTCOME_CLASS = { ok: "text-bg-success", requested: "text-bg-secondary", failed: "text-bg-danger", denied: "text-bg-danger" };
  const statusBadge = (s) => h("span", { class: `badge ${STATUS_CLASS[s] || "text-bg-secondary"}` }, s);

  function table(columns, rows) {
    return h("div", { class: "qw-table-wrap" }, h("table", { class: "table table-sm qw-table align-middle" },
      h("thead", {}, h("tr", {}, columns.map((c) => h("th", { scope: "col", class: c.num ? "num" : null }, c.label || c)))),
      h("tbody", {}, rows)));
  }

  /* ---------------------------------------------------------------- overview */
  function renderOverview(o, el) {
    const f = o.freshness;
    const tile = (label, value, note) => h("div", { class: "col-6 col-md-3" }, h("div", { class: "qw-card" },
      h("div", { class: "qw-stat" }, value), h("div", { class: "qw-stat-label" }, label), note ? h("div", { class: "small" }, note) : null));
    const c = o.collections;
    const failed24 = o.runs_24h.reduce((s, r) => s + (r.by_status.failed || 0), 0);
    el.append(h("div", { class: "row g-3" },
      tile("Freshness", h("span", { class: "qw-freshness", "data-status": f.status }, h("span", { class: "qw-dot", "aria-hidden": "true" }), f.status), f.last_success_at ? ["last success ", time(f.last_success_at)] : "no successful sync"),
      tile("Events stored", fmt.num(c.events), `${fmt.num(c.event_revisions)} revisions`),
      tile("Failed runs, 24 h", fmt.num(failed24), `circuit ${f.circuit.status}`),
      tile("Open dead letters", fmt.num(c.dead_letters), `${fmt.num(c.raw_payloads)} raw payloads retained`)),
      h("div", { class: "qw-card mt-3" },
        h("h2", { class: "h3" }, "Run statistics (last 24 hours)"),
        o.runs_24h.length
          ? table(["Kind", { label: "Runs", num: true }, "By status", { label: "p50", num: true }, { label: "p95", num: true }],
            o.runs_24h.map((r) => h("tr", {}, h("td", {}, r.kind), h("td", { class: "num" }, fmt.num(r.total)),
              h("td", {}, Object.entries(r.by_status).map(([s, n]) => [statusBadge(`${s} ${n}`), " "])),
              h("td", { class: "num" }, `${fmt.num(Math.round(r.p50_ms))} ms`), h("td", { class: "num" }, `${fmt.num(Math.round(r.p95_ms))} ms`))))
          : h("p", { class: "mb-0" }, "No runs in the last 24 hours — is the worker running?"),
        h("details", { class: "mt-2 small" }, h("summary", {}, "Collection counts"),
          table(["Collection", { label: "Documents", num: true }], Object.entries(c).map(([k, v]) => h("tr", {}, h("td", {}, h("code", {}, k)), h("td", { class: "num" }, fmt.num(v))))))));
    return true;
  }

  /* ---------------------------------------------------------------- runs */
  function loadRuns() {
    const params = { ...formToParams($("runs-filter")), page: runsPage, page_size: 15 };
    load($("runs"), "/operations/runs", (data, el) => {
      renderPager(data);
      if (!data.results.length) return false;
      el.append(table(["Started", "Kind", "Status", { label: "Fetched", num: true }, { label: "New", num: true }, { label: "Revised", num: true }, { label: "Failed", num: true }, { label: "Duration", num: true }],
        data.results.map((r) => {
          const c = r.counts || {};
          return h("tr", {},
            h("td", {}, fmt.utc(r.started_at)), h("td", {}, r.kind), h("td", {}, statusBadge(r.status),
              r.error ? h("div", { class: "small text-danger text-break" }, r.error.message || r.error.type || String(r.error)) : null),
            h("td", { class: "num" }, fmt.num(c.fetched)), h("td", { class: "num" }, fmt.num(c.inserted)),
            h("td", { class: "num" }, fmt.num(c.revised)), h("td", { class: "num" }, fmt.num(c.failed)),
            h("td", { class: "num" }, r.duration_ms === null || r.duration_ms === undefined ? "—" : `${fmt.num(Math.round(r.duration_ms))} ms`));
        })));
      return true;
    }, { params, empty: "No runs match these filters.", rows: 6 });
  }

  function renderPager(data) {
    const pager = $("runs-pager");
    pager.replaceChildren();
    if (data.total_pages <= 1) return;
    const btn = (label, page, disabled) => h("li", { class: `page-item${disabled ? " disabled" : ""}` },
      h("button", { type: "button", class: "page-link", disabled, onclick: () => { runsPage = page; loadRuns(); } }, label));
    pager.append(h("ul", { class: "pagination pagination-sm mb-0" }, btn("Newer", data.page - 1, data.page === 1),
      h("li", { class: "page-item disabled" }, h("span", { class: "page-link" }, `Page ${data.page} of ${data.total_pages}`)),
      btn("Older", data.page + 1, data.page === data.total_pages)));
  }

  /* ---------------------------------------------------------------- dead letters, audit, jobs */
  function loadDeadLetters() {
    load($("dead-letters"), "/operations/dead-letters", (data, el) => {
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled small mb-0" }, data.results.map((d) => h("li", { class: "py-2 border-bottom" },
        h("div", { class: "d-flex justify-content-between gap-2" },
          h("div", {}, h("code", {}, d.source_event_id || d.payload_hash || d._key), ` · ${d.reason} · failed ${d.retry_count}× · last `, time(d.last_failure_at)),
          h("button", { type: "button", class: "btn btn-sm btn-outline-primary", "aria-label": `Retry ${d.source_event_id || d._key}`, onclick: () => retry(d._key) }, "Retry")),
        d.detail ? h("div", { class: "text-danger text-break" }, typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail)) : null))));
      return true;
    }, { params: { page_size: 20 }, empty: "No unresolved dead letters. Records that fail validation or storage appear here.", rows: 2 });
  }

  function loadAudit() {
    load($("audit"), "/operations/audit", (data, el) => {
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled small mb-0" }, data.results.map((a) => h("li", { class: "py-1 border-bottom" },
        h("div", {}, h("code", {}, a.action), " ", h("span", { class: `badge ${OUTCOME_CLASS[a.outcome] || "text-bg-secondary"}` }, a.outcome)),
        h("div", { class: "text-body-secondary" }, `${a.actor_username || "system"} · `, time(a.at), a.target ? ` · ${a.target}` : "")))));
      return true;
    }, { params: { page_size: 15 }, empty: "No audit entries yet.", rows: 3 });
  }

  function loadJobs() {
    load($("jobs"), "/operations/backfill", (data, el) => {
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled small mb-0" }, data.results.slice(0, 8).map((j) => h("li", { class: "py-1 border-bottom" },
        statusBadge(j.status), " ", `${(j.start || "").slice(0, 10)} → ${(j.end || "").slice(0, 10)} · M${j.min_magnitude ?? "any"}+ · ${fmt.num(j.windows_completed)} windows done`,
        j.last_error ? h("div", { class: "text-danger text-break" }, j.last_error.message || j.last_error.code) : null,
        h("div", { class: "text-body-secondary" }, `${j.requested_by || ""} · `, time(j.created_at))))));
      return true;
    }, { empty: "No backfill jobs yet.", rows: 2 });
  }

  function loadDiagnostics() {
    load($("diagnostics"), "/operations/diagnostics", (data, el) => {
      const bad = data.queries.filter((q) => !q.uses_expected);
      el.append(h("p", { class: `small ${bad.length ? "text-danger" : ""}` },
        bad.length ? `${bad.length} of ${data.queries.length} queries do not use their expected index.` : `All ${data.queries.length} named queries use their expected indexes.`),
        table(["Query", "Category", "Indexes used", { label: "Est. cost", num: true }, "OK"],
          data.queries.map((q) => h("tr", {},
            h("td", {}, h("code", {}, q.name), h("div", { class: "small text-body-secondary" }, q.question)),
            h("td", {}, q.category), h("td", { class: "small" }, q.indexes_used.join(", ") || "none"),
            h("td", { class: "num" }, fmt.num(q.estimated_cost)),
            h("td", {}, q.uses_expected ? h("span", { class: "text-success" }, h("i", { class: "bi bi-check-circle", "aria-hidden": "true" }), h("span", { class: "visually-hidden" }, "uses expected index"))
              : h("span", { class: "text-danger" }, h("i", { class: "bi bi-x-circle", "aria-hidden": "true" }), " not using ", q.expected_indexes.join(" or ")))))));
      return true;
    }, { rows: 5 });
  }

  /* ---------------------------------------------------------------- actions */
  function actionResult(result, okMessage) {
    const out = $("action-status");
    if (!result.ok) return errorState(out, result, null, { throttled: "Admin action limit reached; try again later." });
    out.replaceChildren(h("div", { class: "alert alert-success py-2 mb-0", role: "status" }, okMessage));
    announce(okMessage);
    window.setTimeout(() => { loadRuns(); loadAudit(); loadJobs(); loadDeadLetters(); }, 2000);
  }

  async function syncNow() {
    const button = $("sync-now");
    button.disabled = true;
    const r = await api("/operations/sync", { method: "POST", body: {} });
    button.disabled = false;
    actionResult(r, r.ok ? `Sync of ${r.data.feed} queued.` : "");
  }

  async function backfill(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = formToParams(form);
    const r = await api("/operations/backfill", { method: "POST", body: values });
    if (!r.ok && r.status === 400) showFieldErrors(form, r.error);
    else showFieldErrors(form, null);
    actionResult(r, r.ok ? `Backfill job ${r.data.job_id.slice(0, 8)} queued.` : "");
  }

  async function retry(key) {
    const r = await api(`/operations/dead-letters/${encodeURIComponent(key)}/retry`, { method: "POST", body: {} });
    actionResult(r, r.ok ? `Retry result: ${r.data.outcome}.` : "");
  }

  document.addEventListener("DOMContentLoaded", () => {
    load($("overview"), "/operations/overview", renderOverview, { rows: 4 });
    $("runs-filter").addEventListener("change", () => { runsPage = 1; loadRuns(); });
    $("runs-filter").addEventListener("submit", (e) => e.preventDefault());
    $("sync-now").addEventListener("click", syncNow);
    $("backfill-form").addEventListener("submit", backfill);
    loadRuns(); loadDeadLetters(); loadAudit(); loadJobs(); loadDiagnostics();
  });
})();
