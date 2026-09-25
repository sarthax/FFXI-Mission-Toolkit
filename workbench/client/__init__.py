"""Client DAT/EXE/DLL capability and synchronization tooling."""

from .binary_index import BinaryFormatError, PEImage, index_binary, write_index

__all__=["BinaryFormatError","PEImage","index_binary","write_index"]
