"""Keep capture path UI handoffs compatible with the standalone 2D/3D viewers."""
from __future__ import annotations

from workbench.runtime.paths import GUI_ROOT


def run() -> None:
    detail = (GUI_ROOT / "templates" / "capture_detail.html").read_text(encoding="utf-8")

    # The Zone Editor Paths integration is additive.  The legacy 2D viewer is still a supported
    # first-class route and remains the gateway to the standalone 3D path viewer.
    assert "/zoneplot/from_capture?capture_id={{ detail.capture_id }}" in detail
    assert "/captures/plot_all?capture_id={{ detail.capture_id }}" in detail

    single = (GUI_ROOT / "templates" / "path_plot.html").read_text(encoding="utf-8")
    multi = (GUI_ROOT / "templates" / "path_plot_all.html").read_text(encoding="utf-8")
    assert 'href="/zones/{{ zoneid }}/view3d?capture_id={{ capture_id }}&{{ qs_id }}"' in single
    assert 'href="/zones/{{ zoneid }}/view3d_all?capture_id={{ capture_id }}&zone_db={{ zone_db }}"' in multi


if __name__ == "__main__":
    run()
    print("plot viewer capture handoffs: OK")
