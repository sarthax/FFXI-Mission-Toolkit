#!/usr/bin/env python3
"""Focused regression coverage for Client Overview multi-snapshot GUI support."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.client import identity_gui
from workbench.client.identity_extract import ExtractionResult
from workbench.core.services.identity_resolver import ensure_schema
from workbench.gui_shell import build_shell_context


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "gui" / "templates"


def _request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path), method="GET")


def _shell(path: str) -> dict:
    return build_shell_context(
        path=path,
        method="GET",
        settings={},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def _render(**values) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(("html",)),
    )
    env.globals.update(
        current_theme=lambda: "light",
        backport_enabled=lambda: False,
        shell_context=lambda _request: _shell("/clientoverview"),
    )
    return env.get_template("client_overview.html").render(
        request=_request("/clientoverview"),
        **values,
    )


def _insert_record(
    con: sqlite3.Connection,
    record_id: str,
    snapshot_id: str,
    namespace: str,
    numeric_id: str,
):
    con.execute(
        "INSERT INTO identity_records "
        "(record_id,snapshot_id,namespace,semantic_key,numeric_id,zone_key,actor_key,"
        "owner_key,content_fingerprint,evidence_id,confidence,metadata_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            record_id,
            snapshot_id,
            namespace,
            f"{namespace.lower()}:{numeric_id}",
            numeric_id,
            "TEST_ZONE",
            "100",
            None,
            None,
            None,
            "HIGH",
            "{}",
        ),
    )


def main() -> int:
    with TemporaryDirectory() as td:
        root = Path(td)
        db = root / "workbench.db"
        current_client = root / "current-client"
        current_client.mkdir()

        con = sqlite3.connect(db)
        ensure_schema(con)
        con.execute(
            "INSERT INTO identity_snapshots VALUES (?,?,?,?,?,?,?,?)",
            (
                "client-current",
                "CLIENT",
                "RETAIL",
                "30191204_1",
                "2026-09-26T00:00:00+00:00",
                str(current_client),
                "fingerprint-a",
                json.dumps({"region": "NA", "language": "EN"}),
            ),
        )
        _insert_record(con, "event-1", "client-current", "EVENT", "10")
        _insert_record(con, "event-2", "client-current", "EVENT", "11")
        _insert_record(con, "entity-1", "client-current", "ENTITY", "100")
        _insert_record(con, "dialog-1", "client-current", "DIALOG", "200")
        con.commit()
        con.close()

        rows = identity_gui.list_client_snapshots(
            db,
            current_snapshot_id="unrelated-installed-id",
            current_client_path=str(current_client),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["snapshot_id"] == "client-current"
        assert row["build"] == "30191204_1"
        assert row["region"] == "NA"
        assert row["language"] == "EN"
        assert row["event_count"] == 2
        assert row["entity_count"] == 1
        assert row["dialog_count"] == 1
        assert row["is_current"] is True

        try:
            identity_gui.validate_client_snapshot_import(
                client_root=root / "missing",
                snapshot_id="new-client",
                xi_tinkerer=root / "xi.exe",
                db_path=db,
                output_dir=root / "snapshots" / "new-client",
            )
            raise AssertionError("missing client root should fail")
        except identity_gui.ClientSnapshotImportError as ex:
            assert "does not exist" in str(ex)

        import_client = root / "import-client"
        import_client.mkdir()
        xi = root / "xi-tinkerer-cli.exe"
        xi.write_bytes(b"tool")
        for name in ("FFXiMain.dll", "FTABLE.DAT", "VTABLE.DAT"):
            (import_client / name).write_bytes(b"fixture")

        assert identity_gui.validate_client_snapshot_import(
            client_root=import_client,
            snapshot_id="new-client",
            xi_tinkerer=xi,
            db_path=db,
            output_dir=root / "snapshots" / "new-client",
        ) == "new-client"

        try:
            identity_gui.validate_client_snapshot_import(
                client_root=import_client,
                snapshot_id="client-current",
                xi_tinkerer=xi,
                db_path=db,
                output_dir=root / "snapshots" / "client-current",
            )
            raise AssertionError("duplicate snapshot ID should fail")
        except identity_gui.ClientSnapshotImportError as ex:
            assert "already exists" in str(ex)

        nonempty = root / "snapshots" / "occupied"
        nonempty.mkdir(parents=True)
        (nonempty / "payload.yml").write_text("fixture", encoding="utf-8")
        try:
            identity_gui.validate_client_snapshot_import(
                client_root=import_client,
                snapshot_id="occupied",
                xi_tinkerer=xi,
                db_path=db,
                output_dir=nonempty,
            )
            raise AssertionError("non-empty output directory should fail")
        except identity_gui.ClientSnapshotImportError as ex:
            assert "will not be overwritten" in str(ex)

        zone_db = root / "zones.db"
        zcon = sqlite3.connect(zone_db)
        zcon.execute("CREATE TABLE zones (zoneid INTEGER PRIMARY KEY, name TEXT)")
        zcon.executemany(
            "INSERT INTO zones(zoneid,name) VALUES (?,?)",
            [(1, "Phanauet Channel"), (55, "Ilrusi Atoll")],
        )
        zcon.commit()
        zcon.close()
        import_db = root / "import-workbench.db"
        captured = {}
        original_extract = identity_gui.extract_client_identity_snapshot
        original_ingest = identity_gui.ingest_client_identity_manifest

        def fake_extract(**kwargs):
            captured["extract"] = kwargs
            output = Path(kwargs["output_dir"])
            output.mkdir(parents=True, exist_ok=True)
            manifest = output / "identity_snapshot.json"
            manifest.write_text("{}", encoding="utf-8")
            return ExtractionResult(
                snapshot_id=kwargs["snapshot_id"],
                output_dir=str(output),
                build=kwargs["build"],
                client_fingerprint="fixture-fingerprint",
                resources=(),
                failures=(),
                manifest_path=str(manifest),
            )

        def fake_ingest(con, *, manifest_path, snapshot_root=None):
            captured["ingest"] = {
                "manifest_path": Path(manifest_path),
                "snapshot_root": Path(snapshot_root),
            }
            return {
                "record_count": 12,
                "failures": [],
                "entity_graph": {
                    "status": "OK",
                    "semantic_entities": 4,
                    "identifiers": 4,
                    "relationships": 4,
                },
            }

        try:
            identity_gui.extract_client_identity_snapshot = fake_extract
            identity_gui.ingest_client_identity_manifest = fake_ingest
            result = identity_gui.import_client_snapshot(
                client_root=import_client,
                snapshot_id="retail-2022",
                build_label="2022 retail",
                region="NA",
                language="EN",
                xi_tinkerer=xi,
                db_path=import_db,
                zone_db=zone_db,
                snapshots_root=root / "client_snapshots",
            )
        finally:
            identity_gui.extract_client_identity_snapshot = original_extract
            identity_gui.ingest_client_identity_manifest = original_ingest

        assert result["record_count"] == 12
        assert result["entity_graph"]["semantic_entities"] == 4
        assert result["entity_graph"]["relationships"] == 4
        requests = list(captured["extract"]["zones"])
        assert [(r.zone_id, r.zone_key) for r in requests] == [
            (1, "PHANAUET_CHANNEL"),
            (55, "ILRUSI_ATOLL"),
        ]
        assert captured["extract"]["build"] == "2022 retail"
        assert captured["extract"]["region"] == "NA"
        assert captured["extract"]["language"] == "EN"
        assert captured["ingest"]["manifest_path"].name == "identity_snapshot.json"

        summary = identity_gui.summarize_comparison({
            "total": 9,
            "counts": {
                "EXACT": 2,
                "TARGET_EQUIVALENT": 3,
                "TARGET_ID_AMBIGUOUS": 1,
                "SOURCE_ID_AMBIGUOUS": 1,
                "TARGET_ID_LOW_CONFIDENCE": 1,
                "TARGET_ID_UNRESOLVED": 1,
            },
        })
        assert summary == {
            "total": 9,
            "EXACT": 2,
            "TARGET_EQUIVALENT": 3,
            "ambiguous": 2,
            "LOW_CONFIDENCE": 1,
            "unresolved": 1,
        }

        gui_source = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
        assert '@app.post("/clientoverview/import"' in gui_source
        assert '@app.post("/clientoverview/compare"' in gui_source
        assert '@app.get("/clientoverview/compare.csv")' in gui_source
        assert "identity_gui.compare_client_snapshots(" in gui_source

        comparison = {
            "source_snapshot_id": "client-a",
            "target_snapshot_id": "client-b",
            "zone_key": None,
            "minimum_confidence": "HIGH",
            "entity_diagnostics": {
                "total": 1,
                "constraint_ready": 1,
                "counts": {"TARGET_EQUIVALENT": 1},
                "rows": [{
                    "zone_key": "ILRUSI_ATOLL",
                    "source_actor_id": "17000001",
                    "semantic_identity": "Door Alpha",
                    "target_actor_id": "17000099",
                    "status": "TARGET_EQUIVALENT",
                    "confidence": "HIGH",
                    "target_candidates": [{"numeric_id": "17000099"}],
                    "reason": "Semantic identity matches with target numeric drift.",
                    "recommendation": "Actor identity is strong enough to constrain target EVENT candidates.",
                }],
            },
            "rows": [{
                "zone_key": "ILRUSI_ATOLL",
                "source_actor_key": "17000001",
                "source_event_id": "100",
                "target_actor_key": "17000099",
                "actor_status": "TARGET_EQUIVALENT",
                "actor_confidence": "HIGH",
                "actor_semantic_identity": "Door Alpha",
                "actor_candidate_count": 1,
                "actor_reason": "Semantic identity matches with target numeric drift.",
                "actor_recommendation": "Actor identity is strong enough to constrain target EVENT candidates.",
                "target_event_id": "101",
                "status": "TARGET_EQUIVALENT",
                "confidence": "HIGH",
                "match_basis": "DECODED_STRUCTURE",
                "reason": "Unique target EVENT matched by DECODED_STRUCTURE.",
            }],
        }
        html = _render(
            error="installed client fixture unavailable",
            ov=None,
            snapshots=rows,
            import_result={
                "snapshot_id": "fixture-import",
                "record_count": 4,
                "resources": 3,
                "zones_requested": 1,
                "extraction_failures": [],
                "ingest_failures": [],
                "entity_graph": {
                    "semantic_entities": 2,
                    "identifiers": 2,
                    "relationships": 2,
                },
            },
            import_error=None,
            comparison=comparison,
            comparison_summary=identity_gui.summarize_comparison({
                "total": 1, "counts": {"TARGET_EQUIVALENT": 1},
            }),
            entity_summary=identity_gui.summarize_entity_diagnostics({
                "total": 1,
                "constraint_ready": 1,
                "counts": {"TARGET_EQUIVALENT": 1},
            }),
            compare_error=None,
            import_form={
                "client_root": str(import_client),
                "snapshot_id": "",
                "build_label": "",
                "region": "",
                "language": "",
            },
            compare_form={
                "source_snapshot": "client-a",
                "target_snapshot": "client-b",
                "zone": "",
                "minimum_confidence": "HIGH",
            },
        )
        assert "Imported Client Snapshots" in html
        assert "Compare Client Builds" in html
        assert "TARGET_EQUIVALENT" in html
        assert "EVENT rows" in html
        assert '<body class="shell-dense">' in html
        assert 'class="client-kpis"' in html
        assert 'class="client-form-grid"' in html
        assert "17000001" in html
        assert "17000099" in html
        assert "DECODED_STRUCTURE" in html
        assert "ENTITY / Actor Identity Coverage" in html
        assert "Feature Trace mirror" in html
        assert "Constraint-ready 1" in html
        assert "Door Alpha" in html
        assert "Export comparison CSV" in html

    print("Client snapshot GUI regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
