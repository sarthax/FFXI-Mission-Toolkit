from workbench.editors.items import weapon_effects as effects


def test_catalog_exposes_existing_additional_effect_fields():
    catalog = effects.catalog()
    fields = {row["key"]: row["modId"] for row in catalog["fields"]}
    assert fields == {
        "type": 431,
        "subeffect": 499,
        "damage": 500,
        "chance": 501,
        "element": 950,
        "status": 951,
        "power": 952,
        "duration": 953,
    }
    assert catalog["storage"] == "item_mods or item_latents"
    assert catalog["clientCoupled"] is False
    assert "LSB" in catalog["serverReferences"]
    assert any(p["key"] == "self_buff" for p in catalog["presets"])


def test_build_fire_damage_rows_uses_normal_item_mods_bundle():
    rows = effects.build_mod_rows(
        proc_type=1,
        chance=20,
        subeffect=1,
        damage=25,
        element=1,
    )
    by_mod = {row["modId"]: row["value"] for row in rows}
    assert by_mod == {431: 1, 499: 1, 500: 25, 501: 20, 950: 1}


def test_named_fire_preset_builds_same_bundle_and_accepts_overrides():
    rows = effects.build_preset_rows("fire_damage", chance=35, damage=60)
    by_mod = {row["modId"]: row["value"] for row in rows}
    assert by_mod == {431: 1, 499: 1, 500: 60, 501: 35, 950: 1}


def test_build_latent_rows_adds_condition_without_changing_effect_bundle():
    rows = effects.build_latent_rows(
        latent_id=28,
        latent_param=0,
        proc_type=1,
        chance=35,
        subeffect=1,
        damage=40,
        element=1,
    )
    assert rows
    assert all(row["latentId"] == 28 for row in rows)
    assert all(row["latentParam"] == 0 for row in rows)
    assert {row["modId"] for row in rows} == {431, 499, 500, 501, 950}


def test_debuff_bundle_preserves_status_power_and_duration():
    rows = effects.build_mod_rows(
        proc_type=2,
        chance=100,
        subeffect=11,
        status=4,
        power=30,
        duration=30,
    )
    by_mod = {row["modId"]: row["value"] for row in rows}
    assert by_mod == {431: 2, 499: 11, 501: 100, 951: 4, 952: 30, 953: 30}


def test_self_buff_blueprint_is_explicit_server_handoff():
    blueprint = effects.build_self_buff_blueprint(
        status=33,
        chance=25,
        power=150,
        duration=45,
        subeffect=23,
        lineage="lsb",
    )
    assert blueprint["requiresServerCode"] is True
    assert blueprint["lineage"] == "LSB"
    assert "additional_effects.lua" in blueprint["serverReference"]["additional_effects"]
    assert blueprint["implementationContract"]["target"] == "attacker/self"
    assert blueprint["implementationContract"]["statusId"] == 33
    assert "stacking" in blueprint["implementationContract"]
    assert len(blueprint["localAgentTasks"]) >= 5
    by_mod = {row["modId"]: row["value"] for row in blueprint["rows"]}
    assert by_mod == {431: 12, 499: 23, 501: 25, 951: 33, 952: 150, 953: 45}


def test_dsp_reference_warns_about_legacy_proc_numbering():
    blueprint = effects.build_self_buff_blueprint(status=33, lineage="DSP")
    assert "5=self-buff" in blueprint["serverReference"]["legacy_type_comment"]
    assert "predates modern LSB proc numbering" in blueprint["serverReference"]["notes"]


def test_inspect_rows_recognizes_existing_effect_rows_and_ignores_other_mods():
    summary = effects.inspect_rows([
        {"modId": 25, "value": 10},
        {"modId": 431, "value": 1},
        {"modId": 499, "value": 1},
        {"modId": 500, "value": 25},
        {"modId": 501, "value": 20},
        {"modId": 950, "value": 1},
    ])
    assert summary["recognized"] is True
    assert summary["procTypeLabel"] == "damage"
    assert summary["elementLabel"] == "fire"
    assert summary["subeffectLabel"] == "fire damage"
    assert 25 not in summary["modIds"]


def test_validation_and_server_boundary_are_fail_closed():
    try:
        effects.build_mod_rows(proc_type=999, chance=20)
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("unknown proc type was accepted")

    try:
        effects.build_mod_rows(proc_type=1, chance=101)
    except ValueError as exc:
        assert "chance" in str(exc)
    else:
        raise AssertionError("invalid chance was accepted")

    try:
        effects.build_preset_rows("not_real")
    except ValueError as exc:
        assert "unknown weapon-effect preset" in str(exc)
    else:
        raise AssertionError("unknown preset was accepted")

    assert effects.requires_server_code(1) is False
    assert effects.requires_server_code(2) is False
    assert effects.requires_server_code(10) is False
    assert effects.requires_server_code(12) is True
    assert effects.requires_server_code(14) is True
