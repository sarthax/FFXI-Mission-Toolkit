from workbench.editors.items import weapon_effect_ui_contract as ui


def test_lsb_catalog_auto_stages_only_row_safe_presets():
    catalog = ui.preset_catalog("LandSandBoat")
    fire = next(row for row in catalog["presets"] if row["key"] == "fire_damage")
    self_buff = next(row for row in catalog["presets"] if row["key"] == "self_buff")

    assert catalog["lineage"] == "LSB"
    assert fire["rowsSafeToApply"] is True
    assert fire["capability"] == "row-only"
    assert self_buff["rowsSafeToApply"] is False
    assert self_buff["requiresServerCode"] is True
    assert catalog["savePath"] == "/itemedit/validate -> /itemedit/save-atomic"


def test_catalog_includes_all_eight_elemental_damage_variants():
    keys = {row["key"] for row in ui.preset_catalog("LSB")["presets"]}
    assert {
        "fire_damage", "ice_damage", "wind_damage", "earth_damage",
        "lightning_damage", "water_damage", "light_damage", "dark_damage",
    } <= keys


def test_elemental_plan_generates_existing_row_bundle():
    plan = ui.plan_preset("lightning_damage", "LSB", chance=33, damage=42)
    by_mod = {row["modId"]: row["value"] for row in plan["rows"]}

    assert plan["rowsSafeToApply"] is True
    assert plan["targetCollection"] == "mods"
    assert plan["ui"]["primaryAction"] == "stage"
    assert by_mod == {431: 1, 499: 5, 500: 42, 501: 33, 950: 5}


def test_legacy_lineage_routes_same_preset_to_handoff():
    plan = ui.plan_preset("fire_damage", "DSP", chance=20, damage=25)
    assert plan["rowsSafeToApply"] is False
    assert plan["capability"] == "verify-lineage"
    assert plan["ui"]["primaryAction"] == "server-handoff"


def test_self_buff_never_becomes_row_safe_in_ui_contract():
    plan = ui.plan_preset("self_buff", "LSB", status=33, chance=20, power=15, duration=60)
    assert plan["rowsSafeToApply"] is False
    assert plan["capability"] == "server-code-required"
    assert plan["ui"]["primaryAction"] == "server-handoff"
    assert {"status", "power", "duration"} <= set(plan["ui"]["fields"])


def test_conditional_variant_targets_existing_latent_staging_collection():
    plan = ui.plan_preset("ice_damage", "LSB", latent_id=28, latent_param=50)
    assert plan["targetCollection"] == "latents"
    assert plan["rowsSafeToApply"] is True
    assert all(row["latentId"] == 28 and row["latentParam"] == 50 for row in plan["rows"])
