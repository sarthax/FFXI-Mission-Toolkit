#!/usr/bin/env python3
"""Regression checks for canonical graph persistence of feature surfaces."""
from pathlib import Path
import tempfile
from workbench.core import graph
from workbench.core.schema import Feature
from workbench.core.services.feature_surface_graph import persist_feature_surface
from workbench.migrations.feature_surface import FeatureSurface, SurfaceArtifact

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        feature=Feature(
            feature_id="feature:test",
            name="Test Feature",
            feature_type="TEST",
            domain_id="domain:test",
            source_snapshot_id="src",
            target_snapshot_id="dst",
            status="ANALYZED",
        )
        src=FeatureSurface(
            feature_id="feature:test",
            family="LSB",
            artifacts=(SurfaceArtifact("battlefield_script","a.lua","LUA"),),
            entity_ids=(100,),
        )
        dst=FeatureSurface(
            feature_id="feature:test",
            family="DSP",
            artifacts=(SurfaceArtifact("battlefield_script","b.lua","LUA"),),
            entity_ids=(100,),
        )
        persist_feature_surface(con,src,feature,"src")
        persist_feature_surface(con,dst,feature,"dst")

        assert con.execute("SELECT COUNT(*) FROM implementations WHERE feature_id='feature:test'").fetchone()[0]==2
        refs={r[0] for r in con.execute("SELECT entity_id FROM entities WHERE entity_type='ENTITY_REF'")}
        assert refs=={"entity-ref:src:100","entity-ref:dst:100"},refs
        edges=con.execute("SELECT target_node,relationship,confidence FROM entity_relationships WHERE relationship='USES_ID' ORDER BY target_node").fetchall()
        assert edges==[
            ("entity-ref:dst:100","USES_ID","VERIFIED"),
            ("entity-ref:src:100","USES_ID","VERIFIED"),
        ],edges
        con.close()
    print("feature surface graph self-test: PASS")

if __name__=="__main__":
    main()
