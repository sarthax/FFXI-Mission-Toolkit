"""Compatibility entry point for the relocated Lua event analyzer.

New code should import from ``workbench.analyzers.server.lua_events``.
"""
from workbench.analyzers.server.lua_events import *  # noqa: F401,F403

if __name__ == "__main__":
    from workbench.analyzers.server.lua_events import main
    raise SystemExit(main())
