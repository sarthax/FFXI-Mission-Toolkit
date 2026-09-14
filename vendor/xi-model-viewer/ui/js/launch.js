/**
 * Launch options — how another app (an editor's "Preview" button, a shortcut,
 * a shell, or an external tool's own entity page) asks the viewer to come up
 * already showing something specific.
 *
 *   Tauri:    xi-model-viewer.exe --zone "ROM/171/34.DAT" [--time 18:00] [--weather rain]
 *             xi-model-viewer.exe --npc 98765
 *   Browser:  index.html?zone=ROM/171/34.DAT&time=18:00&weather=rain
 *             index.html?npc=98765
 *
 * A `--zone` launch is *minimal* by default: no menu bar, no asset panel, no
 * status bars, no object browser — just the zone and the Zone panel (weather,
 * time of day, fog, brightness, audio). `--full-ui` opens the same zone in the
 * whole app instead.
 *
 * A `--npc <fileId>` launch opens the whole app on the NPC/PC page with that
 * model auto-selected -- fileId is the real DAT file id (98239 + model_id for
 * a monster/NPC, per ui/js/dat/modelids.js's ENTITY_MODEL_OFFSET), matched
 * against lists/npcs.json's own `fileId` field, the same data NpcList already
 * browses by hand. Always full UI (unlike --zone, there's no minimal npc
 * chrome) -- meant for another tool's "view this entity's model" link, not a
 * standalone preview window.
 *
 * Options:
 *   --zone <dat|id>  zone DAT (game-relative `ROM/171/34.DAT`, a leveleditor
 *                    `game/ROM/…` path, or the DAT's absolute path), or a zone id
 *   --minimal        chrome-free viewer (the default when --zone is given)
 *   --full-ui        keep the whole app around the zone
 *   --weather <id>   starting weather, e.g. fine / rain / snow / aura
 *   --time <t>       starting time of day, `HH:MM` or minutes past midnight
 *   --clock          run the day clock (a full FFXI day per minute)
 *   --npc <fileId>   real DAT file id of an NPC/monster model to auto-select
 *
 * Both parsers below are pure so the same option set works whichever way the
 * viewer was started.
 */

import { backend } from './backend.js';

/** Long names that consume the next argv entry (or an `=value`). */
const VALUE_FLAGS = new Set(['zone', 'weather', 'time', 'npc']);
/** Short forms, for hand-typed launches. */
const ALIASES = { z: 'zone', w: 'weather', t: 'time', m: 'minimal', n: 'npc' };

const NO_LAUNCH = Object.freeze({
  zone: null, minimal: false, weather: null, timeMinutes: null, clock: false, npcFileId: null,
});

/** `--flag`, `--flag=0`, `--flag=false`: absent value means "on". */
function flagOn(value) {
  if (value == null) return true;
  const v = String(value).trim().toLowerCase();
  return !(v === '0' || v === 'false' || v === 'no' || v === 'off');
}

/**
 * `HH:MM` or minutes past midnight → minutes in [0, 1440), or null if the
 * value is not a time at all.
 */
export function parseLaunchTime(value) {
  if (value == null) return null;
  const s = String(value).trim();
  const hhmm = /^(\d{1,2}):(\d{1,2})$/.exec(s);
  let minutes;
  if (hhmm) minutes = Number(hhmm[1]) * 60 + Number(hhmm[2]);
  else if (/^\d+(\.\d+)?$/.test(s)) minutes = Math.round(Number(s));
  else return null;
  if (!Number.isFinite(minutes)) return null;
  return ((minutes % 1440) + 1440) % 1440;
}

/**
 * Reduce a `--zone` value to the path loadZone wants: relative to the install
 * root, Windows-separated. Callers pass the configured roots (HD pack, game
 * dir) so an absolute DAT path inside either is trimmed back to `ROM\…`.
 */
export function launchZoneRel(value, roots = []) {
  let p = String(value ?? '').trim()
    .replace(/^["']|["']$/g, '')     // a quoted path pasted into a shortcut
    .replace(/\//g, '\\');
  for (const root of roots) {
    if (!root) continue;
    const r = String(root).replace(/\//g, '\\').replace(/\\+$/, '');
    if (p.toLowerCase().startsWith(`${r.toLowerCase()}\\`)) {
      p = p.slice(r.length);
      break;
    }
  }
  p = p.replace(/^\\+/, '').replace(/^game\\/i, '');
  // An absolute path from somewhere we don't know (a copy of the install, a
  // different drive letter): keep it from the ROM folder on.
  const rom = /(?:^|\\)((?:ROM|SOUND|VIDEO)\d*\\.*)$/i.exec(p);
  return rom ? rom[1] : p;
}

/** A positive integer file id, or null (rejects garbage/negative/zero silently). */
function parseFileId(value) {
  if (value == null) return null;
  const n = Number(String(value).trim());
  return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
}

/** Shape the collected key/values into the options the app reads. */
function normalize(raw) {
  const zone = raw.zone == null ? '' : String(raw.zone).trim();
  const npcFileId = parseFileId(raw.npcFileId);
  if (!zone && npcFileId == null) return { ...NO_LAUNCH };
  if (!zone) {
    // NPC-model deep link, no zone involved -- always full UI (there's no
    // minimal npc chrome the way --zone has one).
    return { ...NO_LAUNCH, npcFileId };
  }
  // Minimal unless asked otherwise; an explicit --minimal beats --full-ui.
  const minimal = raw.minimal != null ? !!raw.minimal : !raw.fullUi;
  return {
    zone,
    minimal,
    weather: raw.weather ? String(raw.weather).trim().toLowerCase() : null,
    timeMinutes: parseLaunchTime(raw.time),
    clock: !!raw.clock,
    npcFileId,
  };
}

/** Parse a Tauri/CLI argv (argv[0] already dropped). */
export function parseLaunchArgs(argv = []) {
  const args = (argv ?? []).map((a) => String(a));
  const raw = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (!arg.startsWith('-')) continue;    // bare paths (file association) aren't options
    const eq = arg.indexOf('=');
    const name = (eq >= 0 ? arg.slice(0, eq) : arg).replace(/^--?/, '').toLowerCase();
    const key = ALIASES[name] ?? name;
    let value = eq >= 0 ? arg.slice(eq + 1) : null;
    if (VALUE_FLAGS.has(key) && value === null) {
      const next = args[i + 1];
      // A DAT path never starts with '-', so this can't swallow the next flag.
      if (next !== undefined && !next.startsWith('-')) {
        value = next;
        i++;
      }
    }
    switch (key) {
      case 'zone': case 'weather': case 'time': case 'npc':
        if (value !== null) raw[key === 'npc' ? 'npcFileId' : key] = value;
        break;
      case 'minimal': raw.minimal = flagOn(value); break;
      case 'no-minimal': raw.minimal = !flagOn(value); break;
      case 'full-ui': case 'fullui': raw.fullUi = flagOn(value); break;
      case 'clock': raw.clock = flagOn(value); break;
      default: break;                       // unknown flags are the shell's business
    }
  }
  return normalize(raw);
}

/** Parse the browser-dev-mode equivalent: `?zone=…&time=…` or `?npc=<fileId>`. */
export function parseLaunchSearch(search = '') {
  const q = new URLSearchParams(search);
  if (!q.has('zone') && !q.has('npc')) return { ...NO_LAUNCH };
  const raw = {
    zone: q.get('zone'), weather: q.get('weather'), time: q.get('time'),
    npcFileId: q.get('npc'),
  };
  if (q.has('minimal')) raw.minimal = flagOn(q.get('minimal'));
  // ?ui=full is the query-string spelling of --full-ui.
  if (q.has('ui')) raw.fullUi = String(q.get('ui')).toLowerCase() === 'full';
  if (q.has('clock')) raw.clock = flagOn(q.get('clock'));
  return normalize(raw);
}

/**
 * The launch options for this run: CLI args in the Tauri shell, the query
 * string in a browser (and as an override when the app is started by a URL).
 * Never throws — a bad launch line just means "open normally".
 */
export async function readLaunchOptions() {
  const fromUrl = parseLaunchSearch(window.location?.search ?? '');
  if (fromUrl.zone || fromUrl.npcFileId != null) return fromUrl;
  try {
    return parseLaunchArgs(await backend.launchArgs());
  } catch {
    return { ...NO_LAUNCH };
  }
}
