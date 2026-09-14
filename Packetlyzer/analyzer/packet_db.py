"""Database Access Layer for the Packetlyzer Analyzer.

Parses a VieweD-compatible XML packet definition database and an optional
extension JSON file. Provides lookup, update, and persistence for packet
definitions keyed by (direction, opcode).
"""

import json
import logging
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FieldDefinition:
    """A single field within a packet definition."""

    name: str
    type: str  # byte, uint16, uint32, int8, int16, int32, float, bits, t, a, pos, dir, ms, ip
    pos: int  # Byte offset
    bits: Optional[int] = None  # Bit width (for 'bits' type)
    bit_offset: Optional[int] = None  # Bit offset within byte position (for 'bits' type)
    lookup: Optional[str] = None  # Lookup table name
    size: Optional[int] = None  # For 't' and 'a' types
    comment: Optional[str] = None  # Field comment from XML
    group: Optional[str] = None  # Parent group label (e.g. "Nation 1", "Zone 3")
    group_lookup: Optional[str] = None  # Lookup table for group label (e.g. "campaignzones")
    group_index: Optional[int] = None  # 1-based index within the group's lookup


@dataclass
class PacketDefinition:
    """A complete packet definition with opcode, direction, and fields."""

    opcode: int
    direction: str  # "s2c" | "c2s"
    description: str
    fields: list[FieldDefinition] = field(default_factory=list)


class PacketDB:
    """Manages the packet definition database (VieweD XML + extension JSON).

    Loads definitions from a VieweD-compatible XML file and an optional
    extension JSON sidecar. Provides lookup by (direction, opcode) and
    supports live editing with persistence back to XML.
    """

    def __init__(self, xml_path: str, ext_path: Optional[str] = None):
        """Parse VieweD XML and optional extension JSON.

        Args:
            xml_path: Path to the packetlyzer_db.xml file. If missing or
                      unparseable, the process will exit with an error.
            ext_path: Path to the packetlyzer_ext.json file. If None or
                      missing, a warning is logged and operation continues.
        """
        self._xml_path = xml_path
        self._ext_path = ext_path
        self._definitions: dict[tuple[str, int], PacketDefinition] = {}
        self._extensions: dict = {}

        self._load_xml(xml_path)
        self._load_extensions(ext_path)

    def _load_xml(self, xml_path: str) -> None:
        """Parse the VieweD XML file into in-memory definitions.

        Supports both formats:
        - Simplified: <rule> → <s2c>/<c2s> → <packet> → <data>
        - VieweD full: <root> → <rule> → <s2c>/<c2s> → <packet> → <data>

        Exits the process if the file is missing or cannot be parsed.
        """
        try:
            tree = ET.parse(xml_path)
        except FileNotFoundError:
            print(
                f"Error: Packet database XML not found: {xml_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        except ET.ParseError as e:
            print(
                f"Error: Failed to parse packet database XML '{xml_path}': {e}",
                file=sys.stderr,
            )
            sys.exit(1)

        root = tree.getroot()

        # Handle VieweD full format: <root> → <rule> → <s2c>/<c2s>
        rule_elem = root
        if root.tag == "root":
            rule_elem = root.find("rule")
            if rule_elem is None:
                # Try finding it nested in any child
                for child in root:
                    if child.tag == "rule":
                        rule_elem = child
                        break
                if rule_elem is None:
                    rule_elem = root  # fallback

        for direction in ("s2c", "c2s"):
            section = rule_elem.find(direction)
            if section is None:
                continue
            for packet_elem in section.findall("packet"):
                self._parse_packet_element(packet_elem, direction)

    def _parse_packet_element(self, packet_elem: ET.Element, direction: str) -> None:
        """Parse a single <packet> element into a PacketDefinition.

        Handles both explicit pos= attributes and sequential (no pos) formats.
        Uses bit-level cursor tracking for sequential bit fields.
        Recursively extracts <data> fields from nested structures.
        """
        type_attr = packet_elem.get("type", "")
        desc = packet_elem.get("desc", "")

        try:
            opcode = int(type_attr, 16)
        except (ValueError, TypeError):
            logger.warning("Skipping packet with invalid type attribute: '%s'", type_attr)
            return

        fields = []
        self._collect_fields_recursive(packet_elem, fields, 4, 0)

        definition = PacketDefinition(
            opcode=opcode,
            direction=direction,
            description=desc,
            fields=fields,
        )
        self._definitions[(direction, opcode)] = definition

    def _collect_fields_recursive(self, parent_elem: ET.Element, fields: list, auto_pos: int, bit_cursor: int = 0) -> tuple[int, int]:
        """Recursively collect <data> elements from an element and its children.

        Uses a bit-level cursor to track position within the byte stream.
        Bit fields pack sequentially without advancing to next byte boundary.
        Byte-aligned fields (byte, uint16, etc.) advance to next byte boundary first.

        Args:
            parent_elem: The parent XML element to search.
            fields: List to append FieldDefinition objects to.
            auto_pos: Current byte position (for byte-aligned fields).
            bit_cursor: Current bit offset from auto_pos (0-7 within current byte).
                        When > 0, we're in the middle of a bit-packed sequence.

        Returns:
            Tuple of (updated auto_pos, updated bit_cursor).
        """
        _CONTAINER_TAGS = {"ifeq", "ifneq", "ifgt", "iflt", "ifge", "ifle",
                           "echo", "else", "switch", "case", "default"}

        for child in parent_elem:
            if child.tag == "data":
                auto_pos, bit_cursor = self._process_data_element(
                    child, fields, auto_pos, bit_cursor
                )
            elif child.tag == "cursor":
                pos_str = child.get("pos", "")
                try:
                    if pos_str.startswith("0x") or pos_str.startswith("0X"):
                        auto_pos = int(pos_str, 16)
                    else:
                        auto_pos = int(pos_str)
                    bit_cursor = 0  # Reset bit cursor on explicit position
                except (ValueError, TypeError):
                    pass
            elif child.tag == "loop":
                auto_pos, bit_cursor = self._unroll_loop(child, fields, auto_pos, bit_cursor)
            elif child.tag in _CONTAINER_TAGS:
                auto_pos, bit_cursor = self._collect_fields_recursive(
                    child, fields, auto_pos, bit_cursor
                )

        return auto_pos, bit_cursor

    def _process_data_element(self, data_elem: ET.Element, fields: list,
                              auto_pos: int, bit_cursor: int) -> tuple[int, int]:
        """Process a single <data> element with bit-level cursor tracking.

        For bit fields (bits/bitval): uses current bit_cursor position, advances
        by the field's bit width.
        For byte-aligned fields: aligns to next byte boundary first, then advances
        by the field's byte size.
        """
        field_type = data_elem.get("type", "")
        is_bit_field = field_type in ("bits", "bitval")

        # Check if this element has an explicit pos attribute
        pos_str = data_elem.get("pos")
        has_explicit_pos = pos_str is not None

        if has_explicit_pos:
            # Explicit pos overrides auto_pos
            try:
                if pos_str.startswith("0x") or pos_str.startswith("0X"):
                    explicit_pos = int(pos_str, 16)
                elif pos_str.startswith("0") and len(pos_str) > 1 and pos_str.isalnum():
                    explicit_pos = int(pos_str, 16)
                else:
                    explicit_pos = int(pos_str)
            except (ValueError, TypeError):
                explicit_pos = auto_pos

            # Check for explicit bit offset
            bit_attr = data_elem.get("bit")
            if bit_attr is not None:
                try:
                    explicit_bit = int(bit_attr)
                except (ValueError, TypeError):
                    explicit_bit = 0
            else:
                explicit_bit = 0

            field_def = self._parse_data_element_with_pos(
                data_elem, explicit_pos, explicit_bit
            )
            if field_def is not None:
                fields.append(field_def)
                # Update cursors based on explicit position
                if is_bit_field and field_def.bits:
                    # Don't advance auto_pos for explicitly-positioned bit fields
                    pass
                else:
                    auto_pos = explicit_pos + self._field_byte_size(field_def)
                    bit_cursor = 0
        else:
            # Auto-positioned field
            if is_bit_field:
                # Bit field: pack at current bit cursor position
                bits_width = 0
                bits_str = data_elem.get("bits")
                if bits_str:
                    try:
                        bits_width = int(bits_str)
                    except (ValueError, TypeError):
                        bits_width = 1

                # Calculate byte pos and bit offset from absolute bit position
                abs_bit_pos = (auto_pos * 8) + bit_cursor
                byte_pos = abs_bit_pos // 8
                bit_offset = abs_bit_pos % 8

                field_def = self._parse_data_element_with_pos(
                    data_elem, byte_pos, bit_offset
                )
                if field_def is not None:
                    fields.append(field_def)

                # Advance bit cursor
                bit_cursor += bits_width
                # Carry over to bytes
                auto_pos += bit_cursor // 8
                bit_cursor = bit_cursor % 8
            else:
                # Byte-aligned field: align to byte boundary first
                if bit_cursor > 0:
                    auto_pos += 1
                    bit_cursor = 0

                field_def = self._parse_data_element_with_pos(
                    data_elem, auto_pos, 0
                )
                if field_def is not None:
                    fields.append(field_def)
                    auto_pos += self._field_byte_size(field_def)

        return auto_pos, bit_cursor

    def _parse_data_element_with_pos(self, data_elem: ET.Element,
                                     pos: int, bit_offset: int) -> Optional[FieldDefinition]:
        """Parse a <data> element using the given position and bit offset."""
        name = data_elem.get("name", "")
        field_type = data_elem.get("type", "")

        # Normalize type
        if field_type == "bitval":
            field_type = "bits"

        # Bits width
        bits_str = data_elem.get("bits")
        bits = None
        if bits_str is not None:
            try:
                bits = int(bits_str)
            except (ValueError, TypeError):
                pass

        # Lookup
        lookup = data_elem.get("lookup")
        if lookup and lookup.startswith("@"):
            lookup = None

        # Size
        size_str = data_elem.get("size") or data_elem.get("arg")
        size = None
        if size_str is not None:
            try:
                size = int(size_str)
            except (ValueError, TypeError):
                pass

        # Comment
        comment = data_elem.get("comment")

        # Bit offset: use explicit "bit" attr if present, otherwise use calculated
        bit_attr = data_elem.get("bit")
        if bit_attr is not None:
            try:
                bit_offset = int(bit_attr)
            except (ValueError, TypeError):
                pass

        return FieldDefinition(
            name=name,
            type=field_type,
            pos=pos,
            bits=bits,
            bit_offset=bit_offset if (field_type == "bits" and (bits or bit_offset)) else None,
            lookup=lookup,
            size=size,
            comment=comment,
        )

    def _unroll_loop(self, loop_elem: ET.Element, fields: list,
                     auto_pos: int, bit_cursor: int) -> tuple[int, int]:
        """Attempt to unroll a <loop> block with deterministic iteration count.

        Detects the pattern:
            <add dst="Var" arg1="#Var" arg2="1"/>
            <ifgt arg1="#Var" arg2="N"> <break/> </ifgt>
            <echo ...> <data .../> ... </echo>

        Unrolls into N iterations with advancing positions and group labels.
        Falls back to single-pass extraction if pattern isn't recognized.
        """
        loop_count = self._detect_loop_count(loop_elem)
        echo_elem = loop_elem.find("echo")

        if loop_count is not None and echo_elem is not None:
            group_name = echo_elem.get("name", "Item")
            group_lookup = echo_elem.get("lookup")  # e.g. "campaignzones"

            # Collect template fields from echo (single pass to measure size)
            template_fields: list[FieldDefinition] = []
            template_start_pos = auto_pos
            template_start_bit = bit_cursor
            end_pos, end_bit = self._collect_fields_recursive(
                echo_elem, template_fields, template_start_pos, template_start_bit
            )

            # Calculate iteration size in bits
            iter_bits = (end_pos - template_start_pos) * 8 + (end_bit - template_start_bit)
            if iter_bits <= 0 and template_fields:
                # Fallback: calculate from field extents
                max_end = 0
                for f in template_fields:
                    f_bits = self._field_bit_size(f)
                    f_start = (f.pos - template_start_pos) * 8 + (f.bit_offset or 0) - template_start_bit
                    f_end = f_start + f_bits
                    if f_end > max_end:
                        max_end = f_end
                iter_bits = max_end

            if iter_bits <= 0:
                iter_bits = 32  # Fallback

            # Unroll N iterations
            abs_start_bit = auto_pos * 8 + bit_cursor
            for i in range(loop_count):
                iter_start_bit = abs_start_bit + (i * iter_bits)

                for tf in template_fields:
                    # Calculate this field's absolute bit position within the iteration
                    tf_offset_bits = (tf.pos - template_start_pos) * 8 + (tf.bit_offset or 0) - template_start_bit
                    field_abs_bit = iter_start_bit + tf_offset_bits

                    field_byte_pos = field_abs_bit // 8
                    field_bit_offset = field_abs_bit % 8

                    unrolled = FieldDefinition(
                        name=tf.name,
                        type=tf.type,
                        pos=field_byte_pos,
                        bits=tf.bits,
                        bit_offset=field_bit_offset if tf.type == "bits" else tf.bit_offset,
                        lookup=tf.lookup,
                        size=tf.size,
                        comment=tf.comment,
                        group=f"{group_name} {i + 1}",
                        group_lookup=group_lookup,
                        group_index=i + 1,
                    )
                    fields.append(unrolled)

            # Advance past all iterations
            total_bits = loop_count * iter_bits
            abs_end_bit = abs_start_bit + total_bits
            auto_pos = abs_end_bit // 8
            bit_cursor = abs_end_bit % 8
        else:
            # Can't determine loop count — single-pass
            auto_pos, bit_cursor = self._collect_fields_recursive(
                loop_elem, fields, auto_pos, bit_cursor
            )

        return auto_pos, bit_cursor

    def _field_bit_size(self, field_def: FieldDefinition) -> int:
        """Get the size of a field in bits."""
        if field_def.type == "bits" and field_def.bits:
            return field_def.bits
        return self._field_byte_size(field_def) * 8

    def _detect_loop_count(self, loop_elem: ET.Element) -> Optional[int]:
        """Detect loop iteration count from <ifgt arg1="#Var" arg2="N"><break/></ifgt>."""
        for child in loop_elem:
            if child.tag == "ifgt":
                arg2 = child.get("arg2", "")
                if child.find("break") is not None:
                    try:
                        return int(arg2)
                    except (ValueError, TypeError):
                        pass
        return None

    @staticmethod
    def _field_byte_size(field_def: FieldDefinition) -> int:
        """Estimate byte size of a field for auto-position calculation."""
        _SIZES = {
            "byte": 1, "uint16": 2, "uint32": 4, "int8": 1, "int16": 2,
            "int32": 4, "float": 4, "dir": 1, "ms": 4, "ip": 4, "pos": 12,
        }
        if field_def.type in _SIZES:
            return _SIZES[field_def.type]
        if field_def.type == "bits":
            # bits field: use bits attribute to compute byte coverage
            if field_def.bits:
                return (field_def.bits + 7) // 8
            return 1
        if field_def.type in ("t", "a") and field_def.size:
            return field_def.size
        # Unknown size — guess 4
        return 4

    def _load_extensions(self, ext_path: Optional[str]) -> None:
        """Load the optional extension JSON file.

        Logs a warning if the file is missing and continues.
        """
        if ext_path is None:
            return

        try:
            with open(ext_path, "r", encoding="utf-8") as f:
                self._extensions = json.load(f)
        except FileNotFoundError:
            logger.warning(
                "Extension JSON file not found: '%s'. Continuing without extensions.",
                ext_path,
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to load extension JSON '%s': %s. Continuing without extensions.",
                ext_path,
                e,
            )

    def get_definition(self, direction: str, opcode: int) -> Optional[PacketDefinition]:
        """Look up a packet definition by direction and opcode.

        Args:
            direction: "s2c" or "c2s"
            opcode: The packet opcode as an integer.

        Returns:
            The PacketDefinition if found, otherwise None.
        """
        return self._definitions.get((direction, opcode))

    def set_definition(self, direction: str, opcode: int, definition: PacketDefinition) -> None:
        """Create or update a packet definition.

        Called by the Live_Editor when saving changes.

        Args:
            direction: "s2c" or "c2s"
            opcode: The packet opcode as an integer.
            definition: The new or updated PacketDefinition.
        """
        self._definitions[(direction, opcode)] = definition

    def save_xml(self) -> None:
        """Write current state to the XML file in VieweD-compatible format.

        Produces a well-formed XML document preserving the VieweD structure:
        <rule> → <s2c>/<c2s> → <packet> → <data> elements.
        """
        root = ET.Element("rule")

        for direction in ("s2c", "c2s"):
            section = ET.SubElement(root, direction)

            # Gather definitions for this direction, sorted by opcode
            defs_for_dir = sorted(
                [d for d in self._definitions.values() if d.direction == direction],
                key=lambda d: d.opcode,
            )

            for defn in defs_for_dir:
                packet_elem = ET.SubElement(section, "packet")
                # Format opcode as VieweD-style hex (e.g. "0x028" for 3-digit, "0x0028" for 4-digit)
                opcode_hex = f"0x{defn.opcode:03X}"
                packet_elem.set("type", opcode_hex)
                packet_elem.set("desc", defn.description)

                for field_def in defn.fields:
                    data_elem = ET.SubElement(packet_elem, "data")
                    data_elem.set("type", field_def.type)
                    data_elem.set("name", field_def.name)
                    data_elem.set("pos", str(field_def.pos))

                    if field_def.bits is not None:
                        data_elem.set("bits", str(field_def.bits))
                    if field_def.bit_offset is not None and field_def.bit_offset > 0:
                        data_elem.set("bit", str(field_def.bit_offset))
                    if field_def.lookup is not None:
                        data_elem.set("lookup", field_def.lookup)
                    if field_def.size is not None:
                        data_elem.set("size", str(field_def.size))

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(self._xml_path, encoding="utf-8", xml_declaration=True)
