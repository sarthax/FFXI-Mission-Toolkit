"""Detail Panel for the Packetlyzer Analyzer (PyQt6).

Displays decoded fields (with raw hex column) and a hex dump for the
currently selected packet. Selecting a decoded field row highlights the
corresponding bytes in the hex dump below.

Includes a vertical QSlider for navigating through packet history and a
Byte Tracker tab that shows a tracked byte range across all history packets.

Requirements: 6.5, 7.3, 7.6, 10.3
"""

from __future__ import annotations

import logging
import struct as _struct
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analyzer.decoder import PacketDecoder, DecodedField, DecodedPacket
from analyzer.lookup import LookupManager
from analyzer.npc_lookup import NPCLookup
from analyzer.packet_db import FieldDefinition

logger = logging.getLogger(__name__)

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
    "pos": 12,
}

_HIGHLIGHT_BG = QColor(80, 100, 180)
_HIGHLIGHT_FG = QColor(255, 255, 255)


def _get_monospace_font(size: int = 10) -> QFont:
    """Get the preferred monospace font."""
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


def _field_byte_range(field_def: Optional[FieldDefinition]) -> tuple[int, int]:
    """Return (start_byte, end_byte_exclusive) for a field definition."""
    if field_def is None:
        return (0, 0)
    pos = field_def.pos
    field_type = field_def.type

    if field_type in _FIXED_TYPE_SIZES:
        return (pos, pos + _FIXED_TYPE_SIZES[field_type])
    elif field_type == "bits":
        bits_width = field_def.bits if field_def.bits else 0
        byte_size = (bits_width + 7) // 8
        return (pos, pos + byte_size)
    elif field_type in ("t", "a"):
        size = field_def.size if field_def.size else 0
        return (pos, pos + size)
    return (pos, pos)


def _format_raw_hex(raw_bytes: bytes, start: int, end: int) -> str:
    """Extract and format the raw hex bytes for a field's byte range."""
    if start >= end or start >= len(raw_bytes):
        return ""
    actual_end = min(end, len(raw_bytes))
    chunk = raw_bytes[start:actual_end]
    return " ".join(f"{b:02X}" for b in chunk)


def _format_timestamp(timestamp_ms: int) -> str:
    """Format a timestamp in milliseconds to HH:MM:SS.mmm."""
    if timestamp_ms <= 0:
        return "—"
    try:
        dt = datetime.fromtimestamp(timestamp_ms / 1000.0)
        return f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.{timestamp_ms % 1000:03d}"
    except (OSError, OverflowError, ValueError):
        return str(timestamp_ms)


def _interpret_bytes(raw: bytes, byte_order: str = "little") -> str:
    """Interpret raw bytes as common types for display."""
    parts = []
    bo = "<" if byte_order == "little" else ">"
    if len(raw) == 1:
        parts.append(f"{raw[0]} (0x{raw[0]:02X})")
    elif len(raw) == 2:
        val = _struct.unpack(f"{bo}H", raw)[0]
        parts.append(f"{val} (0x{val:04X})")
    elif len(raw) == 4:
        val_u = _struct.unpack(f"{bo}I", raw)[0]
        val_f = _struct.unpack(f"{bo}f", raw)[0]
        parts.append(f"u32={val_u} (0x{val_u:08X})")
        if -1e10 < val_f < 1e10 and val_f != 0:
            parts.append(f"f32={val_f:.4f}")
    else:
        parts.append(" ".join(f"{b:02X}" for b in raw[:8]))
    return " | ".join(parts)


class DetailPanel(QWidget):
    """Renders decoded fields and hex dump for a selected packet.

    Layout:
        [Slider | Header Label                                    ]
        [Slider | Fields Tree (decoded fields)                    ]
        [Slider | [Hex Dump] [Resolved Text] [Byte Tracker] tabs  ]

    The slider is a thin vertical QSlider on the far left, spanning the
    full height of the panel. It ranges from 0 to len(history_packets)-1.
    Moving it updates which packet is displayed.

    Signals:
        bytes_selected(int, int): Emitted when user selects bytes in hex dump.
            Args are (start_offset, length).
    """

    bytes_selected = pyqtSignal(int, int)

    def __init__(self, decoder: PacketDecoder, lookup_mgr: Optional[LookupManager] = None, npc_lookup: Optional[NPCLookup] = None, parent=None):
        super().__init__(parent)
        self._decoder = decoder
        self._lookup_mgr = lookup_mgr
        self._npc_lookup = npc_lookup
        self._signal_db = None  # Set via set_signal_db()
        self._packet: Optional[dict] = None
        self._decoded: Optional[DecodedPacket] = None
        self._raw_bytes: bytes = b""

        # History navigation state
        self._history_packets: list[dict] = []
        self._slider_updating = False  # Guard against re-entrant updates

        # Byte tracker state
        self._tracked_offset: Optional[int] = None
        self._tracked_length: int = 0

        # Sticky highlight state — persists across packet changes
        # When a field or byte range is selected, it stays highlighted
        # as new packets arrive or the slider is moved
        self._sticky_highlight_start: int = -1
        self._sticky_highlight_end: int = -1

        # Debounce timer for hex selection (prevents erratic resizing during drag)
        self._hex_select_timer = QTimer(self)
        self._hex_select_timer.setSingleShot(True)
        self._hex_select_timer.setInterval(150)  # 150ms debounce
        self._hex_select_timer.timeout.connect(self._process_hex_selection)

        self._setup_ui()

    def set_signal_db(self, signal_db) -> None:
        """Set the signal database for user-defined signal display.

        Args:
            signal_db: A SignalDB instance.
        """
        self._signal_db = signal_db

    def _setup_ui(self) -> None:
        # Outer horizontal layout: slider on left, content on right
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(4)

        # --- Left: Vertical slider + position label ---
        slider_layout = QVBoxLayout()
        slider_layout.setContentsMargins(2, 4, 2, 4)
        slider_layout.setSpacing(2)

        self._slider_pos_label = QLabel("—")
        self._slider_pos_label.setFont(_get_monospace_font(8))
        self._slider_pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._slider_pos_label.setFixedWidth(40)
        slider_layout.addWidget(self._slider_pos_label)

        self._history_slider = QSlider(Qt.Orientation.Vertical)
        self._history_slider.setMinimum(0)
        self._history_slider.setMaximum(0)
        self._history_slider.setInvertedAppearance(True)  # Top = 0 (earliest)
        self._history_slider.setFixedWidth(20)
        self._history_slider.valueChanged.connect(self._on_slider_moved)
        slider_layout.addWidget(self._history_slider)

        outer_layout.addLayout(slider_layout)

        # --- Right: Main content area ---
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 4, 4, 4)
        content_layout.setSpacing(4)

        # Header label
        self._header_label = QLabel("Select a packet to view details")
        self._header_label.setFont(_get_monospace_font(10))
        self._header_label.setStyleSheet("color: #c8d0f0; padding: 4px; background-color: #2a2d3c;")
        self._header_label.setWordWrap(True)
        content_layout.addWidget(self._header_label)

        # Vertical splitter: decoded fields on top, tabs on bottom
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)
        content_layout.addWidget(self._splitter)

        # Decoded Fields tree
        self._fields_tree = QTreeWidget()
        self._fields_tree.setHeaderLabels(["Position", "Name", "Type", "Value", "Raw Hex", "DB Lookup", "Comment"])
        self._fields_tree.setFont(_get_monospace_font(10))
        self._fields_tree.setAlternatingRowColors(True)
        self._fields_tree.setRootIsDecorated(True)
        header = self._fields_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(0, 60)
        header.resizeSection(1, 160)
        header.resizeSection(2, 60)
        header.resizeSection(3, 200)
        header.resizeSection(4, 120)
        header.resizeSection(5, 200)
        self._splitter.addWidget(self._fields_tree)

        # Bottom tabs: Hex Dump + Resolved Text + Byte Tracker
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setFont(_get_monospace_font(9))

        # Tab 1: Hex Dump (with Pin Selection button bar)
        hex_container = QWidget()
        hex_layout = QVBoxLayout(hex_container)
        hex_layout.setContentsMargins(0, 0, 0, 0)
        hex_layout.setSpacing(2)

        # Button bar above hex dump
        hex_btn_bar = QHBoxLayout()
        hex_btn_bar.setContentsMargins(4, 2, 4, 2)
        hex_btn_bar.setSpacing(6)

        self._pin_selection_btn = QPushButton("Pin Selection")
        self._pin_selection_btn.setFixedWidth(100)
        self._pin_selection_btn.setStyleSheet(
            "QPushButton { background-color: #89b4fa; color: #1e1e2e; font-weight: bold; font-size: 9px; }"
            "QPushButton:hover { background-color: #a6c8ff; }"
        )
        self._pin_selection_btn.clicked.connect(self._on_pin_tracker)
        hex_btn_bar.addWidget(self._pin_selection_btn)

        self._clear_pin_btn = QPushButton("Clear Pin")
        self._clear_pin_btn.setFixedWidth(70)
        self._clear_pin_btn.clicked.connect(self._on_clear_tracker)
        hex_btn_bar.addWidget(self._clear_pin_btn)

        self._pin_info_label = QLabel("")
        self._pin_info_label.setFont(_get_monospace_font(9))
        self._pin_info_label.setStyleSheet("color: #89b4fa;")
        hex_btn_bar.addWidget(self._pin_info_label)

        hex_btn_bar.addStretch()
        hex_layout.addLayout(hex_btn_bar)

        self._hex_view = QPlainTextEdit()
        self._hex_view.setReadOnly(True)
        self._hex_view.setFont(_get_monospace_font(10))
        self._hex_view.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e2e; color: #bec0d4; }"
        )
        self._hex_view.selectionChanged.connect(self._on_hex_selection_started)
        hex_layout.addWidget(self._hex_view)

        self._bottom_tabs.addTab(hex_container, "Hex Dump")

        # Tab 2: Resolved Text
        self._resolved_view = QPlainTextEdit()
        self._resolved_view.setReadOnly(True)
        self._resolved_view.setFont(_get_monospace_font(10))
        self._resolved_view.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e2e; color: #fab387; }"
        )
        self._bottom_tabs.addTab(self._resolved_view, "Resolved Text")

        # Tab 3: Byte Tracker
        self._tracker_widget = QWidget()
        tracker_layout = QVBoxLayout(self._tracker_widget)
        tracker_layout.setContentsMargins(4, 4, 4, 4)
        tracker_layout.setSpacing(4)

        # Tracker header (info label only — Pin/Clear buttons are in Hex Dump tab)
        self._tracker_label = QLabel("Select bytes in Hex Dump and click 'Pin Selection' to track")
        self._tracker_label.setFont(_get_monospace_font(9))
        self._tracker_label.setStyleSheet("color: #a6adc8; padding: 2px;")
        tracker_layout.addWidget(self._tracker_label)

        # Tracker table
        self._tracker_table = QTableWidget(0, 4)
        self._tracker_table.setHorizontalHeaderLabels(["#", "Time", "Hex", "Value"])
        self._tracker_table.setFont(_get_monospace_font(9))
        self._tracker_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tracker_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tracker_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._tracker_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tracker_table.horizontalHeader().resizeSection(2, 100)
        self._tracker_table.setAlternatingRowColors(True)
        tracker_layout.addWidget(self._tracker_table)

        self._bottom_tabs.addTab(self._tracker_widget, "Byte Tracker")

        self._splitter.addWidget(self._bottom_tabs)

        # 65/35 split: fields on top, tabs on bottom
        self._splitter.setSizes([650, 350])

        # Prevent collapse and set minimums
        self._fields_tree.setMinimumHeight(100)
        self._bottom_tabs.setMinimumHeight(80)

        # Connect tree selection to hex highlighting
        self._fields_tree.currentItemChanged.connect(self._on_field_selected)

        outer_layout.addLayout(content_layout, stretch=1)

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def set_packet(self, packet: Optional[dict]) -> None:
        """Set the packet to display.

        Args:
            packet: A packet record dict, or None to clear.
        """
        self._packet = packet

        if packet is None:
            self._decoded = None
            self._raw_bytes = b""
            self._header_label.setText("Select a packet to view details")
            self._fields_tree.clear()
            self._hex_view.clear()
            self._resolved_view.clear()
            return

        # Decode the packet
        direction = packet.get("direction", "s2c")
        opcode_str = packet.get("opcode", "0000")
        data_hex = packet.get("data", "")
        size = packet.get("size", 0)

        try:
            opcode_int = int(opcode_str, 16)
            self._raw_bytes = bytes.fromhex(data_hex)
            self._decoded = self._decoder.decode(direction, opcode_int, self._raw_bytes)
        except (ValueError, TypeError) as e:
            logger.warning("Failed to decode packet: %s", e)
            self._decoded = None
            self._raw_bytes = bytes.fromhex(data_hex) if data_hex else b""

        # Update header
        dir_label = "S\u2192C" if direction == "s2c" else "C\u2192S"
        desc = self._decoded.description if self._decoded else "Unknown"
        self._header_label.setText(
            f"{dir_label}  0x{opcode_str.upper()}  ({size} bytes)  \u2014  {desc}"
        )

        # Update decoded fields
        self._update_fields()

        # Update hex dump (no highlight until user selects a row)
        self._update_hex_dump()

        # Update resolved text tab
        resolved = packet.get("_resolved_text", "")
        if resolved:
            self._resolved_view.setPlainText(resolved)
        else:
            self._resolved_view.setPlainText("(no resolved text for this packet)")

        # Apply tracked byte highlighting if active
        if self._tracked_offset is not None and self._tracked_length > 0:
            self.highlight_bytes(self._tracked_offset, self._tracked_offset + self._tracked_length)

    def set_history_packets(self, packets: list[dict]) -> None:
        """Set the list of history packets for slider navigation and byte tracker.

        Args:
            packets: List of packet dicts matching the current opcode/direction.
        """
        self._history_packets = packets
        max_idx = max(0, len(packets) - 1)

        self._slider_updating = True
        self._history_slider.setMaximum(max_idx)
        # Default to the latest packet (end of list)
        self._history_slider.setValue(max_idx)
        self._slider_updating = False

        self._update_slider_label()

        # Refresh byte tracker if tracking
        if self._tracked_offset is not None:
            self._refresh_tracker_table()

    def append_history_packet(self, packet: dict) -> None:
        """Append a single new packet to the history list and update the slider.

        Called when a new packet arrives matching the currently viewed opcode.
        Keeps the slider at the latest position (auto-follow).

        Args:
            packet: The newly arrived packet dict.
        """
        self._history_packets.append(packet)
        max_idx = len(self._history_packets) - 1

        self._slider_updating = True
        self._history_slider.setMaximum(max_idx)
        # Stay at the latest packet (auto-follow)
        self._history_slider.setValue(max_idx)
        self._slider_updating = False

        self._update_slider_label()

        # Show the new packet in the detail view
        self.set_packet(packet)

        # Refresh byte tracker if tracking
        if self._tracked_offset is not None:
            self._refresh_tracker_table()

    def track_bytes(self, offset: int, length: int) -> None:
        """Set the byte range to track across history packets.

        Args:
            offset: Starting byte offset.
            length: Number of bytes to track.
        """
        if length <= 0:
            return

        self._tracked_offset = offset
        self._tracked_length = length
        self._tracker_label.setText(
            f"Tracking: 0x{offset:02X} ({length} byte{'s' if length != 1 else ''})"
        )
        self._refresh_tracker_table()

        # Apply highlight to current packet
        if self._raw_bytes:
            self.highlight_bytes(offset, offset + length)

    def clear(self) -> None:
        """Clear the detail panel."""
        self.set_packet(None)

    def highlight_bytes(self, start: int, end: int) -> None:
        """Highlight a specific byte range in the hex dump.

        Sets the sticky highlight so it persists across packet changes.

        Args:
            start: Start byte offset (inclusive).
            end: End byte offset (exclusive).
        """
        if start >= 0 and end > start:
            self._sticky_highlight_start = start
            self._sticky_highlight_end = end
            if self._raw_bytes:
                self._highlight_hex_bytes(start, end)

    # ---------------------------------------------------------------------------
    # Slider Navigation
    # ---------------------------------------------------------------------------

    def _on_slider_moved(self, value: int) -> None:
        """Handle slider value change — navigate to the packet at that index."""
        if self._slider_updating:
            return
        if not self._history_packets:
            return
        if 0 <= value < len(self._history_packets):
            self._update_slider_label()
            packet = self._history_packets[value]
            self.set_packet(packet)

    def _update_slider_label(self) -> None:
        """Update the position label next to the slider."""
        total = len(self._history_packets)
        if total == 0:
            self._slider_pos_label.setText("—")
        else:
            current = self._history_slider.value() + 1
            self._slider_pos_label.setText(f"{current}/{total}")

    def navigate_to_packet(self, packet: dict) -> None:
        """Navigate the slider to a specific packet in the history list.

        Used when an external component (like HistoryPanel) pins a packet.

        Args:
            packet: The packet dict to navigate to.
        """
        for i, p in enumerate(self._history_packets):
            if p is packet:
                self._slider_updating = True
                self._history_slider.setValue(i)
                self._slider_updating = False
                self._update_slider_label()
                break

    # ---------------------------------------------------------------------------
    # Byte Tracker
    # ---------------------------------------------------------------------------

    def _on_pin_tracker(self) -> None:
        """Pin the current hex selection for tracking across history packets."""
        # Use the sticky highlight as the pinned range
        if self._sticky_highlight_start >= 0 and self._sticky_highlight_end > self._sticky_highlight_start:
            self._tracked_offset = self._sticky_highlight_start
            self._tracked_length = self._sticky_highlight_end - self._sticky_highlight_start
        elif self._tracked_offset is None:
            # Try parsing fresh selection
            cursor = self._hex_view.textCursor()
            if cursor.hasSelection():
                self._process_hex_selection()

        if self._tracked_offset is not None:
            self._tracker_label.setText(
                f"Tracking: 0x{self._tracked_offset:02X} "
                f"({self._tracked_length} byte{'s' if self._tracked_length != 1 else ''})"
            )
            self._pin_info_label.setText(
                f"Pinned: 0x{self._tracked_offset:02X} [{self._tracked_length}B]"
            )
            self._refresh_tracker_table()

    def _on_clear_tracker(self) -> None:
        """Clear the byte tracker and sticky highlight."""
        self._tracked_offset = None
        self._tracked_length = 0
        self._sticky_highlight_start = -1
        self._sticky_highlight_end = -1
        self._tracker_table.setRowCount(0)
        self._tracker_label.setText("Select bytes in Hex Dump and click 'Pin Selection' to track")
        self._pin_info_label.setText("")
        self._hex_view.setExtraSelections([])

    def _refresh_tracker_table(self) -> None:
        """Refresh the byte tracker table showing values across all history packets."""
        self._tracker_table.setRowCount(0)

        if self._tracked_offset is None or not self._history_packets:
            return

        offset = self._tracked_offset
        length = self._tracked_length

        prev_hex = None
        for i, pkt in enumerate(self._history_packets):
            data_hex = pkt.get("data", "")
            try:
                raw_bytes = bytes.fromhex(data_hex)
            except ValueError:
                continue

            if offset + length > len(raw_bytes):
                continue

            chunk = raw_bytes[offset:offset + length]
            hex_str = " ".join(f"{b:02X}" for b in chunk)

            # Interpret value
            value_str = _interpret_bytes(chunk, "little")

            # Format timestamp
            time_str = _format_timestamp(pkt.get("timestamp", 0))

            row = self._tracker_table.rowCount()
            self._tracker_table.insertRow(row)

            num_item = QTableWidgetItem(str(pkt.get("_row_number", i + 1)))
            time_item = QTableWidgetItem(time_str)
            hex_item = QTableWidgetItem(hex_str)
            value_item = QTableWidgetItem(value_str)

            # Highlight rows where value changed from previous
            if prev_hex is not None and hex_str != prev_hex:
                change_color = QColor(250, 179, 135)  # Peach for changes
                hex_item.setForeground(change_color)
                value_item.setForeground(change_color)

            self._tracker_table.setItem(row, 0, num_item)
            self._tracker_table.setItem(row, 1, time_item)
            self._tracker_table.setItem(row, 2, hex_item)
            self._tracker_table.setItem(row, 3, value_item)

            prev_hex = hex_str

        # Scroll to bottom to show latest
        self._tracker_table.scrollToBottom()

    # ---------------------------------------------------------------------------
    # Internal — Decoded Fields
    # ---------------------------------------------------------------------------

    def _update_fields(self) -> None:
        """Populate the decoded fields tree with position info, groups, raw hex, and comments."""
        # Block currentItemChanged during rebuild to prevent spurious highlighting
        self._fields_tree.blockSignals(True)

        # Remember which byte range was selected so we can re-select it after rebuild
        selected_byte_range = None
        current_item = self._fields_tree.currentItem()
        if current_item is not None:
            selected_byte_range = current_item.data(0, Qt.ItemDataRole.UserRole)
        # Also use the sticky highlight as fallback (in case tree had no selection but hex was highlighted)
        if selected_byte_range is None and self._sticky_highlight_start >= 0:
            selected_byte_range = (self._sticky_highlight_start, self._sticky_highlight_end)

        self._fields_tree.clear()

        # Show resolved dialog text if available (from message resolver)
        if self._packet and self._packet.get("_resolved_text"):
            resolved = self._packet["_resolved_text"]
            resolved_item = QTreeWidgetItem(["", "\u2709 Resolved Text", "", resolved, "", "", ""])
            resolved_item.setForeground(1, QColor(166, 227, 161))  # Green label
            resolved_item.setForeground(3, QColor(250, 179, 135))  # Peach text
            self._fields_tree.addTopLevelItem(resolved_item)

        if not self._decoded:
            item = QTreeWidgetItem(["", "(No definition found)", "", "", "", "", ""])
            self._fields_tree.addTopLevelItem(item)
            self._fields_tree.blockSignals(False)
            return

        if not self._decoded.has_definition:
            opcode = self._packet.get("opcode", "0000") if self._packet else "0000"
            item = QTreeWidgetItem(["", f"No definition for 0x{opcode.upper()}", "", "", "", "", ""])
            self._fields_tree.addTopLevelItem(item)
            self._fields_tree.blockSignals(False)
            return

        # Group fields by their group label (for loop-unrolled fields)
        current_group: Optional[str] = None
        group_item: Optional[QTreeWidgetItem] = None

        for field in self._decoded.fields:
            # Format position string like VieweD: "0x10:5~9" for bits
            pos_str = self._format_position(field)

            # Get comment from the field definition if available
            comment = ""
            if hasattr(field, '_field_def') and field._field_def and field._field_def.comment:
                comment = field._field_def.comment
            elif hasattr(field, 'comment') and field.comment:
                comment = field.comment

            # Get raw hex for this field's byte range
            field_def = getattr(field, '_field_def', None)
            start, end = _field_byte_range(field_def)
            raw_hex_str = _format_raw_hex(self._raw_bytes, start, end)

            # Get group from field definition
            group = None
            if hasattr(field, '_field_def') and field._field_def and hasattr(field._field_def, 'group'):
                group = field._field_def.group

            # Handle group changes (create tree parent nodes)
            if group != current_group:
                current_group = group
                if group:
                    group_label = group
                    if (hasattr(field, '_field_def') and field._field_def and
                            field._field_def.group_lookup and field._field_def.group_index and
                            self._lookup_mgr):
                        resolved = self._lookup_mgr.resolve(
                            field._field_def.group_lookup, field._field_def.group_index
                        )
                        if "\u2192" in resolved:
                            lookup_name = resolved.split("\u2192", 1)[1].strip().strip('"')
                            group_label = f"{group} \u2014 {lookup_name}"
                    pos_str_grp = f"0x{field._field_def.pos:02X}" if hasattr(field, '_field_def') and field._field_def else ""
                    group_item = QTreeWidgetItem([pos_str_grp, f"\u2500\u2500 {group_label} \u2500\u2500", "", "", "", "", ""])
                    group_item.setExpanded(True)
                    self._fields_tree.addTopLevelItem(group_item)
                else:
                    group_item = None

            if field.out_of_range:
                item = QTreeWidgetItem([pos_str, field.name, field.type, "(out of range)", "", "", comment])
                item.setForeground(3, QColor(Qt.GlobalColor.red))
            else:
                display = field.display_value
                # DB Lookup: resolve entity IDs (uint32 fields that look like NPC/mob IDs)
                db_lookup_str = self._resolve_db_lookup(field)
                item = QTreeWidgetItem([pos_str, field.name, field.type, display, raw_hex_str, db_lookup_str, comment])
                if db_lookup_str:
                    item.setForeground(5, QColor(250, 179, 135))  # Peach for DB lookups

            # Store byte range on the item for hex highlighting
            item.setData(0, Qt.ItemDataRole.UserRole, (start, end))

            if group_item is not None:
                group_item.addChild(item)
            else:
                self._fields_tree.addTopLevelItem(item)

        # Append user-defined signals for this opcode
        self._render_user_signals()

        self._fields_tree.blockSignals(False)

        # Re-select the field row matching the previously selected byte range
        if selected_byte_range is not None:
            self._reselect_field_by_range(selected_byte_range)

    def _format_position(self, field: DecodedField) -> str:
        """Format field position like VieweD: 0x10, 0x10:5~9, etc."""
        field_def = getattr(field, '_field_def', None)

        pos = 0
        if field_def:
            pos = field_def.pos

        pos_hex = f"0x{pos:02X}"

        if field_def and field_def.bits and field_def.bit_offset is not None:
            bit_start = field_def.bit_offset
            bit_end = bit_start + field_def.bits - 1
            return f"{pos_hex}:{bit_start}~{bit_end}"
        elif field_def and field_def.bits and field_def.bit_offset is None:
            return f"{pos_hex}:0~{field_def.bits - 1}"

        return pos_hex

    def _reselect_field_by_range(self, byte_range: tuple) -> None:
        """Find and re-select the tree item matching the given byte range.

        Walks all top-level items and their children to find a match.
        This keeps the field row highlighted across packet changes.

        Args:
            byte_range: Tuple of (start, end) byte offsets to match.
        """
        def _find_in_children(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) == byte_range:
                    return child
            return None

        for i in range(self._fields_tree.topLevelItemCount()):
            item = self._fields_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == byte_range:
                self._fields_tree.setCurrentItem(item)
                return
            # Check children (group items)
            found = _find_in_children(item)
            if found:
                self._fields_tree.setCurrentItem(found)
                return

    def _resolve_db_lookup(self, field: DecodedField) -> str:
        """Resolve a field value against database lookups.

        Uses field name patterns and value structure to determine what kind
        of data a field holds, then resolves it using the appropriate source:
        - Entity IDs (NPC/mob names from npc_list.sql)
        - Zone IDs (from zones.txt lookup)
        - Item IDs (from items.txt lookup)
        - Model IDs (from itemmodels.txt lookup)
        - Spells, Jobs, Weather (from respective lookup files)

        Args:
            field: The decoded field to check.

        Returns:
            A display string with the resolved name, or empty string.
        """
        if not self._npc_lookup:
            return ""

        # Skip out-of-range or non-numeric fields
        if field.out_of_range:
            return ""

        # Use the expanded resolve_field method
        return self._npc_lookup.resolve_field(
            field.name,
            field.type,
            field.display_value,
            field.raw_value,
        )

    # ---------------------------------------------------------------------------
    # Internal — User-defined Signals
    # ---------------------------------------------------------------------------

    def _render_user_signals(self) -> None:
        """Append user-defined signal interpretations to the decoded fields tree."""
        if not self._signal_db or not self._packet:
            return

        direction = self._packet.get("direction", "")
        opcode = self._packet.get("opcode", "")
        signals = self._signal_db.get_signals_for_opcode(direction, opcode)

        if not signals:
            return

        # Add a separator
        sep_item = QTreeWidgetItem(["", "\u2500\u2500 User Signals \u2500\u2500", "", "", "", "", ""])
        sep_item.setForeground(1, QColor(137, 180, 250))  # Blue label
        self._fields_tree.addTopLevelItem(sep_item)

        for sig in signals:
            pos_str = f"0x{sig.offset:02X}"
            raw_hex_str = _format_raw_hex(self._raw_bytes, sig.offset, sig.offset + sig.length)
            value_str = self._interpret_signal(sig)
            comment = sig.comment

            item = QTreeWidgetItem([pos_str, sig.name, sig.data_type, value_str, raw_hex_str, "", comment])
            item.setForeground(1, QColor(137, 180, 250))  # Blue name
            item.setForeground(3, QColor(166, 227, 161))  # Green value
            item.setData(0, Qt.ItemDataRole.UserRole, (sig.offset, sig.offset + sig.length))
            self._fields_tree.addTopLevelItem(item)

    def _interpret_signal(self, sig) -> str:
        """Interpret a user signal's value from the current packet bytes."""
        offset = sig.offset
        length = sig.length

        if offset + length > len(self._raw_bytes):
            return "(out of range)"

        raw = self._raw_bytes[offset:offset + length]
        bo = "<" if sig.byte_order == "little" else ">"

        try:
            if sig.data_type == "uint8" and length >= 1:
                value = raw[0]
            elif sig.data_type == "uint16" and length >= 2:
                value = _struct.unpack(f"{bo}H", raw[:2])[0]
            elif sig.data_type == "uint32" and length >= 4:
                value = _struct.unpack(f"{bo}I", raw[:4])[0]
            elif sig.data_type == "int8" and length >= 1:
                value = _struct.unpack("b", raw[:1])[0]
            elif sig.data_type == "int16" and length >= 2:
                value = _struct.unpack(f"{bo}h", raw[:2])[0]
            elif sig.data_type == "int32" and length >= 4:
                value = _struct.unpack(f"{bo}i", raw[:4])[0]
            elif sig.data_type == "float" and length >= 4:
                value = _struct.unpack(f"{bo}f", raw[:4])[0]
                scaled = value * sig.scale + sig.offset_val
                unit = f" {sig.unit}" if sig.unit else ""
                return f"{scaled:.4f}{unit}"
            elif sig.data_type == "bitfield":
                # Extract bits
                int_val = int.from_bytes(raw, byteorder=sig.byte_order)
                bit_offset = sig.bit_offset or 0
                bit_count = sig.bit_count or 1
                mask = (1 << bit_count) - 1
                value = (int_val >> bit_offset) & mask
            elif sig.data_type == "string":
                # Decode as null-terminated string
                null_pos = raw.find(0x00)
                text_bytes = raw[:null_pos] if null_pos >= 0 else raw
                try:
                    return f'"{text_bytes.decode("utf-8", errors="replace")}"'
                except Exception:
                    return f'"{text_bytes.decode("latin-1")}"'
            elif sig.data_type == "enum":
                # Read as uint of appropriate size
                if length == 1:
                    value = raw[0]
                elif length == 2:
                    value = _struct.unpack(f"{bo}H", raw[:2])[0]
                elif length == 4:
                    value = _struct.unpack(f"{bo}I", raw[:4])[0]
                else:
                    value = int.from_bytes(raw, byteorder=sig.byte_order)
                # Look up in enum map
                if sig.enum_map:
                    label = sig.enum_map.get(str(value), sig.enum_map.get(str(int(value)), None))
                    if label:
                        return f"{value} \u2192 {label}"
                return str(value)
            else:
                value = int.from_bytes(raw, byteorder=sig.byte_order)
        except (ValueError, _struct.error):
            return "(decode error)"

        # Apply scaling
        scaled = value * sig.scale + sig.offset_val
        unit = f" {sig.unit}" if sig.unit else ""

        if sig.scale != 1.0 or sig.offset_val != 0.0:
            return f"{scaled:.4f}{unit} (raw: {value})"
        elif unit:
            return f"{value}{unit}"
        else:
            return f"{value} (0x{value:X})"

    # ---------------------------------------------------------------------------
    # Internal — Hex Dump
    # ---------------------------------------------------------------------------

    def _update_hex_dump(self) -> None:
        """Render the hex dump into the QPlainTextEdit then re-apply sticky highlight."""
        if not self._raw_bytes:
            self._hex_view.setPlainText("(no data)")
            return

        # Build plain text
        lines = []
        for offset in range(0, len(self._raw_bytes), 16):
            chunk = self._raw_bytes[offset:offset + 16]

            # Offset column
            offset_str = f"{offset:04X}"

            # Hex bytes
            hex_parts = [f"{b:02X}" for b in chunk]
            while len(hex_parts) < 16:
                hex_parts.append("  ")
            hex_left = " ".join(hex_parts[:8])
            hex_right = " ".join(hex_parts[8:])

            # ASCII
            ascii_chars = []
            for b in chunk:
                if 32 <= b <= 126:
                    ascii_chars.append(chr(b))
                else:
                    ascii_chars.append(".")
            ascii_str = "".join(ascii_chars)

            lines.append(f"{offset_str}  {hex_left}  {hex_right}  |{ascii_str}|")

        self._hex_view.setPlainText("\n".join(lines))

        # Re-apply sticky highlight if one is set
        if self._sticky_highlight_start >= 0 and self._sticky_highlight_end > self._sticky_highlight_start:
            self._highlight_hex_bytes(self._sticky_highlight_start, self._sticky_highlight_end)

    def _highlight_hex_bytes(self, start: int, end: int) -> None:
        """Highlight specific bytes in the hex dump view using extra selections.

        Uses QPlainTextEdit.setExtraSelections() which is overlay-based and
        automatically cleared when set to an empty list. This avoids the
        accumulation issues of mergeCharFormat.
        """
        from PyQt6.QtWidgets import QTextEdit

        selections = []
        doc = self._hex_view.document()

        fmt = QTextCharFormat()
        fmt.setBackground(_HIGHLIGHT_BG)
        fmt.setForeground(_HIGHLIGHT_FG)

        for byte_idx in range(start, min(end, len(self._raw_bytes))):
            line_num = byte_idx // 16
            col_in_line = byte_idx % 16

            block = doc.findBlockByLineNumber(line_num)
            if not block.isValid():
                continue

            line_text = block.text()
            block_start = block.position()

            # Calculate hex character position within the line
            # Format: "OOOO  HH HH HH HH HH HH HH HH  HH HH HH HH HH HH HH HH  |AAAAAAAAAAAAAAAA|"
            # Offset: 4 chars + 2 spaces = 6 chars before hex starts
            if col_in_line < 8:
                hex_char_offset = 6 + col_in_line * 3
            else:
                # Extra space between left and right hex groups
                hex_char_offset = 6 + 8 * 3 + 1 + (col_in_line - 8) * 3

            # Highlight the hex byte (2 characters)
            hex_pos = block_start + hex_char_offset
            sel = QTextEdit.ExtraSelection()
            sel.format = QTextCharFormat(fmt)
            sel.cursor = QTextCursor(doc)
            sel.cursor.setPosition(hex_pos)
            sel.cursor.setPosition(hex_pos + 2, QTextCursor.MoveMode.KeepAnchor)
            selections.append(sel)

            # Highlight the ASCII character
            ascii_section_start = line_text.find("|")
            if ascii_section_start >= 0:
                ascii_char_offset = ascii_section_start + 1 + col_in_line
                if ascii_char_offset < len(line_text) - 1:  # -1 for trailing |
                    ascii_pos = block_start + ascii_char_offset
                    sel_ascii = QTextEdit.ExtraSelection()
                    sel_ascii.format = QTextCharFormat(fmt)
                    sel_ascii.cursor = QTextCursor(doc)
                    sel_ascii.cursor.setPosition(ascii_pos)
                    sel_ascii.cursor.setPosition(ascii_pos + 1, QTextCursor.MoveMode.KeepAnchor)
                    selections.append(sel_ascii)

        self._hex_view.setExtraSelections(selections)

    # ---------------------------------------------------------------------------
    # Slots
    # ---------------------------------------------------------------------------

    def _on_field_selected(self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]) -> None:
        """When a field row is selected, highlight its bytes in the hex dump.

        The highlight is sticky — it persists across packet changes so the
        same byte position remains highlighted as new packets arrive.
        """
        if current is None:
            return  # Don't clear sticky highlight on deselect

        # Get byte range stored on the item
        byte_range = current.data(0, Qt.ItemDataRole.UserRole)
        if byte_range is None:
            return

        start, end = byte_range
        if start >= 0 and end > start:
            # Store as sticky highlight
            self._sticky_highlight_start = start
            self._sticky_highlight_end = end
            self._highlight_hex_bytes(start, end)
        else:
            self._hex_view.setExtraSelections([])

    def _on_hex_selection_started(self) -> None:
        """Debounce the hex selection — restart the timer on each change.

        This prevents rapid-fire processing during drag selection which
        would cause layout thrashing in connected widgets.
        """
        self._hex_select_timer.start()

    def _process_hex_selection(self) -> None:
        """Process the hex dump selection after the debounce timer fires.

        Called 150ms after the user stops changing their selection.
        """
        self._on_hex_selection_changed()

    def _on_hex_selection_changed(self) -> None:
        """Detect byte range from user's text selection in the hex dump.

        Maps the text cursor selection back to byte offsets by analyzing
        which hex byte positions are covered. Uses optimized math-based
        calculation instead of iterating all bytes.
        """
        cursor = self._hex_view.textCursor()
        if not cursor.hasSelection():
            return

        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()

        if sel_start == sel_end:
            return

        doc = self._hex_view.document()

        # Optimized: calculate byte offsets from character positions directly
        # Line format: "OOOO  HH HH HH HH HH HH HH HH  HH HH HH HH HH HH HH HH  |AAAAAAAAAAAAAAAA|"
        # Offset: 4 + 2 = 6 chars before hex starts
        # Left group (bytes 0-7): positions 6, 9, 12, 15, 18, 21, 24, 27 (each 3 chars apart)
        # Right group (bytes 8-15): positions 31, 34, 37, 40, 43, 46, 49, 52 (extra space at 30)

        byte_offsets: set[int] = set()

        # Only scan lines that could be affected by the selection
        first_line = doc.findBlock(sel_start).blockNumber()
        last_line = doc.findBlock(sel_end).blockNumber()

        for line_num in range(first_line, last_line + 1):
            block = doc.findBlockByLineNumber(line_num)
            if not block.isValid():
                continue
            block_start = block.position()

            for col_in_line in range(16):
                byte_idx = line_num * 16 + col_in_line
                if byte_idx >= len(self._raw_bytes):
                    break

                if col_in_line < 8:
                    hex_char_offset = 6 + col_in_line * 3
                else:
                    hex_char_offset = 6 + 8 * 3 + 1 + (col_in_line - 8) * 3

                hex_pos = block_start + hex_char_offset
                hex_end = hex_pos + 2

                if hex_end > sel_start and hex_pos < sel_end:
                    byte_offsets.add(byte_idx)

        if not byte_offsets:
            return

        # Determine contiguous range
        start_byte = min(byte_offsets)
        end_byte = max(byte_offsets) + 1
        length = end_byte - start_byte

        if length > 0:
            # Store as sticky highlight (persists across packet changes)
            self._sticky_highlight_start = start_byte
            self._sticky_highlight_end = end_byte
            # Store for byte tracker use
            self._tracked_offset = start_byte
            self._tracked_length = length
            self.bytes_selected.emit(start_byte, length)
