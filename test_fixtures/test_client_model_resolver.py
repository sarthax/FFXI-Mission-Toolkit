#!/usr/bin/env python3
"""Regression coverage for the lightweight Client/Zone Editor model-viewer integration."""

from pathlib import Path

import client_model_resolver as cmr

ROOT = Path(__file__).resolve().parents[1]


def main():
    # FFXiMain monster lookup boundaries (VA 0x100C513D).
    expected = {
        0: 1300,
        1499: 2799,
        1500: 51795,
        2999: 53294,
        3000: 99907,
        3193: 100100,   # last currently registered retail id in band 3, not the band boundary
        3499: 100406,
        3500: 101739,
        4000: 102239,
    }
    for model_id, file_id in expected.items():
        got, _rule = cmr.model_id_to_file_id(model_id)
        assert got == file_id, (model_id, got, file_id)

    try:
        cmr.model_id_to_file_id(-1)
        raise AssertionError("negative model id accepted")
    except ValueError:
        pass
    try:
        cmr.model_id_to_file_id(65536)
        raise AssertionError("oversize model id accepted")
    except ValueError:
        pass

    resolver = (ROOT / "client_model_resolver.py").read_text(encoding="utf-8")
    decode = (ROOT / "mob_look_decode.py").read_text(encoding="utf-8")
    backend = (ROOT / "model_viewer.py").read_text(encoding="utf-8")
    server = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    viewer = (ROOT / "gui" / "templates" / "model_viewer.html").read_text(encoding="utf-8")
    zone = (ROOT / "gui" / "templates" / "zone_plot.html").read_text(encoding="utf-8")

    assert "0x100C513D" in resolver
    assert '(3500, 96907, "3000-3499 +96907")' in resolver
    assert '(None, 98239, "3500+ +98239")' in resolver
    assert "client_model_resolver.model_id_to_file_id(modelid)" in decode
    assert "mob_model_tables.resolve_family_file_id" not in decode
    assert "def resolve_model_id(model_id: int" in backend
    assert "legacy hand-verified family visual DAT" in backend
    assert "resource_rom_path" in backend
    assert "render_rom_path" in backend
    assert '@app.get("/modelviewer/model.json")' in server
    assert 'id="modelid"' in viewer
    assert 'id="load-modelid"' in viewer
    assert "async function loadRawModel()" in viewer
    assert "FFXiMain mapping:" in viewer
    assert "render hint:" in viewer
    assert "qp.get('embed')==='1'" in viewer
    assert 'id="ed-model-details"' in zone
    assert 'id="modelPreviewFrame"' in zone
    assert "function selectedModelViewerUrl(embed=false)" in zone
    assert "function refreshSelectedModelPreview(force=false)" in zone
    assert '"face": {' in decode
    assert 'gear_tables.model_id_to_file_id(race_name, "face", face)' in decode
    assert 'info["composition"] = composition' in backend
    assert '"role": "skeleton"' in backend
    assert '"face", "head", "body", "hands", "legs", "feet", "main", "sub", "ranged"' in backend
    assert "composition manifest:" in viewer
    assert "modelGroup.rotation.x = Math.PI" in viewer
    assert "Parsed vertices are already in bind-pose world space" in viewer
    assert "playback disabled: FFXI-specific skinning/pose math" in viewer
    skeleton_parser = (ROOT / "gui" / "static" / "ffxi-dat" / "SkeletonParser.js").read_text(encoding="utf-8")
    assert "Column-major 4x4 multiply" in skeleton_parser
    assert "mat4Multiply(matrices[parent], local)" in skeleton_parser

    print("Client model resolver/viewer integration regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
