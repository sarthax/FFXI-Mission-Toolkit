#!/usr/bin/env python3
"""Phase C package smoke for Capture timeline/correlation services."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workbench.captures import packet_correlation as canonical_corr
from workbench.captures import timeline_alignment as canonical_timeline
from workbench.captures import packet_identity as canonical_identity
from workbench.core.services import packet_correlation as legacy_corr
from workbench.core.services import timeline_alignment as legacy_timeline


def main() -> int:
    assert legacy_timeline.fit_alignment is canonical_timeline.fit_alignment
    assert legacy_corr.correlate_capture is canonical_corr.correlate_capture
    assert legacy_corr._raw_equivalence is canonical_corr._raw_equivalence
    assert canonical_corr.ta is canonical_timeline
    assert canonical_corr.canonical_opcode is canonical_identity.canonical_opcode

    code = """
from workbench.captures import timeline_alignment as ta
from workbench.captures import packet_correlation as pc
from workbench.captures import packet_identity as pi
assert pc.ta is ta
assert pc.canonical_opcode is pi.canonical_opcode
assert pc._opcode('0x2A') == '0x02a'
print('capture timeline/correlation package migration: OK')
"""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env, check=True)
    print("capture timeline/correlation compatibility: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
