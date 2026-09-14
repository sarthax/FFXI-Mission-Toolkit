#!/usr/bin/env python3
"""
packet_decode.py -- Mission Toolkit GUI, packet decoding.

Not a new decoder -- a thin wrapper around Packetlyzer's own real, working
analyzer.decoder/analyzer.packet_db modules (D:\\Claude\\FFXI-Tools\\Packetlyzer), which already
parse a real VieweD-compatible packet definition DB (318 real opcodes, packetlyzer_db.xml) with
real field types, offsets, and lookup-table resolution (npc names, models, etc.). Reuses it
directly rather than re-deriving field offsets by hand the way this session did for the real
0x02A / RUNE_UNLOCKED_POS packet earlier -- confirmed live that Packetlyzer's own 0x02A
definition (GP_SERV_COMMAND_TALKNUMWORK) lines up exactly with that hand decode (MesNum at byte
26, ActIndex at byte 24, matching the hand-derived Message ID/Player Index offsets).

Two real capabilities this unlocks:
  - "What does this raw captured packet actually mean" -- paste hex + opcode, get named/typed
    fields back, instead of hand-mapping byte offsets.
  - "What is opcode X used for" -- browse/search all 318 real opcodes and their real descriptions.

Note (honest limitation): Packetlyzer's own field granularity doesn't always match Windower's
fields.lua exactly -- e.g. 0x02A's 16-byte "num" block is one opaque field here, where fields.lua
splits it into 4 separate uint32 Params. Both are real, independently-authored sources pointing
at the same offsets; when they disagree on sub-structure, that's the same two-source-agreement
discipline used elsewhere in this toolkit, not a reason to trust one blindly.

Usage:
    py -3 packet_decode.py --opcode 0x02A --direction s2c --hex 2A104E08F8740400AB090000...
    py -3 packet_decode.py --search "dialog"
"""
import argparse
import io
import struct
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent
PACKETLYZER_ROOT = TOOLS_ROOT / "Packetlyzer"
sys.path.insert(0, str(PACKETLYZER_ROOT))

from analyzer.decoder import PacketDecoder, DecodedPacket, DecodedField  # noqa: E402
from analyzer.packet_db import PacketDB  # noqa: E402

DB_XML = PACKETLYZER_ROOT / "packetlyzer_db.xml"
EXT_JSON = PACKETLYZER_ROOT / "packetlyzer_ext.json"
LOOKUP_DIR = PACKETLYZER_ROOT / "lookup"

_decoder: PacketDecoder | None = None


def get_decoder() -> PacketDecoder:
    global _decoder
    if _decoder is None:
        _decoder = PacketDecoder(str(DB_XML), str(EXT_JSON) if EXT_JSON.exists() else None, str(LOOKUP_DIR))
    return _decoder


def parse_hex(hex_str: str) -> bytes:
    """Accepts hex with or without spaces/0x prefixes/newlines -- matches how hex gets pasted
    out of PacketViewer/NPCLogger dumps in practice, not just a clean contiguous string."""
    cleaned = "".join(hex_str.replace("0x", "").replace("0X", "").split())
    if len(cleaned) % 2:
        cleaned = cleaned[:-1]
    return bytes.fromhex(cleaned)


def _split_num_blob(packet: DecodedPacket) -> DecodedPacket:
    """Packetlyzer's own XML defines a real, recurring params blob -- type="a" name="num", always
    a multiple of 4 bytes -- as one opaque raw-hex field on 4 real confirmed opcodes (0x02A
    GP_SERV_COMMAND_TALKNUMWORK size=16, 0x034 GP_SERV_COMMAND_EVENTNUM size=32, 0x05C
    GP_SERV_COMMAND_PENDINGNUM size=32, 0x05D GP_SERV_COMMAND_PENDINGSTR size=36). This is
    genuinely N x int32 Params, not a guess: it's the same real convention Windower's fields.lua
    splits into Param0..ParamN, and the same convention this project's own idview/eventview
    ingestion already normalizes into a comma-separated Params list (see build_capture_index.py's
    IDVIEW2_PARAMS_RE / _ingest_idview_simple_v2) -- this just closes the gap so the STANDALONE
    manual decoder shows the same real breakdown instead of forcing hand-parsing of raw hex.
    Only applies to a field literally named "num" (not e.g. 0x02A's "String" field, also type "a"
    but genuinely a text blob, not param-shaped) -- keeps the original raw row too, for reference."""
    out_fields = []
    for f in packet.fields:
        out_fields.append(f)
        if f.type == "a" and f.name == "num" and isinstance(f.raw_value, (bytes, bytearray)) and len(f.raw_value) % 4 == 0:
            for i in range(0, len(f.raw_value), 4):
                val = struct.unpack_from("<i", f.raw_value, i)[0]
                out_fields.append(DecodedField(
                    name=f"num[{i // 4}]", type="int32 (derived)", raw_value=val,
                    display_value=str(val), out_of_range=False,
                    comment="split from the real N x int32 'num' params blob above",
                ))
    packet.fields = out_fields
    return packet


def decode(direction: str, opcode: int, hex_str: str) -> DecodedPacket:
    raw_bytes = parse_hex(hex_str)
    result = get_decoder().decode(direction, opcode, raw_bytes)
    return _split_num_blob(result)


def get_field_schema(direction: str, opcode: int) -> list[dict] | None:
    """Every real field this opcode's definition declares (name/type/pos/lookup/comment), with NO
    hex required -- lets the decode page show what fields an opcode HAS before/without a real
    packet to decode, as a standing reference. Returns None if this (direction, opcode) has no
    real definition at all (mirrors decoded.has_definition's meaning). Includes the same num[]
    params-blob expansion as decode()/_split_num_blob, so the reference table and the populated-
    after-decode table are shape-identical -- confirmed real convention (0x02A/0x034/0x05C/0x05D),
    not fabricated field names."""
    db = get_decoder()._db
    defn = db._definitions.get((direction, opcode))
    if defn is None:
        return None
    out = []
    for f in defn.fields:
        out.append({"name": f.name, "type": f.type, "pos": f.pos, "size": f.size,
                     "lookup": f.lookup, "comment": f.comment or ""})
        if f.type == "a" and f.name == "num" and f.size and f.size % 4 == 0:
            for i in range(f.size // 4):
                out.append({"name": f"num[{i}]", "type": "int32 (derived)",
                             "pos": f.pos + i * 4, "size": 4, "lookup": None,
                             "comment": "split from the real N x int32 'num' params blob above"})
    return out


def list_opcodes(query: str = "") -> list[dict]:
    """Every real (direction, opcode, description) this DB knows, optionally filtered by a
    substring match on the description or hex opcode. Accesses PacketDB's own _definitions dict
    directly -- no public list-all method exists on the class, and this is read-only research
    tooling, not a reason to add one upstream."""
    db = get_decoder()._db
    results = []
    # Strip an "0x"/"0X" prefix from the query the same way it's already absent from the stored
    # hex comparison string below -- without this, searching "0x00E" (the exact format the
    # opcode input/table both display) never matched anything, since "0x00e" is never a substring
    # of the plain "00e" being compared against.
    query_norm = query.lower().removeprefix("0x")
    for (direction, opcode), defn in db._definitions.items():
        if query_norm and query_norm not in defn.description.lower() and query_norm not in f"{opcode:03x}":
            continue
        results.append({
            "direction": direction, "opcode": opcode, "opcode_hex": f"0x{opcode:03X}",
            "description": defn.description, "field_count": len(defn.fields),
        })
    results.sort(key=lambda r: (r["direction"], r["opcode"]))
    return results


# 2026-09-04: real category taxonomy, extrapolated from the actual 318 opcode descriptions in
# packetlyzer_db.xml (not a guessed handful) -- grepped every real GP_CLI_COMMAND_*/GP_SERV_COMMAND_*
# name and grouped by the keyword clusters that actually recur, so a capture's real opcode mix
# determines the categories, not the other way around. Checked in order -- first match wins, since
# a few names are ambiguous (e.g. GUILD_BUY/GUILD_SELL are shop-shaped but use GUILD_ instead of
# SHOP_). Kept here (not in gui_server.py) so any consumer of packet_decode.py gets the same
# classification, not a second guess.
CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("dialog_npc", (
        "EVENT", "TALK", "CHAT", "TELL", "MES", "NPC", "LINK_CONCIERGE", "INSPECT_MESSAGE",
    )),
    ("item_shop", (
        "ITEM", "INVENTORY", "SHOP", "BAZAAR", "GUILD_BUY", "GUILD_SELL", "GUILD_OPEN", "TRADE",
        "DELIVERY", "AUC", "CURRENCIES", "RECIPE", "SYNTH", "COMBINE", "DIG", "FISH",
        "SCENARIOITEM",
    )),
    ("battle", (
        "ACTION", "EFFECT", "BATTLE", "MAGICSCHEDULOR", "MAPSCHEDULOR", "BUFF", "CLISTATUS",
        "CHARACTER STATS", "CHARACTER UPDATE", "ABIL_RECAST", "WPOS", "MOTIONMES",
    )),
    ("quest_mission", (
        "MISSION", "CONQUEST", "ROE_", "DUNGEON", "BATTLEFIELD", "TROPHY", "KEYITEM",
    )),
    ("social_group", (
        "GROUP", "PARTY", "LINKSHELL", "FRIEND", "BLACK_LIST", "BLACK_EDIT", "ASSIST",
        "SWITCH_", "COMLINK", "LSMSG", "LSPRIV",
    )),
    ("housing_minigame", (
        "MYROOM", "CHOCOBO", "BALLISTA", "DICE", "PLANT", "HARVEST",
    )),
    ("gm_debug", (
        "_GM", "GMCOMMAND", "DEBUG", "UNKNOWN", "FAQ_", "ACK_GMMSG", "TEST PACKET",
    )),
    ("character_system", (
        "LOGIN", "LOGOUT", "ZONE", "GAMEOK", "NETEND", "POSITION", "CLIENT UPDATE", "CONFIG",
        "PREFERENCE", "EQUIP", "JOB", "MERIT", "ALTER_EGO", "MASTERY", "UNITY", "EMOTE",
        "SUBMAP", "PACKETCONTROL", "NARAKU", "REGISTRATION", "WEATHER", "MUSIC", "CAMP", "SIT",
        "JUMP", "RESCUE", "TRACKING", "PLAYER UPDATE", "ENTITY_UPDATE", "ENTITY_VIS",
        "MOUNT_DATA", "GLOBALUNIQUENO",
    )),
]


def categorize_opcode(description: str) -> str:
    """Maps a real opcode description (packet_class name or GP_*_COMMAND_* constant) to one of
    CATEGORY_RULES' real, data-derived categories. Falls back to 'other' rather than guessing --
    an unclassified opcode is more honest than a wrong bucket."""
    upper = description.upper()
    for category, keywords in CATEGORY_RULES:
        if any(kw in upper for kw in keywords):
            return category
    return "other"


def list_categories() -> list[str]:
    return [c for c, _ in CATEGORY_RULES] + ["other"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opcode", help="Opcode, e.g. 0x02A or 42")
    ap.add_argument("--direction", choices=["s2c", "c2s"], default="s2c")
    ap.add_argument("--hex", help="Raw packet hex bytes")
    ap.add_argument("--search", help="Search opcode descriptions")
    args = ap.parse_args()

    if args.search:
        for r in list_opcodes(args.search):
            print(f"  [{r['direction']}] {r['opcode_hex']}  {r['description']}  ({r['field_count']} fields)")
        return

    if not args.opcode or not args.hex:
        ap.error("Provide --opcode and --hex, or --search")

    opcode_int = int(args.opcode, 0)
    result = decode(args.direction, opcode_int, args.hex)
    print(f"{result.description} ({'has definition' if result.has_definition else 'NO DEFINITION FOUND'})")
    for f in result.fields:
        flag = "  [out of range]" if f.out_of_range else ""
        print(f"  {f.name} ({f.type}) = {f.display_value}{flag}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
