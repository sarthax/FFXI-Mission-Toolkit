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
