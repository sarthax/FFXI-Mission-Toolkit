#!/usr/bin/env python3
"""Regression checks for Development dependency-service namespace migration."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.core.services import conditional_dependencies as legacy_conditional
from workbench.core.services import dependency_map_presentation as legacy_presentation
from workbench.core.services import obtainability_closure as legacy_obtainability
from workbench.devtools.dependencies import conditional, obtainability, presentation


def main() -> None:
    # Compatibility shims must expose the exact canonical public objects.
    assert legacy_conditional.ConditionalDependency is conditional.ConditionalDependency
    assert legacy_conditional.project_conditional_dependency is conditional.project_conditional_dependency
    assert legacy_conditional.persist_conditional_dependency is conditional.persist_conditional_dependency
    assert legacy_obtainability.build_obtainability_closure is obtainability.build_obtainability_closure
    assert legacy_obtainability.closure_projection is obtainability.closure_projection
    assert legacy_obtainability.resolve_obtainability_root is obtainability.resolve_obtainability_root
    assert legacy_presentation.direct_dependencies is presentation.direct_dependencies
    assert legacy_presentation.visible_nodes is presentation.visible_nodes
    assert legacy_presentation.path_from_root is presentation.path_from_root
    assert legacy_presentation.initial_presentation is presentation.initial_presentation

    # Editable installation must import the final Development namespace without repo-root help.
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "from workbench.devtools.dependencies import conditional, obtainability, presentation; "
            "mods=(conditional, obtainability, presentation); "
            "assert all('src' in Path(m.__file__).resolve().parts for m in mods); "
            "assert callable(conditional.project_conditional_dependency); "
            "assert callable(obtainability.build_obtainability_closure); "
            "assert callable(presentation.initial_presentation); "
            "print('Development dependency services:', *(m.__file__ for m in mods))"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("Development dependency services migration: PASS")


if __name__ == "__main__":
    main()
