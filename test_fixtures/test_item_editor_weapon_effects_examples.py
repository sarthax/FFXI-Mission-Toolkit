from workbench.editors.items import weapon_effects as effects


def test_fire_example_matches_documented_bundle():
    rows = effects.build_mod_rows(proc_type=1, chance=20, subeffect=1, damage=25, element=1)
    assert {r['modId']: r['value'] for r in rows} == {431: 1, 499: 1, 500: 25, 501: 20, 950: 1}
