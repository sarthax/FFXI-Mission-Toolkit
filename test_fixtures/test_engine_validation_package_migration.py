from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    change = importlib.import_module("workbench.validation.environments.engine_change_index")
    compare = importlib.import_module("workbench.validation.environments.engine_compare")
    assert not (REPO_ROOT / "engine_change_index.py").exists()
    assert not (REPO_ROOT / "engine_migration_compare.py").exists()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        record_dir = root / "sample-change"
        record_dir.mkdir()
        (record_dir / "README.md").write_text("# Sample\n", encoding="utf-8")
        (record_dir / "sample.diff").write_text(
            "diff --git a/src/foo.cpp b/src/foo.cpp\n"
            "--- a/src/foo.cpp\n"
            "+++ b/src/foo.cpp\n"
            "@@ -1 +1,2 @@ Foo\n"
            "+int AddedThing(int value) { return value; }\n",
            encoding="utf-8",
        )
        records = change.index(root)
        assert len(records) == 1
        assert records[0].evidence_status == "RECORDED"
        assert records[0].changed_files == ["src/foo.cpp"]
        assert "AddedThing" in records[0].symbol_hints
        implementations = change.to_implementations(records)
        assert implementations[0].status == "IMPLEMENTED"
        assert implementations[0].requires_build is True

        source = {
            "functions": [
                {"qualified_name": "Foo::same", "signature": {"return_type": "int", "parameters": [], "const": False, "static": False, "noexcept": False}},
                {"qualified_name": "Foo::missing", "signature": {"return_type": "void", "parameters": [], "const": False, "static": False, "noexcept": False}},
            ],
            "bindings": [{"lua_name": "same", "cpp_symbol": "Foo::same"}],
        }
        target = {
            "functions": [
                {"qualified_name": "Foo::same", "signature": {"return_type": "int", "parameters": [], "const": False, "static": False, "noexcept": False}},
            ],
            "bindings": [{"lua_name": "same", "cpp_symbol": "Foo::same"}],
        }
        actions = compare.compare(source, target)
        assert any(a.get("symbol") == "Foo::same" and a["action"] == "NOT_REQUIRED" for a in actions)
        assert any(a.get("symbol") == "Foo::missing" and a["action"] == "IMPLEMENT" for a in actions)

        source_path = root / "source.json"
        target_path = root / "target.json"
        source_path.write_text(json.dumps(source), encoding="utf-8")
        target_path.write_text(json.dumps(target), encoding="utf-8")

        subprocess.run(
            [sys.executable, "-m", "workbench.validation.environments.engine_change_index", str(root)],
            cwd=tempfile.gettempdir(),
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "workbench.validation.environments.engine_compare",
                str(source_path),
                str(target_path),
            ],
            cwd=tempfile.gettempdir(),
            check=True,
        )

    code = (
        "from workbench.validation.environments.engine_change_index import index; "
        "from workbench.validation.environments.engine_compare import compare; "
        "print(index, compare)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("engine Validation package migration: PASS")


if __name__ == "__main__":
    main()
