from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_root(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    api = importlib.import_module("workbench.devtools.server.cpp_api_index")
    dep = importlib.import_module("workbench.devtools.server.cpp_dependency_index")
    build = importlib.import_module("workbench.devtools.server.build_integration_index")
    assert _load_root("cpp_api_index") is api
    assert _load_root("cpp_dependency_index") is dep
    assert _load_root("build_integration_index") is build

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "foo.cpp").write_text(
            '#include "foo.h"\n'
            'int Foo::bar(int x) { GP_SERV_COMMAND packet; return x; }\n'
            'SOL_REGISTER("bar", Foo::bar)\n',
            encoding="utf-8",
        )
        (root / "foo.h").write_text('enum class Mode { A = 1, B };\n', encoding="utf-8")
        (root / "CMakeLists.txt").write_text('add_library(core foo.cpp)\n', encoding="utf-8")

        funcs, enums, bindings = api.index(root)
        assert any(f.name == "bar" for f in funcs)
        assert any(e.symbol == "A" for e in enums)
        assert any(b.lua_name == "bar" for b in bindings)

        edges = dep.index(root)
        assert any(e.relationship == "IMPORTS" for e in edges)
        assert any(e.relationship == "USES_PACKET" for e in edges)

        builders, findings, targets, build_edges = build.index(root)
        assert builders and findings and targets
        assert any(e.relationship == "BUILDS_INTO" for e in build_edges)

    code = (
        "from workbench.devtools.server.cpp_api_index import index; "
        "from workbench.devtools.server.cpp_dependency_index import index as d; "
        "from workbench.devtools.server.build_integration_index import index as b; "
        "print(index, d, b)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
