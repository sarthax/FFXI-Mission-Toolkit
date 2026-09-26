#!/usr/bin/env python3
"""Regression coverage for item_basic logical schema mapping and lineage drift."""
from pathlib import Path
import tempfile

from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter
from workbench.adapters.servers.logical import compare_records


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        topaz=TopazAdapter(root); dsp=DSPAdapter(root); lsb=LSBAdapter(root)

        t=topaz.normalize_row("item_basic",{
            "itemid":1234,"subid":0,"name":"test_item","sortname":"test item",
            "stackSize":12,"flags":5,"aH":99,"NoSale":1,"BaseSell":250,
        })
        d=dsp.normalize_row("item_basic",{
            "itemid":1234,"subid":0,"name":"test_item","sortname":"test item",
            "stackSize":12,"flags":5,"aH":99,"NoSale":1,"BaseSell":250,
        })
        assert compare_records(t,d).status=="EQUIVALENT"

        l=lsb.normalize_row("item_basic",{
            "itemid":1234,"subid":0,"name":"test_item","sortname":"test item",
            "name_jp":"test_jp","type":0,"stackSize":12,"flags":5,"aH":99,"BaseSell":250,
        })

        assert l.identity==( ("item_id",1234), ),l
        assert l.fields["stack_size"]==12,l
        assert l.fields["auction_house_category"]==99,l
        assert l.fields["base_sell"]==250,l
        assert l.fields["name_jp"]=="test_jp",l
        assert l.fields["item_type"]==0,l
        assert "no_sale" not in l.fields,l

        diff=compare_records(t,l)
        fields={d.field:d.status for d in diff.differences}
        assert fields["no_sale"]=="MISSING_FIELD_VALUE",diff
        assert fields["name_jp"]=="MISSING_FIELD_VALUE",diff
        assert fields["item_type"]=="MISSING_FIELD_VALUE",diff

    print("item_basic logical schema self-test: PASS")

if __name__=="__main__":
    raise SystemExit(main())
