#!/usr/bin/env python3
"""Regression checks for logical server schema profiles."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import (
    CustomForkAdapter, DSPAdapter, LSBAdapter, TOPAZ, TopazAdapter, TopazNextAdapter, adapter_for,
)
from workbench.adapters.servers.base import TableShape

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        assert TopazAdapter(root).probe().compatible
        assert LSBAdapter(root).resolve_table("item_equipment").source_file=="item_equipment.sql"
        dsp=DSPAdapter(root)
        assert dsp.resolve_table("item_equipment").source_file=="item_armor.sql"
        assert "instance_zone" in " ".join(dsp.resolve_table("instances").notes)
        assert adapter_for("landsandboat",root).family=="LSB"
        assert adapter_for("darkstar",root).family=="DSP"

        topaz_next=adapter_for("topaz-next",root)
        assert isinstance(topaz_next,TopazNextAdapter),topaz_next
        assert topaz_next.family=="TOPAZ_NEXT"
        assert topaz_next.schema_profile.profile_id=="topaz-next"
        assert topaz_next.schema_profile is not TOPAZ
        assert topaz_next.resolve_table("mob_spawns")==TOPAZ.table("mob_spawns")
        tn_record=topaz_next.normalize_row("item_basic",{
            "itemid":1,"subid":0,"name":"demo","sortname":"demo",
            "stackSize":1,"flags":0,"aH":99,"NoSale":0,"BaseSell":0,
        })
        assert tn_record.source_family=="TOPAZ_NEXT",tn_record
        assert tn_record.identity==( ("item_id",1), ),tn_record

        override=TableShape(
            "item_equipment","custom_equipment.sql","custom_equipment",
            field_mappings=TOPAZ.table("item_equipment").field_mappings,
            identity_fields=("item_id",),
        )
        custom=CustomForkAdapter(
            root,
            fork_id="my-fork",
            base_profile=TOPAZ,
            table_overrides={"item_equipment":override},
            notes=("fixture override",),
        )
        assert custom.family=="CUSTOM:my-fork"
        assert custom.schema_profile.profile_id=="custom:my-fork"
        assert custom.resolve_table("item_equipment").source_file=="custom_equipment.sql"
        assert TOPAZ.table("item_equipment").source_file=="item_equipment.sql"
        assert custom.resolve_table("mob_spawns")==TOPAZ.table("mob_spawns")
        assert "fixture override" in custom.schema_profile.notes
        custom_record=custom.normalize_row("item_equipment",{
            "itemId":123,"name":"custom_item","level":50,"ilevel":0,
            "jobs":1,"shieldSize":0,"slot":1,"rslot":0,
        })
        assert custom_record.source_family=="CUSTOM:my-fork",custom_record
        assert custom_record.source_table=="custom_equipment",custom_record
        assert custom_record.identity==( ("item_id",123), ),custom_record
    print("server adapter profile self-test: PASS")

if __name__=="__main__":
    main()
