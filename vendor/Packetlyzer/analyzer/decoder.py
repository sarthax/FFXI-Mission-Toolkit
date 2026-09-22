"""Packet Decoder Module for the Packetlyzer Analyzer.

Decodes raw packet bytes against VieweD-compatible XML definitions,
applying little-endian byte order for all multi-byte types. Supports
lookup resolution, bit-field extraction, and all VieweD field types.
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, Union

from analyzer.lookup import LookupManager
from analyzer.packet_db import PacketDB, FieldDefinition


@dataclass
class DecodedField:
    """A single decoded field from a packet."""

    name: str
    type: str
    raw_value: Union[int, float, str, bytes]
    display_value: str  # Includes lookup resolution
    out_of_range: bool
    _field_def: Optional["FieldDefinition"] = None  # Reference to the original definition
    comment: str = ""


@dataclass
class DecodedPacket:
    """The result of decoding a packet's raw bytes."""

    fields: list[DecodedField] = field(default_factory=list)
    raw_hex: str = ""
    description: str = ""
    has_definition: bool = True


# Map of field type -> byte size for fixed-size numeric types
_FIXED_TYPE_SIZES: dict[str, int] = {
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
    "pos": 12,  # 3 x float32
}


class PacketDecoder:
    """Decodes raw packet bytes using definitions from PacketDB.

    Looks up opcode definitions and applies field definitions to raw bytes
    using little-endian byte order. Supports lookup resolution via
    LookupManager.
    """

    def __init__(self, db_path: str, ext_path: str, lookup_dir: str, packet_db: Optional[PacketDB] = None):
        """Load XML DB, extension JSON, and all lookup tables.

        Args:
            db_path: Path to packetlyzer_db.xml.
            ext_path: Path to packetlyzer_ext.json (may be None).
            lookup_dir: Path to the lookup/ directory.
            packet_db: Optional pre-loaded PacketDB instance (avoids double-loading).
        """
        self._db_path = db_path
        self._ext_path = ext_path
        self._lookup_dir = lookup_dir
        self._db = packet_db if packet_db is not None else PacketDB(db_path, ext_path)
        self._lookups = LookupManager(lookup_dir)

    def decode(self, direction: str, opcode: int, raw_bytes: bytes) -> DecodedPacket:
        """Decode raw bytes using the definition for direction+opcode.

        Args:
            direction: "s2c" or "c2s".
            opcode: The packet opcode as an integer.
            raw_bytes: The raw packet bytes.

        Returns:
            A DecodedPacket containing decoded fields in definition order.
        """
        raw_hex = raw_bytes.hex()
        definition = self._db.get_definition(direction, opcode)

        if definition is None:
            return DecodedPacket(
                fields=[],
                raw_hex=raw_hex,
                description=f"No definition found for opcode 0x{opcode:04X}",
                has_definition=False,
            )

        decoded_fields: list[DecodedField] = []
        for field_def in definition.fields:
            decoded_field = self._decode_field(field_def, raw_bytes)
            decoded_fields.append(decoded_field)

        return DecodedPacket(
            fields=decoded_fields,
            raw_hex=raw_hex,
            description=definition.description,
            has_definition=True,
        )

    def reload(self) -> None:
        """Re-read all definition files from disk (called after Live_Editor save)."""
        self._db = PacketDB(self._db_path, self._ext_path)
        self._lookups = LookupManager(self._lookup_dir)

    def _decode_field(self, field_def: FieldDefinition, raw_bytes: bytes) -> DecodedField:
        """Decode a single field from raw bytes.

        Args:
            field_def: The field definition specifying type, offset, etc.
            raw_bytes: The complete packet bytes.

        Returns:
            A DecodedField with the decoded value or out-of-range marker.
        """
        field_type = field_def.type
        pos = field_def.pos

        # Determine byte size needed for this field
        byte_size = self._get_field_byte_size(field_def)

        # Special case: bits type uses byte offset from pos, needs enough bytes
        # for the bit range
        if field_type == "bits":
            byte_size = self._get_bits_byte_size(field_def)

        # Check if field is out of range
        if pos + byte_size > len(raw_bytes):
            return DecodedField(
                name=field_def.name,
                type=field_type,
                raw_value=b"",
                display_value="out of range",
                out_of_range=True,
                _field_def=field_def,
                comment=field_def.comment or "",
            )

        # Extract and decode the field value
        raw_value, display_value = self._extract_value(field_def, raw_bytes)

        # Apply lookup resolution if applicable
        if field_def.lookup and isinstance(raw_value, int):
            display_value = self._lookups.resolve(field_def.lookup, raw_value)

        return DecodedField(
            name=field_def.name,
            type=field_type,
            raw_value=raw_value,
            display_value=display_value,
            out_of_range=False,
            _field_def=field_def,
            comment=field_def.comment or "",
        )

    def _get_field_byte_size(self, field_def: FieldDefinition) -> int:
        """Determine the byte size needed for a field type."""
        field_type = field_def.type

        if field_type in _FIXED_TYPE_SIZES:
            return _FIXED_TYPE_SIZES[field_type]
        elif field_type == "bits":
            return self._get_bits_byte_size(field_def)
        elif field_type in ("t", "a"):
            return field_def.size if field_def.size is not None else 0
        else:
            return 0

    def _get_bits_byte_size(self, field_def: FieldDefinition) -> int:
        """Calculate how many bytes are needed to extract the bit field.

        For a bits field starting at byte offset `pos` with `bits` width,
        we need enough bytes from `pos` to cover all the bits.
        """
        bits_width = field_def.bits if field_def.bits is not None else 0
        if bits_width <= 0:
            return 0
        # Number of bytes needed to hold `bits_width` bits
        return (bits_width + 7) // 8

    def _extract_value(
        self, field_def: FieldDefinition, raw_bytes: bytes
    ) -> tuple[Union[int, float, str, bytes], str]:
        """Extract and format a field value from raw bytes.

        Returns:
            A tuple of (raw_value, display_value).
        """
        field_type = field_def.type
        pos = field_def.pos

        if field_type == "byte":
            value = raw_bytes[pos]
            return value, str(value)

        elif field_type == "uint16":
            value = struct.unpack_from("<H", raw_bytes, pos)[0]
            return value, str(value)

        elif field_type == "uint32":
            value = struct.unpack_from("<I", raw_bytes, pos)[0]
            return value, str(value)

        elif field_type == "int8":
            value = struct.unpack_from("<b", raw_bytes, pos)[0]
            return value, str(value)

        elif field_type == "int16":
            value = struct.unpack_from("<h", raw_bytes, pos)[0]
            return value, str(value)

        elif field_type == "int32":
            value = struct.unpack_from("<i", raw_bytes, pos)[0]
            return value, str(value)

        elif field_type == "float":
            value = struct.unpack_from("<f", raw_bytes, pos)[0]
            return value, f"{value}"

        elif field_type == "bits":
            bit_offset = field_def.bit_offset or 0
            value = self._extract_bits(raw_bytes, pos, bit_offset, field_def.bits or 0)
            return value, str(value)

        elif field_type == "t":
            return self._extract_string(raw_bytes, pos, field_def.size or 0)

        elif field_type == "a":
            size = field_def.size or 0
            raw = raw_bytes[pos : pos + size]
            display = " ".join(f"{b:02X}" for b in raw)
            return raw, display

        elif field_type == "pos":
            x = struct.unpack_from("<f", raw_bytes, pos)[0]
            y = struct.unpack_from("<f", raw_bytes, pos + 4)[0]
            z = struct.unpack_from("<f", raw_bytes, pos + 8)[0]
            display = f"{x}, {y}, {z}"
            # Store all three as a tuple-like string for raw_value
            return display, display

        elif field_type == "dir":
            value = raw_bytes[pos]
            return value, str(value)

        elif field_type == "ms":
            value = struct.unpack_from("<I", raw_bytes, pos)[0]
            return value, f"{value}ms"

        elif field_type == "ip":
            b0 = raw_bytes[pos]
            b1 = raw_bytes[pos + 1]
            b2 = raw_bytes[pos + 2]
            b3 = raw_bytes[pos + 3]
            display = f"{b0}.{b1}.{b2}.{b3}"
            return display, display

        else:
            # Unknown field type - return raw bytes
            return b"", ""

    def _extract_bits(self, raw_bytes: bytes, byte_offset: int, bit_offset: int, bit_width: int) -> int:
        """Extract N bits in little-endian bit order from a given bit position.

        Little-endian bit order means bit 0 is the LSB of byte at byte_offset,
        bit 8 is the LSB of byte at byte_offset+1, etc. We extract `bit_width`
        consecutive bits starting from `bit_offset` of the byte at `byte_offset`.

        Args:
            raw_bytes: The complete packet bytes.
            byte_offset: The byte offset where the bits field starts.
            bit_offset: Starting bit position within the byte (0 = LSB).
            bit_width: Number of bits to extract (1-32).

        Returns:
            The extracted unsigned integer value.
        """
        if bit_width <= 0:
            return 0

        # Read enough bytes to cover the bit range starting from bit_offset
        total_bits_needed = bit_offset + bit_width
        num_bytes = (total_bits_needed + 7) // 8
        if byte_offset + num_bytes > len(raw_bytes):
            num_bytes = len(raw_bytes) - byte_offset
        if num_bytes <= 0:
            return 0

        chunk = raw_bytes[byte_offset : byte_offset + num_bytes]

        # Build an integer from the bytes in little-endian order
        value = int.from_bytes(chunk, byteorder="little")

        # Shift right by bit_offset to align the desired bits to position 0
        value >>= bit_offset

        # Mask to the requested bit width
        mask = (1 << bit_width) - 1
        return value & mask

    def _extract_string(
        self, raw_bytes: bytes, pos: int, max_size: int
    ) -> tuple[str, str]:
        """Extract a null-terminated string field.

        FFXI strings are null-terminated but may extend to the end of the
        packet if the packet is truncated. In that case, we decode all
        available bytes as the string (truncation is an implicit terminator).

        Args:
            raw_bytes: The complete packet bytes.
            pos: Byte offset of the string.
            max_size: Maximum length of the string field.

        Returns:
            Tuple of (raw string value, display string).
        """
        # Clamp to available data
        available_end = min(pos + max_size, len(raw_bytes))
        field_bytes = raw_bytes[pos:available_end]

        if not field_bytes:
            return "", ""

        # Find null terminator
        null_idx = field_bytes.find(b"\x00")
        if null_idx >= 0:
            # Found null terminator - decode up to it
            text = field_bytes[:null_idx].decode("utf-8", errors="replace")
        else:
            # No null terminator found - decode all available bytes
            # Strip any trailing non-printable bytes that look like padding
            text = field_bytes.decode("utf-8", errors="replace").rstrip("\x00")

        return text, text
