"""Read-only source inventory contract."""
import importlib.util
import json
import subprocess
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("chocobo_inventory", Path(__file__).resolve().parents[1] / "scripts/inventory_chocobo_dsp.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_inventory_never_claims_implemented(tmp_path):
    root = tmp_path / "server"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "--allow-empty", "-qm", "fixture"], check=True)
    npc = root / "scripts/zones/Bastok_Mines/npcs/Zopago.lua"
    npc.parent.mkdir(parents=True)
    npc.write_text("-- existing npc\n", encoding="utf-8")
    report = mod.inventory(root)
    assert len(report["findings"]) == 10
    assert all(f["dsp"] == "unknown" for f in report["findings"])
    target = next(f for f in report["findings"] if f["name"] == "Stable NPCs and event dialogue")
    assert target["evidence"] == ["inventory:scripts/zones/Bastok_Mines/npcs/Zopago.lua"]
    assert report["source"]["dirty"] is True
