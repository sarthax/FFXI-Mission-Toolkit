"""Categories, usage parsing and ID lookup for the GM Command Center."""
from pathlib import Path
from workbench.server_admin.gm_commands.catalog import catalog_commands, CATEGORIES
from workbench.server_admin.gm_commands.lookup import lookup


def _server(tmp_path: Path) -> Path:
    (tmp_path / "scripts" / "commands").mkdir(parents=True)
    (tmp_path / "scripts" / "globals").mkdir(parents=True)
    (tmp_path / "sql").mkdir()
    (tmp_path / "scripts" / "commands" / "addkeyitem.lua").write_text(
        'cmdprops = { permission = 1, parameters = "ss" }\n'
        'function error(player) player:PrintToPlayer("!addkeyitem <key item ID> {player}") end')
    (tmp_path / "scripts" / "commands" / "mystery.lua").write_text('cmdprops={permission=1, parameters="i"}')
    (tmp_path / "scripts" / "globals" / "keyitems.lua").write_text("ZERUHN_REPORT = 1;\nMAP_OF_X = 395;\n")
    (tmp_path / "sql" / "item_basic.sql").write_text(
        "INSERT INTO `item_basic` VALUES (4096,0,'fire_crystal','fire_crystal',1,0,0,0,0);\n")
    return tmp_path


def test_category_usage_and_lookup_kind(tmp_path):
    rec = {r["name"]: r for r in catalog_commands(_server(tmp_path))}
    k = rec["addkeyitem"]
    assert k["category"] in CATEGORIES and k["category"].startswith("Key Items")
    assert k["usage"] == "!addkeyitem <key item ID> {player}"
    assert [(p["required"], p["lookup"]) for p in k["params"]] == [(True, "keyitem"), (False, None)]
    assert rec["mystery"]["category"] == "Other" and len(rec["mystery"]["params"]) == 1


def test_lookup_by_name_and_id(tmp_path):
    root = _server(tmp_path)
    assert lookup(root, "keyitem", "zeruhn") == [{"id": 1, "name": "zeruhn report"}]
    assert lookup(root, "keyitem", "395")[0]["id"] == 395
    assert lookup(root, "item", "fire")[0] == {"id": 4096, "name": "fire crystal"}


def test_enumerable_lookups_currency_and_logs(tmp_path):
    from workbench.server_admin.gm_commands.lookup import lookup
    (tmp_path / "sql").mkdir()
    (tmp_path / "scripts" / "globals").mkdir(parents=True)
    (tmp_path / "sql" / "char_points.sql").write_text(
        "CREATE TABLE `char_points` (\n  `charid` int(10) NOT NULL,\n  `valor_point` int,\n  `scyld` int\n) ENGINE=MyISAM;\n")
    (tmp_path / "scripts" / "globals" / "log_ids.lua").write_text(
        'QUEST_LOGS = {\n    [0] = "SANDORIA",\n    [4] = "OTHER_AREAS",\n};\nMISSION_LOGS = {\n    [6] = "COP",\n};\n')
    assert [r["id"] for r in lookup(tmp_path, "currency")] == ["valor_point", "scyld"]
    assert lookup(tmp_path, "questlog", "other")[0] == {"id": 4, "name": "Other Areas"}
    assert lookup(tmp_path, "missionlog", "6")[0]["name"] == "Cop"
