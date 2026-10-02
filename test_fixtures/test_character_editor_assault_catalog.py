#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.assault_catalog import assault_catalog


SAMPLE = """xi = xi or {}
xi.assault = xi.assault or {}
xi.assault.mission =
{
    LEUJAOAM_CLEANSING = 1,
    LAMIA_NO_13 = 42,
    NYZUL_ISLE_UNCHARTED_AREA_SURVEY = 52,
}
xi.assault.instance =
{
    SHOULD_NOT_PARSE = 5500,
}
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "scripts" / "enum" / "assault.lua"
        path.parent.mkdir(parents=True)
        path.write_text(SAMPLE, encoding="utf-8")
        catalog = assault_catalog(root)
        assert catalog["source"]["available"] is True
        assert catalog["source"]["kind"] == "assault.lua"
        assert catalog["missions"]["1"]["label"] == "Leujaoam Cleansing"
        assert catalog["missions"]["42"]["symbol"] == "LAMIA_NO_13"
        assert catalog["missions"]["52"]["label"] == "Nyzul Isle Uncharted Area Survey"
        assert "5500" not in catalog["missions"]

    with tempfile.TemporaryDirectory() as tmp:
        catalog = assault_catalog(Path(tmp))
        assert catalog["source"]["available"] is False
        assert catalog["missions"] == {}


if __name__ == "__main__":
    main()
