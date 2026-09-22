"""Database Enrichment Importers for Packetlyzer.

Provides XiPacketsImporter for merging XiPackets markdown field definitions
into the PacketDB, and XiEventsImporter for importing XiEvents markdown
event opcodes into the extension JSON.
"""

import json
import logging
import os
import re
import sys
from typing import Optional

from analyzer.packet_db import FieldDefinition, PacketDB, PacketDefinition

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type mapping: XiPackets type names -> supported Decoder field types
# ---------------------------------------------------------------------------

_XIPACKETS_TYPE_MAP: dict[str, str] = {
    # Direct matches (case-insensitive lookup applied at runtime)
    "uint8": "byte",
    "byte": "byte",
    "unsigned char": "byte",
    "char": "byte",
    "uint16": "uint16",
    "unsigned short": "uint16",
    "uint32": "uint32",
    "unsigned int": "uint32",
    "unsigned long": "uint32",
    "int8": "int8",
    "signed char": "int8",
    "int16": "int16",
    "short": "int16",
    "int32": "int32",
    "int": "int32",
    "long": "int32",
    "float": "float",
    "single": "float",
    "float32": "float",
    "bits": "bits",
    "bit": "bits",
    "string": "t",
    "char[]": "t",
    "char*": "t",
    "raw": "a",
    "bytes": "a",
    "data": "a",
    "blob": "a",
    "pos": "pos",
    "position": "pos",
    "dir": "dir",
    "direction": "dir",
    "rotation": "dir",
    "ms": "ms",
    "time": "ms",
    "ip": "ip",
    "ipaddress": "ip",
    "ip address": "ip",
}

# Size inference from type name when size column is not present
_TYPE_SIZES: dict[str, int] = {
    "byte": 1,
    "uint16": 2,
    "uint32": 4,
    "int8": 1,
    "int16": 2,
    "int32": 4,
    "float": 4,
    "dir": 1,
    "ms": 4,
    "ip": 4,
    "pos": 12,
}


def _map_xipackets_type(xipackets_type: str) -> str:
    """Map an XiPackets field type to a supported Decoder type.

    Args:
        xipackets_type: The type string from the XiPackets markdown.

    Returns:
        A supported Decoder type string. Defaults to 'a' if no mapping found.
    """
    normalized = xipackets_type.strip().lower()
    if normalized in _XIPACKETS_TYPE_MAP:
        return _XIPACKETS_TYPE_MAP[normalized]

    # Try without trailing digits or brackets (e.g. "uint8[4]" -> "uint8")
    base = re.sub(r"\[.*\]$", "", normalized).strip()
    if base in _XIPACKETS_TYPE_MAP:
        return _XIPACKETS_TYPE_MAP[base]

    # No match found - log warning and default to 'a'
    logger.warning("Unknown XiPackets field type '%s', defaulting to 'a'", xipackets_type)
    return "a"


def _infer_size_from_type(decoder_type: str, size_hint: Optional[int] = None) -> Optional[int]:
    """Infer size for 'a' and 't' typed fields.

    Returns the size_hint if provided, otherwise None for types that
    need explicit size (a, t) and None for fixed-size types.
    """
    if decoder_type in ("a", "t"):
        return size_hint
    return None


# ---------------------------------------------------------------------------
# Markdown parsing helpers
# ---------------------------------------------------------------------------

_OPCODE_FILENAME_RE = re.compile(r"0x([0-9a-fA-F]{2,4})")


def _extract_opcode_from_filename(filename: str) -> Optional[int]:
    """Extract the opcode integer from a filename like '0x0028.md'.

    Args:
        filename: The markdown filename (basename).

    Returns:
        The opcode as an integer, or None if extraction fails.
    """
    stem = os.path.splitext(filename)[0]
    match = _OPCODE_FILENAME_RE.search(stem)
    if match:
        try:
            return int(match.group(1), 16)
        except ValueError:
            return None
    return None


def _extract_name_from_heading(content: str) -> str:
    """Extract the packet name from the top-level heading.

    Looks for the first `# ` heading line in the content.

    Args:
        content: The full markdown file content.

    Returns:
        The heading text, or empty string if not found.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return ""


def _parse_table_row(row: str) -> list[str]:
    """Parse a markdown table row into cell values.

    Handles leading/trailing pipes and strips whitespace from cells.

    Args:
        row: A single markdown table row string.

    Returns:
        List of cell values (strings).
    """
    # Remove leading/trailing pipes and split
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _is_separator_row(row: str) -> bool:
    """Check if a table row is a separator (e.g. |---|---|---|)."""
    cells = _parse_table_row(row)
    return all(re.match(r"^[-:]+$", cell) for cell in cells if cell)


def _parse_size_from_text(size_text: str) -> Optional[int]:
    """Parse a size value from markdown table text.

    Handles formats like "4", "0x04", "4 bytes", etc.

    Args:
        size_text: The size column text.

    Returns:
        Integer size or None if unparseable.
    """
    size_text = size_text.strip().lower()
    # Remove common suffixes
    size_text = re.sub(r"\s*(bytes?|octets?)\s*$", "", size_text)
    size_text = size_text.strip()

    if not size_text:
        return None

    try:
        if size_text.startswith("0x"):
            return int(size_text, 16)
        return int(size_text)
    except ValueError:
        return None


def _parse_offset_from_text(offset_text: str) -> Optional[int]:
    """Parse an offset/position value from markdown table text.

    Handles formats like "0x04", "4", "0x0004".

    Args:
        offset_text: The offset column text.

    Returns:
        Integer offset or None if unparseable.
    """
    offset_text = offset_text.strip()
    if not offset_text:
        return None

    try:
        if offset_text.lower().startswith("0x"):
            return int(offset_text, 16)
        return int(offset_text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# XiPackets field table parsing
# ---------------------------------------------------------------------------


def _find_field_table_section(content: str) -> Optional[str]:
    """Find and return the content of the '## Packet Fields' section.

    Args:
        content: Full markdown content.

    Returns:
        The text from the Packet Fields section, or None if not found.
    """
    lines = content.splitlines()
    in_section = False
    section_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## packet fields"):
            in_section = True
            continue
        elif in_section and stripped.startswith("## "):
            # Next section starts
            break
        elif in_section:
            section_lines.append(line)

    if not in_section:
        return None
    return "\n".join(section_lines)


def _identify_columns(header_cells: list[str]) -> dict[str, int]:
    """Map known column names to their indices from the table header.

    Recognizes: offset, size, type, name/field, description/notes.

    Args:
        header_cells: List of header cell values.

    Returns:
        Dict mapping column role to index.
    """
    columns: dict[str, int] = {}
    for i, cell in enumerate(header_cells):
        lower = cell.lower().strip()
        if lower in ("offset", "off", "pos", "position"):
            columns["offset"] = i
        elif lower in ("size", "length", "len", "bytes"):
            columns["size"] = i
        elif lower in ("type",):
            columns["type"] = i
        elif lower in ("name", "field", "field name"):
            columns["name"] = i
        elif lower in ("description", "desc", "notes", "note", "info"):
            columns["description"] = i
    return columns


def _parse_field_table(table_section: str) -> list[FieldDefinition]:
    """Parse field definitions from a markdown table section.

    Args:
        table_section: The text content of the Packet Fields section.

    Returns:
        List of FieldDefinition objects parsed from the table.
    """
    lines = [l for l in table_section.splitlines() if l.strip()]
    if len(lines) < 2:
        return []

    # Find the table: first line with | that looks like a header
    table_start = -1
    for i, line in enumerate(lines):
        if "|" in line and not _is_separator_row(line):
            # Check if next line is a separator
            if i + 1 < len(lines) and _is_separator_row(lines[i + 1]):
                table_start = i
                break

    if table_start < 0:
        return []

    header_cells = _parse_table_row(lines[table_start])
    columns = _identify_columns(header_cells)

    # Must have at least name or type column to proceed
    if "name" not in columns and "type" not in columns:
        return []

    fields: list[FieldDefinition] = []
    # Start after header and separator
    data_start = table_start + 2

    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped or not "|" in stripped:
            break  # End of table
        if _is_separator_row(stripped):
            continue

        cells = _parse_table_row(stripped)

        # Extract values using identified columns
        offset_text = cells[columns["offset"]] if "offset" in columns and columns["offset"] < len(cells) else ""
        size_text = cells[columns["size"]] if "size" in columns and columns["size"] < len(cells) else ""
        type_text = cells[columns["type"]] if "type" in columns and columns["type"] < len(cells) else ""
        name_text = cells[columns["name"]] if "name" in columns and columns["name"] < len(cells) else ""

        # Skip rows with no name
        if not name_text.strip():
            continue

        # Clean name: replace spaces with underscores, remove non-alphanum
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name_text.strip())
        clean_name = re.sub(r"_+", "_", clean_name).strip("_")
        if not clean_name:
            continue

        # Map type
        decoder_type = _map_xipackets_type(type_text) if type_text.strip() else "a"

        # Parse offset
        pos = _parse_offset_from_text(offset_text)
        if pos is None:
            pos = 0

        # Parse size
        size = _parse_size_from_text(size_text)

        # Determine size attribute for 'a' and 't' types
        field_size = None
        if decoder_type in ("a", "t"):
            if size is not None:
                field_size = size
            else:
                field_size = 1  # Default minimum

        field_def = FieldDefinition(
            name=clean_name,
            type=decoder_type,
            pos=pos,
            bits=None,
            lookup=None,
            size=field_size,
        )
        fields.append(field_def)

    return fields


def _extract_notes(content: str) -> str:
    """Extract non-table text content from the markdown as notes.

    Captures text outside the field table that provides additional context
    (enum descriptions, flag breakdowns, usage descriptions, etc.).

    Args:
        content: Full markdown content.

    Returns:
        Notes text (may be empty string).
    """
    lines = content.splitlines()
    note_lines: list[str] = []
    in_field_table = False
    past_heading = False

    for line in lines:
        stripped = line.strip()

        # Skip the top-level heading
        if stripped.startswith("# ") and not stripped.startswith("## ") and not past_heading:
            past_heading = True
            continue

        # Track when we're in the Packet Fields table area
        if stripped.lower().startswith("## packet fields"):
            in_field_table = True
            continue

        if in_field_table:
            # We're in the field table section - skip table rows
            if "|" in stripped or _is_separator_row(stripped):
                continue
            elif stripped.startswith("## "):
                # New section - we're past the field table
                in_field_table = False
                note_lines.append(stripped)
            elif stripped:
                # Non-table content in the fields section (notes about fields)
                note_lines.append(stripped)
        elif past_heading:
            # Content before or after the Packet Fields section
            if stripped and not stripped.startswith("## packet fields"):
                note_lines.append(stripped)

    return "\n".join(note_lines).strip()


# ---------------------------------------------------------------------------
# XiPacketsImporter
# ---------------------------------------------------------------------------


class XiPacketsImporter:
    """Imports XiPackets markdown field definitions into the PacketDB.

    Parses markdown files from XiPackets' world/server/ (s2c) and
    world/client/ (c2s) directories. Merges new fields without overwriting
    existing VieweD-sourced definitions.
    """

    def import_from(self, world_dir: str, db: PacketDB) -> tuple[int, int]:
        """Parse XiPackets markdown and merge into the PacketDB.

        Args:
            world_dir: Path to the XiPackets world directory containing
                       server/ and client/ subdirectories.
            db: The PacketDB instance to merge definitions into.

        Returns:
            A tuple of (added_count, updated_count) representing the number
            of new opcodes created and the number of existing opcodes that
            received new fields.
        """
        added = 0
        updated = 0
        notes_data: dict[str, dict] = {}

        # Load existing extension data
        ext_path = db._ext_path
        ext_data: dict = {}
        if ext_path:
            try:
                with open(ext_path, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                ext_data = {}

        # Process server/ (s2c) and client/ (c2s) directories
        dir_mappings = [
            (os.path.join(world_dir, "server"), "s2c"),
            (os.path.join(world_dir, "client"), "c2s"),
        ]

        for dir_path, direction in dir_mappings:
            if not os.path.isdir(dir_path):
                logger.warning("Directory not found: %s", dir_path)
                continue

            for filename in sorted(os.listdir(dir_path)):
                if not filename.lower().endswith(".md"):
                    continue

                filepath = os.path.join(dir_path, filename)
                result = self._process_file(filepath, filename, direction, db)

                if result is None:
                    continue

                action, opcode = result
                if action == "added":
                    added += 1
                elif action == "updated":
                    updated += 1

                # Extract and store notes
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    notes = _extract_notes(content)
                    if notes:
                        opcode_key = f"{opcode:03x}"
                        if opcode_key not in ext_data:
                            ext_data[opcode_key] = {}
                        ext_data[opcode_key]["notes"] = notes
                except OSError:
                    pass

        # Save updated XML
        db.save_xml()

        # Save extension JSON with notes
        if ext_path and ext_data:
            try:
                with open(ext_path, "w", encoding="utf-8") as f:
                    json.dump(ext_data, f, indent=2, ensure_ascii=False)
            except OSError as e:
                logger.warning("Failed to write extension JSON: %s", e)

        return added, updated

    def _process_file(
        self, filepath: str, filename: str, direction: str, db: PacketDB
    ) -> Optional[tuple[str, int]]:
        """Process a single XiPackets markdown file.

        Args:
            filepath: Full path to the markdown file.
            filename: The basename of the file.
            direction: "s2c" or "c2s".
            db: The PacketDB to merge into.

        Returns:
            A tuple of (action, opcode) where action is "added" or "updated",
            or None if the file was skipped.
        """
        # Extract opcode from filename
        opcode = _extract_opcode_from_filename(filename)
        if opcode is None:
            logger.warning(
                "Skipping '%s': cannot extract opcode from filename", filename
            )
            return None

        # Read file content
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            logger.warning("Skipping '%s': cannot read file: %s", filename, e)
            return None

        # Extract packet name from heading
        name = _extract_name_from_heading(content)
        if not name:
            name = f"Packet 0x{opcode:04X}"

        # Find and parse the field table
        field_section = _find_field_table_section(content)
        if field_section is None:
            logger.warning(
                "Skipping '%s': no '## Packet Fields' section found", filename
            )
            return None

        fields = _parse_field_table(field_section)
        if not fields:
            logger.warning(
                "Skipping '%s': no parseable fields in table", filename
            )
            return None

        # Check if definition already exists
        existing = db.get_definition(direction, opcode)

        if existing is None:
            # Create new definition
            definition = PacketDefinition(
                opcode=opcode,
                direction=direction,
                description=name,
                fields=fields,
            )
            db.set_definition(direction, opcode, definition)
            return ("added", opcode)
        else:
            # Merge: add fields whose name doesn't match existing (case-insensitive)
            existing_names = {f.name.lower() for f in existing.fields}
            new_fields = [
                f for f in fields if f.name.lower() not in existing_names
            ]

            if new_fields:
                existing.fields.extend(new_fields)
                db.set_definition(direction, opcode, existing)
                return ("updated", opcode)

            # No new fields to add
            return None


# ---------------------------------------------------------------------------
# XiEventsImporter
# ---------------------------------------------------------------------------

# Regex for event opcodes: matches 2-4 hex digits (with optional 0x prefix)
# in filenames or headings. Must be at least 2 hex chars to avoid false
# positives from single letters in words.
_EVENT_OPCODE_FILENAME_RE = re.compile(
    r"^(?:0x)?([0-9A-Fa-f]{2,4})$"
)
_EVENT_OPCODE_HEADING_RE = re.compile(
    r"(?:0x)?([0-9A-Fa-f]{2,4})\b"
)


class XiEventsImporter:
    """Imports XiEvents markdown event opcode definitions into ext JSON.

    Parses markdown files from XiEvents' OpCodes/ directory and stores
    them in the packetlyzer_ext.json under the "events" key.
    """

    def import_from(self, opcodes_dir: str, ext_path: str) -> int:
        """Parse XiEvents markdown and write to extension JSON.

        Args:
            opcodes_dir: Path to the XiEvents OpCodes directory.
            ext_path: Path to the packetlyzer_ext.json file.

        Returns:
            Count of event opcodes imported.

        Raises:
            SystemExit: If the directory doesn't exist or has no .md files.
        """
        # Validate directory exists (Req 10.7)
        if not os.path.isdir(opcodes_dir):
            print(
                f"Error: OpCodes directory not found: {opcodes_dir}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Find markdown files (Req 10.7)
        md_files = sorted(
            f
            for f in os.listdir(opcodes_dir)
            if f.lower().endswith(".md")
            and os.path.isfile(os.path.join(opcodes_dir, f))
        )

        if not md_files:
            print(
                f"Error: No .md files found in: {opcodes_dir}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Load existing extension data
        ext_data: dict = {}
        if os.path.isfile(ext_path):
            try:
                with open(ext_path, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                ext_data = {}

        if "events" not in ext_data:
            ext_data["events"] = {}

        count = 0
        for filename in md_files:
            filepath = os.path.join(opcodes_dir, filename)
            result = self._process_event_file(filepath, filename)
            if result is not None:
                opcode_key, entry = result
                # Overwrite existing entries on re-import (Req 10.6)
                ext_data["events"][opcode_key] = entry
                count += 1

        # Write updated extension JSON
        try:
            with open(ext_path, "w", encoding="utf-8") as f:
                json.dump(ext_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Failed to write extension JSON: %s", e)

        return count

    def _process_event_file(
        self, filepath: str, filename: str
    ) -> Optional[tuple[str, dict]]:
        """Process a single XiEvents markdown file.

        Args:
            filepath: Full path to the markdown file.
            filename: The basename of the file.

        Returns:
            A tuple of (opcode_key, entry_dict) or None if unparseable.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            logger.warning("Skipping '%s': cannot read: %s", filename, e)
            return None

        # Extract opcode from filename first, then heading (Req 10.1, 10.5)
        opcode = self._extract_event_opcode(filename, content)

        if opcode is None:
            # Log warning for files without recognizable opcode (Req 10.5)
            logger.warning(
                "XiEvents: no recognizable opcode in '%s', skipping.",
                filename,
            )
            return None

        # Format as 4-char uppercase zero-padded hex key (Req 10.2)
        opcode_key = f"{opcode:04X}"

        # Extract event details
        name = self._extract_event_name(content, filename)
        description = self._extract_event_description(content)
        size = self._extract_event_size(content)
        pseudo_code = self._extract_event_pseudo_code(content)

        entry = {
            "name": name,
            "description": description,
            "size": size,
            "pseudo_code": pseudo_code,
        }

        return opcode_key, entry

    def _extract_event_opcode(
        self, filename: str, content: str
    ) -> Optional[int]:
        """Extract event opcode from filename or first heading.

        Tries filename stem first (e.g. '00A1.md', '0x004B.md'),
        then falls back to the first heading line.

        Args:
            filename: The markdown filename basename.
            content: The full file content.

        Returns:
            Integer opcode, or None if not found.
        """
        # Try filename stem (strip .md extension)
        stem = os.path.splitext(filename)[0]
        match = _EVENT_OPCODE_FILENAME_RE.match(stem)
        if match:
            try:
                return int(match.group(1), 16)
            except ValueError:
                pass

        # Try first heading in content
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                heading_text = stripped.lstrip("#").strip()
                match = _EVENT_OPCODE_HEADING_RE.match(heading_text)
                if match:
                    try:
                        return int(match.group(1), 16)
                    except ValueError:
                        pass
                break

        return None

    def _extract_event_name(self, content: str, filename: str) -> str:
        """Extract the event name from the first heading.

        Handles formats like:
        - "# 0x004B - EVT_SET_ENTITY_SPEED"
        - "# 004B EVT_SET_ENTITY_SPEED"
        - "# EVT_SET_ENTITY_SPEED"

        Args:
            content: Full file content.
            filename: Filename for fallback.

        Returns:
            The extracted event name.
        """
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.startswith("##"):
                heading_text = stripped.lstrip("#").strip()

                # Try to separate opcode prefix from name
                # Pattern: "0x004B - NAME" or "004B - NAME"
                name_match = re.match(
                    r"(?:0x)?[0-9A-Fa-f]{2,4}\s*[-–—:]\s*(.+)",
                    heading_text,
                )
                if name_match:
                    return name_match.group(1).strip()

                # Pattern: "0x004B NAME" (space separated)
                name_match = re.match(
                    r"(?:0x)?[0-9A-Fa-f]{2,4}\s+(.+)", heading_text
                )
                if name_match:
                    return name_match.group(1).strip()

                # If heading doesn't start with opcode-like text, use as-is
                if not re.match(
                    r"^(?:0x)?[0-9A-Fa-f]{2,4}$", heading_text
                ):
                    return heading_text

                # Heading is just an opcode number — use filename stem
                return os.path.splitext(filename)[0]

        # Fallback to filename stem
        return os.path.splitext(filename)[0]

    def _extract_event_description(self, content: str) -> str:
        """Extract description from the first paragraph after heading.

        Collects text lines after the first heading, stopping at:
        - Another heading
        - A code fence
        - A line starting with "Size:" (metadata, not description)
        - An empty line after collecting some text

        Args:
            content: Full file content.

        Returns:
            Description string (may be empty).
        """
        lines = content.splitlines()
        found_heading = False
        desc_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            if not found_heading:
                if stripped.startswith("#"):
                    found_heading = True
                continue

            # Skip empty lines immediately after heading
            if not desc_lines and not stripped:
                continue

            # Stop conditions
            if stripped.startswith("#"):
                break
            if stripped.startswith("```"):
                break
            if stripped.startswith("|"):
                break
            if re.match(r"^[Ss]ize\s*[:=]", stripped):
                break

            # Empty line after we have text means end of paragraph
            if not stripped and desc_lines:
                break

            desc_lines.append(stripped)

        return " ".join(desc_lines) if desc_lines else ""

    def _extract_event_size(self, content: str) -> int:
        """Extract size in bytes from the content.

        Looks for patterns like "Size: 4", "Size: 4 bytes".

        Args:
            content: Full file content.

        Returns:
            Size as integer, or 0 if not found.
        """
        # Try "Size: N" or "Size: N bytes" patterns
        match = re.search(
            r"\b[Ss]ize\s*[:=]\s*(\d+)\s*(?:bytes?)?\b", content
        )
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

        # Try table row: "| Size | N |"
        match = re.search(
            r"\|\s*[Ss]ize\s*\|\s*(\d+)\s*\|", content
        )
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

        return 0

    def _extract_event_pseudo_code(self, content: str) -> str:
        """Extract pseudo-code from fenced code blocks.

        Concatenates all code block contents, separated by double newlines
        if multiple blocks exist.

        Args:
            content: Full file content.

        Returns:
            Pseudo-code string (may be empty).
        """
        code_blocks: list[str] = []
        current_block: list[str] = []
        in_block = False

        for line in content.splitlines():
            if line.strip().startswith("```"):
                if in_block:
                    # End of code block
                    code_blocks.append("\n".join(current_block))
                    current_block = []
                    in_block = False
                else:
                    # Start of code block
                    in_block = True
            elif in_block:
                current_block.append(line)

        if code_blocks:
            return "\n\n".join(code_blocks).strip()

        return ""
