"""Packet Export Module for the Packetlyzer Analyzer.

Provides JSONL (.jsonl) and hex dump (.txt) export of the visible (filtered)
packet list. Opens a file-save dialog via tkinter, runs export on a background
thread, and provides status messages for success/failure.

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class PacketExporter:
    """Exports visible (filtered) packets to JSONL or hex dump files.

    Integrates with the display module's visible_packets property to export
    only what the user currently sees. Runs export on a background thread to
    avoid blocking the GUI.
    """

    def __init__(self, on_status: Optional[Callable[[str, float], None]] = None):
        """Initialize the exporter.

        Args:
            on_status: Optional callback invoked with (message, duration_seconds)
                       to display status in the toolbar. Called from the export
                       thread — the GUI layer should handle thread-safety.
        """
        self._on_status = on_status
        self._exporting = False

    @property
    def exporting(self) -> bool:
        """Whether an export is currently in progress."""
        return self._exporting

    def export_visible(self, packets: list[dict], path: str, fmt: str) -> None:
        """Export packets to the specified file in the given format.

        This is the main entry point called from the GUI when the user confirms
        the file-save dialog. Runs on a background thread.

        Args:
            packets: List of packet dicts (the visible/filtered set).
            path: Destination file path.
            fmt: Format string — "jsonl" or "txt".
        """
        self._exporting = True
        thread = threading.Thread(
            target=self._export_worker,
            args=(packets, path, fmt),
            daemon=True,
        )
        thread.start()

    def start_export(self, packets: list[dict]) -> None:
        """Initiate the export flow: check for empty list, open dialog, export.

        This handles the full export workflow:
        1. Check if packet list is empty (show message, skip dialog)
        2. Open file-save dialog for destination path and format
        3. Launch background export

        Args:
            packets: The visible (filtered) packet list to export.
        """
        # Req 14.4: Show message if list is empty, skip dialog
        if not packets:
            self._notify("No packets to export", 5.0)
            return

        # Req 14.3: Open file-save dialog (uses tkinter since pygame has none)
        path, fmt = self._open_save_dialog()
        if not path:
            # User cancelled
            return

        # Req 14.5: Run export on background thread
        self.export_visible(packets, path, fmt)

    def export_jsonl(self, packets: list[dict], path: str) -> None:
        """Write packets as newline-delimited JSON (one JSON_Message per line).

        Each line is a valid JSON object containing the packet's fields:
        type, direction, opcode, size, data, timestamp.

        Args:
            packets: List of packet dicts to export.
            path: Destination file path.

        Raises:
            IOError: If the file cannot be written.
        """
        with open(path, "w", encoding="utf-8") as f:
            for packet in packets:
                # Build a clean JSON_Message from the packet dict
                # Exclude internal fields (prefixed with _)
                message = {
                    k: v for k, v in packet.items() if not k.startswith("_")
                }
                f.write(json.dumps(message, ensure_ascii=False) + "\n")

    def export_hexdump(self, packets: list[dict], path: str) -> None:
        """Write packets as formatted hex dump text.

        Each packet gets a header line followed by hex dump rows of 16 bytes
        each showing offset, hex bytes, and ASCII representation.

        Args:
            packets: List of packet dicts to export.
            path: Destination file path.

        Raises:
            IOError: If the file cannot be written.
        """
        with open(path, "w", encoding="utf-8") as f:
            for i, packet in enumerate(packets):
                # Write packet header
                direction = packet.get("direction", "???")
                opcode = packet.get("opcode", "0000")
                size = packet.get("size", 0)
                timestamp = packet.get("timestamp", 0)

                dir_label = "S→C" if direction == "s2c" else "C→S"
                f.write(
                    f"--- Packet #{i + 1}: [{dir_label}] "
                    f"Opcode: 0x{opcode.upper()} | "
                    f"Size: {size} bytes | "
                    f"Timestamp: {timestamp} ---\n"
                )

                # Write hex dump of packet data
                data_hex = packet.get("data", "")
                try:
                    raw_bytes = bytes.fromhex(data_hex)
                except ValueError:
                    raw_bytes = b""

                f.write(format_hexdump(raw_bytes))
                f.write("\n")

    def _export_worker(self, packets: list[dict], path: str, fmt: str) -> None:
        """Background thread worker that performs the actual file write.

        On success: displays packet count + filename for 5 seconds.
        On failure: displays error for 5 seconds, cleans up partial file.

        Args:
            packets: List of packet dicts.
            path: Destination file path.
            fmt: "jsonl" or "txt".
        """
        try:
            if fmt == "jsonl":
                self.export_jsonl(packets, path)
            else:
                self.export_hexdump(packets, path)

            # Req 14.6: Success message with packet count + filename for 5s
            filename = os.path.basename(path)
            self._notify(
                f"Exported {len(packets)} packets to {filename}", 5.0
            )
        except Exception as e:
            # Req 14.7: Error message for 5 seconds, clean up partial file
            logger.error("Export failed: %s", e)
            self._cleanup_partial(path)
            self._notify(f"Export failed: {e}", 5.0)
        finally:
            self._exporting = False

    def _open_save_dialog(self) -> tuple[str, str]:
        """Open a QFileDialog for export destination.

        Returns:
            Tuple of (path, format) where format is "jsonl" or "txt".
            Returns ("", "") if the user cancels.
        """
        try:
            from PyQt6.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                None,
                "Export Packets",
                "",
                "JSONL files (*.jsonl);;Text files - hex dump (*.txt);;All files (*.*)",
            )

            if not path:
                return ("", "")

            # Determine format from extension
            _, ext = os.path.splitext(path)
            if ext.lower() == ".txt":
                fmt = "txt"
            else:
                fmt = "jsonl"

            return (path, fmt)

        except Exception as e:
            logger.error("Failed to open file dialog: %s", e)
            self._notify(f"Failed to open file dialog: {e}", 5.0)
            return ("", "")

    def _cleanup_partial(self, path: str) -> None:
        """Remove a partial/incomplete export file if it exists.

        Args:
            path: The file path to clean up.
        """
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("Cleaned up partial export file: %s", path)
        except OSError as e:
            logger.warning("Failed to clean up partial file %s: %s", path, e)

    def _notify(self, message: str, duration: float) -> None:
        """Send a status notification via the callback.

        Args:
            message: The status message text.
            duration: How long the message should be displayed (seconds).
        """
        if self._on_status:
            self._on_status(message, duration)
        else:
            logger.info("Export status: %s (%.1fs)", message, duration)


def format_hexdump(data: bytes) -> str:
    """Format raw bytes as a hex dump string (16 bytes per row).

    Each row shows: offset (8 hex digits), hex bytes (space-separated,
    grouped in two sets of 8), and ASCII representation.

    Args:
        data: The raw bytes to format.

    Returns:
        Formatted hex dump string with newlines between rows.
    """
    if not data:
        return "(empty)\n"

    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]

        # Offset column
        offset_str = f"{offset:08X}"

        # Hex bytes column (two groups of 8)
        hex_parts = []
        for i, byte in enumerate(chunk):
            hex_parts.append(f"{byte:02X}")
        # Pad to 16 bytes for alignment
        while len(hex_parts) < 16:
            hex_parts.append("  ")

        hex_left = " ".join(hex_parts[:8])
        hex_right = " ".join(hex_parts[8:])
        hex_str = f"{hex_left}  {hex_right}"

        # ASCII column
        ascii_chars = []
        for byte in chunk:
            if 32 <= byte <= 126:
                ascii_chars.append(chr(byte))
            else:
                ascii_chars.append(".")
        ascii_str = "".join(ascii_chars)

        lines.append(f"{offset_str}  {hex_str}  |{ascii_str}|")

    return "\n".join(lines) + "\n"
