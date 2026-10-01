"""Client DAT/EXE/DLL capability and synchronization tooling.

The client package now lives entirely under ``src/workbench/client``. Exports remain lazy so
importing one client submodule does not also import unrelated adapters or legacy root utilities.
"""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "BinaryFormatError": (".binary_index", "BinaryFormatError"),
    "PEImage": (".binary_index", "PEImage"),
    "index_binary": (".binary_index", "index_binary"),
    "write_index": (".binary_index", "write_index"),
    "diff_binary_indexes": (".binary_diff", "diff_binary_indexes"),
    "BinaryAnalysisError": (".binary_deep", "BinaryAnalysisError"),
    "parse_hex_pattern": (".binary_deep", "parse_hex_pattern"),
    "byte_search": (".binary_deep", "byte_search"),
    "xrefs": (".binary_deep", "xrefs"),
    "function_candidates": (".binary_deep", "function_candidates"),
    "ClientDatRecord": (".dat_adapter", "ClientDatRecord"),
    "ClientServerFieldBinding": (".dat_adapter", "ClientServerFieldBinding"),
    "ClientServerFieldComparison": (".dat_adapter", "ClientServerFieldComparison"),
    "ItemDatAdapter": (".dat_adapter", "ItemDatAdapter"),
    "bindings_for": (".dat_adapter", "bindings_for"),
    "compare_server_record_to_client": (".dat_adapter", "compare_server_record_to_client"),
    "persist_client_dat_record_capability": (".dat_adapter", "persist_client_dat_record_capability"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
