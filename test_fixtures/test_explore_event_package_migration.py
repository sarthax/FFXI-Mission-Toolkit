from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.devtools.server import explore_event
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, VENDOR_ROOT, repo_path


def main() -> None:
    assert not (ROOT / "explore_event.py").exists()
    assert explore_event.TOOLS_ROOT == REPO_ROOT == ROOT
    assert explore_event.DB_PATH == DATABASE_PATH
    assert explore_event.MISSION_REPORTS == repo_path("mission_reports")
    assert explore_event.XI_EVENTS_BRIDGE == VENDOR_ROOT / "xi-events-py" / "decompile_from_mission_toolkit.py"
    assert explore_event.__file__ == str(ROOT / "explore_event.py")

    impl_source = (SRC / "workbench" / "devtools" / "server" / "_explore_event_impl.py").read_text(encoding="utf-8")
    assert '"-m", "workbench.devtools.app.mission_toolkit"' in impl_source
    assert 'cwd=str(TOOLS_ROOT)' in impl_source
    assert 'MISSION_REPORTS = TOOLS_ROOT / "mission_reports"' in impl_source


if __name__ == "__main__":
    main()
