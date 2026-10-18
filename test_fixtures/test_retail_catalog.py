"""Retail catalog + downloader wrapper: deterministic local fixtures, no network, no retail binaries."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workbench.client.retail import catalog, downloader  # noqa: E402


def put(root: Path, stamp: str, data: bytes, *, name="FFXiMain.dll", sha=None, verified=True, size=None):
    d = root / stamp
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    meta = {"schema": 1, "file": name, "retail_version": stamp,
            "sha256": sha or hashlib.sha256(data).hexdigest(),
            "expected_decoded_bytes": len(data) if size is None else size,
            "manifest_signature_verified": verified, "retrieved_utc": "2026-10-18T00:00:00Z",
            "downloader": "ffxi-retail-selective 0.1.0"}
    (d / (name + ".provenance.json")).write_text(json.dumps(meta), encoding="utf-8")
    return d / name


def test_retail_root_precedence(tmp_path=None):
    import tempfile
    from workbench.client.retail import catalog
    saved_fns = (catalog._saved_root, catalog._client_folder)
    old_env = os.environ.pop("WORKBENCH_RETAIL_ROOT", None)
    try:
        catalog._client_folder = lambda: None
        catalog._saved_root = lambda: ""
        assert catalog.retail_root_info()["source"] == "builtin"
        catalog._client_folder = lambda: "C:/FFXI"
        i = catalog.retail_root_info()
        assert i["source"] == "client" and i["path"] == Path("C:/FFXI") / "RetailVersions"
        catalog._saved_root = lambda: "D:/Alt"
        i = catalog.retail_root_info()
        assert i["source"] == "setting" and i["path"] == Path("D:/Alt") and i["default"] == Path("C:/FFXI") / "RetailVersions"
        os.environ["WORKBENCH_RETAIL_ROOT"] = "E:/Env"
        assert catalog.retail_root_info()["source"] == "env"
    finally:
        catalog._saved_root, catalog._client_folder = saved_fns
        os.environ.pop("WORKBENCH_RETAIL_ROOT", None)
        if old_env is not None:
            os.environ["WORKBENCH_RETAIL_ROOT"] = old_env


def main() -> None:
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        assert catalog.scan(root / "nope") == []
        put(root, "30210706_0", b"old-bytes")
        put(root, "30261006_0", b"new-bytes!")
        rows = catalog.scan(root)
        assert [r["version"] for r in rows] == ["30210706_0", "30261006_0"], rows
        assert all(r["status"] == "VALID" for r in rows)

        # identical (file, sha256) in a second folder collapses to one entry
        put(root, "copy_of_new", b"new-bytes!")
        rows = catalog.scan(root)
        assert len([r for r in rows if r["status"] == "VALID"]) == 2
        assert any(r.get("duplicates") for r in rows)

        # tampering is detected by re-hashing, not trusted from the sidecar
        bad = put(root, "30300101_0", b"abc", sha="0" * 64)
        r = next(r for r in catalog.scan(root) if r["version"] == "30300101_0")
        assert r["status"] == "INVALID" and any("SHA-256" in p for p in r["problems"]), r
        put(root, "30300202_0", b"abcd", size=99)
        r = next(r for r in catalog.scan(root) if r["version"] == "30300202_0")
        assert r["status"] == "INVALID" and any("size" in p for p in r["problems"]), r
        put(root, "30300303_0", b"abcd", verified=False)
        r = next(r for r in catalog.scan(root) if r["version"] == "30300303_0")
        assert r["status"] == "INVALID", r

        # missing binary and corrupt sidecar
        bad.unlink()
        r = next(r for r in catalog.scan(root) if r["version"] == "30300101_0")
        assert r["status"] == "MISSING", r
        (root / "x.provenance.json").write_text("{not json", encoding="utf-8")
        assert any(r["status"] == "INVALID_SIDECAR" for r in catalog.scan(root))

        # find() only returns VALID entries
        assert catalog.find("ffximain.dll", "30261006_0", root)["version"] == "30261006_0"
        assert catalog.find("FFXiMain.dll", "30300303_0", root) is None

        # a sidecar that points outside the retail root is rejected
        outside = ROOT / "test_fixtures"
        sub = root / "evil"
        sub.mkdir()
        assert catalog._inside(root, sub / "a")
        assert not catalog._inside(root, outside / "a")

    # downloader argument validation and output parsing
    for good in ("FFXiMain.dll", "ROM/119/51.DAT"):
        assert downloader.valid_file(good) == good
    for badn in ("../x", "a/../b", "C:/x", "a b", "a;b", "", "a\\b", "/abs"):
        try:
            downloader.valid_file(badn)
        except ValueError:
            continue
        raise AssertionError(badn)
    assert downloader.valid_stamp("30261006_0") == "30261006_0"
    for bad_stamp in ("2026", "30261006", "x_0", "30261006_0; rm"):
        try:
            downloader.valid_stamp(bad_stamp)
        except ValueError:
            continue
        raise AssertionError(bad_stamp)
    assert downloader.parse_list("FFXiMain.dll  latest=30261006_0\njunk\n") == [{"file": "FFXiMain.dll", "latest": "30261006_0"}]
    h = downloader.parse_history("FFXiMain.dll  30210706_0  2878544 bytes  direct=2151611 bytes\n")
    assert h == [{"file": "FFXiMain.dll", "version": "30210706_0", "decoded_bytes": 2878544, "transfer_bytes": 2151611}]

    # manifest cache: status without network, cache_only picker reads, limit
    with tempfile.TemporaryDirectory() as t:
        os.environ["WORKBENCH_RETAIL_ROOT"] = t
        try:
            assert downloader.cache_info() == {"exists": False, "count": 0, "mtime": None}
            r = downloader.manifest_list("rom", cache_only=True)
            assert r["ok"] is False and r["no_cache"] is True and r["files"] == [], r
            rows = [{"file": f"ROM/{i}/1.DAT", "latest": "30210706_0"} for i in range(600)] + [{"file": "FFXiMain.dll", "latest": "30261006_0"}]
            (Path(t) / downloader.CACHE_NAME).write_text(json.dumps({"files": rows}), encoding="utf-8")
            info = downloader.cache_info()
            assert info["exists"] and info["count"] == 601 and info["mtime"], info
            assert len(downloader.manifest_list("rom", cache_only=True)["files"]) == 500
            assert len(downloader.manifest_list("rom", cache_only=True, limit=50)["files"]) == 50
            r = downloader.manifest_list("ffxi", cache_only=True)
            assert r["ok"] and r["cached"] and [f["file"] for f in r["files"]] == ["FFXiMain.dll"], r
        finally:
            del os.environ["WORKBENCH_RETAIL_ROOT"]

    # missing executable is reported, not raised
    os.environ["RETAIL_FETCH_EXE"] = str(ROOT / "definitely" / "missing.exe")
    old = downloader.REPO_ROOT
    downloader.REPO_ROOT = ROOT / "no_repo_here"
    try:
        r = downloader.history("FFXiMain.dll")
    finally:
        downloader.REPO_ROOT = old
        del os.environ["RETAIL_FETCH_EXE"]
    assert r["ok"] is False and "not built" in r["error"]
    print("retail catalog self-test OK")


if __name__ == "__main__":
    main()
