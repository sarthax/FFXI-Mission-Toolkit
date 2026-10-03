"""Reads must not leave a transaction open: apply paths call connection.start_transaction() and mysql.connector
raises "Transaction already in progress" if an implicit (autocommit=False) read transaction is still open."""
import sys
import types

from workbench.editors.character import connection as conn_mod


def _fake_connector(captured):
    mod = types.ModuleType("mysql.connector")
    mod.connect = lambda **kw: captured.update(kw) or object()
    pkg = types.ModuleType("mysql")
    pkg.connector = mod
    return pkg, mod


def _connect(**kwargs):
    captured = {}
    pkg, mod = _fake_connector(captured)
    saved = {k: sys.modules.get(k) for k in ("mysql", "mysql.connector")}
    sys.modules["mysql"], sys.modules["mysql.connector"] = pkg, mod
    try:
        profile = conn_mod.DatabaseProfile(server_root=".", conf_path=".", host="h", port=1, user="u", password="p", database="d", config_family="dsp")
        conn_mod.connect(profile, **kwargs)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return captured


def test_connect_defaults_to_autocommit():
    assert _connect()["autocommit"] is True


def test_connect_allows_caller_override():
    assert _connect(autocommit=False)["autocommit"] is False


if __name__ == "__main__":
    test_connect_defaults_to_autocommit()
    test_connect_allows_caller_override()
    print("Character Editor connection autocommit self-test: PASS")
