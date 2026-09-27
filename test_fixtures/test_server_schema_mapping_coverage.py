#!/usr/bin/env python3
"""Regression coverage for server logical schema mapping coverage."""
from workbench.adapters.servers import DSP, LSB, TOPAZ, TOPAZ_NEXT
from workbench.adapters.servers.schema_coverage import compare_profile_coverage, profile_mapping_coverage

def main():
    topaz=profile_mapping_coverage(TOPAZ)
    dsp=profile_mapping_coverage(DSP)
    lsb=profile_mapping_coverage(LSB)

    assert topaz["family"]=="TOPAZ",topaz
    assert dsp["family"]=="DSP",dsp
    assert lsb["family"]=="LSB",lsb

    matrix=compare_profile_coverage((TOPAZ,TOPAZ_NEXT,DSP,LSB))
    rows={row["logical_type"]:row for row in matrix["matrix"]}

    item=rows["item_equipment"]["families"]
    assert item["TOPAZ"]["physical_table"]=="item_equipment",item
    assert item["DSP"]["physical_table"]=="item_armor",item
    assert item["LSB"]["physical_table"]=="item_equipment",item

    instances=rows["instances"]["families"]
    assert "instance_zone" in instances["TOPAZ"]["mapped_logical_fields"],instances
    assert "instance_zone" in instances["DSP"]["mapped_logical_fields"],instances

    # Coverage must expose fields present in parse shapes but not yet promoted to
    # the logical schema. This keeps broader schema work measurable.
    assert any(
        table["status"] in {"PARTIAL_FIELD_MAPPING","NO_LOGICAL_MAPPING"}
        for profile in matrix["profiles"].values()
        for table in profile["tables"]
    ),matrix

    # Every adapter-defined identity field must be logically mapped.
    assert not any(
        table["missing_identity_mappings"]
        for profile in matrix["profiles"].values()
        for table in profile["tables"]
    ),matrix

    print("server schema mapping coverage self-test: PASS")

if __name__=="__main__":
    raise SystemExit(main())
