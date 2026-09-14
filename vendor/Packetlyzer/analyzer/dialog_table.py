"""FFXI Dialog Table DAT parser.

Reads and decrypts dialog table DAT files from the FFXI client installation.
Ports the logic from POLUtils DialogTable.cs and DialogTableEntry.cs.

DAT file format:
  - Byte 0-3: File size marker (0x10000000 + actual_data_length)
  - Byte 4+:  Offset table (each entry is 4 bytes, XOR'd with 0x80808080)
              Number of entries = first_text_offset / 4
  - Text data: Entries at the offsets, each byte XOR'd with 0x80

Special text markers (after XOR decryption):
  0x07 → Line break
  0x08 → Player Name (you)
  0x09 → Speaker Name (NPC/target)
  0x0A + byte → Numeric Parameter N
  0x0B → Selection Dialog (prompt)
  0x0C + byte → Multiple Choice (Parameter N)
  0x19 + byte → Item Parameter N
  0x1A + byte → Key Item Parameter N
  0x1E + byte → Set Color #N
  0x7F + byte → Extended marker (Prompt, Gender choice, etc.)
"""

from __future__ import annotations

import logging
import os
import struct
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# XOR keys used by FFXI for dialog table encryption
_OFFSET_XOR = 0x80808080
_TEXT_XOR = 0x80


@dataclass
class DialogEntry:
    """A single entry from a dialog table."""

    index: int
    raw_text: str  # Text with special markers converted to readable form
    choices: dict[int, list[str]]  # Parameter N → list of choice strings (for Multiple Choice)


class DialogTable:
    """Parsed dialog table for a single zone.

    Loads a dialog table DAT file, decrypts and parses all entries,
    and provides indexed access to dialog text.
    """

    def __init__(self):
        self._entries: dict[int, DialogEntry] = {}
        self._zone_id: int = -1
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Whether a dialog table has been successfully loaded."""
        return self._loaded

    @property
    def zone_id(self) -> int:
        """The zone ID this table was loaded for."""
        return self._zone_id

    @property
    def entry_count(self) -> int:
        """Number of entries in the table."""
        return len(self._entries)

    def load(self, dat_path: str, zone_id: int = -1) -> bool:
        """Load and parse a dialog table DAT file.

        Args:
            dat_path: Absolute path to the dialog table .dat file.
            zone_id: Zone ID for reference (optional).

        Returns:
            True if loading succeeded.
        """
        self._entries.clear()
        self._zone_id = zone_id
        self._loaded = False

        if not os.path.isfile(dat_path):
            logger.warning("Dialog table DAT not found: %s", dat_path)
            return False

        try:
            with open(dat_path, "rb") as f:
                data = f.read()
        except OSError as e:
            logger.error("Failed to read dialog table: %s", e)
            return False

        if len(data) < 8:
            logger.warning("Dialog table too small: %d bytes", len(data))
            return False

        # Validate header: first 4 bytes should be 0x10000000 + (len(data) - 4)
        header = struct.unpack_from("<I", data, 0)[0]
        expected_header = 0x10000000 + (len(data) - 4)
        if header != expected_header:
            logger.debug(
                "Dialog table header mismatch: got 0x%08X, expected 0x%08X",
                header, expected_header,
            )
            # Some tables have slight variations — try to continue anyway

        # Read the first offset to determine entry count
        first_offset_raw = struct.unpack_from("<I", data, 4)[0]
        first_text_pos = first_offset_raw ^ _OFFSET_XOR

        if first_text_pos % 4 != 0 or first_text_pos < 4:
            logger.warning("Invalid first text position: %d", first_text_pos)
            return False

        entry_count = first_text_pos // 4

        if entry_count == 0:
            logger.info("Dialog table has 0 entries")
            self._loaded = True
            return True

        # Read all entry offsets (decrypting with XOR)
        offsets: list[int] = []
        for i in range(entry_count):
            raw_offset = struct.unpack_from("<I", data, 4 + i * 4)[0]
            offsets.append(raw_offset ^ _OFFSET_XOR)

        # Add end sentinel (file length minus header)
        offsets_sorted = sorted(set(offsets))
        data_length = len(data) - 4  # Subtract header

        # Parse each entry
        for i in range(entry_count):
            entry_start = offsets[i]

            # Find end: next offset in sorted order, or end of data
            entry_end = data_length
            for off in offsets_sorted:
                if off > entry_start:
                    entry_end = off
                    break

            # Bounds check
            if entry_start >= data_length or entry_start < first_text_pos:
                continue

            # Extract and decrypt text bytes (skip header by adding 4)
            text_start = 4 + entry_start
            text_end = min(4 + entry_end, len(data))

            if text_start >= text_end:
                self._entries[i] = DialogEntry(index=i, raw_text="", choices={})
                continue

            encrypted_bytes = data[text_start:text_end]
            decrypted = bytes(b ^ _TEXT_XOR for b in encrypted_bytes)

            # Parse the decrypted text
            raw_text, choices = self._parse_text(decrypted)
            self._entries[i] = DialogEntry(index=i, raw_text=raw_text, choices=choices)

        self._loaded = True
        logger.info(
            "Loaded dialog table for zone %d: %d entries from %s",
            zone_id, len(self._entries), dat_path,
        )
        return True

    def get_entry(self, index: int) -> Optional[DialogEntry]:
        """Get a dialog entry by index.

        Args:
            index: The dialog table entry index.

        Returns:
            The DialogEntry, or None if not found.
        """
        return self._entries.get(index)

    def get_text(self, index: int) -> Optional[str]:
        """Get raw dialog text by index.

        Args:
            index: The dialog table entry index.

        Returns:
            The dialog text with markers, or None if not found.
        """
        entry = self._entries.get(index)
        return entry.raw_text if entry else None

    def resolve_text(self, index: int, params: Optional[list[int]] = None) -> Optional[str]:
        """Resolve dialog text with parameter substitution.

        Replaces Multiple Choice markers with the selected option based
        on the provided parameter values.

        Args:
            index: The dialog table entry index.
            params: List of parameter values [param0, param1, param2, param3].

        Returns:
            Resolved text string, or None if entry not found.
        """
        entry = self._entries.get(index)
        if entry is None:
            return None

        if not params:
            return entry.raw_text

        text = entry.raw_text
        # Replace each {Choice:N:option1/option2/...} with the selected option
        for param_idx, choices in entry.choices.items():
            if param_idx < len(params):
                selected = params[param_idx]
                if 0 <= selected < len(choices):
                    replacement = choices[selected]
                else:
                    replacement = f"[?{selected}]"
            else:
                replacement = "[?]"

            marker = self._build_choice_marker(param_idx, choices)
            text = text.replace(marker, replacement)

        return text

    # ---------------------------------------------------------------------------
    # Internal parsing
    # ---------------------------------------------------------------------------

    def _parse_text(self, decrypted: bytes) -> tuple[str, dict[int, list[str]]]:
        """Parse decrypted dialog bytes into readable text and choice data.

        Returns:
            Tuple of (formatted_text, choices_dict).
        """
        text_parts: list[str] = []
        choices: dict[int, list[str]] = {}
        i = 0

        while i < len(decrypted):
            b = decrypted[i]

            if b == 0x00:
                # Null terminator — stop
                break
            elif b == 0x07:
                # Line break
                text_parts.append("\n")
                i += 1
            elif b == 0x08:
                # Player name (you)
                text_parts.append("<player>")
                i += 1
            elif b == 0x09:
                # Speaker name (NPC)
                text_parts.append("<speaker>")
                i += 1
            elif b == 0x0A and i + 1 < len(decrypted):
                # Numeric Parameter N
                param_num = decrypted[i + 1]
                text_parts.append(f"<number:{param_num}>")
                i += 2
            elif b == 0x0B:
                # Selection dialog / Prompt
                text_parts.append("<prompt>")
                i += 1
            elif b == 0x0C and i + 1 < len(decrypted):
                # Multiple Choice (Parameter N)
                param_num = decrypted[i + 1]
                i += 2
                # Read the choices: separated by 0x07, terminated by end or next marker
                choice_list, bytes_consumed = self._read_choices(decrypted, i)
                choices[param_num] = choice_list
                marker = self._build_choice_marker(param_num, choice_list)
                text_parts.append(marker)
                i += bytes_consumed
            elif b == 0x19 and i + 1 < len(decrypted):
                # Item Parameter N
                param_num = decrypted[i + 1]
                text_parts.append(f"<item:{param_num}>")
                i += 2
            elif b == 0x1A and i + 1 < len(decrypted):
                # Key Item Parameter N
                param_num = decrypted[i + 1]
                text_parts.append(f"<keyitem:{param_num}>")
                i += 2
            elif b == 0x1C and i + 1 < len(decrypted):
                # Player/Chocobo Parameter N
                param_num = decrypted[i + 1]
                text_parts.append(f"<entity:{param_num}>")
                i += 2
            elif b == 0x1E and i + 1 < len(decrypted):
                # Set Color — skip silently
                i += 2
            elif b == 0x7F and i + 1 < len(decrypted):
                # Extended markers
                marker_type = decrypted[i + 1]
                if marker_type == 0x31 and i + 2 < len(decrypted):
                    # Prompt (with optional delay)
                    delay = decrypted[i + 2]
                    if delay > 0:
                        text_parts.append(f"<wait:{delay}>")
                    else:
                        text_parts.append("<prompt>")
                    i += 3
                elif marker_type == 0x85:
                    # Multiple Choice: Player Gender
                    text_parts.append("<gender>")
                    i += 2
                elif marker_type == 0x92 and i + 2 < len(decrypted):
                    # Singular/Plural Choice
                    param_num = decrypted[i + 2]
                    text_parts.append(f"<plural:{param_num}>")
                    i += 3
                elif i + 2 < len(decrypted):
                    # Unknown extended marker — skip
                    i += 3
                else:
                    i += 2
            elif b < 0x20:
                # Unknown control code — skip
                i += 1
            else:
                # Regular text byte — decode as Shift-JIS (FFXI encoding)
                # Collect consecutive regular bytes for batch decoding
                start = i
                while i < len(decrypted) and decrypted[i] >= 0x20 and decrypted[i] != 0x7F:
                    # Check for multi-byte Shift-JIS
                    if (0x80 <= decrypted[i] <= 0x9F) or (0xE0 <= decrypted[i] <= 0xEF):
                        i += 2  # Two-byte character
                    else:
                        i += 1
                # Decode the text chunk
                chunk = decrypted[start:i]
                try:
                    text_parts.append(chunk.decode("shift_jis", errors="replace"))
                except (UnicodeDecodeError, LookupError):
                    text_parts.append(chunk.decode("latin-1", errors="replace"))

        return "".join(text_parts), choices

    def _read_choices(self, data: bytes, start: int) -> tuple[list[str], int]:
        """Read Multiple Choice options from the byte stream.

        Format: "[" choice0 "/" choice1 "/" ... "/" lastchoice "]"
        The choice block is delimited by '[' and ']' characters.

        Returns:
            Tuple of (choice_list, bytes_consumed).
        """
        choices: list[str] = []
        current: list[bytes] = []
        i = start

        # Skip opening bracket if present
        if i < len(data) and data[i] == 0x5B:  # '['
            i += 1

        while i < len(data):
            b = data[i]

            if b == 0x00:
                # End of string
                break
            elif b == 0x5D:
                # ']' — end of choice block
                # Add the last choice
                if current:
                    try:
                        choices.append(bytes(current).decode("shift_jis", errors="replace"))
                    except (UnicodeDecodeError, LookupError):
                        choices.append(bytes(current).decode("latin-1", errors="replace"))
                    current = []
                i += 1  # consume the ']'
                break
            elif b < 0x20 and b != 0x07:
                # Control character ends the choice block (fallback if no ']')
                break
            elif b == 0x7F:
                # Extended marker ends choice block (fallback if no ']')
                break
            elif b == 0x2F:
                # '/' separator between choices
                try:
                    choices.append(bytes(current).decode("shift_jis", errors="replace"))
                except (UnicodeDecodeError, LookupError):
                    choices.append(bytes(current).decode("latin-1", errors="replace"))
                current = []
                i += 1
            else:
                current.append(b)
                # Handle multi-byte Shift-JIS
                if (0x80 <= b <= 0x9F) or (0xE0 <= b <= 0xEF):
                    if i + 1 < len(data):
                        current.append(data[i + 1])
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1

        # If we broke out without finding ']', add remaining as last choice
        if current:
            try:
                choices.append(bytes(current).decode("shift_jis", errors="replace"))
            except (UnicodeDecodeError, LookupError):
                choices.append(bytes(current).decode("latin-1", errors="replace"))

        return choices, i - start

    @staticmethod
    def _build_choice_marker(param_idx: int, choices: list[str]) -> str:
        """Build the text representation of a Multiple Choice marker."""
        choices_str = "/".join(choices)
        return f"{{Choice:{param_idx}:{choices_str}}}"


class DialogTableCache:
    """Caches loaded dialog tables per zone to avoid re-reading DATs."""

    def __init__(self, dat_resolver):
        """Initialize the cache.

        Args:
            dat_resolver: An FFXIDatResolver instance for path lookups.
        """
        self._resolver = dat_resolver
        self._tables: dict[int, DialogTable] = {}

    def get_table(self, zone_id: int) -> Optional[DialogTable]:
        """Get the dialog table for a zone (loading from DAT if needed).

        Args:
            zone_id: The zone ID.

        Returns:
            The loaded DialogTable, or None if unavailable.
        """
        if zone_id in self._tables:
            return self._tables[zone_id]

        if not self._resolver.is_available:
            return None

        dat_path = self._resolver.get_dialog_dat_path(zone_id)
        if dat_path is None:
            logger.debug("No dialog DAT path for zone %d", zone_id)
            return None

        table = DialogTable()
        if table.load(dat_path, zone_id):
            self._tables[zone_id] = table
            return table

        return None

    def clear(self) -> None:
        """Clear all cached tables."""
        self._tables.clear()

    def preload(self, zone_id: int) -> bool:
        """Preload a zone's dialog table into the cache.

        Args:
            zone_id: The zone ID to preload.

        Returns:
            True if loading succeeded.
        """
        table = self.get_table(zone_id)
        return table is not None and table.is_loaded
