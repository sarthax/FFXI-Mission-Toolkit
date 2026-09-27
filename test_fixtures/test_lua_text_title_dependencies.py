#!/usr/bin/env python3
"""Regression for zone text and title dependency discovery from Lua."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.analyzers.server.lua_dependencies import analyze_script
from workbench.core import graph
from workbench.core.schema import MigrationAction
from workbench.migrations.package_scope import build_dependency_scope


SCRIPT = """local ID = zones[xi.zone.ARRAPAGO_REEF]
local entity = {}

entity.onMobEngage = function(mob, target)
    target:showText(mob, ID.text.MEDUSA_ENGAGE)
end

entity.onMobDeath = function(mob, player)
    player:addTitle(xi.title.GORGONSTONE_SUNDERER)
    player:showText(mob, ID.text.MEDUSA_DEATH)
end

return entity
"""

IDS = """zones = zones or {}
zones[xi.zone.ARRAPAGO_REEF] =
{
    text =
    {
        MEDUSA_ENGAGE = 8600,
        MEDUSA_DEATH  = 8601,
    },
    mob =
    {
    },
}
return zones[xi.zone.ARRAPAGO_REEF]
"""

TITLES = """xi = xi or {}
xi.title =
{
    GORGONSTONE_SUNDERER = 475,
}
"""


def main() -> int:
    with TemporaryDirectory() as td:
        root=Path(td)
        script=root/"scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
        ids=root/"scripts/zones/Arrapago_Reef/IDs.lua"
        titles=root/"scripts/enum/title.lua"
        for path in (script,ids,titles):
            path.parent.mkdir(parents=True,exist_ok=True)
        script.write_text(SCRIPT,encoding="utf-8")
        ids.write_text(IDS,encoding="utf-8")
        titles.write_text(TITLES,encoding="utf-8")

        payload=analyze_script(
            root,
            script,
            source_snapshot_id="lsb:test",
            zone_id=54,
            ids_lua=ids,
            titles_lua=titles,
        )

        assert payload["summary"]["zone_text_dependencies"]==2,payload["summary"]
        assert payload["summary"]["title_dependencies"]==1,payload["summary"]
        assert payload["summary"]["unresolved_findings"]==0,payload["summary"]

        by_type={}
        for row in payload["entities"]:
            by_type.setdefault(row["entity_type"],[]).append(row)

        texts={row["display_name"]:row for row in by_type["ZONE_TEXT"]}
        assert texts["MEDUSA_ENGAGE"]["metadata"]["text_id"]==8600,texts
        assert texts["MEDUSA_DEATH"]["metadata"]["text_id"]==8601,texts

        titles_out={row["display_name"]:row for row in by_type["TITLE"]}
        assert titles_out["GORGONSTONE_SUNDERER"]["metadata"]["title_id"]==475,titles_out

        text_edges=[edge for edge in payload["edges"] if edge["edge_id"].startswith("lua-zone-text:")]
        title_edges=[edge for edge in payload["edges"] if edge["edge_id"].startswith("lua-title:")]
        assert len(text_edges)==2,text_edges
        assert len(title_edges)==1,title_edges
        assert all(edge["relationship"]=="REQUIRES" for edge in text_edges+title_edges),payload["edges"]
        assert all(edge["confidence"]=="VERIFIED" for edge in text_edges+title_edges),payload["edges"]

        out=root/"analysis.json"
        out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        db=root/"workbench.db"
        graph.import_json(out,db)

        con=sqlite3.connect(db)
        try:
            source_artifact=next(
                row["artifact_id"] for row in payload["artifacts"]
                if row["path"]=="scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
            )
            con.execute(
                "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
                ("migration:medusa-text","feature:medusa","lsb:test","dsp:test","DISCOVERED","{}"),
            )
            graph.insert_record(
                con,
                MigrationAction(
                    "action:medusa-text",
                    "migration:medusa-text",
                    "CONVERT",
                    source_artifact,
                    "AUTO_MIGRATABLE",
                    "Medusa text/title root",
                ),
            )
            con.commit()
            scope=build_dependency_scope(con,"migration:medusa-text")
            labels={item["display_name"] for item in scope["items"] if item["display_name"]}
            assert "MEDUSA_ENGAGE" in labels,labels
            assert "MEDUSA_DEATH" in labels,labels
            assert "GORGONSTONE_SUNDERER" in labels,labels
        finally:
            con.close()

        unresolved=analyze_script(
            root,
            script,
            source_snapshot_id="lsb:test",
            zone_id=54,
            ids_lua=None,
            titles_lua=root/"missing_titles.lua",
        )
        fields={row["field"] for row in unresolved["findings"]}
        assert "ID.text.MEDUSA_ENGAGE" in fields,fields
        assert "ID.text.MEDUSA_DEATH" in fields,fields
        assert "xi.title.GORGONSTONE_SUNDERER" in fields,fields

    print("Lua zone text/title dependency self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
