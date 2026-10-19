import pytest
from workbench.server_admin.gm_commands.moghancement_oracle import (
    parse_furnishings, predict_moghancement, check_transition,
)

SQL = """
INSERT INTO `item_furnishing` VALUES (1, 'red_box', 1, 520, 0, 10);
INSERT INTO `item_furnishing` VALUES (2, 'blue_box', 2, 521, 1, 10);
INSERT INTO `item_furnishing` VALUES (3, 'red_bed', 2, 522, 0, 20);
INSERT INTO `item_furnishing` VALUES (4, 'red_table', 2, 523, 0, 20);
"""
DATA = parse_furnishings(SQL)


def placed(item, container, slot, installed=True):
    return {"item_id": item, "container": container, "slot": slot, "installed": installed}


def test_dominant_element_and_strongest_item():
    v = predict_moghancement(DATA, [placed(1, 1, 4), placed(2, 2, 1), placed(3, 2, 2)])
    assert v["aura"] == [30, 10, 0, 0, 0, 0, 0, 0]
    assert v["key_item"] == 522


def test_element_tie_and_empty_and_uninstalled_give_none():
    assert predict_moghancement(DATA, [placed(1, 1, 1), placed(2, 2, 1)])["key_item"] == 0
    assert predict_moghancement(DATA, [placed(3, 1, 1, False)])["key_item"] == 0
    assert predict_moghancement(DATA, [])["key_item"] == 0


def test_equal_best_furnishing_uses_first_safe_then_slot():
    v = predict_moghancement(DATA, [placed(4, 2, 1), placed(3, 1, 7)])
    assert v["key_item"] == 522
    assert v["winning_item"]["container"] == 1


def test_duplicate_slot_rejected_and_prior_item_removed():
    with pytest.raises(ValueError, match="duplicate"):
        predict_moghancement(DATA, [placed(1, 1, 0), placed(2, 1, 0)])
    assert check_transition(520, 522, [522], 522)["verdict"] == "PASS"
    assert check_transition(520, 522, [520, 522], 522)["verdict"] == "FAIL"
    assert check_transition(522, 0, [], 0)["verdict"] == "PASS"
