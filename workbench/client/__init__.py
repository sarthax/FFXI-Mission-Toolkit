"""Client DAT/EXE/DLL capability and synchronization tooling."""

from .binary_index import BinaryFormatError, PEImage, index_binary, write_index

__all__=["BinaryFormatError","BinaryAnalysisError","PEImage","index_binary","write_index","diff_binary_indexes","parse_hex_pattern","byte_search","xrefs","function_candidates"]

from .binary_diff import diff_binary_indexes
