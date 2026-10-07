#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.packets import decode as packet_decode
from workbench.captures.video import ocr


def _garble(symbol: str) -> str:
    swaps = [("O", "0"), ("I", "l"), ("L", "I"), ("S", "5"), ("B", "8")]
    for a, b in swaps:
        if a in symbol:
            return symbol.replace(a, b, 1)
    if len(symbol) > 4:
        return symbol[:-1] + ("X" if symbol[-1] != "X" else "Y")
    return symbol + "X"


def main():
    defs = [row for row in packet_decode.list_opcodes("") if row["direction"] == "s2c"]
    target = next((row for row in defs if row["opcode"] == 0x036), defs[0])
    schema = packet_decode.get_field_schema("s2c", target["opcode"]) or []
    field = next((row["name"] for row in schema if len(row.get("name") or "") >= 4), None)

    parsed = {
        "direction": "<<",
        "opcode": target["opcode_hex"].lower(),
        "gp_command": _garble(target["description"]),
        "packet_class": None,
        "fields": {_garble(field): "123"} if field else {"UnknownField": "123"},
    }
    assist = ocr.packet_symbol_assistance(parsed)
    assert assist["raw_parsed"]["gp_command"] == parsed["gp_command"], assist
    assert assist["effective_packet"]["opcode"] == target["opcode_hex"].lower(), assist
    assert assist["effective_packet"]["gp_command"] == target["description"], assist
    assert assist["symbol_assisted"] is True, assist
    assert any(c["kind"] == "packet_symbol" for c in assist["corrections"]), assist
    if field:
        assert field in assist["effective_packet"]["fields"], assist
        assert assist["effective_packet"]["fields"][field] == "123", assist

    # EView history is interleaved: A, B, A, B. Consensus must still combine both A frames.
    a1 = {
        "frame": "f_000001.png",
        "video_timestamp_seconds": 0.0,
        "direction": "<<",
        "opcode": "0x036",
        "gp_command": "PACKET_A",
        "fields": {"MesNum": "100", "UniqueNo": "55"},
        "effective_packet": {"direction": "<<", "opcode": "0x036", "gp_command": "PACKET_A",
                             "fields": {"MesNum": "100", "UniqueNo": "55"}},
    }
    b1 = {
        "frame": "f_000001.png#1",
        "video_timestamp_seconds": 0.0,
        "direction": "<<",
        "opcode": "0x034",
        "gp_command": "PACKET_B",
        "fields": {"Event": "7"},
        "effective_packet": {"direction": "<<", "opcode": "0x034", "gp_command": "PACKET_B",
                             "fields": {"Event": "7"}},
    }
    a2 = {
        "frame": "f_000002.png",
        "video_timestamp_seconds": 0.5,
        "direction": "<<",
        "opcode": "0x036",
        "gp_command": "PACKET_A",
        "fields": {"MesNum": "100", "UniqueNo": "S5"},
        "effective_packet": {"direction": "<<", "opcode": "0x036", "gp_command": "PACKET_A",
                             "fields": {"MesNum": "100", "UniqueNo": "S5"}},
    }
    b2 = {
        "frame": "f_000002.png#1",
        "video_timestamp_seconds": 0.5,
        "direction": "<<",
        "opcode": "0x034",
        "gp_command": "PACKET_B",
        "fields": {"Event": "7"},
        "effective_packet": {"direction": "<<", "opcode": "0x034", "gp_command": "PACKET_B",
                             "fields": {"Event": "7"}},
    }
    rows = ocr.apply_cross_frame_consensus([a1, b1, a2, b2])
    assert a1["consensus"]["support"] == 2, a1
    assert set(a1["consensus"]["source_frames"]) == {"f_000001.png", "f_000002.png"}, a1
    assert a1["effective_packet"]["fields"]["MesNum"] == "100", a1
    assert "UniqueNo" in a1["consensus"]["unresolved_fields"], a1
    assert b1["consensus"]["support"] == 2, b1

    # Verify capture materialization keeps raw/correction/consensus provenance while using effective packet.
    original_root = ocr.RUNS_ROOT
    original_timing = ocr.OCR_TIMING_PATH
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            ocr.RUNS_ROOT = root
            ocr.OCR_TIMING_PATH = root / "_ocr_timing.json"
            run_id = "abcdefghijk"
            sdir = root / run_id / "sections" / "packet"
            sdir.mkdir(parents=True)
            (root / run_id / "source_url.txt").write_text("https://youtu.be/abcdefghijk", encoding="utf-8")
            (sdir / "meta.json").write_text(json.dumps({
                "label": "packet", "fps": 2.0, "crop": "0,0,100,100",
                "capture_profile": ocr.CAPTURE_PROFILE_PACKETLOGGER,
            }), encoding="utf-8")
            record = {
                "frame": "f_000001.png",
                "video_timestamp_seconds": 0.0,
                "raw_text": "garbled raw",
                "display_text": "display",
                "confidence": 90.0,
                "direction": parsed["direction"],
                "opcode": parsed["opcode"],
                "gp_command": parsed["gp_command"],
                "fields": parsed["fields"],
                **assist,
                "consensus": {
                    "support": 2,
                    "source_frames": ["f_000001.png", "f_000002.png"],
                    "applied": True,
                    "field_votes": {"x": {"1": 2}},
                    "unresolved_fields": None,
                },
            }
            (sdir / "ocr_matched.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            observations = ocr.capture_observations(run_id)
            assert len(observations) == 1, observations
            obs = observations[0]
            assert obs["opcode"] == target["opcode_hex"].lower(), obs
            assert obs["gp_command"] == target["description"], obs
            provenance = obs["provenance"]
            assert provenance["raw_parsed"]["gp_command"] == parsed["gp_command"], provenance
            assert provenance["symbol_corrections"], provenance
            assert provenance["cross_frame_consensus"]["support"] == 2, provenance
    finally:
        ocr.RUNS_ROOT = original_root
        ocr.OCR_TIMING_PATH = original_timing

    template = (Path(__file__).resolve().parents[1] / "gui" / "templates" / "ocr_run.html").read_text(encoding="utf-8")
    assert "Assist" in template and "Consensus" in template
    assert "raw_parsed" in template

    print("OCR consensus and packet symbol correction regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
