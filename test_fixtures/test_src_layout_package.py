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
    assert (SRC_PACKAGE / "app" / "host.py").is_file()
    assert (SRC_PACKAGE / "app" / "_host_impl.py").is_file()
    assert (SRC_PACKAGE / "core").is_dir()
    assert (SRC_PACKAGE / "runtime" / "paths.py").is_file()
    assert (SRC_PACKAGE / "runtime" / "settings_store.py").is_file()
    assert (SRC_PACKAGE / "domains" / "service.py").is_file()
    assert (SRC_PACKAGE / "domains" / "definitions.json").is_file()
    assert (SRC_PACKAGE / "client" / "binary_index.py").is_file()
    assert (SRC_PACKAGE / "client" / "identity_snapshot.py").is_file()
    assert (SRC_PACKAGE / "client" / "event_fingerprint.py").is_file()
    assert (SRC_PACKAGE / "client" / "identity_extract.py").is_file()
    assert (SRC_PACKAGE / "client" / "dat" / "extractor_bin.py").is_file()
    assert (SRC_PACKAGE / "client" / "dat" / "inspector.py").is_file()
    assert (SRC_PACKAGE / "gui_shell.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "feature_candidates.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "feature_checker.py").is_file()
    assert (SRC_PACKAGE / "devtools" / "features" / "checker.py").is_file()
    assert (SRC_PACKAGE / "devtools" / "features" / "trace_binding_drilldown.py").is_file()
    assert (SRC_PACKAGE / "devtools" / "server" / "binding_index.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "feature_package_analyzer.py").is_file()
    assert (SRC_PACKAGE / "core" / "services" / "id_bridge.py").is_file()

    assert ROOT_PACKAGE.is_dir()
    assert sorted(path.name for path in ROOT_PACKAGE.iterdir()) == ["__init__.py"]
    assert BRIDGE.is_file()
    bridge_text = BRIDGE.read_text(encoding="utf-8")
    assert "src" in bridge_text and "workbench" in bridge_text
    assert "__path__.append" in bridge_text
    assert "Do not add implementation modules" in bridge_text

    root_gui = (ROOT / "gui_server.py").read_text(encoding="utf-8")
    assert "from workbench.app import host as _canonical" in root_gui
    assert "FastAPI(" not in root_gui and "@app." not in root_gui
    root_settings = (ROOT / "settings.py").read_text(encoding="utf-8")
    assert "from workbench.runtime import settings_store as _canonical" in root_settings
    assert "sqlite3.connect" not in root_settings

    moved_root_artifacts = (
        "appraisal_item_id_xref.csv",
        "appraisal_pools_with_item_ids.csv",
        "uncharted90_names.txt",
        "mission_toolkit_gui_artifact.html",
        "backport_coverage_report.md",
    )
    for name in moved_root_artifacts:
        assert not (ROOT / name).exists(), name
    assert (ROOT / "data" / "reference" / "appraisal" / "item_id_xref.csv").is_file()
    assert (ROOT / "data" / "reference" / "appraisal" / "pools_with_item_ids.csv").is_file()
    assert (ROOT / "data" / "reference" / "uncharted90_names.txt").is_file()
    assert (ROOT / "docs" / "archive" / "ui" / "mission_toolkit_gui_artifact.html").is_file()
    assert (ROOT / "docs" / "reports" / "backport" / "backport_coverage_report.md").is_file()

    for name in ("install_xi_tinkerer.py", "install_external_tools.py", "reset_install.py"):
        assert not (ROOT / name).exists(), name
    assert (ROOT / "scripts" / "bootstrap" / "install_xi_tinkerer.py").is_file()
    assert (ROOT / "scripts" / "bootstrap" / "install_external_tools.py").is_file()
    assert (ROOT / "scripts" / "bootstrap" / "reset_install.py").is_file()

    setup_text = (ROOT / "setup.bat").read_text(encoding="utf-8")
    assert "%PY% -m pip install --quiet --disable-pip-version-check -e ." in setup_text
    assert "%PY% scripts\\bootstrap\\install_xi_tinkerer.py" in setup_text
    assert "%PY% scripts\\bootstrap\\install_external_tools.py xi-tinkerer-cli" in setup_text
    assert "%PY% -m workbench.devtools.indexing.build_database" in setup_text
    assert "%PY% -m workbench.devtools.indexing.build_npc_index" in setup_text
    assert "%PY% -m workbench.devtools.reference.dialog.build_index" in setup_text
    assert "%PY% -m workbench.client.dat.global_tables" in setup_text
    assert "%PY% -m workbench.captures.ingestion.build_index list" in setup_text
    assert "%PY% -m workbench.devtools.indexing.build_sql_index" in setup_text
    assert "%PY% -m workbench.devtools.indexing.build_lsb_index" in setup_text
    assert "%PY% -m workbench.devtools.reference.scrape_bg_wiki" in setup_text
    for legacy_call in (
        "%PY% install_xi_tinkerer.py",
        "%PY% install_external_tools.py",
        "%PY% build_database.py",
        "%PY% build_npc_index.py",
        "%PY% build_dialog_index.py",
        "%PY% ingest_global_tables.py",
        "%PY% build_capture_index.py",
        "%PY% build_sql_index.py",
        "%PY% build_lsb_index.py",
        "%PY% scrape_bg_wiki.py",
    ):
        assert legacy_call not in setup_text, legacy_call

    start_text = (ROOT / "start.bat").read_text(encoding="utf-8")
    assert '"%PY%" -m workbench.app.host' in start_text
    assert '"%PY%" gui_server.py' not in start_text
    reset_text = (ROOT / "reset_install.bat").read_text(encoding="utf-8")
    assert "python scripts\\bootstrap\\reset_install.py" in reset_text
    assert "python reset_install.py" not in reset_text

    retired = (
        "workbench_graph.py",
        "workbench_schema.py",
        "source_snapshot.py",
        "feature_candidates.py",
        "feature_package_analyzer.py",
        "build_database.py",
        "build_npc_index.py",
        "build_dialog_index.py",
        "ingest_global_tables.py",
        "build_sql_index.py",
        "build_lsb_index.py",
        "scrape_bg_wiki.py",
        "backport_binding_audit.py",
        "backport_lua_sanity_check.py",
        "backport_binding_index.py",
        "backport_item_audit.py",
        "backport_coverage_check.py",
        "backport_map_confidence_check.py",
        "backport_map_lint.py",
        "dat_extractor_bin.py",
        "dat_inspector.py",
    )
    for name in retired:
        assert not (ROOT / name).exists(), name

    capture_shim = (ROOT / "build_capture_index.py").read_text(encoding="utf-8")
    assert "workbench.captures.ingestion import build_index as _canonical" in capture_shim
    assert "sqlite3.connect" not in capture_shim
    assert "Path(__file__)" not in capture_shim

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

    feature_checker_wrapper_path = ROOT / "feature_checker.py"
    assert feature_checker_wrapper_path.is_file()
    feature_checker_wrapper = feature_checker_wrapper_path.read_text(encoding="utf-8")
    assert "workbench.devtools.features.checker" in feature_checker_wrapper
    core_checker_shim = (SRC_PACKAGE / "core" / "services" / "feature_checker.py").read_text(encoding="utf-8")
    assert "workbench.devtools.features.checker" in core_checker_shim
    legacy_feature_checker_callers = []
    for path in first_party_python:
        if path.resolve() in {Path(__file__).resolve(), feature_checker_wrapper_path.resolve()}:
            continue
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
        if any(line == "import feature_checker" or line.startswith("from feature_checker import") for line in lines):
            legacy_feature_checker_callers.append(path.relative_to(ROOT).as_posix())
    assert legacy_feature_checker_callers == ["src/workbench/app/_host_impl.py"], legacy_feature_checker_callers

    id_bridge_wrapper_path = ROOT / "id_bridge.py"
    assert id_bridge_wrapper_path.is_file()
    id_bridge_wrapper = id_bridge_wrapper_path.read_text(encoding="utf-8")
    assert "workbench.core.services.id_bridge" in id_bridge_wrapper
    assert "Path(__file__)" not in id_bridge_wrapper
    assert "sqlite3.connect" not in id_bridge_wrapper

    workflow = (ROOT / ".github" / "workflows" / "workbench-regression.yml").read_text(encoding="utf-8")
    assert '- "src/workbench/**"' in workflow
    character_workflow = (ROOT / ".github" / "workflows" / "character-editor-regression.yml").read_text(encoding="utf-8")
    assert '- "gui_server.py"' in character_workflow
    assert '- "src/workbench/app/**"' in character_workflow
    assert '- "src/workbench/runtime/settings_store.py"' in character_workflow
    ancient_vows = (ROOT / ".github" / "workflows" / "workbench-ancient-vows.yml").read_text(encoding="utf-8")
    assert 'src/workbench/devtools/features/checker.py' in ancient_vows
    assert 'src/workbench/core/services/feature_checker.py' not in ancient_vows
    assert '"feature_checker.py"' not in ancient_vows

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
            "from workbench.client.dat import extractor_bin as de, inspector as di; "
            "import workbench.gui_shell as gs; "
            "from workbench.core.services.feature_candidates import candidates; "
            "from workbench.devtools.features.checker import resolve_feature, check_feature; "
            "from workbench.devtools.features.trace_binding_drilldown import binding_lookup; "
            "from workbench.devtools.server import binding_index as dbi; "
            "from workbench.core.services.feature_package_analyzer import analyze; "
            "from workbench.core.services import id_bridge as ib; "
            "pkg=Path(workbench.__file__).resolve(); "
            "assert 'src' in pkg.parts, pkg; "
            "assert p.REPO_ROOT.name == 'FFXI-Mission-Toolkit', p.REPO_ROOT; "
            "assert d.DEF_PATH.parent == pkg.parent / 'domains', d.DEF_PATH; "
            "assert d.WIKI_DUMP == p.repo_path('vendor','ffxi-wiki-dumps-dist','bg-wiki.jsonl.gz'), d.WIKI_DUMP; "
            "assert d.load(), 'domain catalog must load'; "
            "assert callable(candidates) and callable(resolve_feature) and callable(check_feature) and callable(analyze); "
            "assert callable(binding_lookup) and callable(dbi.build_topaz_index) and callable(dbi.build_dsp_index); "
            "assert callable(ib.normalize) and ib.DB_PATH == p.DATABASE_PATH, ib.DB_PATH; "
            "assert de.PROJECT_DIR == p.VENDOR_ROOT / 'dat-extractor', de.PROJECT_DIR; "
            "assert di.dat_id_for_zone_family(0, 'dialog') == 6420; "
            "assert di.resource_context(6421) == {'family':'dialog','zone_id':1}; "
            "assert 'src' in Path(de.__file__).resolve().parts, de.__file__; "
            "assert 'src' in Path(di.__file__).resolve().parts, di.__file__; "
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
