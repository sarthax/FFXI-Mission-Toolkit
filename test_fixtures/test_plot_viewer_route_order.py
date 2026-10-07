"""Ensure static capture plot routes are registered before the dynamic capture detail route."""
from __future__ import annotations

from workbench.app.host import app


def run() -> None:
    paths = [getattr(route, "path", "") for route in app.routes]
    dynamic = paths.index("/captures/{capture_id}")
    for static in ("/captures/plot", "/captures/plot.png", "/captures/plot_all", "/captures/plot_all.png"):
        assert paths.index(static) < dynamic, (static, paths.index(static), dynamic)


if __name__ == "__main__":
    run()
    print("plot viewer route order: OK")
