#!/usr/bin/env python3
"""Confirm dynamically defined sidebar page routes remain wired in source.

Source contract only; does not claim startup or HTTP acceptance.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    host = (ROOT / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    shell = (ROOT / "src/workbench/gui_shell.py").read_text(encoding="utf-8")
    character = (ROOT / "src/workbench/editors/character/gui.py").read_text(encoding="utf-8")
    assert '@app.get("/domains/{key}"' in host
    assert '@app.get("/zones/{zoneid}/view3d"' in host
    assert 'prefix="/character-editor"' in character
    assert '@router.get("", response_class=HTMLResponse)' in character
    assert 'app.include_router(character_editor_router)' in host
    for route in ("/character-editor", "/zones/0/view3d", "/domains/abyssea", "/domains/battlefields"):
        assert f'"href": "{route}' in shell, f"Sidebar link vanished: {route}"
    print("Dynamic sidebar source contracts: PASS")

if __name__ == "__main__":
    main()
