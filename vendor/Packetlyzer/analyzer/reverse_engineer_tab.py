"""Reverse Engineer Tab for the Packetlyzer Analyzer.

Provides a signal definition workbench where users can select byte ranges
from the hex dump, define what the data represents (type, scaling, enum states),
and save signal definitions to the JSON database.
"""

from __future__ import annotations

import struct
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analyzer.signal_db import SignalDB, SignalDefinition


def _get_monospace_font(size: int = 9) -> QFont:
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


_DATA_TYPES = [
    "uint8", "uint16", "uint32", "int8", "int16", "int32",
    "float", "bitfield", "enum", "string",
]

_BYTE_ORDERS = ["little", "big"]


class ReverseEngineerTab(QWidget):
    """Reverse engineering workbench tab.

    Displays selection context from the hex dump, provides a signal definition
    form, and manages the list of saved signals for the current opcode.

    Signals:
        signal_saved(): Emitted when a signal is saved (triggers re-decode).
        signal_deleted(): Emitted when a signal is deleted.
    """

    signal_saved = pyqtSignal()
    signal_deleted = pyqtSignal()

    def __init__(self, signal_db: SignalDB, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._signal_db = signal_db
        self._current_direction: str = ""
        self._current_opcode: str = ""
        self._current_packet_data: bytes = b""
        self._editing_signal: Optional[SignalDefinition] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Selection Context ---
        ctx_group = QGroupBox("Selection Context")
        ctx_group.setFont(_get_monospace_font(9))
        ctx_layout = QHBoxLayout(ctx_group)
        ctx_layout.setSpacing(12)

        self._ctx_opcode_label = QLabel("Opcode: —")
        self._ctx_opcode_label.setFont(_get_monospace_font(9))
        ctx_layout.addWidget(self._ctx_opcode_label)

        self._ctx_offset_label = QLabel("Offset: —")
        self._ctx_offset_label.setFont(_get_monospace_font(9))
        ctx_layout.addWidget(self._ctx_offset_label)

        self._ctx_length_label = QLabel("Length: —")
        self._ctx_length_label.setFont(_get_monospace_font(9))
        ctx_layout.addWidget(self._ctx_length_label)

        self._ctx_raw_label = QLabel("Raw: —")
        self._ctx_raw_label.setFont(_get_monospace_font(9))
        ctx_layout.addWidget(self._ctx_raw_label)

        self._ctx_value_label = QLabel("Value: —")
        self._ctx_value_label.setFont(_get_monospace_font(9))
        ctx_layout.addWidget(self._ctx_value_label)

        ctx_layout.addStretch()
        layout.addWidget(ctx_group)

        # --- Signal Definition Form + Saved Signals side by side ---
        mid_layout = QHBoxLayout()

        # Left: Signal form
        form_group = QGroupBox("Signal Definition")
        form_group.setFont(_get_monospace_font(9))
        form_layout = QVBoxLayout(form_group)
        form_layout.setSpacing(4)

        # Row 1: Name
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Name:"))
        self._name_input = QLineEdit()
        self._name_input.setFont(_get_monospace_font(9))
        self._name_input.setPlaceholderText("Signal name")
        r1.addWidget(self._name_input)
        form_layout.addLayout(r1)

        # Row 2: Offset, Length, Type, Byte Order
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Offset:"))
        self._offset_spin = QSpinBox()
        self._offset_spin.setRange(0, 4096)
        self._offset_spin.setFont(_get_monospace_font(9))
        self._offset_spin.setFixedWidth(70)
        r2.addWidget(self._offset_spin)

        r2.addWidget(QLabel("Len:"))
        self._length_spin = QSpinBox()
        self._length_spin.setRange(1, 256)
        self._length_spin.setFont(_get_monospace_font(9))
        self._length_spin.setFixedWidth(60)
        r2.addWidget(self._length_spin)

        r2.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(_DATA_TYPES)
        self._type_combo.setFont(_get_monospace_font(9))
        self._type_combo.setFixedWidth(90)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        r2.addWidget(self._type_combo)

        r2.addWidget(QLabel("Order:"))
        self._order_combo = QComboBox()
        self._order_combo.addItems(_BYTE_ORDERS)
        self._order_combo.setFont(_get_monospace_font(9))
        self._order_combo.setFixedWidth(70)
        r2.addWidget(self._order_combo)

        r2.addStretch()
        form_layout.addLayout(r2)

        # Row 3: Bitfield options (hidden unless bitfield selected)
        self._bit_row = QHBoxLayout()
        self._bit_row_widget = QWidget()
        bit_inner = QHBoxLayout(self._bit_row_widget)
        bit_inner.setContentsMargins(0, 0, 0, 0)
        bit_inner.addWidget(QLabel("Bit Offset:"))
        self._bit_offset_spin = QSpinBox()
        self._bit_offset_spin.setRange(0, 63)
        self._bit_offset_spin.setFont(_get_monospace_font(9))
        self._bit_offset_spin.setFixedWidth(60)
        bit_inner.addWidget(self._bit_offset_spin)
        bit_inner.addWidget(QLabel("Bit Count:"))
        self._bit_count_spin = QSpinBox()
        self._bit_count_spin.setRange(1, 32)
        self._bit_count_spin.setFont(_get_monospace_font(9))
        self._bit_count_spin.setFixedWidth(60)
        bit_inner.addWidget(self._bit_count_spin)
        bit_inner.addStretch()
        self._bit_row_widget.setVisible(False)
        form_layout.addWidget(self._bit_row_widget)

        # Row 4: Scale, Offset, Unit (for analog/numeric types)
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Scale:"))
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(-1e9, 1e9)
        self._scale_spin.setDecimals(6)
        self._scale_spin.setValue(1.0)
        self._scale_spin.setFont(_get_monospace_font(9))
        self._scale_spin.setFixedWidth(90)
        r4.addWidget(self._scale_spin)

        r4.addWidget(QLabel("+"))
        self._offset_val_spin = QDoubleSpinBox()
        self._offset_val_spin.setRange(-1e9, 1e9)
        self._offset_val_spin.setDecimals(4)
        self._offset_val_spin.setValue(0.0)
        self._offset_val_spin.setFont(_get_monospace_font(9))
        self._offset_val_spin.setFixedWidth(90)
        r4.addWidget(self._offset_val_spin)

        r4.addWidget(QLabel("Unit:"))
        self._unit_input = QLineEdit()
        self._unit_input.setFont(_get_monospace_font(9))
        self._unit_input.setFixedWidth(80)
        self._unit_input.setPlaceholderText("e.g. HP")
        r4.addWidget(self._unit_input)
        r4.addStretch()
        form_layout.addLayout(r4)

        # Row 5: Enum table (visible when type=enum)
        self._enum_group = QGroupBox("Value Mapping (Enum/State)")
        self._enum_group.setFont(_get_monospace_font(9))
        self._enum_group.setVisible(False)
        enum_layout = QVBoxLayout(self._enum_group)
        self._enum_table = QTableWidget(0, 2)
        self._enum_table.setHorizontalHeaderLabels(["Value", "Label"])
        self._enum_table.setFont(_get_monospace_font(9))
        self._enum_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._enum_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._enum_table.horizontalHeader().resizeSection(0, 60)
        self._enum_table.setMaximumHeight(120)
        enum_layout.addWidget(self._enum_table)
        enum_btn_row = QHBoxLayout()
        add_enum_btn = QPushButton("Add Row")
        add_enum_btn.setFixedWidth(70)
        add_enum_btn.clicked.connect(self._add_enum_row)
        enum_btn_row.addWidget(add_enum_btn)
        del_enum_btn = QPushButton("Del Row")
        del_enum_btn.setFixedWidth(70)
        del_enum_btn.clicked.connect(self._del_enum_row)
        enum_btn_row.addWidget(del_enum_btn)
        enum_btn_row.addStretch()
        enum_layout.addLayout(enum_btn_row)
        form_layout.addWidget(self._enum_group)

        # Row 6: Comment
        r6 = QHBoxLayout()
        r6.addWidget(QLabel("Comment:"))
        self._comment_input = QLineEdit()
        self._comment_input.setFont(_get_monospace_font(9))
        self._comment_input.setPlaceholderText("Notes about this signal")
        r6.addWidget(self._comment_input)
        form_layout.addLayout(r6)

        # Row 7: Buttons
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save Signal")
        self._save_btn.setFixedWidth(100)
        self._save_btn.setStyleSheet(
            "QPushButton { background-color: #40a02b; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #4cb533; }"
        )
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        self._clear_btn = QPushButton("Clear Form")
        self._clear_btn.setFixedWidth(90)
        self._clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(self._clear_btn)

        btn_row.addStretch()
        form_layout.addLayout(btn_row)

        mid_layout.addWidget(form_group, stretch=2)

        # Right: Saved signals list
        signals_group = QGroupBox("Saved Signals (this opcode)")
        signals_group.setFont(_get_monospace_font(9))
        signals_layout = QVBoxLayout(signals_group)

        self._signals_list = QListWidget()
        self._signals_list.setFont(_get_monospace_font(9))
        self._signals_list.itemClicked.connect(self._on_signal_clicked)
        signals_layout.addWidget(self._signals_list)

        sig_btn_row = QHBoxLayout()
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedWidth(60)
        self._edit_btn.clicked.connect(self._on_edit)
        sig_btn_row.addWidget(self._edit_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setFixedWidth(60)
        self._delete_btn.setStyleSheet(
            "QPushButton { background-color: #d20f39; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #e0164a; }"
        )
        self._delete_btn.clicked.connect(self._on_delete)
        sig_btn_row.addWidget(self._delete_btn)
        sig_btn_row.addStretch()
        signals_layout.addLayout(sig_btn_row)

        mid_layout.addWidget(signals_group, stretch=1)

        layout.addWidget(self._build_mid_widget(mid_layout))

    def _build_mid_widget(self, layout: QHBoxLayout) -> QWidget:
        """Wrap the mid layout in a widget."""
        w = QWidget()
        w.setLayout(layout)
        return w

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def set_packet_context(self, direction: str, opcode: str, data: bytes) -> None:
        """Set the current packet context (called when a packet is selected).

        Args:
            direction: "s2c" or "c2s"
            opcode: Opcode hex string (e.g. "0027")
            data: Raw packet bytes
        """
        self._current_direction = direction
        self._current_opcode = opcode
        self._current_packet_data = data

        dir_label = "S\u2192C" if direction == "s2c" else "C\u2192S"
        self._ctx_opcode_label.setText(f"Opcode: {dir_label} 0x{opcode.upper()}")

        # Refresh the saved signals list for this opcode
        self._refresh_signals_list()

    def set_selection(self, offset: int, length: int) -> None:
        """Set the currently selected byte range (from hex dump selection).

        Args:
            offset: Starting byte offset.
            length: Number of bytes selected.
        """
        self._ctx_offset_label.setText(f"Offset: 0x{offset:02X}")
        self._ctx_length_label.setText(f"Length: {length}")

        # Show raw hex for the selection
        if offset + length <= len(self._current_packet_data):
            raw = self._current_packet_data[offset:offset + length]
            hex_str = " ".join(f"{b:02X}" for b in raw)
            self._ctx_raw_label.setText(f"Raw: {hex_str}")

            # Show interpreted value based on length
            value_str = self._interpret_value(raw, "little")
            self._ctx_value_label.setText(f"Value: {value_str}")
        else:
            self._ctx_raw_label.setText("Raw: (out of range)")
            self._ctx_value_label.setText("Value: —")

        # Auto-fill the form offset/length
        self._offset_spin.setValue(offset)
        self._length_spin.setValue(length)

        # Auto-select data type based on length
        if length == 1:
            self._type_combo.setCurrentText("uint8")
        elif length == 2:
            self._type_combo.setCurrentText("uint16")
        elif length == 4:
            self._type_combo.setCurrentText("uint32")

    # ---------------------------------------------------------------------------
    # Internal
    # ---------------------------------------------------------------------------

    def _interpret_value(self, raw: bytes, byte_order: str) -> str:
        """Interpret raw bytes as common types for display."""
        parts = []
        bo = "<" if byte_order == "little" else ">"
        if len(raw) == 1:
            parts.append(f"{raw[0]} (0x{raw[0]:02X})")
        elif len(raw) == 2:
            val = struct.unpack(f"{bo}H", raw)[0]
            parts.append(f"{val} (0x{val:04X})")
        elif len(raw) == 4:
            val_u = struct.unpack(f"{bo}I", raw)[0]
            val_f = struct.unpack(f"{bo}f", raw)[0]
            parts.append(f"u32={val_u} (0x{val_u:08X})")
            if -1e10 < val_f < 1e10 and val_f != 0:
                parts.append(f"f32={val_f:.4f}")
        else:
            # Just show first few bytes as uint
            parts.append(" ".join(f"{b:02X}" for b in raw[:8]))
        return " | ".join(parts)

    def _on_type_changed(self, text: str) -> None:
        """Show/hide bitfield and enum options based on selected type."""
        self._bit_row_widget.setVisible(text == "bitfield")
        self._enum_group.setVisible(text == "enum")

    def _add_enum_row(self) -> None:
        """Add a row to the enum table."""
        row = self._enum_table.rowCount()
        self._enum_table.insertRow(row)
        self._enum_table.setItem(row, 0, QTableWidgetItem(str(row)))
        self._enum_table.setItem(row, 1, QTableWidgetItem(""))

    def _del_enum_row(self) -> None:
        """Delete the selected row from the enum table."""
        row = self._enum_table.currentRow()
        if row >= 0:
            self._enum_table.removeRow(row)

    def _clear_form(self) -> None:
        """Reset the form to empty state."""
        self._name_input.clear()
        self._offset_spin.setValue(0)
        self._length_spin.setValue(1)
        self._type_combo.setCurrentIndex(0)
        self._order_combo.setCurrentIndex(0)
        self._bit_offset_spin.setValue(0)
        self._bit_count_spin.setValue(1)
        self._scale_spin.setValue(1.0)
        self._offset_val_spin.setValue(0.0)
        self._unit_input.clear()
        self._comment_input.clear()
        self._enum_table.setRowCount(0)
        self._editing_signal = None

    def _on_save(self) -> None:
        """Save the current form as a signal definition."""
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a signal name.")
            return

        if not self._current_opcode:
            QMessageBox.warning(self, "No Packet", "Select a packet first.")
            return

        # Build enum map if type is enum
        enum_map = None
        if self._type_combo.currentText() == "enum":
            enum_map = {}
            for row in range(self._enum_table.rowCount()):
                val_item = self._enum_table.item(row, 0)
                label_item = self._enum_table.item(row, 1)
                if val_item and label_item:
                    enum_map[val_item.text().strip()] = label_item.text().strip()

        signal = SignalDefinition(
            name=name,
            direction=self._current_direction,
            opcode=self._current_opcode,
            offset=self._offset_spin.value(),
            length=self._length_spin.value(),
            data_type=self._type_combo.currentText(),
            byte_order=self._order_combo.currentText(),
            bit_offset=self._bit_offset_spin.value() if self._type_combo.currentText() == "bitfield" else None,
            bit_count=self._bit_count_spin.value() if self._type_combo.currentText() == "bitfield" else None,
            enum_map=enum_map,
            scale=self._scale_spin.value(),
            offset_val=self._offset_val_spin.value(),
            unit=self._unit_input.text().strip(),
            comment=self._comment_input.text().strip(),
        )

        self._signal_db.add_signal(signal)
        self._refresh_signals_list()
        self._editing_signal = None
        self.signal_saved.emit()

    def _on_signal_clicked(self, item: QListWidgetItem) -> None:
        """Select a signal in the list."""
        pass  # Selection tracked for edit/delete

    def _on_edit(self) -> None:
        """Load the selected signal into the form for editing."""
        item = self._signals_list.currentItem()
        if not item:
            return

        sig: SignalDefinition = item.data(Qt.ItemDataRole.UserRole)
        if not sig:
            return

        self._editing_signal = sig
        self._name_input.setText(sig.name)
        self._offset_spin.setValue(sig.offset)
        self._length_spin.setValue(sig.length)
        self._type_combo.setCurrentText(sig.data_type)
        self._order_combo.setCurrentText(sig.byte_order)

        if sig.bit_offset is not None:
            self._bit_offset_spin.setValue(sig.bit_offset)
        if sig.bit_count is not None:
            self._bit_count_spin.setValue(sig.bit_count)

        self._scale_spin.setValue(sig.scale)
        self._offset_val_spin.setValue(sig.offset_val)
        self._unit_input.setText(sig.unit)
        self._comment_input.setText(sig.comment)

        # Load enum map
        self._enum_table.setRowCount(0)
        if sig.enum_map:
            for val, label in sig.enum_map.items():
                row = self._enum_table.rowCount()
                self._enum_table.insertRow(row)
                self._enum_table.setItem(row, 0, QTableWidgetItem(str(val)))
                self._enum_table.setItem(row, 1, QTableWidgetItem(str(label)))

    def _on_delete(self) -> None:
        """Delete the selected signal."""
        item = self._signals_list.currentItem()
        if not item:
            return

        sig: SignalDefinition = item.data(Qt.ItemDataRole.UserRole)
        if not sig:
            return

        reply = QMessageBox.question(
            self, "Delete Signal",
            f"Delete signal '{sig.name}' at offset 0x{sig.offset:02X}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._signal_db.remove_signal(sig)
            self._refresh_signals_list()
            self.signal_deleted.emit()

    def _refresh_signals_list(self) -> None:
        """Refresh the saved signals list for the current opcode."""
        self._signals_list.clear()
        if not self._current_opcode:
            return

        signals = self._signal_db.get_signals_for_opcode(
            self._current_direction, self._current_opcode
        )
        for sig in signals:
            label = f"0x{sig.offset:02X} [{sig.length}B] {sig.data_type}: {sig.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, sig)
            self._signals_list.addItem(item)


