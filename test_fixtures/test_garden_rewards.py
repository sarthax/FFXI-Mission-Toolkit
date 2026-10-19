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


def test_exact_oracle_matches_cpp_arithmetic():
    from workbench.server_admin.gm_commands.garden_rewards import expected_result, validate_harvest_exact
    # herb (plant 2, wind) with no crystals: elements[0]+=10, wind+=10 -> strength = max = 10; pot 31 -> 10+int(90*31/32)=97
    sql = ("INSERT INTO `gardening_results` VALUES (1, 2, 0, 0, 100, 1, 5, 50);\n"
           "INSERT INTO `gardening_results` VALUES (2, 2, 0, 0, 200, 1, 3, 50);\n")
    t = parse_results(sql)
    e = expected_result(t, 2, 0, 0, 31)
    assert e["strength"] == 10 + int(90 * 31 / 32) == 97
    assert (e["item_id"], e["quantity"]) == (200, 1 + int(2 * (47 / 50) + 0.1))
    assert validate_harvest_exact(t, 2, 0, 0, 31, 200, e["quantity"])["verdict"] == "PASS"
    assert validate_harvest_exact(t, 2, 0, 0, 31, 100, 1)["verdict"] == "FAIL"
    assert expected_result(t, 8, 0, 0, 0)["verdict"] == "BLOCKED"


def test_quantity_uses_float32_like_cpp():
    from workbench.server_admin.gm_commands.garden_rewards import expected_result
    # fruit tree, no crystals, pot 31 -> strength 98; row [80,100) pct 0.9f -> int(0.9f+0.1)=0 in C++ (observed live: qty 1, not 2)
    sql = ("INSERT INTO `gardening_results` VALUES (1, 1, 0, 0, 100, 1, 1, 80);\n"
           "INSERT INTO `gardening_results` VALUES (2, 1, 0, 0, 770, 1, 2, 20);\n")
    e = expected_result(parse_results(sql), 1, 0, 0, 31)
    assert (e["strength"], e["item_id"], e["quantity"]) == (98, 770, 1)
