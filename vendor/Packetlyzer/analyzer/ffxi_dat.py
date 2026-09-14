"""FFXI DAT file system resolver.

Reads VTABLE.DAT and FTABLE.DAT to map ROM file IDs to filesystem paths.
Mirrors the logic from POLUtils FFXI.cs GetFilePath().

The FFXI ROM filesystem uses a two-table lookup:
  - VTABLE: byte array indexed by file number → which ROM partition (1-based)
  - FTABLE: uint16 array indexed by file number → encoded dir/file
    dir  = ftable_value // 0x80
    file = ftable_value %  0x80
    path = Rom{partition}/dir/file.dat

Typical default install: C:/Program Files (x86)/PlayOnline/SquareEnix/FINAL FANTASY XI
"""

from __future__ import annotations

import logging
import os
import struct
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default FFXI install paths to search (in order)
_DEFAULT_PATHS = [
    r"C:\Program Files (x86)\PlayOnline\SquareEnix\FINAL FANTASY XI",
    r"C:\Program Files\PlayOnline\SquareEnix\FINAL FANTASY XI",
    r"C:\SquareEnix\FINAL FANTASY XI",
]

# Dialog table base ROM file ID: zone_id offset from here gives the dialog DAT
DIALOG_TABLE_BASE = 6420
DIALOG_TABLE_EXT_BASE = 85590  # Extended zones (zone IDs 256+)


class FFXIDatResolver:
    """Resolves FFXI ROM file IDs to local filesystem DAT paths.

    Loads VTABLE/FTABLE from the configured FFXI install directory and
    provides path resolution for any ROM file number.
    """

    def __init__(self, ffxi_path: Optional[str] = None):
        """Initialize the DAT resolver.

        Args:
            ffxi_path: Path to the FFXI install directory. If None, searches
                       default locations automatically.
        """
        self._ffxi_path: Optional[str] = None
        self._vtables: dict[int, bytes] = {}   # partition → vtable bytes
        self._ftables: dict[int, bytes] = {}   # partition → ftable bytes
        self._initialized = False

        if ffxi_path:
            self.set_path(ffxi_path)
        else:
            self._auto_detect()

    @property
    def ffxi_path(self) -> Optional[str]:
        """The resolved FFXI install path, or None if not found."""
        return self._ffxi_path

    @property
    def is_available(self) -> bool:
        """Whether the DAT resolver is ready (path found and tables loaded)."""
        return self._initialized

    def set_path(self, path: str) -> bool:
        """Set the FFXI install path and load ROM tables.

        Args:
            path: Absolute path to the FFXI install directory.

        Returns:
            True if the path is valid and tables were loaded successfully.
        """
        if not os.path.isdir(path):
            logger.warning("FFXI path does not exist: %s", path)
            return False

        self._ffxi_path = path
        self._vtables.clear()
        self._ftables.clear()
        self._initialized = False

        try:
            self._load_tables()
            self._initialized = True
            logger.info("FFXI DAT resolver initialized: %s", path)
            return True
        except Exception as e:
            logger.error("Failed to load ROM tables from %s: %s", path, e)
            return False

    def get_dat_path(self, file_number: int) -> Optional[str]:
        """Resolve a ROM file number to its filesystem DAT path.

        Args:
            file_number: The ROM file ID (e.g., 6507 for zone 87 dialog).

        Returns:
            Absolute path to the .dat file, or None if not found.
        """
        if not self._initialized:
            return None

        # Search all loaded partitions
        for partition, vtable in self._vtables.items():
            if file_number >= len(vtable):
                continue

            # VTABLE byte at file_number tells us which partition owns it
            vt_val = vtable[file_number]
            if vt_val != partition:
                continue

            # FTABLE gives us the encoded dir/file
            ftable = self._ftables.get(partition)
            if ftable is None:
                continue

            offset = file_number * 2
            if offset + 2 > len(ftable):
                continue

            file_dir = struct.unpack_from("<H", ftable, offset)[0]
            dir_num = file_dir // 0x80
            file_num = file_dir % 0x80

            # Build the path
            if partition == 1:
                rom_dir = "Rom"
            else:
                rom_dir = f"Rom{partition}"

            dat_path = os.path.join(
                self._ffxi_path, rom_dir, str(dir_num), f"{file_num}.dat"
            )

            if os.path.isfile(dat_path):
                return dat_path

            logger.debug("DAT not found: %s (file %d)", dat_path, file_number)
            return None

        return None

    def get_dialog_dat_path(self, zone_id: int) -> Optional[str]:
        """Get the dialog table DAT path for a zone.

        Args:
            zone_id: The zone ID (0-based).

        Returns:
            Absolute path to the zone's dialog table .dat file, or None.
        """
        if zone_id < 256:
            file_number = DIALOG_TABLE_BASE + zone_id
        else:
            file_number = DIALOG_TABLE_EXT_BASE + (zone_id - 256)

        return self.get_dat_path(file_number)

    # ---------------------------------------------------------------------------
    # Internal
    # ---------------------------------------------------------------------------

    def _auto_detect(self) -> None:
        """Try to find the FFXI install directory automatically."""
        for path in _DEFAULT_PATHS:
            if os.path.isdir(path):
                if self.set_path(path):
                    return
        logger.info("FFXI install not auto-detected")

    def _load_tables(self) -> None:
        """Load all VTABLE/FTABLE pairs from the FFXI install directory.

        FFXI uses multiple ROM partitions:
          - Partition 1: VTABLE.DAT / FTABLE.DAT in the root
          - Partition 2+: VTABLE{n}.DAT / FTABLE{n}.DAT in Rom{n}/
        """
        root = self._ffxi_path

        for partition in range(1, 20):
            if partition == 1:
                suffix = ""
                table_dir = root
            else:
                suffix = str(partition)
                table_dir = os.path.join(root, f"Rom{partition}")

            vtable_path = os.path.join(table_dir, f"VTABLE{suffix}.DAT")
            ftable_path = os.path.join(table_dir, f"FTABLE{suffix}.DAT")

            if not os.path.isfile(vtable_path) or not os.path.isfile(ftable_path):
                continue

            try:
                with open(vtable_path, "rb") as f:
                    self._vtables[partition] = f.read()
                with open(ftable_path, "rb") as f:
                    self._ftables[partition] = f.read()
                logger.debug(
                    "Loaded ROM partition %d: VTABLE=%d bytes, FTABLE=%d bytes",
                    partition,
                    len(self._vtables[partition]),
                    len(self._ftables[partition]),
                )
            except OSError as e:
                logger.warning("Failed to read ROM tables for partition %d: %s", partition, e)

        if not self._vtables:
            raise FileNotFoundError(
                f"No VTABLE/FTABLE files found in {root}"
            )
