/* Native Node tests for the actual browser-local Feature Trace save logic.
 * Synthetic IDs and fake browser storage only. No DOM, runtime or server access.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const saved = require("../gui/static/feature_trace_local_saves.js");

const origin = "http://localhost:8000";
class MemoryStorage {
  constructor() { this.data = new Map(); this.writes = 0; }
  getItem(key) { return this.data.has(key) ? this.data.get(key) : null; }
  setItem(key, value) { this.writes++; this.data.set(key, value); }
  removeItem(key) { this.writes++; this.data.delete(key); }
}
function target(root = "synthetic:root", mode = "mission") {
  const q = new URLSearchParams({q: root, mode, depth: "2", direction: "out",
    trail: JSON.stringify(["synthetic:prior", "synthetic:branch"])});
  return "/features/trace?" + q.toString();
}
function add(store, id="synthetic-id") {
  return saved.save(store, origin, {
    name:"Synthetic investigation", note:"Inspect synthetic source",
    href:target(),
  }, id, 1234567890);
}

test("local named save survives a fresh read and deletes explicitly", () => {
  const storage = new MemoryStorage();
  assert.deepEqual(saved.read(storage, origin).items, []);
  const items = add(storage);
  assert.equal(items.length, 1);
  assert.equal(storage.writes, 1);
  const restored = saved.read(storage, origin);
  assert.equal(restored.error, "");
  assert.equal(restored.items[0].name, "Synthetic investigation");
  assert.equal(restored.items[0].note, "Inspect synthetic source");
  const url = new URL(restored.items[0].href, origin);
  assert.equal(url.pathname, "/features/trace");
  assert.equal(url.searchParams.get("q"), "synthetic:root");
  assert.equal(url.searchParams.get("mode"), "mission");
  assert.equal(url.searchParams.get("depth"), "2");
  assert.equal(url.searchParams.get("direction"), "out");
  assert.deepEqual(JSON.parse(url.searchParams.get("trail")),
    ["synthetic:prior", "synthetic:branch"]);
  assert.deepEqual(saved.remove(storage, origin, "synthetic-id"), []);
  assert.equal(saved.read(storage, origin).items.length, 0);
  assert.equal(storage.writes, 2);
});

test("multiple names can fork the same root without overwriting another save", () => {
  const storage = new MemoryStorage();
  add(storage, "synthetic-A");
  saved.save(storage, origin, {name:"Synthetic fork", note:"Alternative route", href:target()},
    "synthetic-B", 1234567891);
  const state = saved.read(storage, origin);
  assert.equal(state.items.length, 2);
  assert.equal(state.items[0].name, "Synthetic fork");
  assert.equal(state.items[1].name, "Synthetic investigation");
  assert.equal(saved.remove(storage, origin, "synthetic-B").length, 1);
  assert.equal(saved.read(storage, origin).items[0].id, "synthetic-A");
});

test("only same-origin exact-route bounded fields enter browser storage", () => {
  for (const bad of [
    "https://attacker.example/features/trace?q=synthetic",
    "//attacker.example/features/trace?q=synthetic",
    "/features/trace/evil?q=synthetic",
    "/features/trace?q=synthetic&next=https://attacker.example",
    "/features/trace?q=synthetic&q=synthetic-other",
    "/features/trace?q=synthetic&mode=unrecognized",
    "/features/trace?q=synthetic&depth=9",
    "/features/trace?q=synthetic&depth=-1",
    "/features/trace?q=synthetic&depth=banana",
    "/features/trace?q=synthetic&direction=sideways",
    "/features/trace?q=synthetic#jump",
    "/features/trace?q=%0Aroot",
    "/features/trace?q=" + "x".repeat(241),
    "/features/trace?q=root&trail=%5Bnot-json",
    "/features/trace?q=root&trail=" + encodeURIComponent(JSON.stringify(["bad\nid"])),
    "/features/trace?q=root&trail=" + encodeURIComponent(JSON.stringify(Array(9).fill("root"))),
  ]) {
    assert.throws(() => saved.canonicalHref(bad, origin), undefined, bad);
  }
  const result = saved.canonicalHref(target(), origin);
  assert.ok(result.startsWith("/features/trace?"));
  assert.equal(new URL(result, origin).origin, origin);
});

test("corrupt or unknown storage is preserved rather than silently overwritten", () => {
  const storage = new MemoryStorage();
  storage.setItem(saved.KEY, "not-json");
  const before = storage.getItem(saved.KEY);
  assert.match(saved.read(storage, origin).error, /cannot be read/);
  assert.throws(() => add(storage), /cannot be read/);
  assert.throws(() => saved.remove(storage, origin, "any"), /cannot be read/);
  assert.equal(storage.getItem(saved.KEY), before);
  storage.setItem(saved.KEY, JSON.stringify({version: 9, items: []}));
  assert.ok(saved.read(storage, origin).error);
});

test("hostile loaded links and conflicting IDs fail closed", () => {
  const storage = new MemoryStorage();
  add(storage);
  assert.throws(() => add(storage), /Duplicate/);
  let persisted = JSON.parse(storage.getItem(saved.KEY));
  persisted.items[0].href = "/other?q=synthetic";
  storage.setItem(saved.KEY, JSON.stringify(persisted));
  assert.ok(saved.read(storage, origin).error);
});

test("strict cap prevents silent loss of earlier named investigations", () => {
  const storage = new MemoryStorage();
  for(let i=0;i<saved.LIMIT;i++) add(storage, "synthetic-"+i);
  assert.equal(saved.read(storage, origin).items.length, saved.LIMIT);
  assert.throws(() => add(storage, "synthetic-over-limit"), /limit reached/);
  assert.equal(saved.read(storage, origin).items.length, saved.LIMIT);
});

test("browser quota/unavailable-storage failures do not report success", () => {
  const noStorage = {getItem() {throw Error("disabled");}};
  assert.ok(saved.read(noStorage, origin).error);
  assert.throws(() => add(noStorage), /cannot be read/);
  const quota = {getItem(){return null;},setItem(){throw Error("quota exceeded");}};
  assert.throws(() => add(quota), /quota exceeded/);
});

test("saves contain no raw evidence, provenance, capture packets, or graph edges", () => {
  const storage = new MemoryStorage();
  add(storage);
  const raw = storage.getItem(saved.KEY);
  for (const field of ["edges", "evidence_id", "source_snapshot_id",
                        "capture_id", "password", "sql_row", "dat_contents"]) {
    assert.equal(raw.includes(field), false, field);
  }
  assert.deepEqual(Object.keys(JSON.parse(raw)), ["version","items"]);
  assert.deepEqual(Object.keys(JSON.parse(raw).items[0]),
    ["id", "name", "note", "href", "savedAt"]);
});

test("current trace UI data maps to canonical URL, not arbitrary location.href", () => {
  const section = {dataset: {root:"synthetic:resolved",mode:"implementation",
    depth:"1",direction:"both",trail:'["synthetic:prior"]'}};
  const url = new URL(saved.currentHref(section, origin), origin);
  assert.equal(url.searchParams.get("q"), "synthetic:resolved");
  assert.equal(url.searchParams.get("mode"), "implementation");
  assert.equal(url.searchParams.get("trail"), '["synthetic:prior"]');
});

test("UI mounting requires the actual trace result and is inert elsewhere", () => {
  let accessed = false;
  saved.mount({getElementById(){return null;}}, {get localStorage() { accessed=true; }});
  assert.equal(accessed, false);
});

test("drafts start disabled, require opt-in and never alter named saves", () => {
  const storage = new MemoryStorage();
  add(storage);
  const before = storage.getItem(saved.KEY);
  assert.deepEqual(saved.readDraft(storage, origin), {
    enabled:false, href:"", savedAt:null, error:"",
  });
  assert.equal(storage.getItem(saved.DRAFT_KEY), null);
  assert.equal(saved.saveDraft(storage, origin, target(), 1234567891),
    saved.canonicalHref(target(), origin));
  const draft = saved.readDraft(storage, origin);
  assert.equal(draft.enabled, true);
  assert.equal(draft.savedAt, 1234567891);
  assert.deepEqual(JSON.parse(new URL(draft.href, origin).searchParams.get("trail")),
    ["synthetic:prior", "synthetic:branch"]);
  assert.equal(storage.getItem(saved.KEY), before);
  saved.disableDraft(storage, origin);
  assert.equal(saved.readDraft(storage, origin).enabled, false);
  assert.equal(storage.getItem(saved.KEY), before);
});

test("draft validator rejects corrupt schemas and unsafe URLs without overwriting", () => {
  const storage = new MemoryStorage();
  for (const raw of [
    "not-json",
    JSON.stringify({version: 9, href:target(), savedAt:1234567890}),
    JSON.stringify({version: 1, href:target(), savedAt:1234567890, edges:[]}),
    JSON.stringify({version: 1, href:"https://evil.example/?q=x", savedAt:1234567890}),
    JSON.stringify({version: 1, href:"/features/trace?q=root&redirect=evil",
      savedAt:1234567890}),
    JSON.stringify({version: 1, href:target(), savedAt:"not-a-time"}),
    "x".repeat(5000),
  ]) {
    storage.setItem(saved.DRAFT_KEY, raw);
    assert.match(saved.readDraft(storage, origin).error, /cannot be read/);
    assert.throws(() => saved.saveDraft(storage, origin, target(), 1234567899), /cannot be read/);
    assert.throws(() => saved.disableDraft(storage, origin), /cannot be read/);
    assert.equal(storage.getItem(saved.DRAFT_KEY), raw);
  }
});

test("draft quota and storage failures never imply recovery is enabled", () => {
  const storage = {
    getItem(){return null;}, setItem(){throw Error("quota exceeded");},
    removeItem(){throw Error("storage denied");},
  };
  assert.throws(() => saved.saveDraft(storage, origin, target(), 1234567890),
    /quota exceeded/);
  assert.equal(saved.readDraft(storage, origin).enabled, false);
  assert.throws(() => saved.disableDraft(storage, origin), /storage denied/);
  const denied = {getItem(){throw Error("storage denied");}};
  assert.match(saved.readDraft(denied, origin).error, /cannot be read/);
  assert.throws(() => saved.saveDraft(denied, origin, target(), 1234567890),
    /cannot be read/);
});

test("only a navigation URL and timestamp are persisted in the local draft", () => {
  const storage = new MemoryStorage();
  saved.saveDraft(storage, origin, target(), 1234567890);
  const raw = storage.getItem(saved.DRAFT_KEY);
  assert.deepEqual(Object.keys(JSON.parse(raw)), ["version","href","savedAt"]);
  for(const field of ["edges","evidence_id","source_snapshot_id","capture_id",
                      "password","graph","source_contents","account"]) {
    assert.equal(raw.includes(field), false, field);
  }
  assert.throws(() => saved.saveDraft(storage, origin, "//evil.example/?q=a", 1234567891));
  assert.equal(storage.getItem(saved.DRAFT_KEY), raw);
});

function fakeDraftDom(storage, withRoot) {
  const events = new Map(), listeners = new Map();
  const element = (id) => ({
    id, dataset:{}, hidden:false, disabled:false, textContent:"",
    addEventListener(type,fn){events.set(id+":"+type,fn);},
    removeAttribute(name){delete this[name];},
    setAttribute(name,value){this[name]=value;},
    replaceChildren(){},appendChild(){},append(){},
  });
  const ids = ["trace-draft-recovery","trace-draft-link","trace-draft-info",
    "trace-draft-disable","trace-draft-status"];
  if (withRoot) ids.push("trace-saved-views","trace-draft-opt-in",
    "trace-save-name","trace-save-note","trace-save-status",
    "trace-saved-list","trace-save-button");
  const els = Object.fromEntries(ids.map(id=>[id,element(id)]));
  if(withRoot) els["trace-saved-views"].dataset = {
    root:"synthetic:resolved",mode:"mission",depth:"2",direction:"both",trail:"[]",
  };
  const doc = {getElementById(id){return els[id] || null;},
    createElement(tag){return element(tag);}, createTextNode(text){return {textContent:text}}};
  const win = {localStorage:storage,location:{origin},
    addEventListener(type,fn){listeners.set(type,fn);}};
  return {els,events,listeners,doc,win};
}

test("opt-in UI records the latest exact resolved view on page exit", () => {
  const storage = new MemoryStorage(), ui = fakeDraftDom(storage, true);
  saved.mount(ui.doc, ui.win);
  assert.equal(storage.writes, 0);
  assert.equal(ui.els["trace-draft-opt-in"].checked, false);
  assert.equal(ui.els["trace-draft-recovery"].hidden, true);
  ui.els["trace-draft-opt-in"].checked = true;
  ui.events.get("trace-draft-opt-in:change")();
  assert.equal(saved.readDraft(storage, origin).enabled, true);
  ui.els["trace-saved-views"].dataset.mode = "implementation";
  ui.listeners.get("pagehide")();
  assert.equal(new URL(saved.readDraft(storage,origin).href,origin)
    .searchParams.get("mode"),"implementation");
  ui.els["trace-draft-opt-in"].checked = false;
  ui.events.get("trace-draft-opt-in:change")();
  assert.equal(saved.readDraft(storage, origin).enabled, false);
  const writes = storage.writes;
  ui.listeners.get("pagehide")();
  assert.equal(storage.writes, writes);
});

test("recovery link is available on a new empty search page and can be cleared", () => {
  const storage = new MemoryStorage();
  saved.saveDraft(storage, origin, target(), 1234567890);
  const ui = fakeDraftDom(storage, false);
  saved.mount(ui.doc, ui.win);
  assert.equal(ui.els["trace-draft-recovery"].hidden, false);
  assert.equal(ui.els["trace-draft-link"].href, saved.canonicalHref(target(),origin));
  assert.equal(ui.listeners.size, 0);
  ui.events.get("trace-draft-disable:click")();
  assert.equal(saved.readDraft(storage, origin).enabled, false);
  assert.equal(ui.els["trace-draft-recovery"].hidden, true);
});
