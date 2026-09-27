#!/usr/bin/env python3
"""Regression checks for feature-surface validation records and run linkage."""
from pathlib import Path
import tempfile
from workbench.core import graph
from workbench.core.services.feature_surface_validation import build_feature_surface_validation
from workbench.migrations.feature_surface import FeatureSurface, SurfaceArtifact, compare_feature_surfaces

def main():
    src=FeatureSurface("feature:test","SRC",(SurfaceArtifact("script","a.lua","LUA"),),(1,2))
    dst=FeatureSurface("feature:test","DST",(SurfaceArtifact("script","b.lua","LUA"),),(1,2))
    comparison=compare_feature_surfaces(src,dst)
    run,results=build_feature_surface_validation(
        comparison,
        run_id="validation:surface:test",
        source_snapshot_id="src",
        target_snapshot_id="dst",
    )
    assert run.status=="VERIFIED",run
    assert len(results)==1 and results[0].run_id==run.run_id,results
    assert results[0].status=="VERIFIED",results

    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        graph.insert_record(con,run)
        graph.insert_record(con,results[0])
        row=con.execute("SELECT run_id,status FROM validation_results WHERE validation_id=?",(results[0].validation_id,)).fetchone()
        assert row==("validation:surface:test","VERIFIED"),row
        edge=con.execute("SELECT relationship,status FROM entity_relationships WHERE relationship_id=?",
                         (f"validated-by:{results[0].validation_id}",)).fetchone()
        assert edge==("VALIDATED_BY","VERIFIED"),edge
        con.close()
    print("feature surface validation self-test: PASS")

if __name__=="__main__":
    main()
