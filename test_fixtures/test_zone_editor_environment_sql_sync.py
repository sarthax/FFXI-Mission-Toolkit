from pathlib import Path

from workbench.editors.zone import editor as zone_editor


def test_zone_editor_sql_sync_uses_same_active_environment_root_as_live_backend(tmp_path, monkeypatch):
    root = tmp_path / "lsb-test"
    sql_dir = root / "sql"
    sql_dir.mkdir(parents=True)
    seen = []

    monkeypatch.setattr(
        zone_editor.zone_plot,
        "_server_root",
        lambda server=None: seen.append(server) or root,
    )

    assert zone_editor._sql_dir() == sql_dir
    assert seen == [None]


def test_zone_editor_sql_sync_rejects_environment_without_sql_tree(tmp_path, monkeypatch):
    root = tmp_path / "server-without-sql"
    root.mkdir()
    monkeypatch.setattr(zone_editor.zone_plot, "_server_root", lambda server=None: root)

    try:
        zone_editor._sql_dir()
    except ValueError as exc:
        assert "has no sql directory" in str(exc)
        assert str(root / "sql") in str(exc)
    else:
        raise AssertionError("SQL sync must not silently fall back to a different server family root")
