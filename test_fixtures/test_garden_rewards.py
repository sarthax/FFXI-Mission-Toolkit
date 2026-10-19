import pytest

from workbench.server_admin.gm_commands.garden_rewards import parse_results, validate_harvest


SQL = """
CREATE TABLE gardening_results (resultId int);
INSERT INTO `gardening_results` VALUES (1, 1, 0, 0, 936, 12, 24, 30); -- Rock Salt
INSERT INTO `gardening_results` VALUES (2, 1, 0, 0, 4449, 1, 2, 30); -- Reishi Mushroom
INSERT INTO `gardening_results` VALUES (3, 6, 1, 2, 4097, 6, 12, 15);
"""


def test_known_item_and_quantity_pass():
    data = parse_results(SQL)
    assert validate_harvest(data, 1, 0, 0, 936, 12)["verdict"] == "PASS"
    assert validate_harvest(data, 1, 0, 0, 4449, 2)["verdict"] == "PASS"
    assert validate_harvest(data, 6, 1, 2, 4097, 8)["verdict"] == "PASS"


def test_unexpected_item_or_quantity_fail():
    data = parse_results(SQL)
    assert validate_harvest(data, 1, 0, 0, 4096, 12)["verdict"] == "FAIL"
    assert validate_harvest(data, 1, 0, 0, 936, 25)["verdict"] == "FAIL"
    assert validate_harvest(data, 1, 0, 0, 936, 0)["verdict"] == "FAIL"


def test_unrepresented_combo_blocks_not_fails():
    assert validate_harvest(parse_results(SQL), 8, 8, 8, 936, 12)["verdict"] == "BLOCKED"


def test_rejects_malformed_and_duplicate_rows():
    with pytest.raises(ValueError):
        parse_results("not a gardening SQL fixture")
    with pytest.raises(ValueError, match="duplicate"):
        parse_results(SQL + SQL)
