#!/usr/bin/env python3
"""Focused migration smoke for the Workbench runtime connectors."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_root(name: str, path: str):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    from workbench.runtime import connect, connect_server

    assert not (REPO_ROOT / "workbench_connect.py").exists()
    assert not (REPO_ROOT / "workbench_connect_server.py").exists()
    assert callable(connect.connect)
    assert callable(connect.main)
    assert callable(connect_server.import_payload)
    assert callable(connect_server.main)

    code = r'''
import json
import sqlite3
import tempfile
from pathlib import Path
from workbench.runtime import connect, connect_server

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    src = root / "source.db"
    sqlite3.connect(src).close()
    graph = root / "graph.db"
    result = connect.connect(src, graph)
    assert result["schema"] == 1
    assert graph.is_file()

    payload = root / "server.json"
    payload.write_text(json.dumps({"analysis": {}, "functions": [], "bindings": [], "enums_constants": [], "build_targets": [], "opcodes": [], "edges": []}), encoding="utf-8")
    graph2 = root / "graph2.db"
    imported = connect_server.import_payload(payload, graph2)
    assert imported["schema"] == 1
    assert graph2.is_file()
'''
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("runtime connector package migration smoke: OK")


if __name__ == "__main__":
    main()
