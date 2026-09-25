/* Alerts (FR-11): rule CRUD with preview, notification feed with read state. */
(function () {
  "use strict";
  const { h, api, load, fmt, magBadge, time, eventLink, errorState, announce, showFieldErrors, refreshUnread } = window.QW;
  const $ = (id) => document.getElementById(id);
  const FEED_PAGE_SIZE = 20;
  let feedPage = 1;

  /* ---------------------------------------------------------------- form ↔ payload */
  function number(form, name) {
    const raw = form[name].value.trim();
    return raw === "" ? null : Number(raw);
  }

  function payloadFrom(form) {
    const lat = number(form, "lat"), lon = number(form, "lon"), radius = number(form, "radius_km");
    const conditions = {
      minimum_magnitude: number(form, "minimum_magnitude"),
      minimum_depth_km: number(form, "minimum_depth_km"),
      maximum_depth_km: number(form, "maximum_depth_km"),
      alert_levels: [...form.querySelectorAll('input[name="alert_levels"]:checked')].map((c) => c.value),
      tsunami_only: form.tsunami_only.checked,
    };
    if (lat !== null || lon !== null || radius !== null) {
      conditions.center = [lon, lat]; // GeoJSON order, as the API documents
      conditions.radius_km = radius;
    }
    return {
      name: form.name.value.trim(),
      enabled: form.enabled.checked,
      cooldown_minutes: number(form, "cooldown_minutes") ?? 30,
      conditions,
    };
  }

  function fillForm(rule) {
    const form = $("rule-form");
    const c = rule.conditions;
    form.rule_id.value = rule.id;
    form.name.value = rule.name;
    form.minimum_magnitude.value = c.minimum_magnitude ?? "";
    form.minimum_depth_km.value = c.minimum_depth_km ?? "";
    form.maximum_depth_km.value = c.maximum_depth_km ?? "";
    form.lon.value = c.center ? c.center[0] : "";
    form.lat.value = c.center ? c.center[1] : "";
    form.radius_km.value = c.radius_km ?? "";
    for (const box of form.querySelectorAll('input[name="alert_levels"]')) box.checked = c.alert_levels.includes(box.value);
    form.tsunami_only.checked = c.tsunami_only;
    form.cooldown_minutes.value = rule.cooldown_minutes;
    form.enabled.checked = rule.enabled;
    $("rule-form-h").textContent = `Edit rule: ${rule.name}`;
    $("rule-submit").textContent = "Save changes";
    $("rule-cancel").hidden = false;
    form.name.focus();
  }

  function resetForm() {
    const form = $("rule-form");
    form.reset();
    form.rule_id.value = "";
    $("rule-form-h").textContent = "New rule";
    $("rule-submit").textContent = "Create rule";
    $("rule-cancel").hidden = true;
    showFieldErrors(form, null);
    $("rule-form-errors").replaceChildren();
  }

  /** Map API field paths ("conditions.center", "name") onto inputs; the rest go to the summary box. */
  function showRuleErrors(form, error) {
    const fields = (error.details && error.details.fields) || {};
    const mapped = {};
    const general = [];
    for (const [path, message] of Object.entries(fields)) {
      const leaf = path.split(".").pop();
      const target = leaf === "center" ? "lat" : leaf;
      if (form.querySelector(`[name="${CSS.escape(target)}"]`) && target !== "alert_levels") mapped[target] = message;
      else general.push(path === "conditions" || path === "body" ? message : `${path}: ${message}`);
    }
    showFieldErrors(form, { details: { fields: mapped } });
    const box = $("rule-form-errors");
    box.replaceChildren();
    if (general.length || !Object.keys(mapped).length) {
      box.append(h("div", { class: "alert alert-danger py-2", role: "alert" }, general.length ? general.join(" ") : error.message));
    }
  }

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const id = form.rule_id.value;
    const body = payloadFrom(form);
    if (!body.name) return showRuleErrors(form, { message: "", details: { fields: { name: "Enter a name for the rule." } } });
    const button = $("rule-submit");
    button.disabled = true;
    const result = await api(id ? `/alert-rules/${encodeURIComponent(id)}` : "/alert-rules", { method: id ? "PATCH" : "POST", body });
    button.disabled = false;
    if (!result.ok) {
      if (result.status === 400 || result.status === 409) return showRuleErrors(form, result.error);
      return errorState($("rule-form-errors"), result);
    }
    announce(id ? `Rule "${body.name}" updated` : `Rule "${body.name}" created`);
    resetForm();
    loadRules();
    preview(result.data.id, result.data.name);
  }

  /* ---------------------------------------------------------------- rules list */
  function describe(c) {
    const parts = [];
    if (c.minimum_magnitude !== null) parts.push(`M ≥ ${c.minimum_magnitude}`);
    if (c.minimum_depth_km !== null) parts.push(`depth ≥ ${c.minimum_depth_km} km`);
    if (c.maximum_depth_km !== null) parts.push(`depth ≤ ${c.maximum_depth_km} km`);
    if (c.center) parts.push(`within ${fmt.num(c.radius_km)} km of ${c.center[1]}, ${c.center[0]}`);
    if (c.alert_levels.length) parts.push(`PAGER ${c.alert_levels.join("/")}`);
    if (c.tsunami_only) parts.push("tsunami flag");
    return parts.join(" · ");
  }

  function loadRules() {
    load($("rules"), "/alert-rules", (data, el) => {
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled mb-0" }, data.results.map((r) =>
        h("li", { class: "d-flex flex-wrap justify-content-between gap-2 py-2 border-bottom" },
          h("div", {},
            h("div", { class: "fw-semibold" }, r.name, r.enabled ? null : h("span", { class: "badge text-bg-secondary ms-2" }, "paused")),
            h("div", { class: "small text-body-secondary" }, describe(r.conditions), ` · quiet period ${r.cooldown_minutes} min`)),
          h("div", { class: "d-flex gap-1 align-items-start" },
            h("button", { type: "button", class: "btn btn-sm btn-outline-primary", onclick: () => preview(r.id, r.name) }, "Preview"),
            h("button", { type: "button", class: "btn btn-sm btn-outline-secondary", onclick: () => fillForm(r) }, "Edit"),
            h("button", { type: "button", class: "btn btn-sm btn-outline-secondary", "aria-pressed": String(!r.enabled), onclick: () => toggle(r) }, r.enabled ? "Pause" : "Resume"),
            h("button", { type: "button", class: "btn btn-sm btn-outline-danger", "aria-label": `Delete rule ${r.name}`, onclick: () => remove(r) }, h("i", { class: "bi bi-trash", "aria-hidden": "true" })))))));
      return true;
    }, { empty: "No rules yet. Create one with the form — for example, M 5+ within 500 km of a place you care about.", rows: 3 });
  }

  async function toggle(rule) {
    const r = await api(`/alert-rules/${encodeURIComponent(rule.id)}`, { method: "PATCH", body: { enabled: !rule.enabled } });
    if (r.ok) { announce(`Rule ${rule.enabled ? "paused" : "resumed"}`); loadRules(); } else window.alert(r.error.message);
  }

  async function remove(rule) {
    if (!window.confirm(`Delete the rule "${rule.name}"? Its notifications are kept.`)) return;
    const r = await api(`/alert-rules/${encodeURIComponent(rule.id)}`, { method: "DELETE" });
    if (r.ok) { announce(`Deleted ${rule.name}`); $("preview").replaceChildren(); loadRules(); } else window.alert(r.error.message);
  }

  function preview(id, name) {
    const el = $("preview");
    load(el, `/alert-rules/${encodeURIComponent(id)}/preview`, (data) => {
      el.append(h("h3", { class: "h6" }, `Preview: events from the last ${data.window_days} days that “${name}” would match`));
      if (!data.would_match.length) {
        el.append(h("p", { class: "small mb-0" }, "No recent events would have matched. The rule is saved and will be checked against every new event."));
        return true;
      }
      el.append(h("ul", { class: "list-unstyled small mb-0" }, data.would_match.map((m) =>
        h("li", { class: "d-flex gap-2 py-1 border-bottom" }, magBadge(m.event.magnitude),
          h("div", {}, eventLink(m.event.key, m.event.place || m.event.key), " · ", time(m.event.occurred_at),
            h("div", { class: "text-body-secondary" }, m.explanation.reason.join("; ")))))));
      return true;
    }, { rows: 3 });
  }

  /* ---------------------------------------------------------------- feed */
  function loadFeed() {
    load($("feed"), "/alerts/matches", (data, el) => {
      renderFeedPager(data);
      if (!data.results.length) return false;
      el.append(h("ul", { class: "list-unstyled mb-0" }, data.results.map((m) => {
        const e = m.event_snapshot || {};
        const unread = !m.read_at;
        return h("li", { class: `d-flex gap-2 py-2 border-bottom${unread ? "" : " opacity-75"}` },
          magBadge(e.magnitude),
          h("div", { class: "flex-grow-1" },
            h("div", {}, unread ? h("span", { class: "badge text-bg-primary me-1" }, "new") : null,
              eventLink(m.event_key, e.place || m.event_key)),
            h("div", { class: "small text-body-secondary" },
              `Rule “${(m.rule_snapshot || {}).name}” · ${m.trigger === "created" ? "new event" : `updated (${(m.changed_fields || []).join(", ")})`} · matched `, time(m.matched_at),
              m.notify ? "" : " · within quiet period"),
            h("div", { class: "small" }, (m.explanation.reason || []).join("; "))),
          unread ? h("button", { type: "button", class: "btn btn-sm btn-link", onclick: () => markRead(m.id) }, "Mark read") : null);
      })));
      return true;
    }, { params: { page: feedPage, page_size: FEED_PAGE_SIZE, unread: $("unread-only").checked ? "true" : "false" }, empty: "No notifications yet. Matches appear here when new events satisfy one of your rules.", rows: 3 });
  }

  function renderFeedPager(data) {
    const pager = $("feed-pager");
    pager.replaceChildren();
    if (data.total_pages <= 1) return;
    const btn = (label, page, disabled) => h("li", { class: `page-item${disabled ? " disabled" : ""}` },
      h("button", { type: "button", class: "page-link", disabled, onclick: () => { feedPage = page; loadFeed(); } }, label));
    pager.append(h("ul", { class: "pagination pagination-sm mb-0" },
      btn("Newer", data.page - 1, data.page === 1),
      h("li", { class: "page-item disabled" }, h("span", { class: "page-link" }, `Page ${data.page} of ${data.total_pages}`)),
      btn("Older", data.page + 1, data.page === data.total_pages)));
  }

  async function markRead(id) {
    const r = await api("/alerts/matches/read", { method: "POST", body: id ? { id } : {} });
    if (!r.ok) return window.alert(r.error.message);
    announce(id ? "Marked as read" : `Marked ${r.data.marked_read} notifications as read`);
    loadFeed();
    refreshUnread();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("rule-form").addEventListener("submit", submit);
    $("rule-cancel").addEventListener("click", resetForm);
    $("unread-only").addEventListener("change", () => { feedPage = 1; loadFeed(); });
    $("mark-all").addEventListener("click", () => markRead(null));
    loadRules();
    loadFeed();
  });
})();
