"""Compatibility shim for Capture packet correlation services."""
from workbench.captures import packet_correlation as _canonical

for _name in dir(_canonical):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_canonical, _name)
