"""R6 #1210 WP0/WP1: change-set validator and tools/dsp_change_set.py. Synthetic repositories only."""
import copy
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.impact_changeset import validate_change_set

ROOT = Path(__file__).resolve().parents[1]
A, B = "a" * 40, "b" * 40  # format examples only, not real commits


def _good():
    return {"schema_version": 1, "repository": "synthetic/example-repository",
            "base_sha": A, "head_sha": B, "changes": [
                {"status": "M", "path": "scripts/zones/Z/npcs/N.lua", "hunks": [[10, 14], [20, 20]]},
                {"status": "D", "path": "scripts/old.lua"},
                {"status": "A", "path": "scripts/new.lua"},
                {"status": "R", "path": "scripts/b.lua", "old_path": "scripts/a.lua"}]}


def test_valid_change_set_is_normalized_and_deterministic():
    out = validate_change_set(_good())
    assert [c["path"] for c in out["changes"]] == sorted(c["path"] for c in out["changes"])
    assert all(set(c) == {"status", "path", "old_path", "hunks"} for c in out["changes"])
    shuffled = _good()
    shuffled["changes"].reverse()
    assert json.dumps(validate_change_set(shuffled)) == json.dumps(out)
    upper = _good()
    upper["base_sha"] = "A" * 40
    assert validate_change_set(upper)["base_sha"] == A


def _mutated(fn):
    doc = copy.deepcopy(_good())
    fn(doc)
    return doc


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d.update(base_sha="abc"), "base_sha"),
    (lambda d: d.update(head_sha="g" * 40), "head_sha"),
    (lambda d: d.update(head_sha=A), "must differ"),
    (lambda d: d.update(schema_version=2), "schema"),
    (lambda d: d.update(repository=""), "repository"),
    (lambda d: d.update(extra=1), "unexpected"),
    (lambda d: d.pop("changes"), "missing"),
    (lambda d: d["changes"].append("x"), "must be an object"),
    (lambda d: d["changes"][0].update(status="C"), "status"),
    (lambda d: d["changes"][0].update(unknown=1), "unexpected"),
    (lambda d: d["changes"][0].update(path="../etc/passwd"), "segments"),
    (lambda d: d["changes"][0].update(path="/abs/path.lua"), "relative"),
    (lambda d: d["changes"][0].update(path="C:/win.lua"), "relative"),
    (lambda d: d["changes"][0].update(path="a\\b.lua"), "relative"),
    (lambda d: d["changes"][0].update(path="a//b.lua"), "segments"),
    (lambda d: d["changes"][0].update(path="a/./b.lua"), "segments"),
    (lambda d: d["changes"][0].update(path="a/b\x00.lua"), "control"),
    (lambda d: d["changes"][0].update(path="x" * 501), "exceeds"),
    (lambda d: d["changes"][0].update(old_path="scripts/x.lua"), "only allowed for status R"),
    (lambda d: d["changes"][3].pop("old_path"), "old_path"),
    (lambda d: d["changes"][3].update(old_path="scripts/b.lua"), "differ"),
    (lambda d: d["changes"][1].update(hunks=[[1, 2]]), "null for status D"),
    (lambda d: d["changes"][2].update(hunks=[[1, 2]]), "null for status A"),
    (lambda d: d["changes"][0].update(hunks=[[0, 2]]), "start <= end"),
    (lambda d: d["changes"][0].update(hunks=[[5, 4]]), "start <= end"),
    (lambda d: d["changes"][0].update(hunks=[[10, 14], [14, 20]]), "overlap"),
    (lambda d: d["changes"][0].update(hunks=[[20, 25], [1, 2]]), "ordered"),
    (lambda d: d["changes"][0].update(hunks=[[1.5, 2]]), "two integers"),
    (lambda d: d["changes"][0].update(hunks=[[True, 2]]), "two integers"),
    (lambda d: d["changes"][0].update(hunks="1-2"), "list"),
    (lambda d: d["changes"].append({"status": "M", "path": "scripts/new.lua"}), "duplicate path"),
])
def test_malformed_change_sets_are_rejected(mutate, message):
    with pytest.raises(ValueError, match=message):
        validate_change_set(_mutated(mutate))


def test_non_object_and_oversized_inputs_are_rejected():
    for bad in (None, [], "x", 3):
        with pytest.raises(ValueError):
            validate_change_set(bad)
    doc = _good()
    doc["changes"] = [{"status": "A", "path": f"f{i}.lua"} for i in range(5001)]
    with pytest.raises(ValueError, match="at most"):
        validate_change_set(doc)


# --- helper script -------------------------------------------------------------------------

def _load_helper():
    spec = importlib.util.spec_from_file_location("dsp_change_set", ROOT / "tools" / "dsp_change_set.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = _load_helper()
_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=_ENV).stdout.decode().strip()


def _lines(n, tag="x"):
    return "".join(f"{tag}{i}\n" for i in range(1, n + 1))


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "dsp"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "scripts").mkdir()
    (r / "scripts" / "mod.lua").write_text(_lines(30))
    (r / "scripts" / "gone.lua").write_text(_lines(5))
    (r / "scripts" / "ren.lua").write_text(_lines(40, "r"))
    (r / "scripts" / "ren_edit.lua").write_text(_lines(40, "e"))
    (r / "scripts" / "with space.lua").write_text(_lines(10))
    (r / "scripts" / "start.lua").write_text(_lines(5))
    (r / "scripts" / "bin.dat").write_bytes(b"\x00\x01\x02" * 50)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    git(r, "tag", "base")
    # head: edit lines 10-12 and 20; delete; add; renames; space path; insert at start; binary
    lines = _lines(30).splitlines(True)
    lines[9:12] = ["CHANGED\n"] * 3
    lines[19] = "CHANGED20\n"
    (r / "scripts" / "mod.lua").write_text("".join(lines))
    (r / "scripts" / "gone.lua").unlink()
    (r / "scripts" / "added.lua").write_text("brand new\nunrelated content\n")
    git(r, "mv", "scripts/ren.lua", "scripts/renamed.lua")
    git(r, "mv", "scripts/ren_edit.lua", "scripts/renamed_edit.lua")
    edit = _lines(40, "e").splitlines(True)
    edit[4] = "EDITED5\n"
    (r / "scripts" / "renamed_edit.lua").write_text("".join(edit))
    (r / "scripts" / "with space.lua").write_text(_lines(10).replace("x4\n", "S4\n"))
    (r / "scripts" / "start.lua").write_text("INSERTED\n" + _lines(5))
    (r / "scripts" / "bin.dat").write_bytes(b"\x00\x01\x03" * 50)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "head")
    git(r, "tag", "head")
    return r


def _by_path(doc):
    return {c["path"]: c for c in doc["changes"]}


def test_helper_output_matches_git_and_passes_validator(repo):
    doc = helper.build(repo, "synthetic/dsp", "base", "head")
    assert doc["base_sha"] == git(repo, "rev-parse", "base") and doc["head_sha"] == git(repo, "rev-parse", "head")
    validated = validate_change_set(doc)
    rows = _by_path(validated)
    assert rows["scripts/mod.lua"]["status"] == "M" and rows["scripts/mod.lua"]["hunks"] == [[10, 12], [20, 20]]
    assert rows["scripts/gone.lua"]["status"] == "D" and rows["scripts/gone.lua"]["hunks"] is None
    assert rows["scripts/added.lua"]["status"] == "A"
    assert rows["scripts/renamed.lua"] == {"status": "R", "path": "scripts/renamed.lua",
                                          "old_path": "scripts/ren.lua", "hunks": None}
    assert rows["scripts/renamed_edit.lua"]["old_path"] == "scripts/ren_edit.lua"
    assert rows["scripts/renamed_edit.lua"]["hunks"] == [[5, 5]]
    assert rows["scripts/with space.lua"]["hunks"] == [[4, 4]]  # x4 is line 4
    # pure insertion before line 1 is recorded as touching line 1 (over-select, never miss)
    assert rows["scripts/start.lua"]["hunks"] == [[1, 1]]
    assert rows["scripts/bin.dat"]["hunks"] is None


def test_helper_cli_writes_file_and_refuses_overwrite(repo, tmp_path, capsys):
    out = tmp_path / "cs.json"
    args = ["--repo-path", str(repo), "--repository", "synthetic/dsp", "--base", "base", "--head", "head",
            "--output", str(out)]
    assert helper.main(args) == 0
    validate_change_set(json.loads(out.read_text()))
    assert helper.main(args) == 2  # existing output is never overwritten
    assert "refusing to overwrite" in capsys.readouterr().err


def test_helper_does_not_modify_the_checkout(repo):
    before = (git(repo, "rev-parse", "HEAD"), git(repo, "status", "--porcelain"))
    helper.build(repo, "synthetic/dsp", "base", "head")
    assert (git(repo, "rev-parse", "HEAD"), git(repo, "status", "--porcelain")) == before


def test_helper_refusals(repo, tmp_path):
    with pytest.raises(helper.ChangeSetError, match="same commit"):
        helper.build(repo, "r", "base", "base")
    with pytest.raises(helper.ChangeSetError):
        helper.build(repo, "r", "base", "no-such-ref")
    with pytest.raises(helper.ChangeSetError, match="not a directory"):
        helper.build(tmp_path / "missing", "r", "base", "head")
    (repo / "scripts" / "mod.lua").write_text("dirty\n")
    with pytest.raises(helper.ChangeSetError, match="uncommitted"):
        helper.build(repo, "r", "base", "head")


def test_helper_refuses_shallow_checkout(repo, tmp_path):
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)],
                   check=True, capture_output=True, env=_ENV)
    with pytest.raises(helper.ChangeSetError, match="shallow"):
        helper.build(shallow, "r", "HEAD", "HEAD")


def test_helper_rejects_unsupported_status(repo):
    git(repo, "checkout", "-q", "base")
    (repo / "scripts" / "mod.lua").unlink()
    os.symlink("gone.lua", repo / "scripts" / "mod.lua")  # file -> symlink = typechange (T)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "typechange")
    with pytest.raises(helper.ChangeSetError, match="unsupported git status"):
        helper.build(repo, "r", "base", "HEAD")
