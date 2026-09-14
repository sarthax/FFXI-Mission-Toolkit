"""FFXI Message Resolver — resolves packet message IDs to dialog text.

Tracks the current zone (via 0x000A Client Connect packets) and resolves
message IDs in various packet types to human-readable dialog text by
reading the zone's dialog table DAT.

Supported opcodes:
  - 0x0027: String Message (with string parameters)
  - 0x0036: NPC Chat
  - 0x0029: Action Message (battle messages)
  - 0x002D: Combat Message

The message ID in packets references the current zone's dialog table.
Formula: dialog_index = message_id & 0x7FFF
"""

from __future__ import annotations

import logging
from typing import Optional

from analyzer.dialog_table import DialogTableCache
from analyzer.ffxi_dat import FFXIDatResolver

logger = logging.getLogger(__name__)


class MessageResolver:
    """Resolves FFXI packet message IDs to human-readable dialog text.

    Tracks the player's current zone by observing 0x000A packets,
    then uses the zone's dialog table to resolve message IDs found
    in 0x0027, 0x0036, and other dialog-referencing packets.
    """

    def __init__(self, dat_resolver: FFXIDatResolver):
        """Initialize the message resolver.

        Args:
            dat_resolver: An FFXIDatResolver for finding dialog DATs.
        """
        self._dat_resolver = dat_resolver
        self._cache = DialogTableCache(dat_resolver)
        self._current_zone_id: int = -1
        self._zone_name: str = "Unknown"

    @property
    def current_zone_id(self) -> int:
        """The currently tracked zone ID."""
        return self._current_zone_id

    @property
    def current_zone_name(self) -> str:
        """The currently tracked zone name."""
        return self._zone_name

    @property
    def is_available(self) -> bool:
        """Whether the resolver is ready (DAT resolver is available)."""
        return self._dat_resolver.is_available

    def set_zone(self, zone_id: int) -> None:
        """Manually set the current zone (e.g., from config or UI).

        Args:
            zone_id: The zone ID to set.
        """
        if zone_id > 0 and zone_id != self._current_zone_id:
            self._current_zone_id = zone_id
            logger.info("Zone manually set to %d", zone_id)
            self._cache.preload(zone_id)

    def process_packet(self, packet: dict) -> None:
        """Process a packet for zone tracking.

        Call this on every incoming packet to keep zone tracking up to date.
        Watches for:
          - 0x000A (Client Connect) to detect zone changes via raw packet
          - "zone change" events from the addon

        Args:
            packet: The packet dict from the capture stream.
        """
        pkt_type = packet.get("type", "")

        if pkt_type == "event":
            # Handle addon events (zone change, etc.)
            event_name = packet.get("event_name", "")
            if event_name == "zone change":
                params = packet.get("params", {})
                new_zone = params.get("new_zone_id")
                if new_zone is not None and isinstance(new_zone, (int, float)):
                    new_zone = int(new_zone)
                    if new_zone > 0 and new_zone != self._current_zone_id:
                        logger.info("Zone change (event): %d → %d", self._current_zone_id, new_zone)
                        self._current_zone_id = new_zone
                        self._cache.preload(new_zone)
            return

        if pkt_type != "packet":
            return

        opcode = packet.get("opcode", "")
        direction = packet.get("direction", "")

        # Track zone from 0x000A (Client Connect, S2C)
        if direction == "s2c" and opcode == "000a":
            self._handle_zone_change(packet)

    def resolve(self, packet: dict) -> Optional[str]:
        """Attempt to resolve dialog text for a packet.

        Checks the packet opcode and extracts the message ID + parameters,
        then looks up the dialog table entry and performs parameter substitution.

        Args:
            packet: The packet dict.

        Returns:
            Resolved dialog text string, or None if resolution isn't possible.
        """
        if self._current_zone_id < 0:
            return None

        if not self._dat_resolver.is_available:
            return None

        opcode = packet.get("opcode", "")
        direction = packet.get("direction", "")

        if direction != "s2c":
            return None

        if opcode == "0027":
            return self._resolve_0027(packet)
        elif opcode == "0036":
            return self._resolve_0036(packet)
        elif opcode == "0029":
            return self._resolve_0029(packet)
        elif opcode == "002d":
            return self._resolve_002d(packet)

        return None

    # ---------------------------------------------------------------------------
    # Zone tracking
    # ---------------------------------------------------------------------------

    def _handle_zone_change(self, packet: dict) -> None:
        """Extract zone ID from a 0x000A Client Connect packet.

        Zone ID is at offset 0x30 (uint16 LE) based on the ffxi.xml definition.
        """
        data_hex = packet.get("data", "")
        if len(data_hex) < 0x32 * 2:  # Need at least up to offset 0x31
            return

        try:
            raw_bytes = bytes.fromhex(data_hex)
            # Zone field is at offset 0x30 (uint16 LE) per ffxi.xml
            zone_id = int.from_bytes(raw_bytes[0x30:0x32], "little")

            if zone_id != self._current_zone_id and zone_id > 0:
                old_zone = self._current_zone_id
                self._current_zone_id = zone_id
                logger.info(
                    "Zone change detected: %d → %d", old_zone, zone_id
                )
                # Preload the new zone's dialog table
                self._cache.preload(zone_id)
        except (ValueError, IndexError) as e:
            logger.debug("Failed to parse zone from 0x000A: %s", e)

    # ---------------------------------------------------------------------------
    # Opcode-specific resolvers
    # ---------------------------------------------------------------------------

    def _resolve_0027(self, packet: dict) -> Optional[str]:
        """Resolve a 0x0027 String Message packet.

        Fields (from ffxi.xml):
          offset 0x0A: Message ID (uint16) — & 0x7FFF gives dialog index
          offset 0x10: Parameter 1 (uint32) → dialog's Parameter 0
          offset 0x14: Parameter 2 (uint32) → dialog's Parameter 1
          offset 0x18: Parameter 3 (uint32) → dialog's Parameter 2
          offset 0x1C: Parameter 4 (uint32) → dialog's Parameter 3
        """
        data_hex = packet.get("data", "")
        if len(data_hex) < 0x20 * 2:
            return None

        try:
            raw = bytes.fromhex(data_hex)
            message_id = int.from_bytes(raw[0x0A:0x0C], "little")
            dialog_index = message_id & 0x7FFF

            # Parameters: packet's Param1-4 map to dialog's Param0-3
            param0 = int.from_bytes(raw[0x10:0x14], "little")
            param1 = int.from_bytes(raw[0x14:0x18], "little")
            param2 = int.from_bytes(raw[0x18:0x1C], "little")
            param3 = int.from_bytes(raw[0x1C:0x20], "little")
            params = [param0, param1, param2, param3]

            return self._lookup_dialog(dialog_index, params)
        except (ValueError, IndexError):
            return None

    def _resolve_0036(self, packet: dict) -> Optional[str]:
        """Resolve a 0x0036 NPC Chat packet.

        Fields (from ffxi.xml):
          offset 0x0A: Message ID (uint16) — & 0x7FFF gives dialog index
        """
        data_hex = packet.get("data", "")
        if len(data_hex) < 0x0C * 2:
            return None

        try:
            raw = bytes.fromhex(data_hex)
            message_id = int.from_bytes(raw[0x0A:0x0C], "little")
            dialog_index = message_id & 0x7FFF

            return self._lookup_dialog(dialog_index, params=None)
        except (ValueError, IndexError):
            return None

    def _resolve_0029(self, packet: dict) -> Optional[str]:
        """Resolve a 0x0029 Action Message packet.

        Fields (from ffxi.xml):
          offset 0x18: Message (uint16)

        Note: Action messages use a different table system (combat messages)
        and may not always be in the zone dialog table. We attempt resolution
        but return None gracefully if not found.
        """
        data_hex = packet.get("data", "")
        if len(data_hex) < 0x1A * 2:
            return None

        try:
            raw = bytes.fromhex(data_hex)
            message_id = int.from_bytes(raw[0x18:0x1A], "little")

            # Action messages may or may not use the zone dialog table
            # Try with & 0x7FFF first
            dialog_index = message_id & 0x7FFF
            return self._lookup_dialog(dialog_index, params=None)
        except (ValueError, IndexError):
            return None

    def _resolve_002d(self, packet: dict) -> Optional[str]:
        """Resolve a 0x002D Combat Message packet.

        Fields (from ffxi.xml):
          offset 0x0C: Message (uint16) at pos 12
          offset 0x10: Param (uint32) at pos 16
        """
        data_hex = packet.get("data", "")
        if len(data_hex) < 0x14 * 2:
            return None

        try:
            raw = bytes.fromhex(data_hex)
            message_id = int.from_bytes(raw[0x0C:0x0E], "little")
            dialog_index = message_id & 0x7FFF

            param = int.from_bytes(raw[0x10:0x14], "little")
            return self._lookup_dialog(dialog_index, params=[param])
        except (ValueError, IndexError):
            return None

    # ---------------------------------------------------------------------------
    # Common lookup
    # ---------------------------------------------------------------------------

    def _lookup_dialog(self, dialog_index: int, params: Optional[list[int]] = None) -> Optional[str]:
        """Look up a dialog index in the current zone's table.

        Args:
            dialog_index: The dialog table entry index.
            params: Optional parameter values for substitution.

        Returns:
            Resolved text, or None.
        """
        table = self._cache.get_table(self._current_zone_id)
        if table is None:
            return None

        if params:
            resolved = table.resolve_text(dialog_index, params)
        else:
            resolved = table.get_text(dialog_index)

        if resolved:
            # Clean up: strip trailing prompts and null-like markers
            resolved = resolved.replace("<prompt>", "").strip()

        return resolved if resolved else None
