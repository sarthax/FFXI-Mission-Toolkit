#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile

from workbench.captures import related_evidence as canonical
from workbench.captures import integrity
from workbench.core.services import capture_related_evidence as legacy


def main() -> None:
    assert legacy is canonical
    assert canonical.capture_integrity is integrity
    assert callable(canonical.entity_identity_matches)
    assert callable(canonical.item_identity_matches)
    assert callable(canonical.chat_native_source_matches)

    code = "from workbench.captures import related_evidence, integrity; assert related_evidence.capture_integrity is integrity"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, check=True)


if __name__ == "__main__":
    main()
