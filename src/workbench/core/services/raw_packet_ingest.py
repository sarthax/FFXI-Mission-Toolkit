"""Compatibility shim for Capture raw packet ingestion services."""
from workbench.captures import raw_packet_ingest as _canonical

for _name in dir(_canonical):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_canonical, _name)
