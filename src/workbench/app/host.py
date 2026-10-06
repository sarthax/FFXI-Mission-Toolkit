"""Canonical packaged GUI application host.

The historical monolithic FastAPI composition root is stored beside this loader as
``_host_impl.py``.  During this final source-layout migration we execute that exact implementation
with a compatibility ``__file__`` pointing at the repository-root launcher so its established
repository-owned path semantics remain unchanged.  Root ``gui_server.py`` is therefore free to
become a tiny launch/import compatibility entry point without rewriting 10k+ route lines at once.
"""
from __future__ import annotations

from pathlib import Path

from workbench.runtime.paths import REPO_ROOT

_LOADER_FILE = Path(__file__).resolve()
_IMPL_FILE = _LOADER_FILE.with_name("_host_impl.py")
_COMPAT_FILE = REPO_ROOT / "gui_server.py"
_RUNTIME_NAME = __name__

# Prevent the legacy source footer from starting uvicorn while it is being imported/executed as
# the packaged host.  Function/class ``__module__`` values also become the canonical package name.
globals()["__name__"] = "workbench.app.host"
globals()["__file__"] = str(_COMPAT_FILE)
exec(compile(_IMPL_FILE.read_text(encoding="utf-8"), str(_COMPAT_FILE), "exec"), globals(), globals())
globals()["__name__"] = _RUNTIME_NAME


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
