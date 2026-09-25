/* Research Lab (FR-13): freeze snapshots, inspect manifests, download, delete. */
(function () {
  "use strict";
  const { h, api, load, state, fmt, errorState, announce, showFieldErrors, formToParams } = window.QW;
  const $ = (id) => document.getElementById(id);

  function downloads(id) {
    const base = `/api/v1/research/snapshots/${encodeURIComponent(id)}/export`;
    return h("span", { class: "d-inline-flex gap-1 flex-wrap" },
      h("a", { class: "btn btn-sm btn-outline-primary", href: `${base}?format=csv` }, "CSV"),
      h("a", { class: "btn btn-sm btn-outline-primary", href: `${base}?format=json` }, "JSON"),
      h("a", { class: "btn btn-sm btn-primary", href: `${base}?format=zip` }, "ZIP + manifest"));
  }

  function manifestView(m) {
    return h("div", {},
      h("dl", { class: "qw-kv mb-2" },
        h("dt", {}, "Snapshot id"), h("dd", {}, h("code", {}, m.snapshot_id)),
        h("dt", {}, "Query"), h("dd", {}, m.query_definition.summary),
        h("dt", {}, "Rows"), h("dd", {}, fmt.num(m.row_count)),
        h("dt", {}, "Content SHA-256"), h("dd", {}, h("code", { class: "text-break" }, m.content_sha256)),
        h("dt", {}, "Checksum method"), h("dd", {}, m.content_sha256_definition),
        h("dt", {}, "Application"), h("dd", {}, m.application_version),
        h("dt", {}, "Schemas"), h("dd", {}, `database v${m.database_schema_version} · event document v${m.event_document_version} · export v${m.export_schema_version} · revision policy v${m.revision_policy_version}`),
        h("dt", {}, "Attribution"), h("dd", {}, m.attribution)),
      h("details", {}, h("summary", { class: "small" }, "Full manifest (JSON)"), h("pre", { class: "qw-pre mt-2" }, JSON.stringify(m, null, 2))));
  }

  function loadSnapshots() {
    load($("snapshots"), "/research/snapshots", (data, el) => {
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled mb-0" }, data.results.map((s) => {
        const detail = h("div", { class: "mt-2", hidden: true });
        const toggle = h("button", { type: "button", class: "btn btn-sm btn-link px-0", "aria-expanded": "false" }, "Show manifest");
        toggle.addEventListener("click", () => {
          const open = detail.hidden;
          detail.hidden = !open;
          toggle.setAttribute("aria-expanded", String(open));
          toggle.textContent = open ? "Hide manifest" : "Show manifest";
          if (open && !detail.dataset.loaded) {
            detail.dataset.loaded = "1";
            load(detail, `/research/snapshots/${encodeURIComponent(s.id)}`, (d) => { detail.append(manifestView(d.manifest)); });
          }
        });
        return h("li", { class: "py-2 border-bottom" },
          h("div", { class: "d-flex flex-wrap justify-content-between gap-2" },
            h("div", {},
              h("div", { class: "fw-semibold" }, s.title),
              h("div", { class: "small text-body-secondary" }, `${fmt.num(s.row_count)} events · ${s.query_definition.summary} · frozen ${fmt.utc(s.created_at)}`),
              s.notes ? h("div", { class: "small" }, s.notes) : null),
            h("div", { class: "d-flex gap-1 align-items-start" }, downloads(s.id),
              h("button", { type: "button", class: "btn btn-sm btn-outline-danger", "aria-label": `Delete snapshot ${s.title}`, onclick: () => remove(s) }, h("i", { class: "bi bi-trash", "aria-hidden": "true" })))),
          toggle, detail);
      })));
      return true;
    }, { empty: "No snapshots yet. Define a dataset with the form on this page, or export a query from the Explorer.", rows: 3 });
  }

  async function remove(s) {
    if (!window.confirm(`Delete the snapshot "${s.title}"? Downloads already made remain verifiable by their checksum.`)) return;
    const r = await api(`/research/snapshots/${encodeURIComponent(s.id)}`, { method: "DELETE" });
    if (r.ok) { announce(`Deleted ${s.title}`); loadSnapshots(); } else window.alert(r.error.message);
  }

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const out = $("snapshot-status");
    const values = formToParams(form);
    const { title, notes, ...filters } = values;
    if (!title) return showFieldErrors(form, { details: { fields: { title: "Enter a title." } } });
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    state(out, "loading", { message: "Freezing snapshot…", rows: 1 });
    const r = await api("/research/snapshots", { method: "POST", body: { title, notes: notes || "", filters } });
    button.disabled = false;
    if (!r.ok) {
      if (r.status === 400) showFieldErrors(form, r.error);
      return errorState(out, r, null, { throttled: "Snapshot limit reached for this hour. Please try again later." });
    }
    showFieldErrors(form, null);
    form.reset();
    out.replaceChildren(h("div", { class: "alert alert-success py-2 mb-0", role: "status" }, `Frozen “${r.data.title}” with ${fmt.num(r.data.row_count)} events.`));
    loadSnapshots();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("snapshot-form").addEventListener("submit", submit);
    loadSnapshots();
  });
})();
