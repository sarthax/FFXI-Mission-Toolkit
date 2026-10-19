from workbench.server_admin.gm_commands.moghancement_effects import (
    evaluate_modifiers, evaluate_replacement,
)


def test_activation_and_cleanup_restore_baseline():
    assert evaluate_modifiers({"GILFINDER": 3}, {"GILFINDER": 13},
                              {"GILFINDER": 3}, {"GILFINDER": 10})["verdict"] == "PASS"


def test_detects_stacking_and_leaked_modifiers():
    assert evaluate_modifiers({"GILFINDER": 3}, {"GILFINDER": 23},
                              {"GILFINDER": 13}, {"GILFINDER": 10})["verdict"] == "FAIL"


def test_missing_diagnostic_is_blocked():
    assert evaluate_modifiers({}, {"FISH": 1}, {"FISH": 0}, {"FISH": 1})["verdict"] == "BLOCKED"


def test_replacement_clears_prior_and_grants_new():
    original = {"GILFINDER": 2, "GARDENING_WILT_BONUS": 0}
    money = {"GILFINDER": 12, "GARDENING_WILT_BONUS": 0}
    garden = {"GILFINDER": 2, "GARDENING_WILT_BONUS": 36}
    assert evaluate_replacement(original, money, garden,
                                {"GILFINDER": 10}, {"GARDENING_WILT_BONUS": 36})["verdict"] == "PASS"
    assert evaluate_replacement(original, money,
                                {"GILFINDER": 12, "GARDENING_WILT_BONUS": 36},
                                {"GILFINDER": 10}, {"GARDENING_WILT_BONUS": 36})["verdict"] == "FAIL"
