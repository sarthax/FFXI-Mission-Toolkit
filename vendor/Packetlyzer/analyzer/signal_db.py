"""Signal Database for the Packetlyzer Reverse Engineer.

Stores user-defined signal interpretations keyed by (direction, opcode, offset).
Persists to a JSON file (signals_db.json) alongside the main config.

A "signal" represents a user's interpretation of raw bytes at a specific offset
within a packet type. Signals define data type, scaling, enum mappings, etc.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SignalDefinition:
    """A user-defined signal (field interpretation) for a packet byte range."""

    name: str                          # Human-readable signal name
    direction: str                     # "s2c" or "c2s"
    opcode: str                        # Opcode hex string (e.g. "0027")
    offset: int                        # Byte offset within packet data
    length: int                        # Number of bytes
    data_type: str                     # uint8, uint16, uint32, int8, int16, int32, float, bitfield, enum, string
    byte_order: str = "little"         # "little" or "big"
    bit_offset: Optional[int] = None   # For bitfield: starting bit within the byte(s)
    bit_count: Optional[int] = None    # For bitfield: number of bits
    enum_map: Optional[dict] = None    # For enum type: {str(value): label}
    scale: float = 1.0                 # Multiplier for analog scaling
    offset_val: float = 0.0            # Additive offset for analog scaling
    unit: str = ""                     # Unit label (e.g. "meters", "HP", "%")
    comment: str = ""                  # Freeform notes

    @property
    def key(self) -> str:
        """Unique key for this signal: direction:opcode:offset:name."""
        return f"{self.direction}:{self.opcode}:{self.offset}:{self.name}"

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        d = asdict(self)
        # Remove None values for cleaner JSON
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "SignalDefinition":
        """Deserialize from a dict."""
        # Handle optional fields
        return cls(
            name=data.get("name", "Unnamed"),
            direction=data.get("direction", "s2c"),
            opcode=data.get("opcode", "0000"),
            offset=data.get("offset", 0),
            length=data.get("length", 1),
            data_type=data.get("data_type", "uint8"),
            byte_order=data.get("byte_order", "little"),
            bit_offset=data.get("bit_offset"),
            bit_count=data.get("bit_count"),
            enum_map=data.get("enum_map"),
            scale=data.get("scale", 1.0),
            offset_val=data.get("offset_val", 0.0),
            unit=data.get("unit", ""),
            comment=data.get("comment", ""),
        )


class SignalDB:
    """JSON-backed signal definition database.

    Signals are stored in a flat list in the JSON file and indexed
    in memory by (direction, opcode) for fast packet-level lookup.
    """

    def __init__(self, path: str):
        """Initialize the signal database.

        Args:
            path: Path to the signals_db.json file.
        """
        self._path = path
        self._signals: list[SignalDefinition] = []
        self._index: dict[tuple[str, str], list[SignalDefinition]] = {}
        self._load()

    @property
    def path(self) -> str:
        """Path to the JSON file."""
        return self._path

    @property
    def signal_count(self) -> int:
        """Total number of signals defined."""
        return len(self._signals)

    def get_signals_for_opcode(self, direction: str, opcode: str) -> list[SignalDefinition]:
        """Get all signals defined for a specific packet type.

        Args:
            direction: "s2c" or "c2s".
            opcode: Opcode hex string (e.g. "0027").

        Returns:
            List of SignalDefinition instances, sorted by offset.
        """
        key = (direction.lower(), opcode.lower())
        return sorted(self._index.get(key, []), key=lambda s: s.offset)

    def add_signal(self, signal: SignalDefinition) -> None:
        """Add or update a signal definition.

        If a signal with the same key exists, it is replaced.

        Args:
            signal: The signal definition to add.
        """
        # Remove existing with same key if present
        self._signals = [s for s in self._signals if s.key != signal.key]
        self._signals.append(signal)
        self._rebuild_index()
        self._save()
        logger.info("Signal saved: %s", signal.key)

    def remove_signal(self, signal: SignalDefinition) -> bool:
        """Remove a signal definition.

        Args:
            signal: The signal to remove.

        Returns:
            True if the signal was found and removed.
        """
        before = len(self._signals)
        self._signals = [s for s in self._signals if s.key != signal.key]
        if len(self._signals) < before:
            self._rebuild_index()
            self._save()
            logger.info("Signal removed: %s", signal.key)
            return True
        return False

    def remove_by_key(self, key: str) -> bool:
        """Remove a signal by its key string.

        Args:
            key: The signal key (direction:opcode:offset:name).

        Returns:
            True if removed.
        """
        before = len(self._signals)
        self._signals = [s for s in self._signals if s.key != key]
        if len(self._signals) < before:
            self._rebuild_index()
            self._save()
            return True
        return False

    def clear_opcode(self, direction: str, opcode: str) -> int:
        """Remove all signals for a specific opcode.

        Args:
            direction: "s2c" or "c2s".
            opcode: Opcode hex string.

        Returns:
            Number of signals removed.
        """
        before = len(self._signals)
        self._signals = [
            s for s in self._signals
            if not (s.direction == direction and s.opcode == opcode)
        ]
        removed = before - len(self._signals)
        if removed > 0:
            self._rebuild_index()
            self._save()
        return removed

    def all_signals(self) -> list[SignalDefinition]:
        """Return all signal definitions."""
        return list(self._signals)

    # ---------------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------------

    def _load(self) -> None:
        """Load signals from the JSON file."""
        if not os.path.isfile(self._path):
            logger.debug("Signal DB file not found, starting empty: %s", self._path)
            return

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load signal DB: %s", e)
            return

        if not isinstance(data, dict) or "signals" not in data:
            return

        for entry in data["signals"]:
            try:
                sig = SignalDefinition.from_dict(entry)
                self._signals.append(sig)
            except (TypeError, KeyError) as e:
                logger.debug("Skipping invalid signal entry: %s", e)

        self._rebuild_index()
        logger.info("Loaded %d signals from %s", len(self._signals), self._path)

    def _save(self) -> None:
        """Persist signals to the JSON file."""
        data = {
            "version": 1,
            "signals": [s.to_dict() for s in self._signals],
        }
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            logger.error("Failed to save signal DB: %s", e)

    def _rebuild_index(self) -> None:
        """Rebuild the (direction, opcode) → signals index."""
        self._index.clear()
        for sig in self._signals:
            key = (sig.direction.lower(), sig.opcode.lower())
            if key not in self._index:
                self._index[key] = []
            self._index[key].append(sig)
