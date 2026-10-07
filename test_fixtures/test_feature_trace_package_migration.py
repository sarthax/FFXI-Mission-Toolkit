#!/usr/bin/env python3
"""Regression checks for the root -> Development Feature Trace migration."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workbench.core.contracts import capture_row_locators
from workbench.devtools.features import trace as canonical_trace
from workbench.devtools.features import trace_catalog


def main() -> None:
    assert not (ROOT / "feature_trace.py").exists()

    # The staged implementation may retain historical import text, but its bound runtime
    # dependencies must be the final Development catalog and Core capture contract.
    impl = canonical_trace._impl
    assert impl.catalog_node is trace_catalog.catalog_node
    assert impl.search_catalog is trace_catalog.search_catalog
    assert impl.capture_integrity is capture_row_locators
    assert impl.capture_integrity.find_row_locators is capture_row_locators.find_row_locators

    # Editable installation must import the canonical Trace outside repository cwd without the
    # root compatibility script participating in module resolution.
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from workbench.devtools.features import trace; "
            "from workbench.core.contracts import capture_row_locators; "
            "from workbench.devtools.features import trace_catalog; "
            "assert trace._impl.capture_integrity is capture_row_locators; "
            "assert trace._impl.catalog_node is trace_catalog.catalog_node; "
            "assert callable(trace.node_info) and callable(trace.search_nodes); "
            "print('canonical Feature Trace import:', trace.__file__)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("Feature Trace Development package migration: PASS")


if __name__ == "__main__":
    main()
