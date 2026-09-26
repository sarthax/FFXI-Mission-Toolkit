#!/usr/bin/env python3
"""External-source integration smoke test against a real LandSandBoat checkout."""
from __future__ import annotations
import json, sqlite3, tempfile
from dataclasses import asdict
from pathlib import Path
import sys

from workbench.adapters.servers import LSBAdapter
from workbench.adapters.servers.sql_extract import extract_logical_records
from workbench.migrations.instance_feature_slice import extract_instance_feature_slice
from cpp_api_index import index as index_api
from cpp_dependency_index import index as index_dependencies
from build_integration_index import index as index_build
from workbench_connect_server import import_payload


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_external_lsb_pipeline.py <lsb-root>")
    root=Path(sys.argv[1]).resolve()
    probe=LSBAdapter(root).probe()
    assert probe.compatible,probe

    functions,enums,bindings=index_api(root)
    dependencies=index_dependencies(root)
    _builders,_findings,targets,build_edges=index_build(root)

    adapter=LSBAdapter(root)
    logical_counts={}
    for logical_name in ("npc","mob_pools","mob_groups","mob_spawns","mob_drops","instance_entities","instances"):
        logical_counts[logical_name]=len(extract_logical_records(adapter,logical_name))
    assert logical_counts["npc"]>0,logical_counts
    assert logical_counts["mob_spawns"]>0,logical_counts
    assert logical_counts["instances"]>0,logical_counts

    excavation=extract_instance_feature_slice(adapter,6300)
    assert excavation.instance is not None,excavation
    assert excavation.instance.fields.get("name")=="excavation_duty",excavation.instance
    assert excavation.counts()["instance_entities"]>0,excavation.counts()
    assert excavation.counts()["mob_spawns"]>0,excavation.counts()

    assert functions,"no C++ functions indexed from external LSB source"
    assert enums,"no enums/constants indexed from external LSB source"
    assert dependencies,"no C++ dependencies indexed from external LSB source"
    assert targets,"no build targets indexed from external LSB source"

    with tempfile.TemporaryDirectory() as td:
        t=Path(td); payload=t/"external.json"; graph=t/"workbench.db"
        payload.write_text(json.dumps({
            "functions":[asdict(x) for x in functions],
            "bindings":[asdict(x) for x in bindings],
            "enums_constants":[asdict(x) for x in enums],
            "build_targets":[asdict(x) for x in targets],
            "edges":[asdict(x) for x in dependencies+build_edges],
        }),encoding="utf-8")
        result=import_payload(payload,graph)
        con=sqlite3.connect(graph)
        counts={
            "functions":con.execute("SELECT COUNT(*) FROM functions").fetchone()[0],
            "enums":con.execute("SELECT COUNT(*) FROM enum_definitions").fetchone()[0],
            "targets":con.execute("SELECT COUNT(*) FROM build_targets").fetchone()[0],
            "edges":con.execute("SELECT COUNT(*) FROM entity_relationships").fetchone()[0],
        }
        con.close()
        assert counts["functions"]>0,counts
        assert counts["enums"]>0,counts
        assert counts["targets"]>0,counts
        assert counts["edges"]>0,counts
        print(json.dumps({"probe":asdict(probe),"logical_counts":logical_counts,"excavation_duty":excavation.counts(),"imported":result["imported"],"graph_counts":counts},indent=2))


if __name__=="__main__":
    main()
