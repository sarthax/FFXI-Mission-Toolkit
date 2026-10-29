"""Import the real xi_tinkerer first when it is installed.

Several test modules call ``sys.modules.setdefault("xi_tinkerer", <stub>)`` at import time. Without this, whichever
module is collected first installs a stub that has no ``__spec__`` and none of the real parsers, which breaks
``importlib.util.find_spec`` and ``from xi_tinkerer import parse_dialog`` in modules collected later.
"""
try:
    import xi_tinkerer  # noqa: F401
except Exception:  # not installed: the stubs are then the only xi_tinkerer available
    pass
