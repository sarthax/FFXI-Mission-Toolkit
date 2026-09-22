"""Packet History Panel for the Packetlyzer Analyzer (PyQt6).

Shows the chronological history of all packets matching a specific
opcode+direction. Used alongside Fixed Position mode to drill into
the timeline for a particular packet type.

When a row is selected, the detail panel shows that specific packet.
When no row is selected (or selection is cleared), the detail panel
reverts to showing the latest packet for that opcode.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLOR_BG = QColor(30, 30, 46)
_COLOR_TEXT = QColor(205, 214, 244)
_COLOR_SELECTED_BG = QColor(69, 71, 90)


def _format_timestamp(timestamp_ms: int) -> str:
    """Format a Unix millisecond timestamp as HH:MM:SS.mmm in local time.

    Handles non-epoch timestamps (e.g. process uptime) gracefully by falling
    back to simple modulo arithmetic when datetime conversion fails.
    """
    if timestamp_ms <= 0:
        return "00:00:00.000"
    seconds_epoch = timestamp_ms / 1000.0
    try:
        dt = datetime.fromtimestamp(seconds_epoch)
        return f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.{timestamp_ms % 1000:03d}"
    except (OSError, OverflowError, ValueError):
        # Fallback for non-epoch values (uptime, etc.) — display as elapsed time
        total_ms = int(timestamp_ms) % 86_400_000
        hours = total_ms // 3_600_000
        remainder = total_ms % 3_600_000
        minutes = remainder // 60_000
        remainder = remainder % 60_000
        seconds = remainder // 1000
        millis = remainder % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _get_monospace_font(size: int = 10) -> QFont:
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


def _truncate_hex(data_hex: str, max_len: int = 32) -> str:
    if len(data_hex) <= max_len:
        return " ".join(data_hex[i:i+2] for i in range(0, len(data_hex), 2))
    truncated = data_hex[:max_len]
    spaced = " ".join(truncated[i:i+2] for i in range(0, len(truncated), 2))
    return spaced + "…"


_HISTORY_COLUMNS = ["#", "Time", "Size", "Data"]


# ---------------------------------------------------------------------------
# History Table Model
# ---------------------------------------------------------------------------


class HistoryTableModel(QAbstractTableModel):
    """Table model for the packet history list (filtered by opcode+direction)."""

    def __init__(self):
        super().__init__()
        self._packets: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._packets)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_HISTORY_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HISTORY_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        packet = self._packets[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(packet.get("_row_number", row + 1))
            elif col == 1:
                return _format_timestamp(packet.get("timestamp", 0))
            elif col == 2:
                return str(packet.get("size", 0))
            elif col == 3:
                return _truncate_hex(packet.get("data", ""))
        elif role == Qt.ItemDataRole.FontRole:
            return _get_monospace_font(9)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(_COLOR_TEXT)
        elif role == Qt.ItemDataRole.UserRole:
            return packet
        return None

    def get_packet(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._packets):
            return self._packets[row]
        return None

    def set_packets(self, packets: list[dict]) -> None:
        """Replace all packets in the model."""
        self.beginResetModel()
        self._packets = list(packets)
        self.endResetModel()

    def append_packet(self, packet: dict) -> None:
        """Append a single packet to the end."""
        row = len(self._packets)
        self.beginInsertRows(QModelIndex(), row, row)
        self._packets.append(packet)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._packets.clear()
        self.endResetModel()


# ---------------------------------------------------------------------------
# History Panel Widget
# ---------------------------------------------------------------------------


class HistoryPanel(QWidget):
    """Shows chronological history of packets for a selected opcode+direction.

    Signals:
        packet_pinned(dict): Emitted when user clicks a specific history row
            to pin it in the detail panel.
        packet_unpinned(): Emitted when user deselects, meaning detail panel
            should revert to showing the latest packet for the opcode.
    """

    packet_pinned = pyqtSignal(dict)
    packet_unpinned = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._direction: Optional[str] = None
        self._opcode: Optional[str] = None
        self._all_packets: list[dict] = []  # All captured packets (reference)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Header label
        self._header = QLabel("Packet History")
        self._header.setFont(_get_monospace_font(9))
        self._header.setStyleSheet(
            "padding: 4px; background-color: #181825; color: #a6adc8;"
        )
        layout.addWidget(self._header)

        # Table
        self._model = HistoryTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setFont(_get_monospace_font(9))
        self._table.horizontalHeader().setFont(_get_monospace_font(9))

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._table)

        # Selection tracking
        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

        # Auto-scroll
        self._table.verticalScrollBar().rangeChanged.connect(
            self._on_range_changed
        )
        self._auto_scroll = True

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def set_opcode_filter(self, direction: str, opcode: str, all_packets: list[dict]) -> None:
        """Filter the history to show packets matching direction+opcode.

        Args:
            direction: "s2c" or "c2s"
            opcode: The opcode string (e.g. "0028")
            all_packets: Reference to the full chronological packet list.
        """
        self._direction = direction
        self._opcode = opcode
        self._all_packets = all_packets

        # Filter matching packets
        matching = [
            p for p in all_packets
            if p.get("direction") == direction and p.get("opcode") == opcode
        ]
        self._model.set_packets(matching)

        dir_label = "S→C" if direction == "s2c" else "C→S"
        self._header.setText(
            f"History: {dir_label} 0x{opcode.upper()} ({len(matching)} packets)"
        )

        # Clear selection (unpin)
        self._table.clearSelection()

    def append_if_matches(self, packet: dict) -> None:
        """If the packet matches the current filter, append it to history.

        Args:
            packet: A newly arrived packet dict.
        """
        if (self._direction is not None and
                packet.get("direction") == self._direction and
                packet.get("opcode") == self._opcode):
            self._model.append_packet(packet)
            # Update header count
            count = self._model.rowCount()
            dir_label = "S→C" if self._direction == "s2c" else "C→S"
            self._header.setText(
                f"History: {dir_label} 0x{self._opcode.upper()} ({count} packets)"
            )

    def clear_filter(self) -> None:
        """Clear the history panel (no opcode selected)."""
        self._direction = None
        self._opcode = None
        self._all_packets = []
        self._model.clear()
        self._header.setText("Packet History (select a packet in Fixed mode)")
        self._table.clearSelection()

    def has_pinned_selection(self) -> bool:
        """Return True if a specific history row is selected (pinned)."""
        return len(self._table.selectionModel().selectedRows()) > 0

    # ---------------------------------------------------------------------------
    # Slots
    # ---------------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            row = indexes[0].row()
            packet = self._model.get_packet(row)
            if packet:
                self.packet_pinned.emit(packet)
        else:
            self.packet_unpinned.emit()

    def _on_range_changed(self, _min: int, _max: int) -> None:
        if self._auto_scroll:
            self._table.scrollToBottom()
