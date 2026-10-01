"""Client DAT/EXE/DLL capability and synchronization tooling.

Transitional src-layout bridge: path-sensitive client modules remain at the repository root
while path-normalized modules live under src/workbench/client. Both locations stay importable
until the final client migration slice removes this bridge.

Exports are lazy so importing one client submodule does not also import legacy root utilities
through unrelated adapters.
"""
from __future__ import annotations

from importlib import import_module

from workbench.runtime.paths import repo_path

for _client_path in (
    repo_path("src", "workbench", "client"),
    repo_path("workbench", "client"),
):
    _client_s = str(_client_path)
    if _client_path.is_dir() and _client_s not in __path__:
        __path__.append(_client_s)

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
