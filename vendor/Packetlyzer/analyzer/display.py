"""Packet Display Module for the Packetlyzer Analyzer (PyQt6).

Provides a QTableView with a custom QAbstractTableModel for displaying
a scrollable packet list. Columns: #, Time (HH:MM:SS.mmm), Dir (S→C / C→S),
Opcode (0xXXXX), Size, Description. Supports auto-scroll, retention limits,
direction-based color coding, and text-based filtering via QSortFilterProxyModel.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.6, 6.7
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from analyzer.config import Config
from analyzer.decoder import PacketDecoder
from analyzer.packet_db import PacketDB


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

_COLOR_S2C_BG = QColor(35, 55, 85)       # Dark blue for server→client
_COLOR_C2S_BG = QColor(45, 70, 45)       # Dark green for client→server
_COLOR_S2C_TEXT = QColor(160, 200, 255)   # Light blue text
_COLOR_C2S_TEXT = QColor(160, 230, 160)   # Light green text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Get the preferred monospace font."""
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

_COLUMNS = ["#", "Time", "Dir", "Opcode", "Size", "Description", "Data"]


def _truncate_hex(data_hex: str, max_len: int = 48) -> str:
    """Truncate hex data for display, adding ellipsis if needed."""
    if len(data_hex) <= max_len:
        return " ".join(data_hex[i:i+2] for i in range(0, len(data_hex), 2))
    truncated = data_hex[:max_len]
    spaced = " ".join(truncated[i:i+2] for i in range(0, len(truncated), 2))
    return spaced + "…"


# ---------------------------------------------------------------------------
# Table Model
# ---------------------------------------------------------------------------


class PacketTableModel(QAbstractTableModel):
    """Custom table model for the packet list."""

    def __init__(self, config: Config, packet_db: PacketDB, decoder: Optional[PacketDecoder] = None):
        super().__init__()
        self._config = config
        self._packet_db = packet_db
        self._decoder = decoder
        self._packets: list[dict] = []
        self._row_counter: int = 0

    @property
    def packets(self) -> list[dict]:
        """Return the internal packet list."""
        return self._packets

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._packets)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        packet = self._packets[row]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_data(packet, col)
        elif role == Qt.ItemDataRole.BackgroundRole:
            direction = packet.get("direction", "")
            if direction == "s2c":
                return QBrush(_COLOR_S2C_BG)
            else:
                return QBrush(_COLOR_C2S_BG)
        elif role == Qt.ItemDataRole.ForegroundRole:
            direction = packet.get("direction", "")
            if direction == "s2c":
                return QBrush(_COLOR_S2C_TEXT)
            else:
                return QBrush(_COLOR_C2S_TEXT)
        elif role == Qt.ItemDataRole.FontRole:
            return _get_monospace_font(10)
        elif role == Qt.ItemDataRole.UserRole:
            # Return the packet dict for selection
            return packet
        elif role == Qt.ItemDataRole.UserRole + 1:
            # Return searchable text for filtering (opcode, description, decoded fields)
            return self._searchable_text(packet)

        return None

    def _display_data(self, packet: dict, col: int) -> str:
        if col == 0:
            return str(packet.get("_row_number", 0))
        elif col == 1:
            return _format_timestamp(packet.get("timestamp", 0))
        elif col == 2:
            return "S→C" if packet.get("direction") == "s2c" else "C→S"
        elif col == 3:
            opcode = packet.get("opcode", "0000")
            return f"0x{opcode.upper()}"
        elif col == 4:
            return str(packet.get("size", 0))
        elif col == 5:
            return self._get_description(packet)
        elif col == 6:
            return _truncate_hex(packet.get("data", ""))
        return ""

    def _get_description(self, packet: dict) -> str:
        direction = packet.get("direction", "")
        opcode_str = packet.get("opcode", "")
        try:
            opcode_int = int(opcode_str, 16)
        except (ValueError, TypeError):
            return "Unknown"
        definition = self._packet_db.get_definition(direction, opcode_int)
        if definition and definition.description:
            return definition.description
        return "Unknown"

    def _searchable_text(self, packet: dict) -> str:
        """Build a searchable string for filter matching."""
        parts = []
        opcode_str = packet.get("opcode", "")
        parts.append(opcode_str)
        parts.append(f"0x{opcode_str}")
        parts.append(self._get_description(packet))

        # Add decoded field values if decoder is available
        if self._decoder is not None:
            try:
                direction = packet.get("direction", "")
                opcode_int = int(opcode_str, 16)
                data_hex = packet.get("data", "")
                raw_bytes = bytes.fromhex(data_hex)
                decoded = self._decoder.decode(direction, opcode_int, raw_bytes)
                for decoded_field in decoded.fields:
                    parts.append(decoded_field.display_value)
            except (ValueError, TypeError):
                pass

        return " ".join(parts)

    def append_packet(self, packet: dict) -> None:
        """Append a packet, enforcing retention limit."""
        self._row_counter += 1
        packet["_row_number"] = self._row_counter

        # Evict from head if over limit
        max_packets = self._config.max_packets
        if len(self._packets) >= max_packets:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._packets.pop(0)
            self.endRemoveRows()

        # Append new packet
        row = len(self._packets)
        self.beginInsertRows(QModelIndex(), row, row)
        self._packets.append(packet)
        self.endInsertRows()

    def get_packet(self, row: int) -> Optional[dict]:
        """Get packet at the given row index."""
        if 0 <= row < len(self._packets):
            return self._packets[row]
        return None

    def clear(self) -> None:
        """Clear all packets."""
        self.beginResetModel()
        self._packets.clear()
        self._row_counter = 0
        self.endResetModel()

    def set_max_packets(self, value: int) -> None:
        """Update the maximum packet retention limit."""
        self._config.max_packets = value
        # Trim if current list exceeds new limit
        while len(self._packets) > value:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._packets.pop(0)
            self.endRemoveRows()


# ---------------------------------------------------------------------------
# Fixed Position Table Model
# ---------------------------------------------------------------------------

_FIXED_COLUMNS = ["Dir", "Opcode", "Description", "Count", "Last Time", "Size", "Data"]


class FixedPositionModel(QAbstractTableModel):
    """Table model for Fixed Position display mode.

    One row per unique (direction, opcode) pair. Each row updates in-place
    with the latest packet data for that opcode.
    """

    def __init__(self, config: Config, packet_db: PacketDB, decoder: Optional[PacketDecoder] = None):
        super().__init__()
        self._config = config
        self._packet_db = packet_db
        self._decoder = decoder
        self._keys: list[tuple[str, str]] = []
        self._entries: dict[tuple[str, str], dict] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._keys)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_FIXED_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _FIXED_COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        key = self._keys[row]
        entry = self._entries[key]
        packet = entry["packet"]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return "S→C" if packet.get("direction") == "s2c" else "C→S"
            elif col == 1:
                return f"0x{packet.get('opcode', '0000').upper()}"
            elif col == 2:
                return self._get_description(key[0], key[1])
            elif col == 3:
                return str(entry["count"])
            elif col == 4:
                return _format_timestamp(packet.get("timestamp", 0))
            elif col == 5:
                return str(packet.get("size", 0))
            elif col == 6:
                return _truncate_hex(packet.get("data", ""))
        elif role == Qt.ItemDataRole.BackgroundRole:
            return QBrush(_COLOR_S2C_BG if key[0] == "s2c" else _COLOR_C2S_BG)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(_COLOR_S2C_TEXT if key[0] == "s2c" else _COLOR_C2S_TEXT)
        elif role == Qt.ItemDataRole.FontRole:
            return _get_monospace_font(10)
        elif role == Qt.ItemDataRole.UserRole:
            return packet
        elif role == Qt.ItemDataRole.UserRole + 1:
            return f"{key[1]} 0x{key[1]} {self._get_description(key[0], key[1])} {packet.get('data', '')}"
        return None

    def _get_description(self, direction: str, opcode_str: str) -> str:
        try:
            opcode_int = int(opcode_str, 16)
        except (ValueError, TypeError):
            return "Unknown"
        definition = self._packet_db.get_definition(direction, opcode_int)
        return definition.description if definition and definition.description else "Unknown"

    def update_packet(self, packet: dict) -> None:
        """Update or insert a packet into the fixed position model."""
        key = (packet.get("direction", ""), packet.get("opcode", ""))
        if key in self._entries:
            self._entries[key]["packet"] = packet
            self._entries[key]["count"] += 1
            row = self._keys.index(key)
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(_FIXED_COLUMNS) - 1))
        else:
            row = len(self._keys)
            self.beginInsertRows(QModelIndex(), row, row)
            self._keys.append(key)
            self._entries[key] = {"packet": packet, "count": 1}
            self.endInsertRows()

    def get_packet(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._keys):
            return self._entries[self._keys[row]]["packet"]
        return None

    def clear(self) -> None:
        self.beginResetModel()
        self._keys.clear()
        self._entries.clear()
        self.endResetModel()


# ---------------------------------------------------------------------------
# Filter Proxy Model
# ---------------------------------------------------------------------------


class PacketFilterProxy(QSortFilterProxyModel):
    """Filters packet rows by matching against searchable text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""

    @property
    def filter_text(self) -> str:
        return self._filter_text

    @filter_text.setter
    def filter_text(self, value: str) -> None:
        self._filter_text = value.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._filter_text:
            return True
        index = self.sourceModel().index(source_row, 0, source_parent)
        searchable = self.sourceModel().data(index, Qt.ItemDataRole.UserRole + 1)
        if searchable is None:
            return True
        return self._filter_text in searchable.lower()


# ---------------------------------------------------------------------------
# Packet List Widget
# ---------------------------------------------------------------------------


class PacketListWidget(QWidget):
    """Widget containing filter input + packet table view.

    Emits packet_selected(dict) when a row is clicked.
    """

    packet_selected = pyqtSignal(dict)
    packet_updated = pyqtSignal(dict)  # Detail-only update (no history rebuild)

    def __init__(self, config: Config, packet_db: PacketDB, decoder: Optional[PacketDecoder] = None, parent=None):
        super().__init__(parent)
        self._config = config
        self._packet_db = packet_db
        self._decoder = decoder
        self._auto_scroll = config.auto_scroll
        self._user_scrolled_up = False
        self._mode = "chronological"

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Top bar: mode selector + filter
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(4, 2, 4, 2)
        top_bar.setSpacing(8)

        mode_label = QLabel("Mode:")
        mode_label.setFont(_get_monospace_font(9))
        top_bar.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Chronological", "Fixed Position"])
        self._mode_combo.setFont(_get_monospace_font(9))
        self._mode_combo.setFixedWidth(140)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        top_bar.addWidget(self._mode_combo)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter (opcode, description, data)...")
        self._filter_input.setFont(_get_monospace_font(9))
        if config.filter_string:
            self._filter_input.setText(config.filter_string)
        top_bar.addWidget(self._filter_input)

        layout.addLayout(top_bar)

        # Chronological model
        self._chrono_model = PacketTableModel(config, packet_db, decoder)
        self._chrono_proxy = PacketFilterProxy(self)
        self._chrono_proxy.setSourceModel(self._chrono_model)
        if config.filter_string:
            self._chrono_proxy.filter_text = config.filter_string

        # Fixed position model
        self._fixed_model = FixedPositionModel(config, packet_db, decoder)
        self._fixed_proxy = PacketFilterProxy(self)
        self._fixed_proxy.setSourceModel(self._fixed_model)
        if config.filter_string:
            self._fixed_proxy.filter_text = config.filter_string

        # Table view
        self._table = QTableView()
        self._table.setModel(self._chrono_proxy)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setFont(_get_monospace_font(10))
        self._table.horizontalHeader().setFont(_get_monospace_font(9))

        # Column sizing
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.resizeSection(5, 160)

        layout.addWidget(self._table)

        # Connections
        self._filter_input.textChanged.connect(self._on_filter_changed)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Track scrollbar for auto-scroll
        scrollbar = self._table.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)
        scrollbar.rangeChanged.connect(self._on_range_changed)

    # ---------------------------------------------------------------------------
    # Public API (compatible with exporter expectations)
    # ---------------------------------------------------------------------------

    @property
    def visible_packets(self) -> list[dict]:
        """Return the list of packets visible under the current filter."""
        proxy = self._chrono_proxy if self._mode == "chronological" else self._fixed_proxy
        model = self._chrono_model if self._mode == "chronological" else self._fixed_model
        packets = []
        for row in range(proxy.rowCount()):
            source_index = proxy.mapToSource(proxy.index(row, 0))
            pkt = model.get_packet(source_index.row())
            if pkt:
                packets.append(pkt)
        return packets

    @property
    def filter_string(self) -> str:
        """Return the current filter string."""
        return self._filter_input.text()

    @filter_string.setter
    def filter_string(self, value: str) -> None:
        """Set the filter string."""
        self._filter_input.setText(value)

    @property
    def model(self) -> PacketTableModel:
        """Return the underlying chronological table model."""
        return self._chrono_model

    def append_packet(self, packet: dict) -> None:
        """Append a packet to both models."""
        self._chrono_model.append_packet(packet)
        self._fixed_model.update_packet(packet)

        # In fixed mode, auto-update detail panel if selected opcode matches
        if self._mode == "fixed":
            self._auto_update_fixed_selection(packet)

    def clear_packets(self) -> None:
        """Clear all packets from both models."""
        self._chrono_model.clear()
        self._fixed_model.clear()

    def _auto_update_fixed_selection(self, packet: dict) -> None:
        """In fixed mode, update detail panel if the selected opcode matches.

        Uses packet_updated signal to avoid rebuilding the history panel
        (history is already updated via append_if_matches in _poll_queue).
        """
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        proxy_index = indexes[0]
        source_index = self._fixed_proxy.mapToSource(proxy_index)
        selected_pkt = self._fixed_model.get_packet(source_index.row())
        if selected_pkt is None:
            return
        if (selected_pkt.get("opcode") == packet.get("opcode") and
                selected_pkt.get("direction") == packet.get("direction")):
            self.packet_updated.emit(selected_pkt)

    # ---------------------------------------------------------------------------
    # Slots
    # ---------------------------------------------------------------------------

    def _on_filter_changed(self, text: str) -> None:
        self._chrono_proxy.filter_text = text
        self._fixed_proxy.filter_text = text
        self._config.filter_string = text

    def _on_mode_changed(self, index: int) -> None:
        """Switch between Chronological and Fixed Position modes."""
        new_mode = "chronological" if index == 0 else "fixed"
        if new_mode == self._mode:
            return
        self._mode = new_mode

        # Disconnect old selection model
        try:
            self._table.selectionModel().selectionChanged.disconnect(self._on_selection_changed)
        except (TypeError, RuntimeError):
            pass

        # Switch model on the table view
        if self._mode == "chronological":
            self._table.setModel(self._chrono_proxy)
        else:
            self._table.setModel(self._fixed_proxy)

        # Reconnect selection
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Reconfigure column sizes for the new model's column count
        header = self._table.horizontalHeader()
        col_count = self._table.model().columnCount()
        for i in range(col_count - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        if col_count > 0:
            header.setSectionResizeMode(col_count - 1, QHeaderView.ResizeMode.Stretch)

    def _on_selection_changed(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            proxy_index = indexes[0]
            if self._mode == "chronological":
                source_index = self._chrono_proxy.mapToSource(proxy_index)
                packet = self._chrono_model.get_packet(source_index.row())
            else:
                source_index = self._fixed_proxy.mapToSource(proxy_index)
                packet = self._fixed_model.get_packet(source_index.row())
            if packet:
                self.packet_selected.emit(packet)

    def _on_scroll_changed(self, value: int) -> None:
        scrollbar = self._table.verticalScrollBar()
        at_bottom = value >= scrollbar.maximum() - 1
        if at_bottom:
            self._user_scrolled_up = False
            self._auto_scroll = True
        else:
            # User scrolled up
            self._user_scrolled_up = True
            self._auto_scroll = False

    def _on_range_changed(self, _min: int, _max: int) -> None:
        """Auto-scroll to bottom when new rows arrive (chronological mode only)."""
        if self._mode == "chronological" and self._auto_scroll and not self._user_scrolled_up:
            self._table.scrollToBottom()
