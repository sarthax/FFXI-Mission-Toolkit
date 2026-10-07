from pathlib import Path
import tempfile

from workbench.app.host import app
from workbench.editors.character.connection import discover_database_profile, normalize_server_root


def _write_legacy_conf(path: Path):
    path.write_text(
        "\n".join(
            [
                "mysql_host: 127.0.0.1",
                "mysql_port: 3306",
                "mysql_login: dsp",
                "mysql_password: secret",
                "mysql_database: dspdb",
            ]
        ),
        encoding="utf-8",
    )


def test_live_app_mounts_environment_profile_api():
    paths = set(app.openapi()["paths"])
    assert "/character-editor/environments/profiles.json" in paths
    assert "/character-editor/environments/profiles" in paths
    assert "/character-editor/environments/profiles/{profile_id}/test" in paths


def test_dsp_root_conf_folder_and_config_file_normalize_to_same_root():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "darkstar"
        conf = root / "conf"
        conf.mkdir(parents=True)
        config_file = conf / "map_darkstar.conf"
        _write_legacy_conf(config_file)

        expected = root.resolve()
        assert normalize_server_root(root) == expected
        assert normalize_server_root(conf) == expected
        assert normalize_server_root(config_file) == expected

        for supplied in (root, conf, config_file):
            profile = discover_database_profile(supplied)
            assert profile.server_root == expected
            assert profile.conf_path == config_file.resolve()
            assert profile.config_family == "legacy_conf"
            assert profile.database == "dspdb"
