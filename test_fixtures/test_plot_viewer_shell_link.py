"""Server workspace must continue to expose the standalone 3D viewer entry point."""
from __future__ import annotations

from workbench.gui_shell import WORKSPACES


def run() -> None:
    server = next(workspace for workspace in WORKSPACES if workspace["name"] == "Server")
    viewer = next(section for section in server["sections"] if section["label"] == "3D Viewer")
    assert viewer["href"] == "/zones/0/view3d"


if __name__ == "__main__":
    run()
    print("plot viewer shell link: OK")
