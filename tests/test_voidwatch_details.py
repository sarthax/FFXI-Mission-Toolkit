from workbench.server_admin.voidwatch import details as D


def test_parse_lua_drops_and_tags():
    t = '-- [C] x [J] y\nlocal cfg = { region = "THREE", stage = 1, drops = {11667, 12} }\nfunction onMobDeath(mob) end\nmob:setMod(MOD_DOUBLE_ATTACK, 10)\n'
    p = D.parse_lua(t)
    assert p["drops"] == [11667, 12] and p["region"] == "THREE" and p["stage"] == "1"
    assert p["hooks"] == ["onMobDeath"] and p["mods"][0]["mod"] == "MOD_DOUBLE_ATTACK"
    assert p["tags"]["C"] == 1 and p["tags"]["J"] == 1


def test_checks_flags_built_without_script():
    d = {"tracker": {"status": "built", "rifts": [], "ki_id": 1}, "pools": [], "script": None, "rifts": []}
    levels = [c["level"] for c in D.checks(d)]
    assert levels.count("bad") == 2


def test_tracker_loads_and_paths_defined():
    nms = D.load_tracker()
    assert len(nms) >= 70  # Cetus removed: ROV 2-18, not a VW NM
    assert {"Crimson", "Indigo", "Jade", "White", "Ashen"} <= set(D.PATHS)


def test_validation_status_rollup():
    ok = {k: "ok" for k, _ in D.AREAS}
    assert D.validation_status(None) == "unvalidated"
    assert D.validation_status({"areas": ok}) == "validated"
    assert D.validation_status({"areas": {**ok, "drops": "issue"}}) == "issue"
    assert D.validation_status({"areas": {**ok, "drops": "untested"}}) == "partial"
    assert D.validation_status({"areas": {**ok, "model": "n/a"}}) == "validated"
