"""DAT Inspector must describe installed decoders without inventing parse certainty."""
from __future__ import annotations

from types import SimpleNamespace

from workbench.client.dat import inspector


def test_parser_inventory_handles_missing_bindings(monkeypatch):
    monkeypatch.setattr(inspector, "xi_tinkerer", None)
    report = inspector.parser_capabilities()
    assert report["bindings_installed"] is False
    assert report["available_count"] == 0
    assert report["registered_count"] == len(inspector.PARSERS)


def test_inspection_marks_missing_decoder_without_falsely_matching(tmp_path, monkeypatch):
    dat = tmp_path / "example.DAT"
    dat.write_bytes(b"not a supported structured DAT")
    monkeypatch.setattr(inspector, "PARSERS", ("parse_dialog", "parse_events"))
    monkeypatch.setattr(inspector, "xi_tinkerer", SimpleNamespace(
        parse_dialog=lambda path: {"lines": ["hello"]},
    ))
    report = inspector._inspect_path(dat, client_root=tmp_path)
    assert report["parser_capabilities"]["available_count"] == 1
    assert report["parser_match_count"] == 1
    assert report["matches"][0]["parser"] == "parse_dialog"
    assert report["rejected"][0]["parser"] == "parse_events"
    assert report["rejected"][0]["unavailable"] is True
    assert report["classification"]["status"] == "recognized"
