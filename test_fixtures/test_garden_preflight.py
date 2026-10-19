from workbench.server_admin.gm_commands.garden_preflight import (
    parse_garden_info, preflight_garden_mutation,
)

ONE = "[c1 s5] pot 216: plant=2 stage=3(growing) crystal1=0 crystal2=0 strength=5 dried=0 examined=0 tree=0 nextStageIn=9 vanaSec"
TWO = ONE + "\n[c2 s5] pot 217: plant=2 stage=3(growing) crystal1=0 crystal2=0 strength=4 dried=0 examined=0 tree=0 nextStageIn=9 vanaSec"


def check(info=ONE, action="grow", value=1, slot=5):
    return preflight_garden_mutation(info, action, value, slot,
                                    expected_container=1, expected_item=216)


def test_parses_container_and_slot():
    assert [(p["container"], p["slot"]) for p in parse_garden_info(TWO)] == [(1, 5), (2, 5)]


def test_unique_pot_can_be_preflighted_but_not_executed():
    result = check()
    assert result["allow"]
    assert result["preview"] == "!garden grow 1 5"


def test_rejects_cross_container_collision_and_missing_slot():
    assert not check(info=TWO)["allow"]
    assert not check(slot=3)["allow"]


def test_rejects_grow_zero_and_negative_and_bad_values():
    assert not check(value=0)["allow"]
    assert not check(value=-1)["allow"]
    assert not check(action="crystal1", value=9)["allow"]
    assert not check(action="stage", value=12)["allow"]


def test_rejects_missing_or_forged_pot():
    assert not check(info="no flowerpot found in Mog Safe / Safe 2")["allow"]
    assert not check(info="[c1 s5] pot 220: plant=1 stage=3(growing)")["allow"]
    assert not check(info=ONE+"\n"+ONE)["allow"]
