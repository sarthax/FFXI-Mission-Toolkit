"""lua_sanity must import even when luaparser is installed but unusable (antlr4 runtime mismatch -> TypeError)."""
import importlib
import sys
import types


def test_import_survives_a_luaparser_that_raises_typeerror(monkeypatch):
    broken = types.ModuleType("luaparser")

    def boom(name):
        raise TypeError("ord() expected string of length 1, but int found")

    broken.__getattr__ = boom  # `from luaparser import ast` -> TypeError
    monkeypatch.setitem(sys.modules, "luaparser", broken)
    monkeypatch.delitem(sys.modules, "luaparser.ast", raising=False)
    import workbench.validation.packages.lua_sanity as mod
    try:
        mod = importlib.reload(mod)
        assert mod.lua_ast is None
        assert mod.LUAPARSER_UNAVAILABLE_REASON.startswith("TypeError: ord()")
        from pathlib import Path
        assert mod.check_syntax(Path(__file__)) is None  # skipped, not crashed
    finally:
        monkeypatch.undo()
        importlib.reload(mod)
