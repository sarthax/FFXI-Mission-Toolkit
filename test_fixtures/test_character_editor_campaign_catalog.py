#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.campaign_catalog import campaign_catalog


SAMPLE = """
xi = xi or {}
xi.mission = xi.mission or {}
xi.mission.log_id = { CAMPAIGN = 8 }
xi.mission.area = { [xi.mission.log_id.CAMPAIGN] = 'campaign' }
xi.mission.id =
{
    [xi.mission.area[xi.mission.log_id.CAMPAIGN]] =
    {
        OP_ALPHA = 0,
        OP_BETA = 17,
        OP_OMEGA = 511,
        TOO_HIGH = 700,
        NONE = 65535,
    },
}
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "scripts" / "globals" / "missions.lua"
        path.parent.mkdir(parents=True)
        path.write_text(SAMPLE, encoding="utf-8")
        catalog = campaign_catalog(root)
        assert catalog["source"]["available"] is True
        assert catalog["log_id"] == 8
        assert set(catalog["items"]) == {"0", "17", "511"}
        assert catalog["items"]["17"]["label"] == "Op Beta"
        assert catalog["items"]["511"]["symbol"] == "OP_OMEGA"

    missing = campaign_catalog(None)
    assert missing["items"] == {}
    assert missing["source"]["available"] is False


if __name__ == "__main__":
    main()
