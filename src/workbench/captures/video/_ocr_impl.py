#!/usr/bin/env python3
"""
youtube_chat_ocr.py -- pull a YouTube FFXI playthrough, crop its chat-log box, OCR the scrolled
text, and fuzzy-match the result against this toolkit's own `dialog_text_fts` index (built by
build_dialog_index.py) so raw OCR output gets corrected against real client dialog text instead
of being trusted verbatim.

Pipeline stages (each is its own subcommand so you can inspect/redo any one step):
    download   yt-dlp -> mp4 under mission_reports_v2/_ocr_runs/<run_id>/source.mp4
    frames     ffmpeg crop+fps -> raw cropped frames under .../frames/*.png
    dedupe     drop near-identical consecutive frames (perceptual hash) -> .../frames_unique/
    ocr        pytesseract over the deduped frames -> .../ocr_raw.jsonl (one line per frame)
    match      fuzzy-match each OCR line against dialog_text_fts (optionally scoped to --zone)
               -> .../ocr_matched.jsonl + a plain-text transcript
    run        does all five stages back to back for one URL

Usage:
    py -3 youtube_chat_ocr.py run "<youtube-url>" --crop 40,760,760,260 --zone Nyzul_Isle
    py -3 youtube_chat_ocr.py download "<youtube-url>"
    py -3 youtube_chat_ocr.py frames <run_id> --crop 40,760,760,260 --fps 2
    py -3 youtube_chat_ocr.py dedupe <run_id>
    py -3 youtube_chat_ocr.py ocr <run_id>
    py -3 youtube_chat_ocr.py match <run_id> --zone Nyzul_Isle

Requires external tools NOT installed by requirements.txt. All three can be one-click installed
from the OCR page's Prerequisites section (backed by install_external_tools.py), or manually:
    yt-dlp    pip install yt-dlp (or a standalone binary on PATH)
    ffmpeg    a vendored copy lives at vendor/ffmpeg/bin/ (gyan.dev Windows essentials build) and
              is used automatically if ffmpeg isn't found on PATH -- see resolve_tool()
    tesseract a vendored copy lives at vendor/tesseract/ (UB-Mannheim Windows build, installed
              silently via install_external_tools.install_tesseract()) and is used automatically
              if tesseract isn't found on PATH -- see resolve_tool(); also needs
              `pip install pytesseract`
--crop is "x,y,w,h" in source-video pixels -- the fixed on-screen box FFXI draws its chat log in
for a given recording's resolution/UI scale. There is no single universal box: measure it once per
video (or per capturer's settings) with a paused frame in any image viewer, and reuse it for the
rest of that same recording.
"""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
RUNS_ROOT = TOOLS_ROOT / "mission_reports_v2" / "_ocr_runs"
# Cumulative (total_seconds, total_frames) across every completed OCR run on this machine, so a
# future run can estimate its own duration before starting instead of the page just sitting there
# with no idea how long tesseract will take. Keyed by machine, not per-run, since frame count is
# the only real variable (crop size/upscale factor are fixed by cmd_ocr itself).
OCR_TIMING_PATH = RUNS_ROOT / "_ocr_timing.json"
# Prebuilt Windows ffmpeg (gyan.dev essentials build) lives here when it's not on system PATH --
# see resolve_tool(). tesseract's real UB-Mannheim Windows installer (run silently via
# install_external_tools.install_tesseract()) vendors to VENDOR_TESSERACT_DIR the same way.
VENDOR_FFMPEG_BIN = TOOLS_ROOT / "vendor" / "ffmpeg" / "bin"
VENDOR_TESSERACT_DIR = TOOLS_ROOT / "vendor" / "tesseract"
_VENDOR_BIN_DIRS = {"ffmpeg": VENDOR_FFMPEG_BIN, "ffprobe": VENDOR_FFMPEG_BIN, "tesseract": VENDOR_TESSERACT_DIR}
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SAFE_SECTION_RE = re.compile(r"^[a-z0-9_]{1,96}$")
_FRAME_RE = re.compile(r"^f_(\d+)\.png(?:#\d+)?$")


def _contained_child(root: Path, value: str, pattern: re.Pattern, kind: str) -> Path:
    if not pattern.fullmatch(value or ""):
        sys.exit(f"[youtube_chat_ocr] invalid {kind}: {value!r}")
    root_resolved = root.resolve()
    candidate = (root_resolved / value).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        sys.exit(f"[youtube_chat_ocr] {kind} escapes OCR root: {value!r}")
    return candidate


def _run_path(run_id: str) -> Path:
    return _contained_child(RUNS_ROOT, run_id, _SAFE_RUN_ID_RE, "run_id")


def run_dir(run_id: str) -> Path:
    d = _run_path(run_id)
    if not d.exists():
        sys.exit(f"[youtube_chat_ocr] no run '{run_id}' under {RUNS_ROOT} -- run 'download' first")
    return d


DEFAULT_SECTION_LABEL = "chat"

# A section's "capture profile" selects how its OCR'd lines get parsed into structured fields at
# match time. FFXI's chat window layout isn't fixed -- timestamps are an optional client setting,
# channels can be split across multiple user-arranged windows, and some players run plugins that
# consolidate/reformat chat -- so this is a per-section choice, not a global assumption.
CAPTURE_PROFILE_PLAIN = "plain"
CAPTURE_PROFILE_TIMESTAMPED = "timestamped"
CAPTURE_PROFILE_PACKETLOGGER = "packetlogger"
CAPTURE_PROFILE_CAPTUREBAR = "capturebar"
CAPTURE_PROFILES = [
    CAPTURE_PROFILE_PLAIN,
    CAPTURE_PROFILE_TIMESTAMPED,
    CAPTURE_PROFILE_PACKETLOGGER,
    CAPTURE_PROFILE_CAPTUREBAR,
]
DEFAULT_CAPTURE_PROFILE = CAPTURE_PROFILE_PLAIN

PREPROCESS_PROFILE_STANDARD = "standard"
PREPROCESS_PROFILE_CHAT = "chat"
PREPROCESS_PROFILE_PACKET = "packet_overlay"
PREPROCESS_PROFILE_SMALL = "small_overlay"
PREPROCESS_PROFILES = {
    PREPROCESS_PROFILE_STANDARD: {
        "label": "Standard grayscale",
        "description": "Grayscale, autocontrast, 3x upscale, Tesseract PSM 6.",
        "scale": 3,
        "autocontrast": True,
        "threshold": None,
        "invert": False,
        "sharpen": False,
        "psm": 6,
    },
    PREPROCESS_PROFILE_CHAT: {
        "label": "FFXI chat",
        "description": "Grayscale, autocontrast, mild sharpen, 3x upscale, PSM 6.",
        "scale": 3,
        "autocontrast": True,
        "threshold": None,
        "invert": False,
        "sharpen": True,
        "psm": 6,
    },
    PREPROCESS_PROFILE_PACKET: {
        "label": "EView / packet overlay",
        "description": "High-contrast thresholded overlay text, 4x upscale, PSM 6.",
        "scale": 4,
        "autocontrast": True,
        "threshold": 150,
        "invert": False,
        "sharpen": True,
        "psm": 6,
    },
    PREPROCESS_PROFILE_SMALL: {
        "label": "Small overlay text",
        "description": "Aggressive upscale/sharpen for compact addon overlays, PSM 6.",
        "scale": 5,
        "autocontrast": True,
        "threshold": None,
        "invert": False,
        "sharpen": True,
        "psm": 6,
    },
}
DEFAULT_PREPROCESS_PROFILE = PREPROCESS_PROFILE_STANDARD
LAYOUT_PROFILE_PATH = TOOLS_ROOT / "mission_reports_v2" / "_ocr_layout_profiles.json"
_BUILTIN_LAYOUT_PROFILES = {
    "chat_only": {
        "name": "Chat only",
        "description": "One FFXI chat-log region. Coordinates must be filled from a saved real setup.",
        "regions": [{
            "label": "chat",
            "crop": None,
            "fps": 2.0,
            "capture_profile": CAPTURE_PROFILE_PLAIN,
            "preprocess_profile": PREPROCESS_PROFILE_CHAT,
        }],
        "builtin": True,
    },
    "eview_packet": {
        "name": "EView packet overlay",
        "description": "One EView/packet overlay region. Coordinates must be filled from a saved real setup.",
        "regions": [{
            "label": "eview",
            "crop": None,
            "fps": 2.0,
            "capture_profile": CAPTURE_PROFILE_PACKETLOGGER,
            "preprocess_profile": PREPROCESS_PROFILE_PACKET,
        }],
        "builtin": True,
    },
    "npclogger_overlay": {
        "name": "NPCLogger overlay",
        "description": "One compact NPCLogger/addon overlay region; plain OCR with small-text preprocessing.",
        "regions": [{
            "label": "npclogger",
            "crop": None,
            "fps": 2.0,
            "capture_profile": CAPTURE_PROFILE_PLAIN,
            "preprocess_profile": PREPROCESS_PROFILE_SMALL,
        }],
        "builtin": True,
    },
    "capturebar_overlay": {
        "name": "Capturebar overlay",
        "description": (
            "Wiggo32 Capturebar default HUD format: zone, target/player, X/Z/Y coordinates, "
            "rotation, jobs/levels, and moon percent/phase. Configure the real crop before use."
        ),
        "regions": [{
            "label": "capturebar",
            "crop": None,
            "fps": 2.0,
            "capture_profile": CAPTURE_PROFILE_CAPTUREBAR,
            "preprocess_profile": PREPROCESS_PROFILE_SMALL,
        }],
        "builtin": True,
    },
    "research_combo": {
        "name": "Research combo",
        "description": "Chat + EView + NPCLogger region roles. Save a real coordinate layout before reuse.",
        "regions": [
            {"label": "chat", "crop": None, "fps": 2.0, "capture_profile": CAPTURE_PROFILE_PLAIN, "preprocess_profile": PREPROCESS_PROFILE_CHAT},
            {"label": "eview", "crop": None, "fps": 2.0, "capture_profile": CAPTURE_PROFILE_PACKETLOGGER, "preprocess_profile": PREPROCESS_PROFILE_PACKET},
            {"label": "npclogger", "crop": None, "fps": 2.0, "capture_profile": CAPTURE_PROFILE_PLAIN, "preprocess_profile": PREPROCESS_PROFILE_SMALL},
            {"label": "capturebar", "crop": None, "fps": 2.0, "capture_profile": CAPTURE_PROFILE_CAPTUREBAR, "preprocess_profile": PREPROCESS_PROFILE_SMALL},
        ],
        "builtin": True,
    },
}

def list_preprocess_profiles() -> list[dict]:
    return [
        {"id": key, **value}
        for key, value in PREPROCESS_PROFILES.items()
    ]


def load_layout_profiles() -> dict:
    profiles = {key: dict(value) for key, value in _BUILTIN_LAYOUT_PROFILES.items()}
    if LAYOUT_PROFILE_PATH.exists():
        try:
            saved = json.loads(LAYOUT_PROFILE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        for key, value in (saved or {}).items():
            if not isinstance(value, dict):
                continue
            item = dict(value)
            item["builtin"] = False
            profiles[key] = item
    for item in profiles.values():
        regions = item.get("regions") or []
        item["applicable"] = bool(regions) and all(region.get("crop") for region in regions)
    return profiles


def save_layout_profile(profile_id: str, name: str, regions: list[dict], description: str = "") -> dict:
    profile_id = section_slug(profile_id)
    if profile_id in _BUILTIN_LAYOUT_PROFILES:
        raise ValueError("cannot overwrite a built-in layout profile")
    clean_regions = []
    for region in regions:
        crop = region.get("crop")
        if not crop:
            raise ValueError("saved layout regions require real crop coordinates")
        preprocess = region.get("preprocess_profile") or DEFAULT_PREPROCESS_PROFILE
        if preprocess not in PREPROCESS_PROFILES:
            raise ValueError(f"unknown preprocess profile: {preprocess}")
        capture = region.get("capture_profile") or DEFAULT_CAPTURE_PROFILE
        if capture not in CAPTURE_PROFILES:
            raise ValueError(f"unknown capture profile: {capture}")
        clean_regions.append({
            "label": region.get("label") or "section",
            "crop": crop,
            "fps": float(region.get("fps") or 2.0),
            "capture_profile": capture,
            "preprocess_profile": preprocess,
        })
    LAYOUT_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    saved = {}
    if LAYOUT_PROFILE_PATH.exists():
        try:
            saved = json.loads(LAYOUT_PROFILE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
    saved[profile_id] = {
        "name": name.strip() or profile_id,
        "description": description.strip(),
        "regions": clean_regions,
    }
    LAYOUT_PROFILE_PATH.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"id": profile_id, **saved[profile_id], "builtin": False}


def delete_layout_profile(profile_id: str) -> bool:
    if profile_id in _BUILTIN_LAYOUT_PROFILES or not LAYOUT_PROFILE_PATH.exists():
        return False
    try:
        saved = json.loads(LAYOUT_PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if profile_id not in saved:
        return False
    del saved[profile_id]
    LAYOUT_PROFILE_PATH.write_text(json.dumps(saved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def save_run_layout(run_id: str, profile_id: str, name: str, description: str = "") -> dict:
    regions = []
    for section in list_sections(run_id):
        meta = section_meta(run_id, section)
        if not meta.get("crop"):
            continue
        regions.append({
            "label": meta.get("label") or section,
            "crop": meta.get("crop"),
            "fps": meta.get("fps") or 2.0,
            "capture_profile": meta.get("capture_profile") or DEFAULT_CAPTURE_PROFILE,
            "preprocess_profile": meta.get("preprocess_profile") or DEFAULT_PREPROCESS_PROFILE,
        })
    if not regions:
        raise ValueError("run has no configured OCR sections to save")
    return save_layout_profile(profile_id, name, regions, description)


def apply_layout_profile(run_id: str, profile_id: str) -> list[str]:
    profiles = load_layout_profiles()
    profile = profiles.get(profile_id)
    if not profile:
        raise ValueError(f"unknown layout profile: {profile_id}")
    created = []
    for region in profile.get("regions") or []:
        crop = region.get("crop")
        if not crop:
            raise ValueError(
                f"layout profile {profile_id!r} is a template without coordinates; configure sections and save a real layout first"
            )
        cmd_frames(argparse.Namespace(
            run_id=run_id,
            crop=crop,
            fps=float(region.get("fps") or 2.0),
            section=region.get("label") or "section",
            profile=region.get("capture_profile") or DEFAULT_CAPTURE_PROFILE,
            preprocess=region.get("preprocess_profile") or DEFAULT_PREPROCESS_PROFILE,
        ))
        created.append(section_slug(region.get("label") or "section"))
    return created


# Known FFXI chat channel prefixes as they render in the default client log (case-sensitive on
# purpose -- OCR noise on lowercase/garbled text should fall through to "unknown" rather than
# guess).
_CHANNEL_PREFIXES = [
    "Say", "Shout", "Yell", "Party", "Linkshell", "Linkshell2", "Tell", "Emote", "System", "NPC",
]
_TIMESTAMP_RE = re.compile(r"^\[?\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*\]?\s*(.*)$")
_CHANNEL_RE = re.compile(r"^(" + "|".join(_CHANNEL_PREFIXES) + r")\s*[:>]\s*(.*)$")
_TELL_RE = re.compile(r"^(?:Tell|>>)\s*(?:from|to)?\s*([A-Za-z']{3,15})\s*[:>]\s*(.*)$")
# Best-effort hint only -- NOT a decoded opcode/CSID. Surfaced alongside the real EView parse below
# in case a token shows up somewhere the header/field parser doesn't reach (garbled OCR, a packet
# format this project hasn't seen a real sample of yet); it never claims to identify what a token
# means on its own.
_HEX_TOKEN_RE = re.compile(r"\b0x[0-9A-Fa-f]{2,6}\b|\b[0-9A-Fa-f]{4}\b")

# Real EView packet-log header shape, confirmed against an actual in-game capture screenshot
# (2026-09-27): "<< [0x036] GP_SERV_COMMAND_TALKNUM" (overlay box) and the same line prefixed with
# "[EView] " in the scrolling log pane below it. This mirrors build_capture_index.py's
# CAPLOG_EVIEW_HEADER_RE for real CapLog *files* of the same tool's output -- that regex requires a
# trailing "(PacketClass)" which this on-screen overlay does not render, so the group here is
# optional rather than a new, unrelated format.
_EVIEW_HEADER_RE = re.compile(
    r'(?:\[EView\]\s*)?(<<|>>)\s*\[(0x[0-9A-Fa-f]{2,4})\]\s*(\w+)\*?\s*(?:\(([^)]*)\))?'
)

# A real field key is always a bare identifier ("UniqueNo", "num[]", "Flag") -- OCR noise glued onto
# a field line by a bad line-break (see parse_packetlogger_block) produces "keys" that are actually
# whole garbled sentences containing a stray ':'. Reject anything that isn't identifier-shaped so
# that noise gets dropped instead of showing up as a corrupted field.
_EVIEW_KEY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_\[\]]{0,31}$')


def _parse_eview_fields(line: str) -> dict[str, str]:
    """'Key: val, Key2: val2, num[]: {1, 2, 3}' -> {"Key": "val", ...}. Brace-depth tracked so a
    comma inside a real array field never breaks a field boundary -- same approach as
    build_capture_index.py's _parse_caplog_eview_fields, kept as a local copy here since this
    module OCRs a live on-screen overlay rather than parsing an exported CapLog text file and the
    two shouldn't be coupled by import. Also tolerates the overlay box's own rendering, which uses
    2+ spaces instead of commas between fields on one line ("Key: val  Key2: val2") -- that gets
    normalized to commas before the same brace-aware split runs."""
    normalized = re.sub(r"\s{2,}(?=[A-Za-z_]+:)", ", ", line)
    fields: dict[str, str] = {}
    depth = 0
    buf, parts = [], []
    for ch in normalized:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    for part in parts:
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        key, val = key.strip(), val.strip()
        if key and _EVIEW_KEY_RE.match(key):
            fields[key] = val
    return fields


def parse_packetlogger_block(raw_text: str) -> list[dict]:
    """Parse one OCR'd frame's full (multi-line) text from an EView-style packet overlay/log crop.
    Unlike chat profiles, this needs the ORIGINAL line breaks tesseract produced -- the header line
    ("<< [0x036] GP_SERV_COMMAND_TALKNUM") and its field line ("UniqueNo: ..., MesNum: ...") are
    two separate on-screen lines, and flattening them to one string first (as the chat profiles do)
    would make them unparseable as one blob.

    The overlay panel shows packet HISTORY, not just the latest packet -- a single frame routinely
    has two or more "<< [0xNNN] GP_..." headers stacked on screen at once. Returns one dict per
    header found (each with only the field lines that appeared under it), so those don't get merged
    into one corrupted record. A frame with no recognizable header at all still returns a single
    dict with header fields None, so pure-noise frames remain visible as unparsed rows rather than
    silently vanishing. Header detection tolerates OCR garbage stuck to the front of the line (a
    misread glyph before "<<") by searching the line instead of anchoring to its start."""
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    segments: list[tuple] = []  # (header_groups_or_None, [field_lines])
    for line in lines:
        m = _EVIEW_HEADER_RE.search(line)
        if m:
            segments.append((m.groups(), []))
        elif segments:
            segments[-1][1].append(line)
        else:
            segments.append((None, [line]))
    if not segments:
        segments = [(None, [])]

    results = []
    for header, field_lines in segments:
        field_blob = "  ".join(field_lines)
        fields = _parse_eview_fields(field_blob) if field_blob else {}
        direction, opcode, gp_command, packet_class = header if header else (None, None, None, None)
        seg_lines = ([f"{header[0]} [{header[1]}] {header[2]}"] if header else []) + field_lines
        results.append({
            "timestamp": None,
            "channel": "packet",
            "speaker": None,
            "text": " / ".join(seg_lines) if seg_lines else raw_text.strip(),
            "direction": direction,
            "opcode": opcode,
            "gp_command": gp_command,
            "packet_class": packet_class,
            "fields": fields or None,
            "hex_hints": _HEX_TOKEN_RE.findall(field_blob) or None,
        })
    return results


def _packet_direction_key(direction: str | None) -> str | None:
    if direction == "<<":
        return "s2c"
    if direction == ">>":
        return "c2s"
    return None


def _best_unique_symbol(raw: str | None, candidates: list[str], min_score: float = 0.78, min_margin: float = 0.08):
    """Return a conservative fuzzy symbol correction candidate.

    The raw token is never modified here.  A candidate is accepted only when the best score is
    high enough and clearly separated from the runner-up.
    """
    if not raw:
        return None
    norm = raw.strip()
    if not norm:
        return None
    scored = sorted(
        ((SequenceMatcher(None, norm.lower(), cand.lower()).ratio(), cand) for cand in set(candidates) if cand),
        reverse=True,
    )
    if not scored:
        return None
    best_score, best = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if best_score < min_score or (best_score - second_score) < min_margin:
        return None
    return {
        "raw": raw,
        "candidate": best,
        "score": round(best_score, 4),
        "runner_up_score": round(second_score, 4),
        "margin": round(best_score - second_score, 4),
    }


def packet_symbol_assistance(parsed: dict) -> dict:
    """Suggest structural packet corrections from the toolkit's packet definition index.

    Raw OCR/parser output remains under raw_parsed.  Corrections are suggestions with provenance,
    never silent replacement.  Packet name and field keys may be corrected; field VALUES are
    deliberately never fuzzy-corrected.
    """
    raw_parsed = {
        "direction": parsed.get("direction"),
        "opcode": parsed.get("opcode"),
        "gp_command": parsed.get("gp_command"),
        "packet_class": parsed.get("packet_class"),
        "fields": dict(parsed.get("fields") or {}),
    }
    result = {"raw_parsed": raw_parsed, "corrections": [], "effective_packet": dict(raw_parsed)}
    direction_key = _packet_direction_key(parsed.get("direction"))
    if direction_key is None:
        return result

    try:
        from workbench.packets import decode as packet_decode
        opcode_defs = [row for row in packet_decode.list_opcodes("") if row["direction"] == direction_key]
    except Exception as exc:
        result["symbol_index_error"] = str(exc)
        return result

    raw_opcode = parsed.get("opcode")
    raw_name = parsed.get("gp_command")
    candidate_def = None

    if raw_opcode:
        try:
            opcode_int = int(str(raw_opcode), 16) if str(raw_opcode).lower().startswith("0x") else int(str(raw_opcode), 0)
        except (TypeError, ValueError):
            opcode_int = None
        if opcode_int is not None:
            candidate_def = next((row for row in opcode_defs if row["opcode"] == opcode_int), None)

    if candidate_def is None and raw_name:
        symbol = _best_unique_symbol(raw_name, [row["description"] for row in opcode_defs], min_score=0.76, min_margin=0.07)
        if symbol:
            candidate_def = next(row for row in opcode_defs if row["description"] == symbol["candidate"])
            result["corrections"].append({
                "kind": "packet_symbol",
                **symbol,
                "source": "packet_decode.list_opcodes",
            })

    if candidate_def is not None:
        canonical_opcode = candidate_def["opcode_hex"].lower()
        canonical_name = candidate_def["description"]
        if raw_opcode and str(raw_opcode).lower() != canonical_opcode:
            result["corrections"].append({
                "kind": "opcode_from_packet_definition",
                "raw": raw_opcode,
                "candidate": canonical_opcode,
                "score": 1.0 if raw_name == canonical_name else None,
                "source": canonical_name,
            })
        if raw_name and raw_name != canonical_name:
            existing = next((c for c in result["corrections"] if c["kind"] == "packet_symbol"), None)
            if existing is None:
                name_score = SequenceMatcher(None, raw_name.lower(), canonical_name.lower()).ratio()
                if name_score >= 0.76:
                    result["corrections"].append({
                        "kind": "packet_symbol",
                        "raw": raw_name,
                        "candidate": canonical_name,
                        "score": round(name_score, 4),
                        "source": "opcode_definition",
                    })
        result["effective_packet"]["opcode"] = canonical_opcode
        result["effective_packet"]["gp_command"] = canonical_name

        try:
            schema = packet_decode.get_field_schema(direction_key, candidate_def["opcode"]) or []
        except Exception:
            schema = []
        known_fields = [row["name"] for row in schema if row.get("name")]
        corrected_fields = {}
        field_key_corrections = []
        for key, value in (parsed.get("fields") or {}).items():
            if key in known_fields:
                corrected_fields[key] = value
                continue
            suggestion = _best_unique_symbol(key, known_fields, min_score=0.72, min_margin=0.08)
            if suggestion:
                corrected_fields[suggestion["candidate"]] = value
                field_key_corrections.append({
                    "kind": "field_symbol",
                    **suggestion,
                    "source": canonical_name,
                })
            else:
                corrected_fields[key] = value
        if field_key_corrections:
            result["corrections"].extend(field_key_corrections)
            result["effective_packet"]["fields"] = corrected_fields

    result["symbol_assisted"] = bool(result["corrections"])
    return result


def _packet_consensus_key(record: dict) -> tuple:
    effective = record.get("effective_packet") or {}
    return (
        effective.get("direction") or record.get("direction"),
        effective.get("opcode") or record.get("opcode"),
        effective.get("gp_command") or record.get("gp_command"),
    )


def apply_cross_frame_consensus(records: list[dict], max_gap_seconds: float = 1.5) -> list[dict]:
    """Attach conservative consensus metadata across nearby observations of the same packet.

    EView commonly shows a STACK of historical packets in each frame, so observations of packet A
    may be interleaved with B/C records from the same frame.  Clustering is therefore per
    structural identity, not simple list adjacency. Field VALUES vote independently by exact text;
    ties remain unresolved instead of being guessed.
    """
    by_key: dict[tuple, list[dict]] = {}
    for record in records:
        key = _packet_consensus_key(record)
        if any(key):
            by_key.setdefault(key, []).append(record)

    clusters: list[list[dict]] = []
    clustered_ids = set()
    for key_records in by_key.values():
        ordered = sorted(
            key_records,
            key=lambda r: (
                float(r.get("video_timestamp_seconds")) if r.get("video_timestamp_seconds") is not None else float("inf"),
                str(r.get("frame") or ""),
            ),
        )
        current: list[dict] = []
        last_ts = None
        for record in ordered:
            ts = record.get("video_timestamp_seconds")
            close = (
                current
                and ts is not None and last_ts is not None
                and 0 <= float(ts) - float(last_ts) <= max_gap_seconds
            )
            if not close:
                if current:
                    clusters.append(current)
                current = [record]
            else:
                current.append(record)
            last_ts = ts
        if current:
            clusters.append(current)

    for cluster in clusters:
        for record in cluster:
            clustered_ids.add(id(record))
        if len(cluster) < 2:
            cluster[0]["consensus"] = {
                "support": 1,
                "source_frames": [cluster[0].get("frame")],
                "applied": False,
            }
            continue
        field_votes: dict[str, dict[str, int]] = {}
        for record in cluster:
            effective = record.get("effective_packet") or {}
            for key, value in (effective.get("fields") or record.get("fields") or {}).items():
                field_votes.setdefault(key, {}).setdefault(str(value), 0)
                field_votes[key][str(value)] += 1

        consensus_fields = {}
        unresolved = {}
        for key, votes in field_votes.items():
            ranked = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
            if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
                consensus_fields[key] = ranked[0][0]
            else:
                unresolved[key] = dict(ranked)

        source_frames = [r.get("frame") for r in cluster]
        for record in cluster:
            effective = dict(record.get("effective_packet") or {})
            if consensus_fields:
                effective["fields"] = dict(consensus_fields)
            record["effective_packet"] = effective
            record["consensus"] = {
                "support": len(cluster),
                "source_frames": source_frames,
                "applied": True,
                "field_votes": field_votes,
                "unresolved_fields": unresolved or None,
            }

    for record in records:
        if id(record) not in clustered_ids:
            record["consensus"] = {
                "support": 1,
                "source_frames": [record.get("frame")],
                "applied": False,
            }
    return records


_CAPTUREBAR_RE = re.compile(
    r'^\s*\[(?P<zone_id>\d+)\](?P<zone_name>.+?)\s+-\s+'
    r'(?P<target_name>.+?)\s+'
    r'\((?P<x>-?\d+(?:\.\d+)?),(?P<z>-?\d+(?:\.\d+)?),(?P<y>-?\d+(?:\.\d+)?)\)\s+'
    r'R\((?P<rotation>-?\d+)\)\s+'
    r'\((?P<main_job>[A-Za-z?]+)(?P<main_level>\d+)?/'
    r'(?P<sub_job>[A-Za-z?]+)(?P<sub_level>\d+)?\)\s+'
    r'Moon:\s*(?P<moon_pct>\d{1,3})%\s+(?P<moon_phase>.+?)\s*$'
)


def parse_capturebar_line(text: str) -> dict:
    """Parse Wiggo32 Capturebar's default rendered HUD without guessing missing values.

    Capturebar renders coordinates in X,Z,Y order. The returned field names preserve their
    semantic axes rather than their visual position.
    """
    match = _CAPTUREBAR_RE.match(text or "")
    if not match:
        return {
            "timestamp": None,
            "channel": "capturebar",
            "speaker": None,
            "text": text,
            "fields": None,
            "capturebar_parsed": False,
        }
    g = match.groupdict()
    fields = {
        "zone_id": int(g["zone_id"]),
        "zone_name": g["zone_name"].strip(),
        "target_name": g["target_name"].strip(),
        "x": float(g["x"]),
        "y": float(g["y"]),
        "z": float(g["z"]),
        "coordinate_display_order": "x,z,y",
        "rotation": int(g["rotation"]),
        "main_job": g["main_job"],
        "main_job_level": int(g["main_level"]) if g.get("main_level") else None,
        "sub_job": g["sub_job"],
        "sub_job_level": int(g["sub_level"]) if g.get("sub_level") else None,
        "moon_percent": int(g["moon_pct"]),
        "moon_phase": g["moon_phase"].strip(),
    }
    return {
        "timestamp": None,
        "channel": "capturebar",
        "speaker": None,
        "text": text,
        "fields": fields,
        "capturebar_parsed": True,
    }


def parse_capture_line(profile: str, text: str) -> dict:
    """Turn one OCR'd (post dialog-match) line into structured fields per the section's capture
    profile. Never fabricates a value it can't actually find in the text -- fields it can't
    confidently parse come back None/empty rather than guessed. NOTE: packetlogger is handled
    separately by parse_packetlogger_block() since it needs the pre-flattened multi-line text;
    cmd_match() branches on profile before calling either."""
    if profile == CAPTURE_PROFILE_CAPTUREBAR:
        return parse_capturebar_line(text)
    if profile == CAPTURE_PROFILE_TIMESTAMPED:
        m = _TIMESTAMP_RE.match(text)
        timestamp, rest = (m.group(1), m.group(2)) if m else (None, text)
        tm = _TELL_RE.match(rest)
        if tm:
            return {"timestamp": timestamp, "channel": "Tell", "speaker": tm.group(1), "text": tm.group(2)}
        cm = _CHANNEL_RE.match(rest)
        if cm:
            return {"timestamp": timestamp, "channel": cm.group(1), "speaker": None, "text": cm.group(2)}
        return {"timestamp": timestamp, "channel": None, "speaker": None, "text": rest}
    # plain (default): channel splitting is still attempted since it costs nothing and a lot of
    # users leave channel prefixes on even with timestamps off, but timestamp is never guessed.
    tm = _TELL_RE.match(text)
    if tm:
        return {"timestamp": None, "channel": "Tell", "speaker": tm.group(1), "text": tm.group(2)}
    cm = _CHANNEL_RE.match(text)
    if cm:
        return {"timestamp": None, "channel": cm.group(1), "speaker": None, "text": cm.group(2)}
    return {"timestamp": None, "channel": None, "speaker": None, "text": text}


def section_slug(label: str) -> str:
    """Filesystem-safe directory name for a user-given section label ('Chat Log', 'NPCLogger
    overlay', ...) -- collisions on the same slug intentionally re-use/overwrite that section
    rather than creating a near-duplicate, same as re-running 'frames' always did pre-sections."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "section"


def section_dir(run_id: str, section: str) -> Path:
    run = run_dir(run_id)
    sections_root = (run / "sections").resolve()
    return _contained_child(sections_root, section, _SAFE_SECTION_RE, "section")


def frame_index(frame: str) -> int | None:
    match = _FRAME_RE.match(frame or "")
    return int(match.group(1)) if match else None


def frame_video_timestamp(frame: str, fps: float | int | None) -> float | None:
    index = frame_index(frame)
    try:
        rate = float(fps) if fps is not None else 0.0
    except (TypeError, ValueError):
        rate = 0.0
    if index is None or rate <= 0:
        return None
    return round((index - 1) / rate, 6)


def observation_provenance(run_id: str, section: str, frame: str) -> dict:
    meta = section_meta(run_id, section)
    source_url_path = run_dir(run_id) / "source_url.txt"
    source_url = source_url_path.read_text(encoding="utf-8").strip() if source_url_path.exists() else None
    fps = meta.get("fps")
    try:
        rate = float(fps) if fps is not None else 0.0
    except (TypeError, ValueError):
        rate = 0.0
    resolution = (1.0 / rate) if rate > 0 else None
    return {
        "source_kind": "VIDEO_OCR",
        "ocr_run_id": run_id,
        "section": section,
        "frame": frame,
        "frame_index": frame_index(frame),
        "video_timestamp_seconds": frame_video_timestamp(frame, fps),
        "timestamp_basis": "sample_index_over_section_fps",
        "timestamp_resolution_seconds": round(resolution, 6) if resolution is not None else None,
        "timestamp_uncertainty_seconds": round(resolution / 2.0, 6) if resolution is not None else None,
        "fps": fps,
        "crop": meta.get("crop"),
        "capture_profile": meta.get("capture_profile") or DEFAULT_CAPTURE_PROFILE,
        "preprocess_profile": meta.get("preprocess_profile") or DEFAULT_PREPROCESS_PROFILE,
        "source_url": source_url,
    }


def _migrate_legacy_run(run_id: str):
    """Runs created before multi-section support (2026-09-27) kept frames/frames_unique/
    ocr_raw.jsonl/etc directly under the run dir, one crop per run. Move them into
    sections/<DEFAULT_SECTION_LABEL>/ the first time this run is touched by section-aware code, so
    old runs keep working without a manual migration step."""
    d = _run_path(run_id)
    if not d.exists():
        return
    legacy_markers = ["frames", "frames_unique", "ocr_raw.jsonl", "crop.txt"]
    if not any((d / m).exists() for m in legacy_markers):
        return
    slug = section_slug(DEFAULT_SECTION_LABEL)
    dest = d / "sections" / slug
    if dest.exists():
        return  # already migrated
    dest.mkdir(parents=True)
    crop = None
    for name in ["frames", "frames_unique", "ocr_raw.jsonl", "ocr_matched.jsonl", "transcript.txt",
                 "crop.txt", "ocr_progress.json"]:
        src = d / name
        if src.exists():
            src.rename(dest / name)
    crop_file = dest / "crop.txt"
    if crop_file.exists():
        crop = crop_file.read_text(encoding="utf-8").strip()
    (dest / "meta.json").write_text(
        json.dumps({"label": DEFAULT_SECTION_LABEL, "crop": crop, "fps": None,
                    "capture_profile": DEFAULT_CAPTURE_PROFILE,
                    "preprocess_profile": DEFAULT_PREPROCESS_PROFILE}), encoding="utf-8"
    )


def list_sections(run_id: str) -> list[str]:
    _migrate_legacy_run(run_id)
    sdir = run_dir(run_id) / "sections"
    if not sdir.exists():
        return []
    return sorted(p.name for p in sdir.iterdir() if p.is_dir())


def section_meta(run_id: str, section: str) -> dict:
    p = section_dir(run_id, section) / "meta.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def section_status(run_id: str, section: str) -> dict:
    d = section_dir(run_id, section)
    meta = section_meta(run_id, section)
    frames_dir = d / "frames"
    unique_dir = d / "frames_unique"
    frames = list(frames_dir.glob("f_*.png")) if frames_dir.exists() else []
    unique = list(unique_dir.glob("*.png")) if unique_dir.exists() else []
    ocr_path = d / "ocr_raw.jsonl"
    matched_path = d / "ocr_matched.jsonl"
    ocr_lines = sum(1 for _ in ocr_path.open(encoding="utf-8")) if ocr_path.exists() else 0
    matched_lines = sum(1 for _ in matched_path.open(encoding="utf-8")) if matched_path.exists() else 0
    return {
        "section": section,
        "label": meta.get("label") or section,
        "crop": meta.get("crop"),
        "fps": meta.get("fps"),
        "capture_profile": meta.get("capture_profile") or DEFAULT_CAPTURE_PROFILE,
        "preprocess_profile": meta.get("preprocess_profile") or DEFAULT_PREPROCESS_PROFILE,
        "frame_count": len(frames),
        "unique_count": len(unique),
        "ocr_line_count": ocr_lines,
        "matched_line_count": matched_lines,
        "has_transcript": (d / "transcript.txt").exists(),
        "raw_frame_bytes": _dir_size_bytes(frames_dir) if frames_dir.exists() else 0,
        "unique_frame_bytes": _dir_size_bytes(unique_dir) if unique_dir.exists() else 0,
    }


def run_id_from_url(url: str) -> str:
    # Real YouTube video id when present (stable, human-recognizable run folder name);
    # falls back to a short hash for any other URL shape so this never collides/crashes.
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else hashlib.sha1(url.encode()).hexdigest()[:11]


def resolve_tool(name: str) -> str | None:
    """System PATH wins if present; otherwise falls back to a vendored copy (see
    _VENDOR_BIN_DIRS -- ffmpeg/ffprobe/tesseract each vendor under mission_toolkit/vendor/)."""
    from shutil import which
    found = which(name)
    if found:
        return found
    vendor_dir = _VENDOR_BIN_DIRS.get(name)
    if vendor_dir is None:
        return None
    vendored = vendor_dir / f"{name}.exe"
    return str(vendored) if vendored.exists() else None


def check_tool(name: str) -> str:
    path = resolve_tool(name)
    if path is None:
        sys.exit(f"[youtube_chat_ocr] '{name}' not found on PATH (or vendored under "
                  f"mission_toolkit/vendor/) -- see the module docstring, or use the OCR page's "
                  f"Prerequisites section to install it.")
    return path


def tool_available(name: str) -> bool:
    return resolve_tool(name) is not None


def ocr_seconds_per_frame() -> float | None:
    """Measured rate from this machine's own past OCR runs (see _record_ocr_timing), or None if
    none have completed yet -- the page falls back to not showing an estimate rather than
    guessing a number with zero basis."""
    if not OCR_TIMING_PATH.exists():
        return None
    try:
        data = json.loads(OCR_TIMING_PATH.read_text(encoding="utf-8"))
        total_frames = data.get("total_frames", 0)
        if total_frames <= 0:
            return None
        return data["total_seconds"] / total_frames
    except (OSError, json.JSONDecodeError, KeyError, ZeroDivisionError):
        return None


def _record_ocr_timing(elapsed_seconds: float, frame_count: int):
    """Folds one completed run into the running (total_seconds, total_frames) tally -- a simple
    cumulative average weighted by frame count, so one small test run doesn't skew the estimate as
    much as a real multi-hundred-frame run."""
    if frame_count <= 0:
        return
    data = {"total_seconds": 0.0, "total_frames": 0}
    if OCR_TIMING_PATH.exists():
        try:
            data = json.loads(OCR_TIMING_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    data["total_seconds"] = data.get("total_seconds", 0.0) + elapsed_seconds
    data["total_frames"] = data.get("total_frames", 0) + frame_count
    OCR_TIMING_PATH.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# GUI-facing helpers (gui_server.py imports these directly -- no subprocess/CLI round-trip).
# ---------------------------------------------------------------------------------------------

def list_runs() -> list[dict]:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    runs = []
    for d in sorted(RUNS_ROOT.iterdir(), reverse=True):
        if d.is_dir():
            runs.append(run_status(d.name))
    return runs


def delete_run(run_id: str) -> None:
    """Purges an entire run folder (source video, frames, OCR/match output, everything) from
    disk. Irreversible -- there is no trash/undo, the run_id simply won't exist afterward."""
    d = run_dir(run_id)
    shutil.rmtree(d)


def run_status(run_id: str) -> dict:
    d = run_dir(run_id)
    url_file = d / "source_url.txt"
    sections = [section_status(run_id, s) for s in list_sections(run_id)]
    return {
        "run_id": run_id,
        "url": url_file.read_text(encoding="utf-8").strip() if url_file.exists() else None,
        "has_source": (d / "source.mp4").exists(),
        "has_preview": (d / "preview.png").exists(),
        "sections": sections,
        "section_count": len(sections),
        "total_frame_count": sum(s["frame_count"] for s in sections),
        "total_unique_count": sum(s["unique_count"] for s in sections),
        "total_ocr_line_count": sum(s["ocr_line_count"] for s in sections),
        "total_matched_line_count": sum(s["matched_line_count"] for s in sections),
        "any_transcript": any(s["has_transcript"] for s in sections),
        "meta": load_video_meta(run_id),
    }


def extract_preview_frame(run_id: str, timestamp: float) -> Path:
    """Grabs a single uncropped frame at `timestamp` seconds -- what the crop-selection canvas in
    the GUI draws the rectangle over, before any crop box has been chosen."""
    ffmpeg = check_tool("ffmpeg")
    d = run_dir(run_id)
    src = d / "source.mp4"
    if not src.exists():
        sys.exit(f"[youtube_chat_ocr] {src} missing -- run 'download' first")
    out = d / "preview.png"
    subprocess.run([
        ffmpeg, "-y", "-ss", str(timestamp), "-i", str(src), "-frames:v", "1", str(out),
    ], check=True, capture_output=True)
    return out


def preview_frame_size(run_id: str) -> tuple[int, int]:
    from PIL import Image
    with Image.open(run_dir(run_id) / "preview.png") as img:
        return img.size


def read_transcript(run_id: str, section: str, limit: int = 500) -> list[str]:
    path = section_dir(run_id, section) / "transcript.txt"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[:limit]


def read_matched_rows(run_id: str, section: str, limit: int = 500) -> list[dict]:
    """Structured, deduped rows for the table viewer -- same scroll-repeat collapsing as
    transcript.txt, but keeps timestamp/channel/speaker/hex_hints instead of flattening to text."""
    path = section_dir(run_id, section) / "ocr_matched.jsonl"
    if not path.exists():
        return []
    rows = []
    last_text = None
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            display = row.get("matched_text") or row.get("raw_text", "")
            if last_text is not None and SequenceMatcher(None, display, last_text).ratio() >= 0.9:
                continue
            last_text = display
            rows.append(row)
    return rows[:limit]


# ---------------------------------------------------------------------------------------------
# Stage 1: download
# ---------------------------------------------------------------------------------------------

def cmd_download(args):
    yt_dlp = check_tool("yt-dlp")
    rid = run_id_from_url(args.url)
    d = _run_path(rid)
    d.mkdir(parents=True, exist_ok=True)
    out = d / "source.mp4"
    if out.exists() and not args.force:
        print(f"  already downloaded: {out}")
    else:
        # yt-dlp needs ffmpeg itself to merge separate video+audio streams -- it only looks on
        # PATH by default, so the vendored copy (see resolve_tool()) has to be pointed at
        # explicitly via --ffmpeg-location or a vendored-only install silently drops audio.
        ffmpeg_path = resolve_tool("ffmpeg")
        cmd = [
            yt_dlp, "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", str(out), args.url,
            # YouTube's CDN periodically resets long-running connections mid-download on larger/
            # longer videos ("N bytes read, M more expected"); --http-chunk-size forces yt-dlp to
            # fetch in smaller ranged requests so a dropped connection only loses one chunk instead
            # of restarting near-total progress, and --retries/--fragment-retries make it actually
            # keep retrying rather than giving up after the default 10.
            "--http-chunk-size", "10M",
            "--retries", "20",
            "--fragment-retries", "20",
        ]
        if ffmpeg_path:
            cmd += ["--ffmpeg-location", str(Path(ffmpeg_path).parent)]
        # YouTube's "n challenge" (its newest anti-bot signature check) requires yt-dlp to run a
        # snippet of JS; without a JS runtime on PATH it silently degrades ("n challenge solving
        # failed"), which can cascade into garbled/unrelated-looking errors later in the same run.
        # node is far more commonly already installed than deno, so prefer it when present.
        from shutil import which
        if which("node") or which("deno"):
            # A JS runtime alone isn't enough -- yt-dlp also needs the actual EJS challenge-solver
            # script, which it does NOT bundle or fetch by default. Without --remote-components
            # ejs:github it reports "n challenge solving failed" / "The page needs to be reloaded"
            # even with node/deno present and correctly detected.
            cmd += ["--js-runtimes", "node" if which("node") else "deno"]
            cmd += ["--remote-components", "ejs:github"]
        cookies_from_browser = getattr(args, "cookies_from_browser", None)
        if cookies_from_browser:
            cmd += ["--cookies-from-browser", cookies_from_browser]
        # Let yt-dlp's own stdout/stderr (progress bar, and on failure its real reason --
        # private/removed/region-locked/etc.) stream through normally rather than capturing it,
        # but convert a nonzero exit into the same sys.exit(...) style as every other failure
        # here -- the GUI's ocr_start route only catches SystemExit, so an uncaught
        # CalledProcessError was surfacing as a raw 500/traceback with no user-facing reason.
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            sys.exit(f"[youtube_chat_ocr] yt-dlp failed to download {args.url} -- see the "
                      f"'ERROR:' line above/in the server log for the actual reason (private, "
                      f"removed, region-locked, etc.)")
    (d / "source_url.txt").write_text(args.url, encoding="utf-8")
    meta_path = d / "source_meta.json"
    if not meta_path.exists() or args.force:
        fetch_video_meta(args.url, meta_path, cookies_from_browser=getattr(args, "cookies_from_browser", None))
    print(f"  run_id: {rid}")
    return rid


def fetch_video_meta(url: str, out_path: Path, cookies_from_browser: str | None = None) -> dict | None:
    """Pulls title/uploader/upload_date/description via yt-dlp --dump-json (no video download) and
    writes them to out_path. Best-effort: a metadata-fetch failure must never abort the actual
    video download, so failures are swallowed here and the caller just won't have metadata to show
    -- e.g. /ocr/{run_id}/create_capture falls back to the run_id/URL as the capture label."""
    yt_dlp = resolve_tool("yt-dlp")
    if not yt_dlp:
        return None
    cmd = [yt_dlp, "--dump-json", "--skip-download", url]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        full = json.loads(result.stdout)
    except Exception:
        return None
    meta = {
        "title": full.get("title"),
        "uploader": full.get("uploader"),
        "upload_date": full.get("upload_date"),  # YYYYMMDD string, per yt-dlp's own format
        "description": full.get("description"),
        "duration": full.get("duration"),
    }
    out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_video_meta(run_id: str) -> dict | None:
    meta_path = run_dir(run_id) / "source_meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------
# Stage 2: frames (crop + fps via ffmpeg)
# ---------------------------------------------------------------------------------------------

def cmd_frames(args):
    """`args.section` is a free-text LABEL (e.g. "Chat Log", "NPCLogger overlay") -- a run can hold
    several independently-cropped sections (chat box, an on-screen packet-capture overlay, etc.),
    each carrying its own frames/dedupe/ocr/match pipeline so one video can be mined for more than
    just the chat log. Re-using the same label re-extracts that section in place."""
    ffmpeg = check_tool("ffmpeg")
    d = run_dir(args.run_id)
    src = d / "source.mp4"
    if not src.exists():
        sys.exit(f"[youtube_chat_ocr] {src} missing -- run 'download' first")
    label = getattr(args, "section", None) or DEFAULT_SECTION_LABEL
    profile = getattr(args, "profile", None) or DEFAULT_CAPTURE_PROFILE
    if profile not in CAPTURE_PROFILES:
        sys.exit(f"[youtube_chat_ocr] unknown --profile '{profile}' -- choices: {', '.join(CAPTURE_PROFILES)}")
    preprocess = getattr(args, "preprocess", None) or DEFAULT_PREPROCESS_PROFILE
    if preprocess not in PREPROCESS_PROFILES:
        sys.exit(f"[youtube_chat_ocr] unknown --preprocess '{preprocess}' -- choices: {', '.join(PREPROCESS_PROFILES)}")
    slug = section_slug(label)
    sdir = section_dir(args.run_id, slug)
    sdir.mkdir(parents=True, exist_ok=True)
    x, y, w, h = (int(v) for v in args.crop.split(","))
    frames_dir = sdir / "frames"
    frames_dir.mkdir(exist_ok=True)
    (sdir / "meta.json").write_text(
        json.dumps({
            "label": label,
            "crop": args.crop,
            "fps": args.fps,
            "capture_profile": profile,
            "preprocess_profile": preprocess,
        }),
        encoding="utf-8",
    )
    vf = f"crop={w}:{h}:{x}:{y},fps={args.fps}"
    subprocess.run([
        ffmpeg, "-y", "-i", str(src), "-vf", vf, str(frames_dir / "f_%06d.png"),
    ], check=True)
    n = len(list(frames_dir.glob("f_*.png")))
    print(f"  {n} cropped frames -> {frames_dir}")
    return slug


# ---------------------------------------------------------------------------------------------
# Stage 3: dedupe (drop frames that didn't meaningfully change from the last kept one)
# ---------------------------------------------------------------------------------------------

def frame_hash(path: Path):
    """Cheap perceptual hash: shrink to 32x32 grayscale, threshold against the mean. No extra
    dependency beyond Pillow (already in requirements.txt) -- good enough to catch a static chat
    box between scroll events, not meant to be a general-purpose image-similarity tool."""
    from PIL import Image
    img = Image.open(path).convert("L").resize((32, 32))
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return int(bits, 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def cmd_dedupe(args):
    sdir = section_dir(args.run_id, args.section)
    frames_dir = sdir / "frames"
    frames = sorted(frames_dir.glob("f_*.png"))
    if not frames:
        sys.exit(f"[youtube_chat_ocr] no frames under {frames_dir} -- run 'frames' first")
    unique_dir = sdir / "frames_unique"
    unique_dir.mkdir(exist_ok=True)
    for old in unique_dir.glob("*.png"):
        old.unlink()

    kept = []
    last_hash = None
    for f in frames:
        h = frame_hash(f)
        if last_hash is None or hamming(h, last_hash) > args.threshold:
            dest = unique_dir / f.name
            dest.write_bytes(f.read_bytes())
            kept.append(dest.name)
            last_hash = h
    print(f"  kept {len(kept)}/{len(frames)} frames (threshold={args.threshold}) -> {unique_dir}")


# ---------------------------------------------------------------------------------------------
# Stage 4: ocr
# ---------------------------------------------------------------------------------------------

def ocr_progress_path(run_id: str, section: str) -> Path:
    return section_dir(run_id, section) / "ocr_progress.json"


def read_ocr_progress(run_id: str, section: str) -> dict:
    """Progress snapshot for a possibly-still-running OCR stage, for the GUI to poll.
    File may not exist yet (never started) or may be stale from a prior run of the same section --
    callers only care about it while a run is actually in flight, checked via 'finished'."""
    p = ocr_progress_path(run_id, section)
    if not p.exists():
        return {"done": 0, "total": 0, "finished": True, "error": None}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"done": 0, "total": 0, "finished": True, "error": None}


def _write_ocr_progress(run_id: str, section: str, done: int, total: int, finished: bool = False, error: str | None = None):
    p = ocr_progress_path(run_id, section)
    started_at = time.time()
    if done > 0 and p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            started_at = existing.get("started_at", started_at)
        except (OSError, json.JSONDecodeError):
            pass
    p.write_text(
        json.dumps({
            "done": done, "total": total, "finished": finished, "error": error, "started_at": started_at,
        }),
        encoding="utf-8",
    )


def preprocess_ocr_image(img, profile_id: str):
    """Apply one named OCR preprocessing preset without modifying the source frame."""
    from PIL import ImageFilter, ImageOps

    profile = PREPROCESS_PROFILES.get(profile_id) or PREPROCESS_PROFILES[DEFAULT_PREPROCESS_PROFILE]
    out = img.convert("L")
    if profile.get("autocontrast"):
        out = ImageOps.autocontrast(out)
    if profile.get("invert"):
        out = ImageOps.invert(out)
    threshold = profile.get("threshold")
    if threshold is not None:
        threshold = int(threshold)
        out = out.point(lambda p: 255 if p >= threshold else 0)
    if profile.get("sharpen"):
        out = out.filter(ImageFilter.SHARPEN)
    scale = max(1, int(profile.get("scale") or 1))
    if scale != 1:
        out = out.resize((out.width * scale, out.height * scale))
    return out, profile


def cmd_ocr(args):
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        sys.exit("[youtube_chat_ocr] needs `pip install pytesseract pillow` (pillow is already "
                  "in requirements.txt; pytesseract is not, see module docstring)")
    pytesseract.pytesseract.tesseract_cmd = check_tool("tesseract")

    sdir = section_dir(args.run_id, args.section)
    meta = section_meta(args.run_id, args.section)
    preprocess_id = meta.get("preprocess_profile") or DEFAULT_PREPROCESS_PROFILE
    if preprocess_id not in PREPROCESS_PROFILES:
        sys.exit(f"[youtube_chat_ocr] section has unknown preprocess profile '{preprocess_id}'")
    src_dir = sdir / "frames_unique"
    frames = sorted(src_dir.glob("*.png"))
    if not frames:
        sys.exit(f"[youtube_chat_ocr] no deduped frames under {src_dir} -- run 'dedupe' first")

    total = len(frames)
    _write_ocr_progress(args.run_id, args.section, 0, total)
    out_path = sdir / "ocr_raw.jsonl"
    start = time.time()
    try:
        with out_path.open("w", encoding="utf-8") as out:
            for i, f in enumerate(frames):
                img = Image.open(f)
                img, preprocess = preprocess_ocr_image(img, preprocess_id)
                # image_to_data (not image_to_string) so we get a per-word confidence alongside the
                # text in one tesseract pass -- avoids OCRing every frame twice just for confidence.
                data = pytesseract.image_to_data(
                    img,
                    config=f"--psm {int(preprocess.get('psm') or 6)}",
                    output_type=pytesseract.Output.DICT,
                )
                lines: dict[tuple, list[str]] = {}
                confs = []
                for j, word in enumerate(data["text"]):
                    word = word.strip()
                    if not word:
                        continue
                    key = (data["block_num"][j], data["par_num"][j], data["line_num"][j])
                    lines.setdefault(key, []).append(word)
                    try:
                        conf = float(data["conf"][j])
                    except (TypeError, ValueError):
                        conf = -1.0
                    if conf >= 0:
                        confs.append(conf)
                text = "\n".join(" ".join(words) for words in lines.values()).strip()
                if text:
                    provenance = observation_provenance(args.run_id, args.section, f.name)
                    record = {
                        "frame": f.name,
                        "frame_index": provenance["frame_index"],
                        "video_timestamp_seconds": provenance["video_timestamp_seconds"],
                        "raw_text": text,
                        "provenance": provenance,
                    }
                    if confs:
                        record["confidence"] = round(sum(confs) / len(confs), 1)
                    out.write(json.dumps(record) + "\n")
                # every 5 frames (not every frame) -- a JSON write per frame is cheap but pointless
                # at 1000+ frames when the GUI only polls every 30s anyway.
                if (i + 1) % 5 == 0 or (i + 1) == total:
                    _write_ocr_progress(args.run_id, args.section, i + 1, total)
    except Exception as e:
        _write_ocr_progress(args.run_id, args.section, i, total, finished=True, error=str(e))
        raise
    _write_ocr_progress(args.run_id, args.section, total, total, finished=True)
    _record_ocr_timing(time.time() - start, total)
    n = sum(1 for _ in out_path.open(encoding="utf-8"))
    print(f"  {n} non-empty OCR lines -> {out_path}")


# ---------------------------------------------------------------------------------------------
# Stage 5: match (fuzzy-correct against dialog_text_fts, dedupe scrolled repeats)
# ---------------------------------------------------------------------------------------------

def fts_query(raw_line: str) -> str:
    # sqlite FTS5 needs quoted terms when the line has punctuation; keep only word-ish tokens.
    words = re.findall(r"[A-Za-z']{3,}", raw_line)
    return " OR ".join(f'"{w}"' for w in words[:8]) or raw_line


def best_match(con, raw_line: str, zoneid: int | None):
    sql = "SELECT zoneid, idx, text FROM dialog_text_fts WHERE dialog_text_fts MATCH ?"
    params = [fts_query(raw_line)]
    if zoneid is not None:
        sql += " AND zoneid = ?"
        params.append(zoneid)
    sql += " LIMIT 25"
    rows = con.execute(sql, params).fetchall()
    best = None
    best_score = 0.0
    for zid, idx, text in rows:
        score = SequenceMatcher(None, raw_line.lower(), text.lower()).ratio()
        if score > best_score:
            best_score, best = score, (zid, idx, text)
    return best, best_score


def cmd_match(args):
    sdir = section_dir(args.run_id, args.section)
    raw_path = sdir / "ocr_raw.jsonl"
    if not raw_path.exists():
        sys.exit(f"[youtube_chat_ocr] {raw_path} missing -- run 'ocr' first")
    profile = section_meta(args.run_id, args.section).get("capture_profile") or DEFAULT_CAPTURE_PROFILE

    zoneid = None
    con = sqlite3.connect(DB_PATH)
    if args.zone:
        row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (args.zone,)).fetchone()
        if not row:
            sys.exit(f"[youtube_chat_ocr] zone '{args.zone}' not found in {DB_PATH} -- run "
                      f"build_dialog_index.py --zone {args.zone} first")
        zoneid = row[0]

    matched_path = sdir / "ocr_matched.jsonl"
    transcript_path = sdir / "transcript.txt"
    # preserve any hand-made corrections across a re-run of 'match' (e.g. re-matching after
    # widening min_score shouldn't throw away corrections the user already typed in)
    prior_corrections = {}
    if matched_path.exists():
        for line in matched_path.open(encoding="utf-8"):
            old = json.loads(line)
            if old.get("corrected_text"):
                prior_corrections[old["frame"]] = old["corrected_text"]

    last_clean = None
    with raw_path.open(encoding="utf-8") as src, \
         matched_path.open("w", encoding="utf-8") as out, \
         transcript_path.open("w", encoding="utf-8") as transcript:
        for line in src:
            row = json.loads(line)
            if profile == CAPTURE_PROFILE_PACKETLOGGER:
                # Packet field text has no business being fuzzy-matched against chat dialog text --
                # it isn't dialog, and "correcting" a field value against the nearest-sounding
                # dialog line would silently corrupt real data. Skip the dialog match step entirely
                # and parse the ORIGINAL multi-line OCR text (header + field lines are separate
                # on-screen lines; flattening them first would make them unparseable together).
                if not row["raw_text"].strip():
                    continue
                # one frame's overlay can show more than one packet's history at once (see
                # parse_packetlogger_block) -- each becomes its own record/transcript line instead
                # of getting flattened together into one corrupted blob.
                segments = parse_packetlogger_block(row["raw_text"])
                for seg_idx, parsed in enumerate(segments):
                    display = parsed["text"]
                    frame_id = row["frame"] if len(segments) == 1 else f"{row['frame']}#{seg_idx}"
                    assistance = packet_symbol_assistance(parsed)
                    record = {
                        "frame": frame_id,
                        "raw_text": row["raw_text"].replace("\n", " ").strip(),
                        "matched_text": None,
                        "match_score": 0.0,
                        "dialog_zoneid": None,
                        "dialog_idx": None,
                        "confidence": row.get("confidence"),
                        "frame_index": row.get("frame_index"),
                        "video_timestamp_seconds": row.get("video_timestamp_seconds"),
                        "provenance": row.get("provenance") or observation_provenance(args.run_id, args.section, row["frame"]),
                        "display_text": display,
                        **parsed,
                        **assistance,
                    }
                    if frame_id in prior_corrections:
                        record["corrected_text"] = prior_corrections[frame_id]
                    out.write(json.dumps(record) + "\n")
                    transcript_line = record.get("corrected_text") or display
                    if last_clean is None or SequenceMatcher(None, transcript_line, last_clean).ratio() < 0.9:
                        transcript.write(transcript_line + "\n")
                        last_clean = transcript_line
                continue
            else:
                raw = row["raw_text"].replace("\n", " ").strip()
                if not raw:
                    continue
                if profile == CAPTURE_PROFILE_CAPTUREBAR:
                    # Capturebar is structured HUD context, not game dialog. Never fuzzy-match it
                    # against dialog_text_fts, which could silently replace real coordinates or IDs.
                    match, score, clean = None, 0.0, None
                    display = raw
                else:
                    match, score = best_match(con, raw, zoneid)
                    clean = match[2] if (match and score >= args.min_score) else None
                    display = clean or raw
                parsed = parse_capture_line(profile, display)
                record = {
                    "frame": row["frame"],
                    "raw_text": raw,
                    "matched_text": clean,
                    "match_score": round(score, 3),
                    "dialog_zoneid": match[0] if match else None,
                    "dialog_idx": match[1] if match else None,
                    "confidence": row.get("confidence"),
                    "frame_index": row.get("frame_index"),
                    "video_timestamp_seconds": row.get("video_timestamp_seconds"),
                    "provenance": row.get("provenance") or observation_provenance(args.run_id, args.section, row["frame"]),
                    "display_text": display,
                    **parsed,
                }
            if row["frame"] in prior_corrections:
                record["corrected_text"] = prior_corrections[row["frame"]]
            out.write(json.dumps(record) + "\n")
            # collapse consecutive near-duplicate lines from the chat box scrolling upward (or a
            # packet overlay box repeating the same packet across several static frames); a manual
            # correction wins over the auto-generated display text.
            transcript_line = record.get("corrected_text") or display
            if last_clean is None or SequenceMatcher(None, transcript_line, last_clean).ratio() < 0.9:
                transcript.write(transcript_line + "\n")
                last_clean = transcript_line
    if profile == CAPTURE_PROFILE_PACKETLOGGER and matched_path.exists():
        records = [json.loads(line) for line in matched_path.open(encoding="utf-8")]
        records = apply_cross_frame_consensus(records)
        with matched_path.open("w", encoding="utf-8") as out:
            for record in records:
                out.write(json.dumps(record) + "\n")
        last_clean = None
        with transcript_path.open("w", encoding="utf-8") as transcript:
            for record in records:
                effective = record.get("effective_packet") or {}
                direction = effective.get("direction") or record.get("direction") or ""
                opcode = effective.get("opcode") or record.get("opcode") or ""
                command = effective.get("gp_command") or record.get("gp_command") or ""
                fields = effective.get("fields") or record.get("fields") or {}
                field_text = ", ".join(f"{k}: {v}" for k, v in fields.items())
                generated = " ".join(part for part in [direction, f"[{opcode}]" if opcode else "", command] if part)
                if field_text:
                    generated = f"{generated} / {field_text}" if generated else field_text
                transcript_line = record.get("corrected_text") or generated or record.get("display_text") or record.get("raw_text", "")
                if transcript_line and (last_clean is None or SequenceMatcher(None, transcript_line, last_clean).ratio() < 0.9):
                    transcript.write(transcript_line + "\n")
                    last_clean = transcript_line

    print(f"  matched output -> {matched_path}")
    print(f"  deduped transcript -> {transcript_path}")


def cmd_correct(args):
    """Hand-correct one frame's OCR result in place. Rewrites ocr_matched.jsonl (adding/clearing
    that frame's corrected_text) and rebuilds transcript.txt with the same scroll-repeat collapsing
    cmd_match uses, so a correction shows up everywhere the frame's text is displayed."""
    sdir = section_dir(args.run_id, args.section)
    matched_path = sdir / "ocr_matched.jsonl"
    if not matched_path.exists():
        sys.exit(f"[youtube_chat_ocr] {matched_path} missing -- run 'match' first")

    records = [json.loads(line) for line in matched_path.open(encoding="utf-8")]
    found = False
    for r in records:
        if r["frame"] == args.frame:
            if args.clear:
                r.pop("corrected_text", None)
            else:
                r["corrected_text"] = args.text
            found = True
            break
    if not found:
        sys.exit(f"[youtube_chat_ocr] frame '{args.frame}' not found in {matched_path}")

    with matched_path.open("w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r) + "\n")

    transcript_path = sdir / "transcript.txt"
    last_clean = None
    with transcript_path.open("w", encoding="utf-8") as transcript:
        for r in records:
            line = r.get("corrected_text") or r.get("display_text") or r.get("raw_text", "")
            if not line:
                continue
            if last_clean is None or SequenceMatcher(None, line, last_clean).ratio() < 0.9:
                transcript.write(line + "\n")
                last_clean = line
    if args.clear:
        print(f"  cleared correction on {args.frame}")
    else:
        print(f"  {args.frame} -> corrected_text={args.text!r}")


def capture_observations(run_id: str) -> list[dict]:
    """Materialize matched OCR rows as capture-ready observations with explicit provenance."""
    status = run_status(run_id)
    out = []
    for section_row in status.get("sections", []):
        section = section_row["section"]
        path = section_dir(run_id, section) / "ocr_matched.jsonl"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as src:
            for ordinal, line in enumerate(src, 1):
                row = json.loads(line)
                provenance = row.get("provenance") or observation_provenance(run_id, section, row.get("frame", ""))
                frame = row.get("frame") or f"observation_{ordinal}"
                observation_id = hashlib.sha1(
                    f"{run_id}|{section}|{frame}|{row.get('opcode') or ''}|{row.get('display_text') or row.get('raw_text') or ''}".encode()
                ).hexdigest()[:20]
                effective = row.get("effective_packet") or {}
                effective_opcode = effective.get("opcode") or row.get("opcode")
                provenance = dict(provenance)
                if row.get("raw_parsed") is not None:
                    provenance["raw_parsed"] = row.get("raw_parsed")
                if row.get("corrections"):
                    provenance["symbol_corrections"] = row.get("corrections")
                if row.get("consensus"):
                    provenance["cross_frame_consensus"] = row.get("consensus")
                out.append({
                    "observation_id": f"video-ocr:{observation_id}",
                    "section": section,
                    "frame": frame,
                    "video_timestamp_seconds": row.get("video_timestamp_seconds", provenance.get("video_timestamp_seconds")),
                    "source_url": provenance.get("source_url") or status.get("url"),
                    "observation_type": (
                        "PACKET" if effective_opcode
                        else "CAPTUREBAR_CONTEXT" if row.get("capturebar_parsed")
                        else "OCR_TEXT"
                    ),
                    "direction": effective.get("direction") or row.get("direction"),
                    "opcode": effective_opcode,
                    "gp_command": effective.get("gp_command") or row.get("gp_command"),
                    "packet_class": effective.get("packet_class") or row.get("packet_class"),
                    "fields": effective.get("fields") or row.get("fields"),
                    "raw_text": row.get("raw_text"),
                    "corrected_text": row.get("corrected_text"),
                    "confidence": row.get("confidence"),
                    "provenance": provenance,
                })
    return out


# ---------------------------------------------------------------------------------------------
# cleanup: drop the bulky per-frame PNGs once a section's OCR text output is trusted. This is a
# separate, user-triggered step (not automatic after 'ocr') because the raw/unique frames are
# still useful if OCR needs to be re-run with a different crop or tesseract config -- only the
# user knows when they're actually done experimenting with a given section.
# ---------------------------------------------------------------------------------------------

def _dir_size_bytes(d: Path) -> int:
    if not d.exists():
        return 0
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())


def cmd_cleanup(args):
    sdir = section_dir(args.run_id, args.section)
    if not sdir.exists():
        sys.exit(f"[youtube_chat_ocr] no section '{args.section}' under {args.run_id}")
    targets = []
    if getattr(args, "frames", True):
        targets.append(sdir / "frames")
    if getattr(args, "unique", True):
        targets.append(sdir / "frames_unique")
    freed = 0
    for d in targets:
        if d.exists():
            freed += _dir_size_bytes(d)
            shutil.rmtree(d)
    print(f"  freed {freed / (1024 * 1024):.1f} MB from {args.run_id}/{args.section}")
    return freed


# ---------------------------------------------------------------------------------------------
# run: chain everything
# ---------------------------------------------------------------------------------------------

def cmd_run(args):
    rid = cmd_download(args)
    args.run_id = rid
    slug = cmd_frames(args)
    args.section = slug
    cmd_dedupe(args)
    cmd_ocr(args)
    cmd_match(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("download", help="yt-dlp the video into a new run folder")
    p.add_argument("url")
    p.add_argument("--force", action="store_true")
    p.add_argument("--cookies-from-browser", dest="cookies_from_browser", default=None,
                    help="reuse an existing logged-in browser session's cookies (e.g. 'chrome', "
                         "'edge', 'firefox') so yt-dlp can fetch unlisted/private videos that "
                         "need auth -- same value you'd pass to yt-dlp's own --cookies-from-browser")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("delete", help="purge an entire run folder (source video, frames, OCR/match output)")
    p.add_argument("run_id")
    p.set_defaults(func=lambda args: delete_run(args.run_id))

    p = sub.add_parser("frames", help="ffmpeg crop+sample a screen region into frames")
    p.add_argument("run_id")
    p.add_argument("--crop", required=True, help="x,y,w,h in source-video pixels")
    p.add_argument("--fps", type=float, default=2.0)
    p.add_argument("--section", default=DEFAULT_SECTION_LABEL,
                    help="label for this cropped region, e.g. 'chat' or 'npclogger' -- a run can "
                         "hold several independently-cropped sections")
    p.add_argument("--profile", choices=CAPTURE_PROFILES, default=DEFAULT_CAPTURE_PROFILE,
                    help="how 'match' should parse this section's lines")
    p.add_argument("--preprocess", choices=sorted(PREPROCESS_PROFILES), default=DEFAULT_PREPROCESS_PROFILE,
                    help="named image preprocessing preset used by OCR")
    p.set_defaults(func=cmd_frames)

    p = sub.add_parser("dedupe", help="drop near-identical consecutive frames")
    p.add_argument("run_id")
    p.add_argument("--section", default=section_slug(DEFAULT_SECTION_LABEL))
    p.add_argument("--threshold", type=int, default=6, help="hamming distance to count as changed (0-1024)")
    p.set_defaults(func=cmd_dedupe)

    p = sub.add_parser("ocr", help="tesseract OCR over the deduped frames")
    p.add_argument("run_id")
    p.add_argument("--section", default=section_slug(DEFAULT_SECTION_LABEL))
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("match", help="fuzzy-match OCR text against dialog_text_fts")
    p.add_argument("run_id")
    p.add_argument("--section", default=section_slug(DEFAULT_SECTION_LABEL))
    p.add_argument("--zone", help="Zone name in the zones table (e.g. Nyzul_Isle) to scope matching")
    p.add_argument("--min-score", type=float, default=0.55, help="below this, keep raw OCR text instead")
    p.set_defaults(func=cmd_match)

    p = sub.add_parser("correct", help="hand-correct one frame's OCR line in ocr_matched.jsonl + transcript.txt")
    p.add_argument("run_id")
    p.add_argument("--section", default=section_slug(DEFAULT_SECTION_LABEL))
    p.add_argument("frame", help="frame filename as it appears in ocr_matched.jsonl (e.g. frame_00042.png)")
    p.add_argument("--text", default="", help="corrected text; omit (or pass --clear) to revert to the OCR result")
    p.add_argument("--clear", action="store_true", help="remove an existing correction instead of setting one")
    p.set_defaults(func=cmd_correct)

    p = sub.add_parser("cleanup", help="delete a section's bulky frame PNGs once OCR text is trusted")
    p.add_argument("run_id")
    p.add_argument("--section", default=section_slug(DEFAULT_SECTION_LABEL))
    p.add_argument("--keep-frames", dest="frames", action="store_false", default=True,
                    help="don't delete frames/ (raw cropped frames)")
    p.add_argument("--keep-unique", dest="unique", action="store_false", default=True,
                    help="don't delete frames_unique/ (deduped frames)")
    p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("run", help="download + frames + dedupe + ocr + match in one go")
    p.add_argument("url")
    p.add_argument("--crop", required=True, help="x,y,w,h in source-video pixels")
    p.add_argument("--fps", type=float, default=2.0)
    p.add_argument("--section", default=DEFAULT_SECTION_LABEL, help="label for this cropped region")
    p.add_argument("--profile", choices=CAPTURE_PROFILES, default=DEFAULT_CAPTURE_PROFILE)
    p.add_argument("--preprocess", choices=sorted(PREPROCESS_PROFILES), default=DEFAULT_PREPROCESS_PROFILE)
    p.add_argument("--threshold", type=int, default=6)
    p.add_argument("--zone", help="Zone name in the zones table to scope matching")
    p.add_argument("--min-score", type=float, default=0.55)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
