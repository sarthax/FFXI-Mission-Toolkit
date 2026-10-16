import pytest
from workbench.runtime.live_client import native_install as ni


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "ashita"
    (root / "plugins").mkdir(parents=True)
    dll = tmp_path / "x.dll"
    dll.write_bytes(b"MZ-new")
    monkeypatch.setenv("WORKBENCH_NATIVE_DLL", str(dll))
    return root, dll


def test_preview_apply_backup_and_settings_never_overwritten(setup):
    root, dll = setup
    p = ni.preview(str(root))
    assert p["dll_found"] and not p["target_exists"] and not p["settings_exists"]
    (root / "plugins" / ni.DLL_NAME).write_bytes(b"old")
    r = ni.apply(str(root), p["dll_sha256"], allow_file_commands=True)
    assert r["dll_copied"] and r["backup"] and r["settings_written"]
    assert (root / "plugins" / ni.DLL_NAME).read_bytes() == b"MZ-new"
    ini = root / "config" / "workbench_native" / "settings.ini"
    assert "allow_file_commands=1" in ini.read_text()
    ini.write_text("allow_file_commands=0\n")
    r2 = ni.apply(str(root), p["dll_sha256"], allow_file_commands=True)
    assert not r2["dll_copied"] and not r2["settings_written"]
    assert ini.read_text() == "allow_file_commands=0\n"


def test_rejects_stale_hash_and_bad_root(setup, tmp_path):
    root, _ = setup
    with pytest.raises(ValueError):
        ni.apply(str(root), "0" * 64)
    with pytest.raises(ValueError):
        ni.preview(str(tmp_path / "nope"))
    assert "allow_file_commands=0" in ni.render_settings(False)
    with pytest.raises(ValueError):
        ni.render_settings(True, auto_arm="evil")


def test_release_download_is_hash_pinned(tmp_path, monkeypatch):
    import hashlib, io, json
    data = b"MZ-release"
    good = hashlib.sha256(data).hexdigest()
    man = tmp_path / "release.json"
    man.write_text(json.dumps({"tag": "t", "sha256": good,
                               "url": "https://github.com/sarthax/FFXI-Mission-Toolkit/releases/download/t/x.dll"}))
    monkeypatch.setattr(ni, "MANIFEST", man)
    monkeypatch.setattr(ni, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(ni, "CANDIDATES", ())
    monkeypatch.delenv("WORKBENCH_NATIVE_DLL", raising=False)

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(ni.urllib.request, "urlopen", lambda *a, **k: R(data))
    root = tmp_path / "a"; (root / "plugins").mkdir(parents=True)
    p = ni.preview(str(root))
    assert p["dll_found"] and p["dll_sha256"] == good and p["release_available"]
    assert ni.apply(str(root), good)["dll_copied"]
    assert (root / "plugins" / ni.DLL_NAME).read_bytes() == data
    # tampered download is rejected
    (tmp_path / "cache" / ni.DLL_NAME).unlink()
    (root / "plugins" / ni.DLL_NAME).unlink()
    monkeypatch.setattr(ni.urllib.request, "urlopen", lambda *a, **k: R(b"evil"))
    with pytest.raises(ValueError):
        ni.apply(str(root), good)
    # non-github URLs are never trusted
    man.write_text(json.dumps({"tag": "t", "sha256": good, "url": "https://evil.example/x.dll"}))
    assert ni.preview(str(root))["release_available"] is False


def test_settings_template_documents_both_opt_ins():
    text = ni.render_settings(True, allow_chat_commands=False)
    assert "allow_file_commands=1" in text and "allow_chat_commands=0" in text
    assert "REQUIRED" in text and "stock" in text and "OPTIONAL" in text
    assert "allow_chat_commands=1" in ni.render_settings(True, allow_chat_commands=True)
