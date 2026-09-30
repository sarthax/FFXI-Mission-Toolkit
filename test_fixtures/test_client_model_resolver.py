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
    assert '@app.get("/modelviewer/model.json")' in server
    assert 'id="modelid"' in viewer
    assert 'id="load-modelid"' in viewer
    assert "async function loadRawModel()" in viewer
    assert "qp.get('embed')==='1'" in viewer
    assert 'id="ed-model-details"' in zone
    assert 'id="modelPreviewFrame"' in zone
    assert "function selectedModelViewerUrl(embed=false)" in zone
    assert "function refreshSelectedModelPreview(force=false)" in zone

    print("Client model resolver/viewer integration regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
