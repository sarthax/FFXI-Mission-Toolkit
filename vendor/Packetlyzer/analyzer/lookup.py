"""Lookup Table Manager for the Packetlyzer Analyzer.

Loads VieweD-compatible lookup files (<integer>=<string> format) from a
directory and resolves numeric field values to human-readable names.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Pattern matches lines like "230=Windurst Waters" or "230;Windurst Waters"
# Also handles hex keys like "0x2001;Leather Vest;body 1"
_LINE_PATTERN = re.compile(r"^(0x[0-9A-Fa-f]+|\d+)[=;](.+)$")

# Maximum valid unsigned 32-bit integer
_MAX_UINT32 = 4294967295


class LookupManager:
    """Manages lookup tables loaded from .txt files in a directory.

    Each file is parsed as newline-separated <integer>=<string> pairs.
    The filename (without extension) becomes the table name.
    """

    def __init__(self, lookup_dir: str):
        """Load all .txt files from the lookup directory.

        Args:
            lookup_dir: Path to the directory containing lookup .txt files.
                        If the directory doesn't exist or is empty, a warning
                        is logged and the manager operates with an empty map.
        """
        self._tables: dict[str, dict[int, str]] = {}
        self._load_tables(lookup_dir)

    def _load_tables(self, lookup_dir: str) -> None:
        """Load all .txt files from the lookup directory into memory."""
        if not os.path.isdir(lookup_dir):
            logger.warning(
                "Lookup directory '%s' does not exist. Continuing with empty lookup map.",
                lookup_dir,
            )
            return

        txt_files = [f for f in os.listdir(lookup_dir) if f.lower().endswith(".txt")]

        if not txt_files:
            logger.warning(
                "Lookup directory '%s' is empty. Continuing with empty lookup map.",
                lookup_dir,
            )
            return

        for filename in txt_files:
            table_name = os.path.splitext(filename)[0]
            filepath = os.path.join(lookup_dir, filename)
            self._tables[table_name] = self._parse_file(filepath)

    def _parse_file(self, filepath: str) -> dict[int, str]:
        """Parse a single lookup file into an integer→string map.

        Lines matching <integer>=<string> or <hex>=<string> are loaded.
        Supports both decimal (230) and hex (0x2001) keys.
        Blank lines and non-matching lines are ignored.
        Duplicate keys use last occurrence.

        Args:
            filepath: Full path to the .txt lookup file.

        Returns:
            Dictionary mapping integer keys to string values.
        """
        table: dict[int, str] = {}
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.rstrip("\n").rstrip("\r")
                    match = _LINE_PATTERN.match(line)
                    if match:
                        key_str = match.group(1)
                        value = match.group(2)
                        # Parse key as hex or decimal
                        try:
                            if key_str.startswith("0x") or key_str.startswith("0X"):
                                key = int(key_str, 16)
                            else:
                                key = int(key_str)
                        except ValueError:
                            continue
                        if 0 <= key <= _MAX_UINT32:
                            table[key] = value
        except OSError as e:
            logger.warning("Failed to read lookup file '%s': %s", filepath, e)
        return table

    def resolve(self, table_name: str, value: int) -> str:
        """Resolve a numeric value against a named lookup table.

        Args:
            table_name: Name of the lookup table (filename without extension).
            value: The integer value to look up.

        Returns:
            Display string in one of three formats:
            - '<value> → "<name>"' if value found in table
            - '<value> (unknown)' if value not found in loaded table
            - '<value> (lookup missing)' if table not loaded/doesn't exist
        """
        if table_name not in self._tables:
            return f"{value} (lookup missing)"

        table = self._tables[table_name]
        if value in table:
            return f'{value} \u2192 "{table[value]}"'
        else:
            return f"{value} (unknown)"

    def get_table_names(self) -> list[str]:
        """Return a sorted list of all loaded lookup table names.

        Returns:
            Alphabetically sorted list of table names (filenames without extension).
        """
        return sorted(self._tables.keys())
