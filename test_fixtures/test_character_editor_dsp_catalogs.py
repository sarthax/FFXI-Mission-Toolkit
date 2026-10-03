"""DSP checkout fallbacks: merit catalog from merits.sql/merit.cpp, legacy missions.lua banners."""
from pathlib import Path
import sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from workbench.editors.character.merit_catalog import merit_catalog
from workbench.editors.character.progression_catalog import mission_catalog


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake_root(tmp: Path) -> Path:
    _write(tmp, "sql/merits.sql", "INSERT INTO `merits` VALUES (65,'max_hp',15,1,1048575,0,0);\n"
                                  "INSERT INTO `merits` VALUES (129,'str',15,1,1048575,1,1);\n"
                                  "INSERT INTO `merits` VALUES (193,'h2h',8,1,53,2,2);\n")
    _write(tmp, "src/map/merit.h", "MCATEGORY_HP_MP = 0x0040,\nMCATEGORY_ATTRIBUTES = 0x0080,\nMCATEGORY_COMBAT = 0x00C0,\nMCATEGORY_COUNT\n")
    _write(tmp, "src/map/merit.cpp",
           "static const MeritCategoryInfo_t meritCatInfo[] =\n{\n"
           "    {3,0,0}, //MCATEGORY_HP_MP\n    {7,60,1}, //MCATEGORY_ATTRIBUTES\n    {19,112,2}, //MCATEGORY_COMBAT\n};\n"
           "static uint8 upgrade[3][16] =\n{\n"
           "    {1,2,3,4,5,5,5,5,5,7,7,7,9,9,9},\n    {3,6,9,9,9,12,12,12,12,15,15,15,15,19,18},\n    {1,2,3,3,4,4,5,5,6,6,7,7,8,8,9},\n};\n")
    _write(tmp, "scripts/globals/missions.lua",
           "-----\n--  San d'Oria (0)\n-----\nSMASH_THE_ORCISH_SCOUTS = 0;  -- x --\nBAT_HUNT = 1;\n"
           "-----\n--  Assault (7)\n-----\nLEUJAOAM_CLEANSING = 1;\n")
    return tmp


with tempfile.TemporaryDirectory() as td:
    root = _fake_root(Path(td))
    cat = merit_catalog(root, "dsp")
    assert cat["source"]["available"], cat
    assert [c["label"] for c in cat["categories"]] == ["HP MP", "Attributes", "Combat"], cat["categories"]
    hp = cat["items"]["65"]
    assert hp["max_upgrades"] == 15 and hp["costs"][:4] == [1, 2, 3, 4] and hp["jobs"] == [], hp
    assert cat["items"]["129"]["costs"][:3] == [3, 6, 9]
    assert cat["items"]["193"]["jobs"] == ["WAR", "WHM", "RDM", "THF"], cat["items"]["193"]["jobs"]

    missions = mission_catalog(root)
    assert missions["areas"]["0"][1]["label"] == "Bat Hunt"
    assert missions["areas"]["7"][1]["symbol"] == "LEUJAOAM_CLEANSING"

# Mission trace regression: BehaviorRule has no .hook attribute, only .trigger.
src = (ROOT / "src/workbench/devtools/features/state_surface.py").read_text(encoding="utf-8")
assert "rule.hook" not in src

print("ok")

# Usability script must be loaded by the editor page, after the loaders it wraps.
tpl = (ROOT / "gui/templates/character_editor_progression.html").read_text(encoding="utf-8")
assert tpl.index("character_editor_state_surface.js") < tpl.index("character_editor_usability.js")
assert "65535" in (ROOT / "gui/static/character_editor_progression.js").read_text(encoding="utf-8")
print("ui ok")
