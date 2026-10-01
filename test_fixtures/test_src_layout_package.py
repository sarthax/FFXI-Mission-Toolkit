#!/usr/bin/env python3
"""Regression checks for the canonical src-layout package and repo-root bootstrap."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PACKAGE = ROOT / "src" / "workbench"
ROOT_PACKAGE = ROOT / "workbench"
BRIDGE = ROOT_PACKAGE / "__init__.py"


def main() -> None:
    assert (ROOT / "pyproject.toml").is_file()
    assert (SRC_PACKAGE / "__init__.py").is_file()
    assert (SRC_PACKAGE / "core").is_dir()
    assert (SRC_PACKAGE / "runtime" / "paths.py").is_file()
    assert (SRC_PACKAGE / "domains" / "service.py").is_file()
    assert (SRC_PACKAGE / "domains" / "definitions.json").is_file()
    assert (SRC_PACKAGE / "client" / "binary_index.py").is_file()
    assert (SRC_PACKAGE / "client" / "identity_snapshot.py").is_file()
    assert (SRC_PACKAGE / "client" / "event_fingerprint.py").is_file()
    assert (SRC_PACKAGE / "client" / "identity_extract.py").is_file()
    assert (SRC_PACKAGE / "gui_shell.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "feature_candidates.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "feature_checker.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "feature_package_analyzer.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "id_bridge.py").is_file()

    # Canonical implementation lives under src/workbench. The root package is intentionally
    # limited to one compatibility bootstrap so implementation files cannot drift back there.
    assert ROOT_PACKAGE.is_dir()
    assert sorted(path.name for path in ROOT_PACKAGE.iterdir()) == ["__init__.py"]
    assert BRIDGE.is_file()
    bridge_text = BRIDGE.read_text(encoding="utf-8")
    assert "src" in bridge_text and "workbench" in bridge_text
    assert "__path__.append" in bridge_text
    assert "Do not add implementation modules" in bridge_text

    # These former root compatibility/implementation modules are retired. First-party code and
    # regressions must use canonical package imports directly rather than recreating hidden root
    # coupling.
    retired = (
        "workbench_graph.py",
        "workbench_schema.py",
        "source_snapshot.py",
        "feature_candidates.py",
        "feature_package_analyzer.py",
    )
    for name in retired:
        assert not (ROOT / name).exists(), name
    forbidden_imports = (
        "import workbench_graph",
        "from workbench_schema import",
        "from source_snapshot import",
        "from feature_candidates import",
        "from feature_package_analyzer import",
        "import feature_package_analyzer",
    )
    first_party_python = list(ROOT.glob("*.py")) + list(SRC_PACKAGE.rglob("*.py")) + list((ROOT / "test_fixtures").glob("*.py"))
    for path in first_party_python:
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for legacy_import in forbidden_imports:
            assert legacy_import not in text, f"{legacy_import!r} remains in {path.relative_to(ROOT)}"

    # Feature Checker is canonical under src. One compatibility wrapper remains solely because
    # gui_server.py is still a monolithic root entry point; every other first-party caller must use
    # the canonical service directly.
    feature_checker_wrapper_path = ROOT / "feature_checker.py"
    assert feature_checker_wrapper_path.is_file()
    feature_checker_wrapper = feature_checker_wrapper_path.read_text(encoding="utf-8")
    assert "workbench.core.services.feature_checker" in feature_checker_wrapper
    assert "gui_server.py" in feature_checker_wrapper
    legacy_feature_checker_callers = []
    for path in first_party_python:
        if path.resolve() in {Path(__file__).resolve(), feature_checker_wrapper_path.resolve()}:
            continue
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
        if any(line == "import feature_checker" or line.startswith("from feature_checker import") for line in lines):
            legacy_feature_checker_callers.append(path.relative_to(ROOT).as_posix())
    assert legacy_feature_checker_callers == ["gui_server.py"], legacy_feature_checker_callers

    # ID Bridge is canonical under src but retains a root CLI compatibility entry point because
    # operator documentation still uses `python id_bridge.py ...`. The wrapper must contain no
    # database-path derivation or implementation logic of its own.
    id_bridge_wrapper_path = ROOT / "id_bridge.py"
    assert id_bridge_wrapper_path.is_file()
    id_bridge_wrapper = id_bridge_wrapper_path.read_text(encoding="utf-8")
    assert "workbench.core.services.id_bridge" in id_bridge_wrapper
    assert "Path(__file__)" not in id_bridge_wrapper
    assert "sqlite3.connect" not in id_bridge_wrapper

    workflow = (ROOT / ".github" / "workflows" / "workbench-regression.yml").read_text(encoding="utf-8")
    assert '- "src/workbench/**"' in workflow
    ancient_vows = (ROOT / ".github" / "workflows" / "workbench-ancient-vows.yml").read_text(encoding="utf-8")
    assert 'src/workbench/core/services/feature_checker.py' in ancient_vows
    assert '"feature_checker.py"' not in ancient_vows

    # Editable installation in CI must make the canonical src package importable even when
    # neither the repository root nor PYTHONPATH participates in import resolution. Package
    # resources must load from src while repository-owned vendor/docs data remains anchored at
    # the repository root via workbench.runtime.paths.
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "import workbench, workbench.runtime.paths as p; "
            "from workbench.domains import service as d; "
            "import workbench.client.binary_index as bi; "
            "import workbench.client.event_fingerprint as ef; "
            "import workbench.client.identity_extract as ie; "
            "import workbench.gui_shell as gs; "
            "from workbench.core.services.feature_candidates import candidates; "
            "from workbench.core.services.feature_checker import resolve_feature, check_feature; "
            "from workbench.core.services.feature_package_analyzer import analyze; "
            "from workbench.core.services import id_bridge as ib; "
            "pkg=Path(workbench.__file__).resolve(); "
            "assert 'src' in pkg.parts, pkg; "
            "assert p.REPO_ROOT.name == 'FFXI-Mission-Toolkit', p.REPO_ROOT; "
            "assert d.DEF_PATH.parent == pkg.parent / 'domains', d.DEF_PATH; "
            "assert d.WIKI_DUMP == p.repo_path('vendor','ffxi-wiki-dumps-dist','bg-wiki.jsonl.gz'), d.WIKI_DUMP; "
            "assert d.load(), 'domain catalog must load'; "
            "assert callable(candidates) and callable(resolve_feature) and callable(check_feature) and callable(analyze); "
            "assert callable(ib.normalize) and ib.DB_PATH == p.DATABASE_PATH, ib.DB_PATH; "
            "assert 'src' in Path(ib.__file__).resolve().parts, ib.__file__; "
            "assert 'src' in Path(bi.__file__).resolve().parts, bi.__file__; "
            "assert 'src' in Path(ef.__file__).resolve().parts, ef.__file__; "
            "assert 'src' in Path(ie.__file__).resolve().parts, ie.__file__; "
            "assert 'src' in Path(gs.__file__).resolve().parts, gs.__file__; "
            "assert ef._events_dump_root() == p.repo_path('vendor','FFXI-EventsDump'), ef._events_dump_root(); "
            "assert ie.repo_path('vendor','FFXI-Resources','scripts','events','dats.yaml') == p.repo_path('vendor','FFXI-Resources','scripts','events','dats.yaml'); "
            "assert gs.ROUTE_MAP == p.repo_path('docs','workbench','GUI_ROUTE_MAP.json'), gs.ROUTE_MAP; "
            "assert gs.route_owner('/captures/search')['home'] == 'Captures'; "
            "print(pkg)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("src-layout package self-test: PASS")


if __name__ == "__main__":
    main()
