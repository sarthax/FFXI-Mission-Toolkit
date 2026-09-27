#!/usr/bin/env python3
"""Regression checks for conservative logical migration planning."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, TopazAdapter
from workbench.adapters.servers.logical import compare_records
from workbench.migrations.logical_planner import plan_logical_comparison

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        topaz=TopazAdapter(root); dsp=DSPAdapter(root)

        src=topaz.normalize_row("item_equipment",{"itemId":1,"name":"x","level":99})
        dst=dsp.normalize_row("item_equipment",{"itemid":1,"name":"x","level":99})
        actions=plan_logical_comparison(compare_records(src,dst),"m1")
        assert len(actions)==1 and actions[0].action=="NOT_REQUIRED",actions
        assert actions[0].status=="COMPATIBLE",actions

        src_i=topaz.normalize_row("instances",{"instanceid":7,"instance_name":"Demo","instance_zone":56})
        dst_i=dsp.normalize_row("instances",{"instanceid":7,"instance_name":"Demo"})
        actions=plan_logical_comparison(compare_records(src_i,dst_i),"m2")
        assert len(actions)==1,actions
        assert actions[0].action=="MANUAL_REVIEW",actions
        assert actions[0].status=="MANUAL_REQUIRED",actions
        assert actions[0].metadata["field"]=="instance_zone",actions
    print("logical migration planner self-test: PASS")

if __name__=="__main__":
    main()
