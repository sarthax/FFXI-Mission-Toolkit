#!/usr/bin/env python3
"""Focused regression coverage for the Client DAT Inspector UX."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.client.dat import inspector as dat_inspector
from workbench.gui_shell import build_shell_context


ROOT=Path(__file__).resolve().parents[1]
TEMPLATES=ROOT/"gui"/"templates"


def request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path),method="GET")


def shell(path: str):
    return build_shell_context(
        path=path,
        method="GET",
        settings={},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def render(**values) -> str:
    env=Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(("html",)),
    )
    env.globals.update(
        current_theme=lambda: "light",
        backport_enabled=lambda: False,
        shell_context=lambda _request: shell("/datinspector"),
    )
    return env.get_template("dat_inspector.html").render(
        request=request("/datinspector"),
        **values,
    )


def main() -> int:
    assert dat_inspector.dat_id_for_zone_family(77,"dialog")==6497
    assert dat_inspector.dat_id_for_zone_family(55,"events")==5875
    assert dat_inspector.id_hint(6497)=="per-zone dialog for zoneid 77"

    try:
        dat_inspector.dat_id_for_zone_family(77,"unknown")
    except ValueError as ex:
        assert "Unknown DAT family" in str(ex)
    else:
        raise AssertionError("unknown family must fail")

    with TemporaryDirectory() as td:
        root=Path(td)/"FINAL FANTASY XI"
        dat_dir=root/"ROM"/"7"
        dat_dir.mkdir(parents=True)
        dat_path=dat_dir/"44.DAT"
        dat_path.write_bytes(bytes(range(64)))

        safe=dat_inspector._path_under_client(str(root),"ROM/7/44.DAT")
        assert safe==dat_path.resolve(),safe

        outside=Path(td)/"outside.DAT"
        outside.write_bytes(b"x")
        try:
            dat_inspector._path_under_client(str(root),str(outside))
        except ValueError as ex:
            assert "inside the configured FFXI client root" in str(ex)
        else:
            raise AssertionError("outside path must fail")

        summary=dat_inspector._summary({
            "entries":[1,2,3],
            "metadata":{"a":1,"b":2},
            "name":"fixture",
        })
        assert summary["kind"]=="mapping",summary
        assert summary["collection_counts"]=={"entries":3,"metadata":2},summary
        assert "name" in summary["field_names"],summary

        presentation=dat_inspector._presentation({
            "language":"English",
            "entries":[{"id":1,"text":"One"},{"id":2,"text":"Two"}],
        })
        assert presentation["scalars"]==[{"name":"language","value":"English"}],presentation
        assert presentation["collections"][0]["name"]=="entries",presentation
        assert presentation["collections"][0]["count"]==2,presentation

        classification=dat_inspector._classify([
            {"parser":"parse_dialog","label":"Dialog text"},
        ],"dialog")
        assert classification["status"]=="recognized",classification
        assert classification["verdict"]=="Decoded as Dialog text",classification

        mismatch=dat_inspector._classify([
            {"parser":"parse_entity_names","label":"Entity names"},
        ],"dialog")
        assert mismatch["warnings"],mismatch

        multiple=dat_inspector._classify([
            {"parser":"parse_dialog","label":"Dialog text"},
            {"parser":"parse_xistring_table","label":"XI string table"},
        ],"dialog")
        assert multiple["status"]=="multiple",multiple

        original_parsers=dat_inspector.PARSERS
        original_module=dat_inspector.xi_tinkerer
        fake_module=SimpleNamespace()
        dat_inspector.xi_tinkerer=fake_module
        dat_inspector.PARSERS=("parse_dialog","parse_events")
        dat_inspector.xi_tinkerer.parse_dialog=lambda path:{
            "strings":["One","Two","Three"],
            "language":"English",
        }

        def reject(_path):
            raise ValueError("not an event DAT")
        dat_inspector.xi_tinkerer.parse_events=reject
        try:
            result=dat_inspector.inspect_path(str(root),"ROM/7/44.DAT")
        finally:
            dat_inspector.PARSERS=original_parsers
            dat_inspector.xi_tinkerer=original_module

        assert result["rom_relative"]=="ROM/7/44.DAT",result
        assert result["parser_match_count"]==1,result
        assert result["parser_reject_count"]==1,result
        assert result["matches"][0]["label"]=="Dialog text",result
        assert result["matches"][0]["summary"]["collection_counts"]["strings"]==3,result
        assert result["matches"][0]["presentation"]["collections"][0]["name"]=="strings",result
        assert result["classification"]["status"]=="recognized",result
        assert len(result["header_hex"].split())==64,result

        html=render(
            result={
                **result,
                "dat_id":6497,
                "family_hint":"per-zone dialog for zoneid 77",
                "extractor_note":"fixture resolver",
                "zone_name":"Nyzul Isle",
                "actions":[
                    {"label":"Open Dialog Browser","href":"/dialog?zone=Nyzul%20Isle","note":"Search decoded messages.","primary":True},
                    {"label":"Open Model Viewer","href":"/modelviewer","note":"Try direct DAT correlation.","primary":False},
                ],
            },
            error=None,
            dat_id="6497",
            zoneid="77",
            family="dialog",
            dat_path="",
            resolved_dat_id=6497,
            selected_mode="id",
            ffxi_path=str(root),
            families=[
                {"name":"events","label":"Events / cutscenes","base":5820},
                {"name":"dialog","label":"Dialog / message text","base":6420},
            ],
            zones=[
                {"zoneid":55,"name":"Ilrusi Atoll"},
                {"zoneid":77,"name":"Nyzul Isle"},
            ],
        )
        assert "Open a DAT" in html
        assert "Alternate ways to locate one" in html
        assert "77 — Nyzul Isle" in html
        assert "Identification verdict" in html
        assert "Decoded as Dialog text" in html
        assert "What can I do with this?" in html
        assert "Open Dialog Browser" in html
        assert "Decoded collections" in html
        assert "Raw decoded JSON" in html
        assert "File identity / provenance" in html
        assert "Rejected structured parsers (1)" in html
        assert "6496" in html and "6498" in html
        assert "ROM/7/44.DAT" in html

    source=(ROOT/"src"/"workbench"/"app"/"_host_impl.py").read_text(encoding="utf-8")
    assert 'dat_path: str = ""' in source
    assert 'family: str = ""' in source
    assert "dat_id_for_zone_family" in source
    assert "SELECT zoneid,name FROM zones" in source
    assert 'result["actions"] = actions' in source
    assert "Open Events / CSID" in source
    assert "Open Dialog Browser" in source
    assert "Client Overview / ID Drift" in source

    print("DAT Inspector UX regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
