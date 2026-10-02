from workbench.editors.character.adapters import compare_schema
from workbench.editors.character.inventory import inventory_summary
from workbench.editors.character.schema import discover_character_schema


class FakeCursor:
    def __init__(self, tables):
        self.tables = tables
        self.rows = []

    def execute(self, sql, params=None):
        if sql == "SHOW TABLES":
            self.rows = [(name,) for name in self.tables]
            return
        if sql.startswith("DESCRIBE `"):
            name = sql.split("`", 2)[1]
            self.rows = self.tables[name]
            return
        raise AssertionError(sql)

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, tables):
        self.tables = tables

    def cursor(self):
        return FakeCursor(self.tables)


def col(name, sql_type, null="NO", key="", default=None, extra=""):
    return (name, sql_type, null, key, default, extra)


def test_packed_character_state_is_discovered_on_chars_not_profile():
    schema = discover_character_schema(FakeConnection({
        "chars": [
            col("charid", "int(10) unsigned", key="PRI"),
            col("charname", "varchar(15)"),
            col("missions", "blob", null="YES"),
            col("quests", "blob", null="YES"),
            col("keyitems", "blob", null="YES"),
            col("abilities", "blob", null="YES"),
        ],
        "char_profile": [
            col("charid", "int(10) unsigned", key="PRI"),
            col("rank_points", "int(10) unsigned"),
        ],
        "char_inventory": [
            col("charid", "int(10) unsigned"),
            col("location", "tinyint unsigned"),
            col("slot", "tinyint unsigned"),
            col("itemId", "smallint unsigned"),
        ],
    }))

    assert schema.packed_fields["missions"] == "chars.missions"
    assert schema.packed_fields["quests"] == "chars.quests"
    assert schema.packed_fields["key_items"] == "chars.keyitems"
    assert schema.packed_fields["abilities"] == "chars.abilities"
    assert "missions" not in schema.table("char_profile").binary_columns

    inv = inventory_summary(schema, "topaz")
    missions = next(x for x in inv["capabilities"] if x["capability"] == "missions")
    assert missions["supported"] is True
    assert missions["storage"] == ("chars",)
    assert missions["representation"] == "packed_blob"
    assert missions["write_status"] == "blocked_unverified"


def test_lsb_lineage_comparison_reports_missing_and_extra_tables():
    schema = discover_character_schema(FakeConnection({
        "chars": [col("charid", "int unsigned", key="PRI"), col("charname", "varchar(15)")],
        "char_profile": [col("charid", "int unsigned", key="PRI")],
        "char_jobs": [col("charid", "int unsigned", key="PRI")],
        "char_job_points": [col("charid", "int unsigned")],
        "char_custom_extension": [col("charid", "int unsigned")],
    }))
    comparison = compare_schema(schema, "lsb")
    assert comparison["reference_available"] is True
    assert comparison["source_repository"] == "LandSandBoat/server"
    assert "char_job_points" in comparison["present"]
    assert "char_inventory" in comparison["missing_expected"]
    assert "char_custom_extension" in comparison["extra_present"]
