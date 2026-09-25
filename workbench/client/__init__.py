"""Client DAT/EXE/DLL capability and synchronization tooling."""

from .binary_index import BinaryFormatError, PEImage, index_binary, write_index

__all__=["BinaryFormatError","PEImage","index_binary","write_index" ,"diff_binary_indexes"]

from .binary_diff import diff_binary_indexes
