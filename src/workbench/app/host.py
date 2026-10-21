"""Canonical packaged GUI application host.

The historical monolithic FastAPI composition root is stored beside this loader as
``_host_impl.py``. The retained implementation now resolves repository-owned resources through
``workbench.runtime.paths.REPO_ROOT``, so it can execute directly from its packaged location
without a repository-root compatibility launcher.
"""
from __future__ import annotations

from pathlib import Path

_LOADER_FILE = Path(__file__).resolve()
_IMPL_FILE = _LOADER_FILE.with_name("_host_impl.py")
# Execute the retained composition root inside the canonical module namespace.  Its resource
# paths are explicit, so no synthetic repository-root filename is required.
exec(compile(_IMPL_FILE.read_text(encoding="utf-8"), str(_IMPL_FILE), "exec"), globals(), globals())

# Isolated manual design surface. Kept out of the Feature Testing reader/router
# (owned by #1260), and intentionally excluded from the restricted MCP supervisor.
from workbench.server_admin.scenario_authoring.editor_router import router as scenario_developer_router
app.include_router(scenario_developer_router)



def main() -> int:
    """Run the local GUI server through the canonical packaged host."""
    import uvicorn

    con = get_con()
    try:
        port = int(settings_mod.get(con, "port") or settings_mod.DEFAULTS["port"])
    finally:
        con.close()
    uvicorn.run("workbench.app.host:app", host="127.0.0.1", port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
