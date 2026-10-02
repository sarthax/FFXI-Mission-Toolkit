from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_root(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    change = importlib.import_module("workbench.validation.environments.engine_change_index")
    compare = importlib.import_module("workbench.validation.environments.engine_compare")
    assert load_root("engine_change_index", "engine_change_index.py") is change
    assert load_root("engine_migration_compare", "engine_migration_compare.py") is compare

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

    code = (
        "from workbench.validation.environments.engine_change_index import index; "
        "from workbench.validation.environments.engine_compare import compare; "
        "print(index, compare)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("engine Validation package migration: PASS")


if __name__ == "__main__":
    main()
