#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.captures import chat, integrity, pcap_ingest, raw_packet_ingest
from workbench.captures.ingestion import build_index as canonical
from workbench.devtools.entities import profile as entity_profile
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT


def _load_root_compat():
    root_path = Path(__file__).resolve().parents[1] / "build_capture_index.py"
    name = "build_capture_index_compat"
    spec = importlib.util.spec_from_file_location(name, root_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    legacy = _load_root_compat()
    assert legacy is canonical
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.entity_profile is entity_profile
    assert canonical.capture_integrity is integrity
    assert canonical.raw_packet_ingest is raw_packet_ingest
    assert canonical.capture_chat is chat
    assert canonical.pcap_ingest is pcap_ingest
    assert callable(canonical.init_db)
    assert callable(canonical.main)

    original = canonical.DB_PATH
    sentinel = REPO_ROOT / "__capture_index_migration_sentinel__.db"
    canonical.DB_PATH = sentinel
    try:
        assert legacy.DB_PATH == sentinel
    finally:
        canonical.DB_PATH = original

    code = (
        "from workbench.captures import chat, integrity, pcap_ingest, raw_packet_ingest; "
        "from workbench.captures.ingestion import build_index; "
        "from workbench.devtools.entities import profile; "
        "from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT; "
        "assert build_index.DB_PATH == DATABASE_PATH; "
        "assert build_index.TOOLS_ROOT == REPO_ROOT; "
        "assert build_index.entity_profile is profile; "
        "assert build_index.capture_integrity is integrity; "
        "assert build_index.raw_packet_ingest is raw_packet_ingest; "
        "assert build_index.capture_chat is chat; "
        "assert build_index.pcap_ingest is pcap_ingest; "
        "assert callable(build_index.init_db)"
    )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)


if __name__ == "__main__":
    main()
