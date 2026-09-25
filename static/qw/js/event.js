/* Event Detail (FR-08): locator map + lazily loaded tabs (revisions, products, relationships,
 * provenance). The overview is server-rendered. */
(function () {
  "use strict";
  const { h, api, load, fmt, magBadge, time, eventLink, errorState } = window.QW;

  const event = window.QW.readJsonScript("event-data");
  const base = `/events/${encodeURIComponent(event.key)}`;
  const authenticated = document.body.dataset.authenticated === "true";

  const FIELD_LABELS = {
    magnitude: "Magnitude", magnitude_type: "Magnitude type", depth_km: "Depth (km)", latitude: "Latitude",
    longitude: "Longitude", occurred_at: "Origin time", place: "Place", status: "Review status",
    alert: "PAGER alert", tsunami: "Tsunami flag", mmi: "MMI", cdi: "CDI", products: "Products",
    source_event_id: "Preferred event id", event_type: "Event type",
  };

  function value(v) {
    if (v === null || v === undefined) return "—";
    if (Array.isArray(v)) return v.length ? v.join(", ") : "(none)";
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 10000) / 10000);
    if (typeof v === "boolean") return v ? "yes" : "no";
    return String(v);
  }

  function delta(before, after) {
    if (typeof before !== "number" || typeof after !== "number") return null;
    const d = after - before;
    return `${d > 0 ? "+" : ""}${Math.round(d * 1000) / 1000}`;
  }

  function changeTable(rows, [c1, c2, c3]) {
    return window.QW.scrollRegion("Field changes", h("table", { class: "table table-sm qw-table" },
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Field"), h("th", { scope: "col" }, c1), h("th", { scope: "col" }, c2), h("th", { scope: "col", class: "num" }, c3))),
      h("tbody", {}, rows.map((r) => h("tr", {},
        h("th", { scope: "row" }, FIELD_LABELS[r.field] || r.field),
        h("td", {}, value(r.a)), h("td", {}, value(r.b)), h("td", { class: "num" }, delta(r.a, r.b) || ""))))));
  }

  /* ---------------------------------------------------------------- revisions */
  function renderRevisions(data, el) {
    el.append(h("p", { class: "small text-body-secondary" },
      `QuakeWatch stores a new immutable revision when a tracked field changes beyond its tolerance (revision policy v${data.policy_version}). `,
      `${data.revision_count} revision${data.revision_count === 1 ? "" : "s"} recorded.`));
    if (data.initial_vs_current.length) {
      el.append(h("h2", { class: "h3" }, "First report vs current"),
        changeTable(data.initial_vs_current.map((c) => ({ field: c.field, a: c.initial, b: c.current })), ["First report", "Current", "Change"]));
    } else {
      el.append(h("p", {}, "No tracked field has changed since QuakeWatch first saw this event."));
    }
    el.append(h("h2", { class: "h3 mt-4" }, "Timeline"),
      h("ol", { class: "qw-timeline" }, data.timeline.slice().reverse().map((r) => h("li", {},
        h("div", { class: "fw-semibold" }, `Revision ${r.revision_number} · ${r.kind === "created" ? "first observed" : "updated"}`),
        h("div", { class: "small text-body-secondary mb-1" }, "Observed ", fmt.utc(r.observed_at), " · USGS updated ", fmt.utc(r.source_updated_at)),
        r.changes.length ? changeTable(r.changes.map((c) => ({ field: c.field, a: c.before, b: c.after })), ["Before", "After", "Change"]) : null,
        h("div", { class: "small font-mono text-body-secondary" }, `payload ${r.payload_hash.slice(0, 16)}…`)))));
    return true;
  }

  /* ---------------------------------------------------------------- products */
  function renderProducts(el) {
    el.replaceChildren();
    el.append(h("p", { class: "small text-body-secondary" },
      "Availability of USGS scientific products for this event. QuakeWatch surfaces these products; it does not produce competing impact estimates."),
      h("ul", { class: "list-inline" }, event.products.map((p) => h("li", { class: "list-inline-item mb-2" },
        h("span", { class: `badge ${p.available ? "text-bg-success" : "text-bg-light border"}` },
          h("i", { class: `bi bi-${p.available ? "check-circle" : "dash-circle"}`, "aria-hidden": "true" }), " ", p.label,
          h("span", { class: "visually-hidden" }, p.available ? " available" : " not available"))))));
    const enrichment = event.enrichment;
    const box = h("div", { id: "enrichment" });
    el.append(h("h2", { class: "h3 mt-3" }, "Product details"), box);
    if (enrichment && enrichment.products) {
      box.append(h("p", { class: "small" }, "Fetched from the USGS detail feed ", time(enrichment.fetched_at), "."));
      for (const [code, p] of Object.entries(enrichment.products)) {
        box.append(h("div", { class: "border rounded p-2 mb-2" },
          h("div", { class: "fw-semibold" }, (event.products.find((x) => x.type === code) || {}).label || code),
          h("dl", { class: "qw-kv" },
            h("dt", {}, "Status"), h("dd", {}, value(p.status)),
            h("dt", {}, "Source"), h("dd", {}, value(p.source)),
            h("dt", {}, "Updated"), h("dd", {}, fmt.utc(p.update_time)),
            Object.entries(p.properties || {}).map(([k, v]) => [h("dt", {}, k), h("dd", {}, value(v))]))));
      }
    } else {
      box.append(h("p", {}, enrichment && enrichment.last_error
        ? `The last attempt to fetch product details failed (${enrichment.last_error}).`
        : "Product details have not been fetched from the USGS detail feed yet (important events are fetched automatically)."));
    }
    if (authenticated) {
      const out = h("div", { class: "mt-2", "aria-live": "polite" });
      const button = h("button", { type: "button", class: "btn btn-sm btn-outline-primary" }, h("i", { class: "bi bi-arrow-repeat", "aria-hidden": "true" }), " Refresh from USGS");
      button.addEventListener("click", async () => {
        button.disabled = true;
        const r = await api(`${base}/enrich`, { method: "POST" });
        button.disabled = false;
        if (r.ok) window.QW.fill(out, h("div", { class: "alert alert-success py-1 mb-0", role: "status" }, "Refresh queued. Reload the page in a minute to see updated details."));
        else errorState(out, r, null, { throttled: "Refresh limit reached; try again in a minute." });
      });
      box.append(button, out);
    }
  }

  /* ---------------------------------------------------------------- relationships */
  function renderRelationships(data, el) {
    el.append(h("div", { class: "row g-4" },
      h("div", { class: "col-md-6" },
        h("h2", { class: "h3" }, "Graph neighbours"),
        h("dl", { class: "qw-kv" },
          h("dt", {}, "Region"), h("dd", {}, data.region ? `${data.region.name} (${data.region.kind.replace("_", " ")})` : "—",
            data.region_event_count ? ` · ${fmt.num(data.region_event_count)} events` : ""),
          h("dt", {}, "Network"), h("dd", {}, data.network ? `${data.network.name} (${data.network.code})` : "—")),
        h("h3", { class: "h6 mt-3" }, "Other events in the same region"),
        data.same_region && data.same_region.length ? list(data.same_region) : h("p", { class: "small" }, "No other events in this region.")),
      h("div", { class: "col-md-6" },
        h("h2", { class: "h3" }, `Within ${data.nearby.radius_km} km and ${data.nearby.window_days} days`),
        h("p", { class: "small text-body-secondary" }, data.nearby.note),
        data.nearby.events.length ? list(data.nearby.events, true) : h("p", { class: "small" }, "No nearby events in this window."))));
    return true;
  }

  function list(rows, distance) {
    return h("ul", { class: "list-unstyled small" }, rows.map((e) => h("li", { class: "d-flex gap-2 py-1 border-bottom" },
      magBadge(e.magnitude), h("div", {}, eventLink(e.key, e.place || e.key),
        h("div", { class: "text-body-secondary" }, time(e.occurred_at), distance && e.distance_km !== undefined ? ` · ${fmt.num(e.distance_km)} km away` : "")))));
  }

  /* ---------------------------------------------------------------- provenance */
  function renderProvenance(data, el) {
    el.append(
      h("p", { class: "small" }, data.attribution),
      h("dl", { class: "qw-kv mb-3" },
        h("dt", {}, "Source"), h("dd", {}, data.source),
        h("dt", {}, "Preferred id"), h("dd", {}, h("code", {}, data.source_event_id)),
        h("dt", {}, "Associated ids"), h("dd", {}, data.associated_ids.length ? data.associated_ids.join(", ") : "—"),
        h("dt", {}, "Current payload SHA-256"), h("dd", {}, h("code", {}, data.current_payload.payload_hash))),
      h("h2", { class: "h3" }, "Ingestion runs that touched this event"),
      window.QW.scrollRegion("Ingestion runs", h("table", { class: "table table-sm qw-table" },
        h("thead", {}, h("tr", {}, ["Run", "Kind", "Started", "Status", "Requests"].map((c) => h("th", { scope: "col" }, c)))),
        h("tbody", {}, data.ingestion_runs.map((r) => h("tr", {},
          h("td", {}, h("code", {}, r._key.slice(0, 12))), h("td", {}, r.kind), h("td", {}, fmt.utc(r.started_at)), h("td", {}, r.status),
          h("td", {}, (r.requests || []).map((q) => h("div", { class: "small text-break" }, `${q.status_code ?? "—"} · ${q.url}`)))))))),
      h("h2", { class: "h3 mt-3" }, "Raw USGS payload (current revision)"),
      data.current_payload.retained
        ? h("pre", { class: "qw-pre", tabindex: "0", role: "region", "aria-label": "Raw source payload (JSON)" }, JSON.stringify(data.current_payload.payload, null, 2))
        : h("p", {}, "The raw payload for this revision is no longer retained (payload retention window elapsed); its hash is recorded above."));
    return true;
  }

  /* ---------------------------------------------------------------- wiring */
  const loaders = {
    "pane-revisions": () => load(document.getElementById("revisions"), `${base}/revisions`, renderRevisions),
    "pane-products": () => renderProducts(document.getElementById("products")),
    "pane-relationships": () => load(document.getElementById("relationships"), `${base}/relationships`, renderRelationships),
    "pane-provenance": () => load(document.getElementById("provenance"), `${base}/provenance`, renderProvenance),
  };
  const loaded = new Set();

  function activate(paneId) {
    if (loaders[paneId] && !loaded.has(paneId)) {
      loaded.add(paneId);
      loaders[paneId]();
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const s = event.source;
    if (s.latitude !== null && s.longitude !== null) {
      const map = QWMap.create(document.getElementById("event-map"), { center: [s.latitude, s.longitude], zoom: 6, legend: false, scrollWheelZoom: false });
      L.circleMarker([s.latitude, s.longitude], { radius: QWMap.radius(s.magnitude), color: "#222", weight: 1, fillColor: QWMap.color(s.magnitude), fillOpacity: 0.9 }).addTo(map);
    }
    for (const tab of document.querySelectorAll('#event-tabs [data-bs-toggle="tab"]')) {
      tab.addEventListener("shown.bs.tab", () => {
        const pane = tab.getAttribute("aria-controls");
        activate(pane);
        history.replaceState(null, "", `#${pane.replace("pane-", "")}`);
      });
    }
    const hash = location.hash.slice(1);
    if (hash && document.getElementById(`tab-${hash}`)) bootstrap.Tab.getOrCreateInstance(document.getElementById(`tab-${hash}`)).show();
  });
})();
