"""Client DAT/EXE/DLL capability and synchronization tooling.

Transitional src-layout bridge: path-sensitive client modules remain at the repository root
while path-normalized modules live under src/workbench/client. Keep both locations importable
until the final client migration slice removes this bridge.
"""
from pathlib import Path

from workbench.runtime.paths import repo_path

for _client_path in (
    repo_path("src", "workbench", "client"),
    repo_path("workbench", "client"),
):
    _client_s = str(_client_path)
    if _client_path.is_dir() and _client_s not in __path__:
        __path__.append(_client_s)

from .binary_index import BinaryFormatError, PEImage, index_binary, write_index
from .binary_diff import diff_binary_indexes
from .dat_adapter import (
    ClientDatRecord,
    ClientServerFieldBinding,
    ClientServerFieldComparison,
    ItemDatAdapter,
    bindings_for,
    compare_server_record_to_client,
    persist_client_dat_record_capability,
)

__all__ = [
    "BinaryFormatError",
    "BinaryAnalysisError",
    "PEImage",
    "index_binary",
    "write_index",
    "diff_binary_indexes",
    "parse_hex_pattern",
    "byte_search",
    "xrefs",
    "function_candidates",
    "ClientDatRecord",
    "ClientServerFieldBinding",
    "ClientServerFieldComparison",
    "ItemDatAdapter",
    "bindings_for",
    "compare_server_record_to_client",
    "persist_client_dat_record_capability",
]
