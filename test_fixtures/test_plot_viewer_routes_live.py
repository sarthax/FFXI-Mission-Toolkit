"""Regression coverage for the capture 2D/3D viewer routes on the live FastAPI app.

These routes were recently touched indirectly by Capture/Zone Editor handoff changes.  A template
or route-map string is not enough: verify the actual ``workbench.app.host:app`` route table still owns the
URLs the browser opens.
"""
from __future__ import annotations

from workbench.app.host import app


EXPECTED = {
    "/captures/plot": "captures_plot",
    "/captures/plot.png": "captures_plot_png",
    "/captures/plot_all": "captures_plot_all",
    "/captures/plot_all.png": "captures_plot_all_png",
    "/zones/{zoneid}/view3d": "zone_view3d",
    "/zones/{zoneid}/view3d_all": "zone_view3d_all",
}


def run() -> None:
    registered = {
        getattr(route, "path", None): getattr(getattr(route, "endpoint", None), "__name__", None)
        for route in app.routes
    }
    for path, endpoint in EXPECTED.items():
        assert path in registered, f"live FastAPI app is missing {path}"
        assert registered[path] == endpoint, (path, registered[path], endpoint)

    # Guard the exact browser handoffs as well.  The old plot pages remain supported alongside the
    # newer Zone Editor Paths tab; neither is allowed to silently replace the other's route.
    from pathlib import Path
    from workbench.runtime.paths import GUI_ROOT

    templates = Path(GUI_ROOT) / "templates"
    single = (templates / "path_plot.html").read_text(encoding="utf-8")
    multi = (templates / "path_plot_all.html").read_text(encoding="utf-8")
    viewer = (templates / "zone_view3d.html").read_text(encoding="utf-8")

    assert "/zones/{{ zoneid }}/view3d?capture_id={{ capture_id }}" in single
    assert "/zones/{{ zoneid }}/view3d_all?capture_id={{ capture_id }}" in multi
    assert "/captures/plot_all?capture_id={{ capture_id }}" in viewer
    assert "/captures/plot?capture_id={{ capture_id }}" in viewer


if __name__ == "__main__":
    run()
    print("plot viewer live routes: OK")
