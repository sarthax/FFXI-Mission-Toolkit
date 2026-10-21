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
  const DRAFT_KEY = "ffxi.feature-trace.local-draft.v1";
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

  // Drafts are a separate opt-in slot, never a hidden 21st named save.
  // A draft contains just one already validated read-only navigation URL.
  function readDraft(storage, origin) {
    try {
      if (!storage) throw new Error("Browser storage unavailable");
      const raw = storage.getItem(DRAFT_KEY);
      if (raw == null) return {enabled: false, href: "", savedAt: null, error: ""};
      if (raw.length > 4800) throw new Error("Draft exceeds size limit");
      const row = JSON.parse(raw);
      if (!row || typeof row !== "object" || Array.isArray(row) ||
          Object.keys(row).sort().join(",") !== "href,savedAt,version" ||
          row.version !== 1 || !Number.isSafeInteger(row.savedAt) || row.savedAt <= 0)
        throw new Error("Unknown draft schema");
      return {enabled: true, href: canonicalHref(row.href, origin),
        savedAt: row.savedAt, error: ""};
    } catch (_) {
      return {enabled: false, href: "", savedAt: null,
        error: "Local draft cannot be read. Existing browser data was left unchanged."};
    }
  }

  function saveDraft(storage, origin, href, timestamp) {
    const state = readDraft(storage, origin);
    if (state.error) throw new Error(state.error);
    if (!Number.isSafeInteger(timestamp) || timestamp <= 0)
      throw new Error("Invalid draft time");
    const canonical = canonicalHref(href, origin);
    storage.setItem(DRAFT_KEY, JSON.stringify({version: 1, href: canonical,
      savedAt: timestamp}));
    return canonical;
  }

  function disableDraft(storage, origin) {
    const state = readDraft(storage, origin);
    if (state.error) throw new Error(state.error);
    storage.removeItem(DRAFT_KEY);
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
    const draftPanel = document.getElementById("trace-draft-recovery");
    if (!section && !draftPanel) return;
    const name = document.getElementById("trace-save-name");
    const note = document.getElementById("trace-save-note");
    const status = document.getElementById("trace-save-status");
    const list = document.getElementById("trace-saved-list");
    const saveButton = document.getElementById("trace-save-button");
    const origin = window.location.origin;
    const draftCheck = document.getElementById("trace-draft-opt-in");
    const draftStatus = document.getElementById("trace-draft-status");
    const draftLink = document.getElementById("trace-draft-link");
    const draftInfo = document.getElementById("trace-draft-info");
    const draftDisable = document.getElementById("trace-draft-disable");
    let storage;
    try { storage = window.localStorage; } catch (_) { storage = null; }

    function renderDraft(message = "") {
      const state = readDraft(storage, origin);
      if (draftCheck) {
        draftCheck.checked = state.enabled;
        draftCheck.disabled = Boolean(state.error);
      }
      if (draftPanel) {
        draftPanel.hidden = !(state.enabled || state.error);
        if (draftLink) {
          draftLink.hidden = !state.enabled;
          if (state.enabled) draftLink.href = state.href;
          else draftLink.removeAttribute("href");
        }
        if (draftInfo) draftInfo.textContent = state.enabled
          ? "Last recorded navigation: " + new Date(state.savedAt).toLocaleString() +
            ". Re-runs against the current index; source and identity may be stale."
          : state.error;
        if (draftDisable) draftDisable.disabled = Boolean(state.error);
      }
      if (draftStatus) draftStatus.textContent = message || state.error ||
        (state.enabled ? "Opted in: records this resolved view when leaving its page." :
          "Off: no automatic draft is stored.");
    }

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

    if (section) {
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

    if (draftCheck && section) draftCheck.addEventListener("change", () => {
      try {
        if (draftCheck.checked) {
          saveDraft(storage, origin, currentHref(section, origin), Date.now());
          renderDraft("Automatic draft recovery enabled for this browser profile.");
        } else {
          disableDraft(storage, origin);
          renderDraft("Draft deleted and automatic recovery disabled.");
        }
      } catch (error) {
        renderDraft("Draft setting was not changed: " + error.message);
      }
    });
    if (draftDisable) draftDisable.addEventListener("click", () => {
      try {
        disableDraft(storage, origin);
        renderDraft("Draft deleted and automatic recovery disabled.");
      } catch (error) { renderDraft("Could not delete draft: " + error.message); }
    });
    // Save on page exit only after explicit opt-in, and only with an exact root.
    // No source/evidence data, user-entered query, or live client state is read.
    if (section && typeof window.addEventListener === "function")
      window.addEventListener("pagehide", () => {
        if (!readDraft(storage, origin).enabled) return;
        try { saveDraft(storage, origin, currentHref(section, origin), Date.now()); }
        catch (_) { /* Browser may deny writes on exit; never claim guaranteed recovery. */ }
      });
    renderDraft();
  }

  return {KEY, DRAFT_KEY, LIMIT, canonicalHref, read, save, remove,
    readDraft, saveDraft, disableDraft, currentHref, mount};
});
