from __future__ import annotations

from pathlib import Path
import tempfile

from workbench.editors.character.connection import discover_database_profile
from workbench.editors.character.adapters import detect_adapter
from workbench.editors.character.inventory import build_inventory
from workbench.editors.character.schema import CharacterSchema, TableInfo, ColumnInfo


def test_lsb_network_config_and_detection():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "settings").mkdir()
        (root / "tools").mkdir()
        (root / "settings" / "network.lua").write_text(
            "xi.settings.network = {\n"
            " SQL_HOST = '127.0.0.1',\n SQL_PORT = 3306,\n SQL_LOGIN = 'xi',\n"
            " SQL_PASSWORD = 'secret',\n SQL_DATABASE = 'xidb',\n}\n",
            encoding="utf-8",
        )
        (root / "tools" / "dbtool.py").write_text("", encoding="utf-8")
        profile = discover_database_profile(root)
        assert profile.config_family == "lsb_settings"
        assert profile.database == "xidb"
        assert "password" not in profile.public_dict()
        fp = detect_adapter(root)
        assert fp.family == "lsb"
        assert fp.confidence == "high"


def test_legacy_dsp_detection():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "conf").mkdir()
        (root / "conf" / "map_darkstar.conf").write_text(
            "mysql_host: 127.0.0.1\nmysql_port: 3306\nmysql_login: dsp\n"
            "mysql_password: secret\nmysql_database: dspdb\n",
            encoding="utf-8",
        )
        profile = discover_database_profile(root)
        assert profile.config_family == "legacy_conf"
        assert detect_adapter(root).family == "dsp"


def test_inventory_keeps_packed_state_blocked():
    blob = ColumnInfo("missions", "blob", False, "", None, "")
    profile = TableInfo("char_profile", [ColumnInfo("charid", "int", False, "PRI", None, ""), blob], "profile", "charid")
    schema = CharacterSchema(
        tables={"char_profile": profile},
        capabilities={"profile": ["char_profile"]},
        packed_profile_fields={"missions": "missions"},
    )
    rows = {r.capability: r for r in build_inventory(schema, "lsb")}
    assert rows["missions"].supported
    assert rows["missions"].representation == "packed_profile_blob"
    assert rows["missions"].write_status == "blocked_unverified"
