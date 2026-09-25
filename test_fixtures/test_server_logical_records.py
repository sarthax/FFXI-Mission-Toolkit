#!/usr/bin/env python3
"""Regression checks for source-neutral logical server records."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, TopazAdapter
from workbench.adapters.servers.logical import compare_records

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        topaz=TopazAdapter(root)
        dsp=DSPAdapter(root)

        t=topaz.normalize_row("item_equipment",{
            "itemId":1234,"name":"test_blade","level":99,"ilevel":119,
            "jobs":1,"shieldSize":0,"slot":1,"rslot":0,
        })
        d=dsp.normalize_row("item_equipment",{
            "itemid":1234,"name":"test_blade","level":99,"ilevel":119,
            "jobs":1,"shieldsize":0,"slot":1,"rslot":0,
        })
        eq=compare_records(t,d)
        assert eq.status=="EQUIVALENT",eq

        ti=topaz.normalize_row("instances",{
            "instanceid":42,"instance_name":"Example","instance_zone":56,
            "entrance_zone":55,"start_x":1.0,"start_y":2.0,"start_z":3.0,
        })
        di=dsp.normalize_row("instances",{
            "instanceid":42,"instance_name":"Example",
            "entrance_zone":55,"start_x":1.0,"start_y":2.0,"start_z":3.0,
        })
        diff=compare_records(ti,di)
        assert diff.status=="DIFFERENT",diff
        assert len(diff.differences)==1,diff
        assert diff.differences[0].field=="instance_zone",diff
        assert diff.differences[0].status=="MISSING_FIELD_VALUE",diff
    print("logical server record self-test: PASS")

if __name__=="__main__":
    main()
