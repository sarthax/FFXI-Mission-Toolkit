#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.eminence_catalog import eminence_catalog


TOPAZ_SAMPLE = """
tpz.roe.records =
{
    [   1] = { -- First Step Forward
    },
    --[[ TODO
    [1045] = { -- Achieve Level 99
    },
    ]]
    [4095] = { -- Last Record +
    },
}
"""

LSB_SAMPLE = """
xi.roe.records =
{
    [1] =
    { -- First Step Forward +
    },
    [499] =
    { -- Stepping into an Ambuscade
    },
}
"""


def _write(root: Path, text: str) -> None:
    path = root / "scripts" / "globals" / "roe_records.lua"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, TOPAZ_SAMPLE)
        catalog = eminence_catalog(root)
        assert catalog["source"]["available"] is True
        assert set(catalog["items"]) == {"1", "4095"}
        assert catalog["items"]["1"]["label"] == "First Step Forward"
        assert catalog["items"]["4095"]["label"] == "Last Record"
        assert "1045" not in catalog["items"]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, LSB_SAMPLE)
        catalog = eminence_catalog(root)
        assert catalog["items"]["1"]["label"] == "First Step Forward"
        assert catalog["items"]["499"]["label"] == "Stepping into an Ambuscade"

    missing = eminence_catalog(None)
    assert missing["source"]["available"] is False
    assert missing["items"] == {}


if __name__ == "__main__":
    main()
