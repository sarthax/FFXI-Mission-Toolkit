from pathlib import Path

from workbench.editors.items import weapon_effect_capabilities as caps


def test_capability_matrix_is_fail_closed_for_legacy_lineages():
    matrix = caps.capability_matrix()
    damage = next(row for row in matrix["capabilities"] if row["label"] == "damage")
    self_buff = next(row for row in matrix["capabilities"] if row["label"] == "self buff")

    assert damage["LSB"] == "row-only"
    assert damage["DSP"] == "verify-lineage"
    assert damage["TOPAZ"] == "verify-lineage"
    assert self_buff["LSB"] == "server-code-required"
    assert self_buff["DSP"] == "server-code-required"
    assert "Only row-only" in matrix["writeRule"]


def test_preset_plan_builds_existing_staged_effect_shape():
    plan = caps.preset_plan("fire_damage", "LSB", chance=35, damage=60)
    assert plan["targetCollection"] == "mods"
    assert plan["rowsSafeToApply"] is True
    assert plan["capability"] == "row-only"
    assert {row["modId"]: row["value"] for row in plan["rows"]} == {
        431: 1,
        499: 1,
        500: 60,
        501: 35,
        950: 1,
    }
    assert "stagedEffects" in plan["applyRule"]


def test_conditional_plan_uses_latent_collection_without_new_write_path():
    plan = caps.preset_plan("ice_damage", "LSB", latent_id=28, latent_param=50)
    assert plan["targetCollection"] == "latents"
    assert plan["rowsSafeToApply"] is True
    assert all(row["latentId"] == 28 and row["latentParam"] == 50 for row in plan["rows"])


def test_dsp_row_bundle_remains_preview_handoff_only():
    plan = caps.preset_plan("fire_damage", "DSP", chance=20, damage=25)
    assert plan["capability"] == "verify-lineage"
    assert plan["rowsSafeToApply"] is False
    assert plan["serverHandoff"]["lineage"] == "DSP"
    assert "do not auto-stage" in plan["applyRule"]


def test_source_probe_recognizes_lsb_dispatcher_without_writes(tmp_path: Path):
    path = tmp_path / "scripts" / "globals"
    path.mkdir(parents=True)
    (path / "additional_effects.lua").write_text(
        "xi.additionalEffect.attack = {}\n"
        "xi.additionalEffect.procFunctions = {}\n"
        "local SELF_BUFF = 12\n",
        encoding="utf-8",
    )

    result = caps.probe_server_tree(tmp_path, "LandSandBoat")
    assert result["lineage"] == "LSB"
    assert result["sourceFound"] is True
    assert result["confidence"] == "source-verified"
    assert result["readOnly"] is True


def test_self_buff_probe_never_promotes_text_match_to_handler_verified(tmp_path: Path):
    path = tmp_path / "scripts" / "globals"
    path.mkdir(parents=True)
    (path / "additional_effects.lua").write_text(
        "xi.additionalEffect.attack = {}\n"
        "xi.additionalEffect.procFunctions = {}\n"
        "local SELF_BUFF = 12\n"
        "-- Haste Blink Regen\n",
        encoding="utf-8",
    )

    result = caps.self_buff_support(tmp_path, "LSB", ["Haste", "Regen"])
    assert result["statusNameMatches"]["Haste"] == ["scripts/globals/additional_effects.lua"]
    assert result["statusNameMatches"]["Regen"] == ["scripts/globals/additional_effects.lua"]
    assert result["handlerVerified"] is False
    assert result["capability"] == "server-code-required"
    assert "advisory only" in result["warning"]


def test_unknown_lineage_fails_closed():
    result = caps.probe_server_tree("/does/not/matter", "mystery-fork")
    assert result["supportedLineage"] is False
    assert result["confidence"] == "unknown"
