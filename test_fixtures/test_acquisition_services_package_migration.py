#!/usr/bin/env python3
"""Regression checks for Development acquisition-service namespace migration."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.core.services import acquisition_catalog as legacy_catalog
from workbench.core.services import acquisition_identity as legacy_identity
from workbench.devtools.acquisition import catalog, identity


def main() -> None:
    assert legacy_catalog.AcquisitionPath is catalog.AcquisitionPath
    assert legacy_catalog.build_acquisition_catalog is catalog.build_acquisition_catalog
    assert legacy_catalog.verified_external_item_ids is catalog.verified_external_item_ids
    assert legacy_identity.reconcile_acquisition_catalog is identity.reconcile_acquisition_catalog
    assert legacy_identity.verified_canonical_item_ids is identity.verified_canonical_item_ids

    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "from workbench.devtools.acquisition import catalog, identity; "
            "assert 'src' in Path(catalog.__file__).resolve().parts; "
            "assert 'src' in Path(identity.__file__).resolve().parts; "
            "assert callable(catalog.build_acquisition_catalog); "
            "assert callable(identity.reconcile_acquisition_catalog); "
            "print('Development acquisition services:', catalog.__file__, identity.__file__)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("Development acquisition services migration: PASS")


if __name__ == "__main__":
    main()
