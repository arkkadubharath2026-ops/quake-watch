/* QuakeWatch browser runtime: API client, UI states, safe DOM builder, formatting, freshness.
 *
 * Every data-driven region goes through QW.load(), which renders exactly one of the standard
 * states: loading, success, empty, partial, validation error, permission error, not found,
 * rate limited, server failure or network failure. Data is inserted with textContent only
 * (QW.h) — never innerHTML — so API content cannot inject markup.
 */
(function () {
  "use strict";

  const API = "/api/v1";

  /* ------------------------------------------------------------ DOM builder */
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
      else el.setAttribute(key, value === true ? "" : String(value));
    }
    append(el, children);
    return el;
  }

  function append(el, children) {
    for (const child of [children].flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  function icon(name) {
    return h("i", { class: `bi bi-${name}`, "aria-hidden": "true" });
  }

  function clear(el) {
    el.replaceChildren();
    return el;
  }

  /** Horizontally scrollable wrapper for wide tables: focusable and named, so keyboard users can
   * scroll it (WCAG 2.1.1; axe scrollable-region-focusable). */
  function scrollRegion(label, child) {
    return h("div", { class: "qw-table-wrap", tabindex: "0", role: "region", "aria-label": label }, child);
  }

  /** Replace a region's content after a manual loading state; ends its aria-busy period. */
  function fill(el, ...children) {
    clear(el).removeAttribute("aria-busy");
    append(el, children);
    return el;
  }

  /* ------------------------------------------------------------ API client */
  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function query(params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value === null || value === undefined || value === "") continue;
      search.set(key, value);
    }
    const text = search.toString();
    return text ? `?${text}` : "";
  }

  /** Returns {ok, status, data, error}; never throws. error = {code, message, details}. */
  async function api(path, { method = "GET", params, body, signal } = {}) {
    const headers = { Accept: "application/json" };
    if (method !== "GET") {
      headers["X-CSRFToken"] = csrfToken();
      if (body !== undefined) headers["Content-Type"] = "application/json";
    }
    let response;
    try {
      response = await fetch(`${API}${path}${query(params)}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: "same-origin",
        signal,
      });
    } catch (err) {
      if (err && err.name === "AbortError") return { ok: false, status: 0, aborted: true, error: null };
      return { ok: false, status: 0, error: { code: "network_error", message: "Could not reach QuakeWatch. Check your connection and try again." } };
    }
    if (response.status === 204) return { ok: true, status: 204, data: null };
    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      data = null;
    }
    if (response.ok) return { ok: true, status: response.status, data };
    const error = (data && data.error) || { code: "http_error", message: `Request failed (${response.status}).` };
    return { ok: false, status: response.status, error };
  }

  /* ------------------------------------------------------------ UI states */
  const STATE_COPY = {
    empty: ["inbox", "Nothing to show yet."],
    validation: ["exclamation-triangle", "Some inputs are not valid."],
    permission: ["lock", "You don't have access to this."],
    auth: ["person-lock", "Please log in to see this."],
    notfound: ["question-circle", "Not found."],
    throttled: ["hourglass-split", "Too many requests — please wait a moment and try again."],
    server: ["cloud-slash", "Something went wrong on our side. Please try again."],
    network: ["wifi-off", "Could not reach QuakeWatch. Check your connection and try again."],
  };

  function kindFor(result) {
    if (result.status === 0) return "network";
    if (result.status === 400) return "validation";
    if (result.status === 401) return "auth";
    if (result.status === 403) return document.body.dataset.authenticated === "true" ? "permission" : "auth";
    if (result.status === 404) return "notfound";
    if (result.status === 429) return "throttled";
    return "server";
  }

  function validationDetails(error) {
    const fields = error && error.details && error.details.fields;
    if (!fields || typeof fields !== "object") return null;
    return h("ul", { class: "text-start small mb-0" },
      Object.entries(fields).map(([field, msg]) => h("li", {}, h("code", {}, field), ": ", String(msg))));
  }

  /** Render a non-success state into `el`. opts: {message, retry, extra} */
  function state(el, kind, opts = {}) {
    if (kind === "loading") {
      clear(el).setAttribute("aria-busy", "true");
      const rows = opts.rows || 3;
      append(el, h("div", { class: "qw-state", "data-kind": "loading", role: "status" },
        h("span", { class: "visually-hidden" }, opts.message || "Loading…"),
        h("div", { class: "w-100", "aria-hidden": "true" }, Array.from({ length: rows }, () => h("span", { class: "qw-skeleton" })))));
      return el;
    }
    el.removeAttribute("aria-busy");
    const [iconName, fallback] = STATE_COPY[kind] || STATE_COPY.server;
    const box = h("div", {
      class: "qw-state",
      "data-kind": kind === "server" || kind === "network" ? "server" : kind === "empty" ? "empty" : "error",
      role: kind === "empty" ? "status" : "alert",
    }, icon(iconName), h("p", { class: "mb-0" }, opts.message || fallback));
    if (opts.extra) append(box, [opts.extra]);
    if (kind === "auth") append(box, [h("a", { class: "btn btn-sm btn-primary", href: loginUrl() }, "Log in")]);
    if (opts.retry && ["server", "network", "throttled"].includes(kind)) {
      append(box, [h("button", { type: "button", class: "btn btn-sm btn-outline-secondary", onclick: opts.retry }, icon("arrow-clockwise"), " Retry")]);
    }
    if (opts.correlationId) append(box, [h("small", { class: "font-mono" }, `Reference: ${opts.correlationId}`)]);
    clear(el).append(box);
    return el;
  }

  function errorState(el, result, retry, overrides = {}) {
    const kind = kindFor(result);
    const error = result.error || {};
    const message = overrides[kind] || (kind === "validation" || kind === "notfound" ? error.message : undefined);
    return state(el, kind, {
      message,
      retry,
      extra: kind === "validation" ? validationDetails(error) : null,
      correlationId: kind === "server" ? error.correlation_id : null,
    });
  }

  function partialNotice(message) {
    return h("div", { class: "qw-state alert alert-warning py-1 px-2 mb-2", "data-kind": "partial", role: "status" },
      icon("exclamation-circle"), h("span", { class: "small" }, message));
  }

  /**
   * Load `path` into `el`: loading → render(data) | empty | error.
   * render(data, el) fills the element and returns false if the data is empty.
   * opts: {params, empty, rows, messages, signal}
   */
  async function load(el, path, render, opts = {}) {
    if (!el) return null;
    state(el, "loading", { rows: opts.rows });
    const retry = () => load(el, path, render, opts);
    const result = await api(path, { params: opts.params, signal: opts.signal });
    if (result.aborted) return null;
    if (!result.ok) {
      errorState(el, result, retry, opts.messages || {});
      return result;
    }
    clear(el).removeAttribute("aria-busy");
    const rendered = render(result.data, el);
    if (rendered === false) state(el, "empty", { message: opts.empty });
    return result;
  }

  function loginUrl() {
    return `/accounts/login/?next=${encodeURIComponent(location.pathname + location.search)}`;
  }

  /* ------------------------------------------------------------ formatting */
  const nf1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  const nf = new Intl.NumberFormat();
  const dateFmt = new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short",
  });
  const rel = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  function band(mag) {
    if (mag === null || mag === undefined) return null;
    if (mag < 2.5) return 0;
    if (mag < 4.5) return 1;
    if (mag < 6) return 2;
    if (mag < 7) return 3;
    return 4;
  }

  const fmt = {
    num: (n) => (n === null || n === undefined ? "—" : nf.format(n)),
    mag: (m) => (m === null || m === undefined ? "—" : nf1.format(m)),
    depth: (d) => (d === null || d === undefined ? "—" : `${nf1.format(d)} km`),
    pct: (x) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`),
    utc(iso) {
      if (!iso) return "—";
      const d = new Date(iso);
      return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
    },
    ago(iso) {
      if (!iso) return "—";
      const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
      const abs = Math.abs(seconds);
      if (abs < 60) return rel.format(Math.round(seconds), "second");
      if (abs < 3600) return rel.format(Math.round(seconds / 60), "minute");
      if (abs < 86400) return rel.format(Math.round(seconds / 3600), "hour");
      return rel.format(Math.round(seconds / 86400), "day");
    },
    duration(seconds) {
      if (seconds === null || seconds === undefined) return "—";
      if (seconds < 120) return `${Math.round(seconds)} s`;
      if (seconds < 7200) return `${nf1.format(seconds / 60)} min`;
      return `${nf1.format(seconds / 3600)} h`;
    },
  };

  function magBadge(mag, type) {
    const b = band(mag);
    return h("span", { class: "qw-mag", "data-band": b === null ? "0" : String(b), title: type ? `Magnitude (${type})` : "Magnitude" },
      h("span", { class: "visually-hidden" }, "Magnitude "), fmt.mag(mag));
  }

  function time(iso) {
    return h("time", { datetime: iso || "", title: fmt.utc(iso) }, fmt.ago(iso));
  }

  function eventLink(key, text) {
    return h("a", { href: `/events/${encodeURIComponent(key)}/` }, text || key);
  }

  /* ------------------------------------------------------------ freshness badge */
  async function refreshFreshness() {
    const badges = document.querySelectorAll("[data-qw-freshness]");
    if (!badges.length) return;
    const result = await api("/system/freshness");
    for (const badge of badges) {
      const label = badge.querySelector("[data-label]");
      const short = badge.querySelector("[data-short]");
      if (!result.ok) {
        badge.dataset.status = "unknown";
        label.textContent = "Freshness unavailable";
        if (short) short.textContent = "Unknown";
        badge.title = "Could not load data freshness.";
        continue;
      }
      const f = result.data;
      badge.dataset.status = f.status;
      const name = f.status === "fresh" ? "Live" : f.status.charAt(0).toUpperCase() + f.status.slice(1);
      const when = f.last_success_at ? `updated ${fmt.ago(f.last_success_at)}` : "never synced";
      label.textContent = `${name} · ${when}`;
      if (short) short.textContent = name;
      badge.title = `${name} · ${when}. ${f.message || ""}`;
      badge.setAttribute("aria-label", `Data freshness: ${name}, ${when}`);
    }
  }

  /* ------------------------------------------------------------ theme */
  function setTheme(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    try { localStorage.setItem("qw-theme", theme); } catch (_) { /* storage disabled */ }
    const toggle = document.querySelector("[data-qw-theme-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(theme === "dark"));
      toggle.querySelector("i").className = `bi bi-${theme === "dark" ? "sun" : "moon-stars"}`;
    }
    document.dispatchEvent(new CustomEvent("qw:theme", { detail: theme }));
  }

  function initTheme() {
    const toggle = document.querySelector("[data-qw-theme-toggle]");
    if (!toggle) return;
    setTheme(document.documentElement.getAttribute("data-bs-theme") || "light");
    toggle.addEventListener("click", () => {
      setTheme(document.documentElement.getAttribute("data-bs-theme") === "dark" ? "light" : "dark");
    });
  }

  /* ------------------------------------------------------------ unread alerts badge */
  async function refreshUnread() {
    const badge = document.querySelector("[data-qw-unread]");
    if (!badge) return;
    const result = await api("/alerts/unread-count");
    const count = result.ok ? result.data.unread : 0;
    badge.hidden = !count;
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.setAttribute("aria-label", `${count} unread alert notifications`);
  }

  /* ------------------------------------------------------------ misc helpers */
  function announce(message) {
    const region = document.getElementById("qw-live");
    if (region) {
      region.textContent = "";
      window.setTimeout(() => { region.textContent = message; }, 50);
    }
  }

  function readJsonScript(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function formToParams(form) {
    const params = {};
    for (const [key, value] of new FormData(form).entries()) {
      if (typeof value === "string" && value.trim() !== "") params[key] = value.trim();
    }
    return params;
  }

  function showFieldErrors(form, error) {
    for (const el of form.querySelectorAll(".is-invalid")) el.classList.remove("is-invalid");
    for (const el of form.querySelectorAll("[data-field-error]")) el.remove();
    const fields = (error && error.details && error.details.fields) || {};
    let first = null;
    for (const [name, message] of Object.entries(fields)) {
      const input = form.querySelector(`[name="${CSS.escape(name.split(".")[0])}"]`);
      if (!input) continue;
      const id = `${input.id || name}-error`;
      input.classList.add("is-invalid");
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", id);
      input.after(h("div", { class: "invalid-feedback", id, "data-field-error": "" }, String(message)));
      first = first || input;
    }
    if (first) first.focus();
    return Object.keys(fields).length;
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    refreshFreshness();
    window.setInterval(refreshFreshness, 60000);
    if (document.body.dataset.authenticated === "true") {
      refreshUnread();
      window.setInterval(refreshUnread, 60000);
    }
  });

  window.QW = {
    api, load, state, errorState, partialNotice, h, append, clear, fill, scrollRegion, icon, fmt, band, magBadge, time,
    eventLink, announce, readJsonScript, formToParams, showFieldErrors, refreshUnread, query,
  };
})();
