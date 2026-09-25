#!/usr/bin/env python3
"""Regression checks for logical server schema profiles."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter, adapter_for

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
    print("server adapter profile self-test: PASS")

if __name__=="__main__":
    main()
