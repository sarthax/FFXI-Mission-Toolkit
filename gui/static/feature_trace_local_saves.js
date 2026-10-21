/* Feature Trace named bookmarks — explicit, browser-local navigation only.
 * Never stores source content, graph edges, credentials, runtime observations
 * or account data. No network calls or server/database writes.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root && root.document) {
    root.FeatureTraceLocalSaves = api;
    root.document.addEventListener("DOMContentLoaded", () => api.mount(root.document, root));
  }
})(typeof window !== "undefined" ? window : undefined, function () {
  "use strict";

  const KEY = "ffxi.feature-trace.local-saves.v1";
  const LIMIT = 20, MAX_HREF = 3500, MAX_ROOT = 240, MAX_TRAIL = 8;
  const MODES = new Set(["", "implementation", "mission", "triggers", "effects",
    "dependencies", "runtime", "identity", "diagnose", "all"]);
  const DIRECTIONS = new Set(["both", "in", "out"]);
  const QUERY_KEYS = new Set(["q", "mode", "depth", "direction", "trail"]);

  function validId(value) {
    return typeof value === "string" && value.length > 0 &&
      value.length <= MAX_ROOT && value.trim() === value &&
      !/[\u0000-\u001f\u007f]/.test(value);
  }

  function canonicalHref(raw, origin = "http://localhost") {
    if (typeof raw !== "string" || !raw.startsWith("/features/trace?") ||
        raw.length > MAX_HREF) throw new Error("Only local Feature Trace URLs may be saved");
    const url = new URL(raw, origin);
    if (url.origin !== origin || url.pathname !== "/features/trace" ||
        url.hash || url.username || url.password) throw new Error("Invalid saved trace URL");
    for (const [key] of url.searchParams) {
      if (!QUERY_KEYS.has(key) || url.searchParams.getAll(key).length !== 1)
        throw new Error("Unexpected or duplicate URL field");
    }
    const root = url.searchParams.get("q"), mode = url.searchParams.get("mode") || "";
    const depthRaw = url.searchParams.get("depth") || "3";
    const direction = url.searchParams.get("direction") || "both";
    if (!validId(root) || !MODES.has(mode) || !DIRECTIONS.has(direction) ||
        !/^(0|[1-8])$/.test(depthRaw)) throw new Error("Invalid trace identity or options");

    let trail = [];
    if (url.searchParams.has("trail")) {
      const encoded = url.searchParams.get("trail");
      if (encoded.length > 2600) throw new Error("Trail is too long");
      try { trail = JSON.parse(encoded); }
      catch (_) { throw new Error("Invalid saved breadcrumb trail"); }
      if (!Array.isArray(trail) || trail.length > MAX_TRAIL ||
          !trail.every(validId)) throw new Error("Invalid saved breadcrumb nodes");
    }
    const qs = new URLSearchParams({q: root});
    if (mode) qs.set("mode", mode);
    qs.set("depth", depthRaw);
    qs.set("direction", direction);
    if (trail.length) qs.set("trail", JSON.stringify(trail));
    const result = "/features/trace?" + qs.toString();
    if (result.length > MAX_HREF) throw new Error("Saved trace URL is too long");
    return result;
  }

  function validTitle(value, max) {
    return typeof value === "string" && value.trim().length > 0 &&
      value.trim().length <= max && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value);
  }

  function normalizeRecord(raw, origin) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) ||
        !validId(raw.id) || !validTitle(raw.name, 80) ||
        typeof raw.note !== "string" || raw.note.length > 240 ||
        !Number.isSafeInteger(raw.savedAt) || raw.savedAt <= 0)
      throw new Error("Stored investigation metadata is invalid");
    const href = canonicalHref(raw.href, origin);
    return {id: raw.id, name: raw.name.trim(), note: raw.note,
      href, savedAt: raw.savedAt};
  }

  function read(storage, origin) {
    try {
      if (!storage) throw new Error("Browser storage unavailable");
      const raw = storage.getItem(KEY);
      if (raw == null) return {items: [], error: ""};
      if (raw.length > 125000) throw new Error("Saved data exceeds limits");
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.items) ||
          parsed.items.length > LIMIT) throw new Error("Unknown saved investigation schema");
      const items = parsed.items.map(row => normalizeRecord(row, origin));
      if (new Set(items.map(x => x.id)).size !== items.length)
        throw new Error("Duplicate saved investigation IDs");
      return {items, error: ""};
    } catch (_) {
      // Do not overwrite/delete unreadable user data implicitly.
      return {items: [], error: "Saved views cannot be read. Existing browser data was left unchanged."};
    }
  }

  function persist(storage, items) {
    storage.setItem(KEY, JSON.stringify({version: 1, items}));
  }

  function save(storage, origin, data, id, timestamp) {
    const state = read(storage, origin);
    if (state.error) throw new Error(state.error);
    if (state.items.length >= LIMIT)
      throw new Error("Saved-view limit reached. Delete a saved view before adding another.");
    const row = normalizeRecord({
      id, name: data.name, note: data.note || "",
      href: data.href, savedAt: timestamp,
    }, origin);
    if (state.items.some(x => x.id === row.id))
      throw new Error("Duplicate saved investigation ID");
    const items = [row, ...state.items];
    persist(storage, items);
    return items;
  }

  function remove(storage, origin, id) {
    const state = read(storage, origin);
    if (state.error) throw new Error(state.error);
    if (!state.items.some(x => x.id === id))
      throw new Error("Saved view no longer exists");
    const items = state.items.filter(x => x.id !== id);
    persist(storage, items);
    return items;
  }

  function currentHref(section, origin) {
    const params = new URLSearchParams({
      q: section.dataset.root, depth: section.dataset.depth,
      direction: section.dataset.direction,
    });
    if (section.dataset.mode) params.set("mode", section.dataset.mode);
    if (section.dataset.trail && section.dataset.trail !== "[]")
      params.set("trail", section.dataset.trail);
    return canonicalHref("/features/trace?" + params.toString(), origin);
  }

  function mount(document, window) {
    const section = document.getElementById("trace-saved-views");
    if (!section) return;
    const name = document.getElementById("trace-save-name");
    const note = document.getElementById("trace-save-note");
    const status = document.getElementById("trace-save-status");
    const list = document.getElementById("trace-saved-list");
    const saveButton = document.getElementById("trace-save-button");
    const origin = window.location.origin;
    let storage;
    try { storage = window.localStorage; } catch (_) { storage = null; }

    function render() {
      const state = read(storage, origin);
      list.replaceChildren();
      saveButton.disabled = Boolean(state.error);
      if (state.error) { status.textContent = state.error; return; }
      for (const item of state.items) {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.href = item.href; link.textContent = item.name; link.className = "zonelink";
        const description = document.createElement("span");
        description.textContent = " · " + new Date(item.savedAt).toLocaleString() +
          (item.note ? " · " + item.note : "");
        const del = document.createElement("button");
        del.type = "button"; del.textContent = "Delete";
        del.setAttribute("aria-label", "Delete saved view " + item.name);
        del.addEventListener("click", () => {
          try {
            remove(storage, origin, item.id);
            status.textContent = "Saved view deleted from this browser.";
          } catch (error) { status.textContent = "Could not delete: " + error.message; }
          render();
        });
        li.append(link, description, document.createTextNode(" "), del);
        list.appendChild(li);
      }
      if (!state.items.length) {
        const li = document.createElement("li");
        li.textContent = "No locally saved views.";
        list.appendChild(li);
      }
    }

    name.value = (section.dataset.root || "").slice(0, 80);
    saveButton.addEventListener("click", () => {
      try {
        const id = (window.crypto && typeof window.crypto.randomUUID === "function")
          ? window.crypto.randomUUID()
          : Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
        save(storage, origin, {
          name: name.value, note: note.value,
          href: currentHref(section, origin),
        }, id, Date.now());
        status.textContent = "Saved in this browser profile. Recheck indexed source evidence when resuming.";
        render();
      } catch (error) { status.textContent = "Could not save: " + error.message; }
    });
    render();
  }

  return {KEY, LIMIT, canonicalHref, read, save, remove, currentHref, mount};
});
