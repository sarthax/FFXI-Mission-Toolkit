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

    for logical_type in ("mob_pool_modifiers","mob_spell_lists","skill_caps","skill_ranks"):
        families=rows[logical_type]["families"]
        assert all(
            families[family]["status"] != "MISSING_LOGICAL_TYPE"
            for family in ("TOPAZ","TOPAZ_NEXT","DSP","LSB")
        ),families

    job_points=rows["job_points"]["families"]
    assert all(
        job_points[family]["status"] != "MISSING_LOGICAL_TYPE"
        for family in ("TOPAZ","TOPAZ_NEXT","DSP","LSB")
    ),job_points

    merits=rows["merits"]["families"]
    assert merits["TOPAZ"]["status"] != "MISSING_LOGICAL_TYPE",merits
    assert merits["TOPAZ_NEXT"]["status"] != "MISSING_LOGICAL_TYPE",merits
    assert merits["DSP"]["status"] != "MISSING_LOGICAL_TYPE",merits
    assert merits["LSB"]["status"] == "MISSING_LOGICAL_TYPE",merits

    for logical_type in ("item_modifiers","item_pet_modifiers","item_latents"):
        families=rows[logical_type]["families"]
        assert all(family in families for family in ("TOPAZ","TOPAZ_NEXT","DSP","LSB")),families
        assert all(
            families[family]["status"] != "MISSING_LOGICAL_TYPE"
            for family in ("TOPAZ","TOPAZ_NEXT","DSP","LSB")
        ),families

    for logical_type in ("abilities","weapon_skills","mob_skills","mob_skill_lists"):
        families=rows[logical_type]["families"]
        assert all(family in families for family in ("TOPAZ","TOPAZ_NEXT","DSP","LSB")),families
        assert all(
            families[family]["status"] != "MISSING_LOGICAL_TYPE"
            for family in ("TOPAZ","TOPAZ_NEXT","DSP","LSB")
        ),families

    abilities=rows["abilities"]["families"]
    assert "radius" not in abilities["TOPAZ"]["mapped_logical_fields"],abilities
    assert "radius" not in abilities["DSP"]["mapped_logical_fields"],abilities
    assert "radius" in abilities["LSB"]["mapped_logical_fields"],abilities

    weapon_skills=rows["weapon_skills"]["families"]
    assert "radius" in weapon_skills["LSB"]["mapped_logical_fields"],weapon_skills
    assert "radius" not in weapon_skills["DSP"]["mapped_logical_fields"],weapon_skills

    mob_skills=rows["mob_skills"]["families"]
    assert "aoe_radius" in mob_skills["LSB"]["mapped_logical_fields"],mob_skills
    assert "aoe_radius" not in mob_skills["TOPAZ"]["mapped_logical_fields"],mob_skills

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
