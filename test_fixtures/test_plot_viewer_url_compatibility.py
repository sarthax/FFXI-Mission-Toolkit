"""Compatibility contract for URLs users may still have in bookmarks/history."""
from __future__ import annotations

from workbench.app.host import app


def run() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}
    # Canonical endpoints used by current templates.
    for path in (
        "/captures/plot",
        "/captures/plot_all",
        "/zones/{zoneid}/view3d",
        "/zones/{zoneid}/view3d_all",
        "/zoneplot2",
        "/zoneplot/from_capture",
    ):
        assert path in paths, path


if __name__ == "__main__":
    run()
    print("plot viewer URL compatibility: OK")
