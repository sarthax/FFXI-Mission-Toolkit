#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.runtime.paths import REPO_ROOT
from workbench.validation import pipeline as canonical



def main() -> None:
    assert not (REPO_ROOT / "validation_pipeline.py").exists()

    class Result:
        run_id = "run:demo"
        validation_id = "demo:alpha beta"
        validation_type = "DEMO"
        subject_id = "alpha beta"
        status = "PASSED"
        evidence_id = "evidence:test"
        source = "source"
        target = "target"
        notes = ["ok"]

    original = canonical.execute_validation
    seen = {}
    try:
        def fake_execute(spec, run_id):
            seen["spec"] = spec
            seen["run_id"] = run_id
            return Result()

        canonical.execute_validation = fake_execute
        out = canonical.run("demo.py", ["alpha", "beta"], "run:demo")
    finally:
        canonical.execute_validation = original

    assert seen["run_id"] == "run:demo"
    assert seen["spec"].script == "demo.py"
    assert seen["spec"].args == ("alpha", "beta")
    assert out["status"] == "PASSED"
    assert out["evidence_id"] == "evidence:test"

    code = (
        "from workbench.validation import pipeline as p; "
        "assert callable(p.run); assert callable(p.main); "
        "print('outside-repo validation pipeline import: PASS')"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("validation pipeline package migration: PASS")


if __name__ == "__main__":
    main()
