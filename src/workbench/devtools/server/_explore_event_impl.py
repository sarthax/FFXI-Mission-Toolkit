#!/usr/bin/env python3
"""
explore_event.py -- Mission Toolkit GUI, Phase 3 scoped slice (event/dialogue explorer).

One command for "decompile this CSID with real text substituted in" -- the single most manual
step this session (reading raw opcode dumps line by line to find where a menu's option values
actually come from, done by hand for the Vending Box mechanic). This is a thin wrapper: the real
decompiler is xi-events-py (via its own mission_toolkit.py bridge script), which already renders
message ids with dialog.yml's text inline. This script just:
  - auto-generates a zone's events.yml/dialog.yml via the packaged Mission Toolkit CLI if not already cached
  - resolves an entity by name (via npc_names) instead of requiring the raw id
  - cross-checks every message id the decompiler renders against OUR OWN dialog_text index
    (built by build_dialog_index.py via dat-extractor -- a second, independently-extracted
    source from dialog.yml's xi-tinkerer extraction) and flags any disagreement between the two,
    the same two-source-agreement discipline used throughout this toolkit

Usage:
    py -3 explore_event.py Nyzul_Isle "Vending Box" 202
    py -3 explore_event.py Nyzul_Isle 17093430 202
"""
import argparse
import io
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
import yaml
from pathlib import Path


TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
MISSION_REPORTS = TOOLS_ROOT / "mission_reports"
XI_EVENTS_BRIDGE = TOOLS_ROOT / "vendor/xi-events-py/decompile_from_mission_toolkit.py"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"

_XI_EVENTS_MODULE = None


def _load_xi_events_bridge():
    """Load the vendored xi-events bridge as a Python module, once.

    The GUI should never shell out to this bridge: subprocess stdout introduces a Windows console
    encoding boundary that can corrupt otherwise-valid Unicode dialog/event text. Keeping decompile
    results as Python str values makes Unicode lossless end-to-end.
    """
    global _XI_EVENTS_MODULE
    if _XI_EVENTS_MODULE is not None:
        return _XI_EVENTS_MODULE

    vendor_root = XI_EVENTS_BRIDGE.parent
    vendor_root_s = str(vendor_root)
    if vendor_root_s not in sys.path:
        sys.path.insert(0, vendor_root_s)

    spec = importlib.util.spec_from_file_location("mission_toolkit_xi_events_bridge", XI_EVENTS_BRIDGE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load xi-events bridge from {XI_EVENTS_BRIDGE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _XI_EVENTS_MODULE = module
    return module


def decompile_event(out_dir: Path, entity_id: int, event_id: int, zone_id: int | None) -> dict:
    """Canonical in-process CSID decompile used by GUI/health scans.

    Returns a structured result rather than printing. SystemExit from fixture validation is
    converted to a normal error string so invalid/stub events cannot crash the web request.
    """
    bridge = _load_xi_events_bridge()
    try:
        fixture = bridge.load_fixture(
            str(out_dir / "events.yml"),
            int(entity_id),
            int(event_id),
            str(out_dir / "dialog.yml"),
            int(zone_id or 0),
        )
        return {"decompiled": bridge.decompile(fixture), "error": None}
    except SystemExit as exc:
        return {"decompiled": None, "error": str(exc)}
    except Exception as exc:
        return {"decompiled": None, "error": f"{type(exc).__name__}: {exc}"}


def scan_event_health(out_dir: Path, zone_id: int | None, *, force: bool = False) -> dict:
    """Preflight every exported entity/CSID once and cache the result beside the zone export.

    Cache validity is tied to events.yml + dialog.yml mtimes/sizes so replacing or rebuilding the
    client export automatically invalidates old health results.
    """
    events_path = out_dir / "events.yml"
    dialog_path = out_dir / "dialog.yml"
    cache_path = out_dir / "event_health.json"
    if not events_path.exists():
        return {"rows": {}, "summary": {"missing_export": 1}}

    fingerprint = {
        "schema_version": 2,
        "events_mtime_ns": events_path.stat().st_mtime_ns,
        "events_size": events_path.stat().st_size,
        "dialog_mtime_ns": dialog_path.stat().st_mtime_ns if dialog_path.exists() else None,
        "dialog_size": dialog_path.stat().st_size if dialog_path.exists() else None,
    }
    if not force and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("fingerprint") == fingerprint:
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    bridge = _load_xi_events_bridge()
    with events_path.open(encoding="utf-8") as fh:
        events_doc = yaml.safe_load(fh)
    strings = {}
    if dialog_path.exists():
        with dialog_path.open(encoding="utf-8") as fh:
            dialog_doc = yaml.safe_load(fh)
        strings = dialog_doc.get("entries", dialog_doc)

    rows = {}
    summary = {"ok": 0, "stub": 0, "invalid": 0, "failed": 0}
    for block in events_doc.get("blocks", []):
        entity_id = block.get("entity_id")
        if entity_id is None:
            continue
        for event in block.get("events", []):
            event_id = event.get("id")
            if event_id in (None, 65535):
                continue
            key = f"{int(entity_id)}:{int(event_id)}"
            try:
                fixture = bridge.fixture_from_documents(
                    events_doc, int(entity_id), int(event_id), strings, int(zone_id or 0)
                )
                text = bridge.decompile(fixture)
                decompile_summary = summarize_decompile(text)
                rows[key] = {
                    "status": "ok",
                    "detail": None,
                    "line_count": len(text.splitlines()),
                    "message_ids": decompile_summary["message_ids"],
                }
                summary["ok"] += 1
            except SystemExit as exc:
                detail = str(exc)
                status = "stub" if "bare '0x00' stub" in detail else "invalid"
                rows[key] = {"status": status, "detail": detail, "line_count": 0}
                summary[status] += 1
            except Exception as exc:
                rows[key] = {
                    "status": "failed",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "line_count": 0,
                }
                summary["failed"] += 1

    message_refs = {}
    for key, row in rows.items():
        if row.get("status") != "ok":
            continue
        entity_id, event_id = (int(part) for part in key.split(":", 1))
        for message_id in row.get("message_ids", []):
            message_refs.setdefault(str(int(message_id)), []).append({
                "entity_id": entity_id,
                "event_id": event_id,
            })

    payload = {
        "fingerprint": fingerprint,
        "rows": rows,
        "summary": summary,
        "message_refs": message_refs,
    }
    try:
        cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
    return payload


def resolve_entity(con: sqlite3.Connection, zoneid: int, query: str) -> int | None:
    if query.isdigit():
        return int(query)
    rows = con.execute(
        "SELECT npcid, name FROM npc_names WHERE zoneid = ? AND name LIKE ?",
        (zoneid, f"%{query}%"),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        print(f"{len(rows)} name matches -- pass a specific id instead:")
        for npcid, name in rows:
            print(f"  {npcid}  {name!r}")
        return None
    return rows[0][0]


def ensure_export(zone_folder_name: str, ffxi_path: str) -> Path:
    out_dir = MISSION_REPORTS / zone_folder_name
    events_yml = out_dir / "events.yml"
    dialog_yml = out_dir / "dialog.yml"
    if events_yml.exists() and dialog_yml.exists():
        return out_dir
    print(f"[{zone_folder_name}] no cached events/dialog export -- generating via the packaged Mission Toolkit CLI...")
    # the Mission Toolkit CLI's own --out-dir defaults to the RELATIVE path "mission_reports", resolved
    # against the subprocess's cwd -- without cwd=TOOLS_ROOT here, this silently inherited whatever
    # directory the GUI server process itself happened to be started from (e.g. D:\Claude, not
    # D:\Claude\mission_toolkit), writing real generated output to a stray mission_reports/ next to
    # the wrong directory every time. events_yml.exists() below then correctly found nothing at the
    # real path, and the page just rendered "0 events found" with no error -- confirmed live: 12
    # zones' worth of real exports had silently piled up at D:\Claude\mission_reports\ this way.
    result = subprocess.run(
        [sys.executable, "-m", "workbench.devtools.app.mission_toolkit", zone_folder_name, "--ffxi-path", ffxi_path],
        capture_output=True, text=True, cwd=str(TOOLS_ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(f"Mission Toolkit CLI failed:\n{result.stdout}\n{result.stderr}")
    return out_dir


# Matches the decompiler's own inline-comment rendering, e.g. `vm:systemMessage(7465)  -- There...`
# or `npc:dialog(7466, 0, 0)  -- Obtain a temporary item?` -- captures the message id to cross-check.
MESSAGE_ID_RE = re.compile(r"(?:systemMessage|dialog|messageSpecial)\((\d+)")


def cross_check(con: sqlite3.Connection, zoneid: int, decompiled: str) -> list[tuple[int, str, str]]:
    """Returns [(message_id, our_text, note), ...] for every message id referenced, our_text is
    what our own dat-extractor-based index says is really there. note flags disagreement."""
    results = []
    seen = set()
    for m in MESSAGE_ID_RE.finditer(decompiled):
        msg_id = int(m.group(1))
        if msg_id in seen:
            continue
        seen.add(msg_id)
        row = con.execute(
            "SELECT text FROM dialog_text WHERE zoneid = ? AND idx = ?", (zoneid, msg_id)
        ).fetchone()
        our_text = row[0] if row else None
        if our_text is None:
            note = "NOT FOUND in our own dialog_text index"
        else:
            note = "OK"
        results.append((msg_id, our_text, note))
    return results



CALL_SITE_RE = re.compile(
    r"(?P<object>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<method>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)


def summarize_decompile(decompiled: str) -> dict:
    """Extract presentation-only facts from xi-events' decompiled text.

    This intentionally does not assign new semantics to work variables or event parameters.
    It only inventories literal message IDs and method names that the decompiler actually emitted
    so the GUI can make a long CSID easier to navigate.
    """
    message_ids = []
    seen_messages = set()
    for match in MESSAGE_ID_RE.finditer(decompiled or ""):
        msg_id = int(match.group(1))
        if msg_id not in seen_messages:
            seen_messages.add(msg_id)
            message_ids.append(msg_id)

    calls = []
    seen_calls = set()
    for match in CALL_SITE_RE.finditer(decompiled or ""):
        key = (match.group("object"), match.group("method"))
        if key in seen_calls:
            continue
        seen_calls.add(key)
        calls.append({"object": key[0], "method": key[1]})

    return {
        "message_ids": message_ids,
        "calls": calls,
        "message_count": len(message_ids),
        "call_count": len(calls),
        "line_count": len((decompiled or "").splitlines()),
    }


WORK_REF_PATTERNS = (
    ("WorkLocal", re.compile(r"(?:ExtData\[1\]->)?WorkLocal\[(\d+)\]")),
    ("Work_Zone", re.compile(r"Work_Zone\[(\d+)\]")),
    ("Work_Zone_Memorize", re.compile(r"Work_Zone_Memorize\[(\d+)\]")),
    ("Work_Zone_1700", re.compile(r"Work_Zone_1700\[(\d+)\]")),
    ("References", re.compile(r"References\[(\d+)\]")),
)
UPDATE_MARKER_RE = re.compile(r"\b(?:SEND_EVENT_UPDATE|updateEvent|eventUpdate)\b", re.IGNORECASE)


def _split_uninterpreted_params(raw: str) -> list[str]:
    """Split a captured parameter rendering on top-level commas only.

    Values remain strings. Nested braces/brackets/parentheses are preserved and no slot semantics
    are assigned.
    """
    text = str(raw or "").strip()
    if not text:
        return []
    parts, buf = [], []
    depth = 0
    quote = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth:
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf or text.endswith(","):
        parts.append("".join(buf).strip())
    return parts


def event_flow_summary(decompiled: str, capture_rows=None, server_refs=None) -> dict:
    """Inventory literal client work references and observed server/runtime flow evidence.

    This is presentation-only. Work-variable names, parameter slots, and option values are never
    assigned gameplay meaning.
    """
    decompiled = decompiled or ""
    capture_rows = [dict(row) for row in (capture_rows or [])]
    server_refs = [dict(row) for row in (server_refs or [])]

    work_refs = []
    seen_refs = set()
    for family, pattern in WORK_REF_PATTERNS:
        for match in pattern.finditer(decompiled):
            key = (family, int(match.group(1)))
            if key in seen_refs:
                continue
            seen_refs.add(key)
            work_refs.append({"family": family, "index": key[1], "label": f"{family}[{key[1]}]"})
    work_refs.sort(key=lambda row: (row["family"], row["index"]))

    update_markers = []
    for line_no, line in enumerate(decompiled.splitlines(), 1):
        if UPDATE_MARKER_RE.search(line):
            update_markers.append({"line": line_no, "text": line.strip()})

    option_values = {}
    param_slots = {}
    for row in capture_rows:
        option = row.get("option")
        if option is not None:
            bucket = option_values.setdefault(str(option), {"value": option, "observations": []})
            bucket["observations"].append({"capture_id": row.get("capture_id"), "seq": row.get("seq")})
        for index, value in enumerate(_split_uninterpreted_params(row.get("params_raw"))):
            slot = param_slots.setdefault(index, {"index": index, "values": {}})
            val = slot["values"].setdefault(value, {"value": value, "observations": []})
            val["observations"].append({"capture_id": row.get("capture_id"), "seq": row.get("seq")})

    parameter_slots = []
    for index in sorted(param_slots):
        slot = param_slots[index]
        parameter_slots.append({
            "index": index,
            "values": sorted(slot["values"].values(), key=lambda item: item["value"]),
            "value_count": len(slot["values"]),
        })

    stages = []
    for ref in server_refs:
        function = ref.get("function")
        fn = str(function or "")
        lower = fn.lower()
        if "eventupdate" in lower:
            stage = "UPDATE"
        elif "eventfinish" in lower:
            stage = "FINISH"
        elif "trigger" in lower or "trade" in lower:
            stage = "START"
        else:
            stage = "REFERENCE"
        stages.append({
            "stage": stage,
            "source": ref.get("source"),
            "npc_script": ref.get("npc_script"),
            "function": function,
            "path": ref.get("path"),
            "line": ref.get("line"),
            "calls": [call.get("method") for call in (ref.get("calls") or []) if call.get("method")],
        })

    return {
        "work_refs": work_refs,
        "work_ref_count": len(work_refs),
        "update_markers": update_markers,
        "option_values": sorted(option_values.values(), key=lambda row: row["value"]),
        "parameter_slots": parameter_slots,
        "server_stages": stages,
        "notes": [
            "Work-variable references are literal client decompile tokens only.",
            "Captured parameter slots are positional and uninterpreted.",
            "Server stages are classified only from callback/function names.",
        ],
    }


def lua_scaffold(csid: int, observed_options=None, observed_params=None) -> str:
    """Create copyable *scaffolding*, never a claim that these callbacks are sufficient.

    Observed option/param values are emitted only as comments. The generated code deliberately
    avoids inventing engine behavior or interpreting parameter positions.
    """
    observed_options = sorted({int(v) for v in (observed_options or []) if v is not None})
    observed_params = [str(v) for v in (observed_params or []) if v]
    option_note = (
        " -- observed option values: " + ", ".join(map(str, observed_options))
        if observed_options else ""
    )
    param_note = (
        "\n    -- observed capture params (uninterpreted): " + " | ".join(observed_params[:5])
        if observed_params else ""
    )
    return f"""-- Scaffolding only: verify callback/parameter semantics against source + capture evidence.
entity.onTrigger = function(player, npc)
    player:startEvent({int(csid)})
end

entity.onEventUpdate = function(player, csid, option, npc)
    if csid == {int(csid)} then{option_note}{param_note}
        -- TODO: implement only behavior supported by evidence.
    end
end

entity.onEventFinish = function(player, csid, option, npc)
    if csid == {int(csid)} then{option_note}
        -- TODO: apply completion/warp/door/etc. behavior only after verification.
    end
end
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zone", help="Zone folder name under scripts/zones (e.g. Nyzul_Isle)")
    ap.add_argument("entity", help="Entity id, or a name substring to search for in this zone")
    ap.add_argument("csid", type=int, help="Event/CSID number")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    zoneid_row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (args.zone.upper(),)).fetchone()
    if not zoneid_row:
        raise SystemExit(f"Could not resolve zoneid for {args.zone}")
    zoneid = zoneid_row[0]

    entity_id = resolve_entity(con, zoneid, args.entity)
    if entity_id is None:
        raise SystemExit(f"Could not resolve entity {args.entity!r} in {args.zone}")

    out_dir = ensure_export(args.zone, args.ffxi_path)

    result = decompile_event(out_dir, entity_id, args.csid, zoneid)
    if result["error"]:
        raise SystemExit(result["error"])

    decompiled = result["decompiled"]
    print(decompiled)

    print("=" * 70)
    print("Cross-check against our own dialog_text index (dat-extractor, independent of xi-tinkerer):")
    checks = cross_check(con, zoneid, decompiled)
    if not checks:
        print("  (no systemMessage/dialog/messageSpecial calls found to check)")
    for msg_id, our_text, note in checks:
        flag = "  [!]" if note != "OK" else "     "
        preview = (our_text or "")[:80].replace("\n", " ").replace("\r", "")
        print(f"{flag} {msg_id}: {note} -- {preview!r}")

    disasm_path = out_dir / "events_disasm.txt"
    if disasm_path.exists():
        print(f"\nRaw disassembly available for cross-checking: {disasm_path}")

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
