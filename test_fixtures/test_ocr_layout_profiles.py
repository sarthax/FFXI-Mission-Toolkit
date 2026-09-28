#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

import youtube_chat_ocr as ocr


def main():
    original_runs = ocr.RUNS_ROOT
    original_layout = ocr.LAYOUT_PROFILE_PATH
    original_timing = ocr.OCR_TIMING_PATH
    original_cmd_frames = ocr.cmd_frames
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            runs.mkdir()
            ocr.RUNS_ROOT = runs
            ocr.LAYOUT_PROFILE_PATH = root / "ocr_layout_profiles.json"
            ocr.OCR_TIMING_PATH = root / "_ocr_timing.json"

            run_id = "abcdefghijk"
            run = runs / run_id
            (run / "sections" / "chat").mkdir(parents=True)
            (run / "sections" / "eview").mkdir(parents=True)
            (run / "source_url.txt").write_text("https://youtu.be/abcdefghijk", encoding="utf-8")

            (run / "sections" / "chat" / "meta.json").write_text(json.dumps({
                "label": "chat",
                "crop": "10,700,800,250",
                "fps": 2.0,
                "capture_profile": ocr.CAPTURE_PROFILE_PLAIN,
                "preprocess_profile": ocr.PREPROCESS_PROFILE_CHAT,
            }), encoding="utf-8")
            (run / "sections" / "eview" / "meta.json").write_text(json.dumps({
                "label": "eview",
                "crop": "1200,100,650,600",
                "fps": 12.0,
                "capture_profile": ocr.CAPTURE_PROFILE_PACKETLOGGER,
                "preprocess_profile": ocr.PREPROCESS_PROFILE_PACKET,
            }), encoding="utf-8")

            saved = ocr.save_run_layout(
                run_id,
                "my_1080p_layout",
                "My 1080p layout",
                "Chat and EView at my normal UI scale",
            )
            assert saved["id"] == "my_1080p_layout", saved
            assert len(saved["regions"]) == 2, saved

            profiles = ocr.load_layout_profiles()
            assert "chat_only" in profiles and profiles["chat_only"]["builtin"] is True
            assert profiles["my_1080p_layout"]["builtin"] is False
            assert profiles["my_1080p_layout"]["regions"][1]["preprocess_profile"] == ocr.PREPROCESS_PROFILE_PACKET

            calls = []
            def fake_cmd_frames(args):
                calls.append({
                    "run_id": args.run_id,
                    "crop": args.crop,
                    "fps": args.fps,
                    "section": args.section,
                    "profile": args.profile,
                    "preprocess": args.preprocess,
                })
                return ocr.section_slug(args.section)

            ocr.cmd_frames = fake_cmd_frames
            created = ocr.apply_layout_profile(run_id, "my_1080p_layout")
            assert created == ["chat", "eview"], created
            assert calls[0]["crop"] == "10,700,800,250", calls
            assert calls[0]["preprocess"] == ocr.PREPROCESS_PROFILE_CHAT, calls
            assert calls[1]["fps"] == 12.0, calls
            assert calls[1]["profile"] == ocr.CAPTURE_PROFILE_PACKETLOGGER, calls
            assert calls[1]["preprocess"] == ocr.PREPROCESS_PROFILE_PACKET, calls

            try:
                ocr.apply_layout_profile(run_id, "research_combo")
            except ValueError as exc:
                assert "without coordinates" in str(exc)
            else:
                raise AssertionError("built-in coordinate template should not apply directly")

            # Preprocessing is non-destructive and preset-specific.
            img = Image.new("RGB", (8, 8), "black")
            for x in range(4, 8):
                for y in range(8):
                    img.putpixel((x, y), (220, 220, 220))
            processed, spec = ocr.preprocess_ocr_image(img, ocr.PREPROCESS_PROFILE_PACKET)
            assert img.size == (8, 8)
            assert processed.mode == "L"
            assert processed.size == (32, 32), processed.size
            assert spec["threshold"] == 150

            provenance = ocr.observation_provenance(run_id, "eview", "f_000013.png")
            assert provenance["preprocess_profile"] == ocr.PREPROCESS_PROFILE_PACKET, provenance
            assert provenance["capture_profile"] == ocr.CAPTURE_PROFILE_PACKETLOGGER, provenance
            assert provenance["video_timestamp_seconds"] == 1.0, provenance

            assert ocr.delete_layout_profile("my_1080p_layout") is True
            assert "my_1080p_layout" not in ocr.load_layout_profiles()
            assert ocr.delete_layout_profile("chat_only") is False

            template = (
                Path(__file__).resolve().parents[1] / "gui" / "templates" / "ocr_run.html"
            ).read_text(encoding="utf-8")
            assert "Reusable screen layouts" in template
            assert 'name="preprocess"' in template
            assert "Save current sections as layout" in template

    finally:
        ocr.RUNS_ROOT = original_runs
        ocr.LAYOUT_PROFILE_PATH = original_layout
        ocr.OCR_TIMING_PATH = original_timing
        ocr.cmd_frames = original_cmd_frames

    print("OCR layout/preprocessing profile regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
