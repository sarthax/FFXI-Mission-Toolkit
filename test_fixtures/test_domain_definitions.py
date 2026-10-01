#!/usr/bin/env python3
"""Domain definitions are well-formed and every nav Domains link resolves to a defined domain."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workbench.domains import service
from workbench.gui_shell import WORKSPACES


def main():
    defs = service.load()
    for k, d in defs.items():
        for f in ("label", "archetype", "summary", "wiki", "entities", "compare"):
            assert f in d, (k, f)
        assert all({"kind", "fields", "server_globs", "edit"} <= set(e) for e in d["entities"]), k
        for p in d.get("pipeline", []):
            assert {"stage", "status", "summary", "handoffs"} <= set(p), (k, p)
            assert p["status"] in {"ready", "partial", "blocked"}, (k, p["status"])
            assert all({"label", "href"} <= set(h) for h in p["handoffs"]), (k, p)

    salvage = defs["salvage"]
    assert salvage["archetype"] == "system.salvage"
    assert salvage["children"] == [
        "Zhayolm Remnants I", "Zhayolm Remnants II",
        "Arrapago Remnants I", "Arrapago Remnants II",
        "Bhaflau Remnants I", "Bhaflau Remnants II",
        "Silver Sea Remnants I", "Silver Sea Remnants II",
    ]
    stages = {p["stage"]: p["status"] for p in salvage["pipeline"]}
    assert stages["1. Evidence intake"] == "ready"
    assert stages["3. Spawn and instance registration proposal"] == "partial"
    assert stages["5. Telepad / door / CSID mapping"] == "partial"
    assert stages["6. Package and validation"] == "ready"

    ws = next(w for w in WORKSPACES if w["name"] == "Domains")
    def walk(items):
        for s in items:
            yield s
            yield from walk(s.get("children", ()))
    for s in walk(ws["sections"]):
        m = re.match(r"/domains/([a-z]+)(#|$)", s.get("href") or "")
        if m and m.group(1) != "assault":
            assert m.group(1) in defs, s
    print("Domain definitions self-test: PASS")


if __name__ == "__main__":
    main()
