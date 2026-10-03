from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The CLI's native DAT parser dependency is optional in CI; a tiny import stub is enough for
# relocation/path regression coverage because no parser is executed here.
xi = types.ModuleType("xi_tinkerer")
xi.parse_dialog = lambda *_args, **_kwargs: {}
xi.parse_entity_names = lambda *_args, **_kwargs: {}
xi.parse_events = lambda *_args, **_kwargs: {}
sys.modules.setdefault("xi_tinkerer", xi)

import mission_toolkit as root_module
from workbench.devtools.app import mission_toolkit


def main() -> None:
    assert root_module is mission_toolkit
    assert mission_toolkit.TOOLS_ROOT == ROOT
    assert mission_toolkit.LEGACY_FILE == ROOT / "mission_toolkit.py"
    assert mission_toolkit.IMPLEMENTATION_FILE == SRC / "workbench" / "devtools" / "app" / "_mission_toolkit_impl.py"
    assert mission_toolkit.DAT_EXTRACTOR_DLL == ROOT / "vendor" / "dat-extractor" / "bin" / "Debug" / "net9.0" / "dat-extractor.dll"
    assert mission_toolkit.ALTANA_ZONES_CSV == ROOT / "vendor" / "ffxi" / "reference" / "AltanaViewer_zones.csv"
    assert mission_toolkit.normalize("Mamool Ja-Training_Grounds") == "mamooljatraininggrounds"
    assert mission_toolkit.dat_id_for_zone(0, "events") == 5820
    assert mission_toolkit.dat_id_for_zone(256, "events") == 84991

    root_source = (ROOT / "mission_toolkit.py").read_text(encoding="utf-8")
    assert "def resolve_topaz_zone" not in root_source
    assert "workbench.devtools.app" in root_source


if __name__ == "__main__":
    main()
