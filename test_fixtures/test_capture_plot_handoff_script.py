"""Regression guard for the shared capture plot handoff repair."""
from __future__ import annotations

from workbench.runtime.paths import GUI_ROOT


def run() -> None:
    script = (GUI_ROOT / "static" / "server_environment_selector.js").read_text(encoding="utf-8")
    assert "repairCapturePlotHandoffs" in script
    assert "/captures/plot?capture_id=${captureId}&entity_id=" in script
    assert "/captures/plot?capture_id=${captureId}&pc=1&zone_db=" in script
    assert "2D / 3D plot" in script
    assert "Zone Editor Paths" in script
    # The repair must run before profile-state loading so it still works if Character Editor
    # profile discovery is temporarily unavailable.
    assert script.index("repairCapturePlotHandoffs();") < script.index("const state = await loadState();")


if __name__ == "__main__":
    run()
    print("capture plot handoff script: OK")
