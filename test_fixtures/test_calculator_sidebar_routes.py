#!/usr/bin/env python3
"""Navigation contract: calculator sidebar destinations retain their GET page handlers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    "/tools/ws-calc": "src/workbench/server_admin/wscalc/router.py",
    "/tools/melee-calc": "src/workbench/server_admin/meleecalc/router.py",
    "/tools/magic-calc": "src/workbench/server_admin/wscalc/magic_router.py",
    "/tools/heal-calc": "src/workbench/server_admin/healcalc/router.py",
    "/tools/pet-calc": "src/workbench/server_admin/petcalc/router.py",
}

def main():
    shell = (ROOT / "src/workbench/gui_shell.py").read_text(encoding="utf-8")
    for url, filename in ROUTES.items():
        assert f'"href": "{url}"' in shell, f"Sidebar missing calculator: {url}"
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert f'get("{url}"' in source, f"GET page handler missing: {url}"
    print("Calculator sidebar source routes: PASS")

if __name__ == "__main__":
    main()
