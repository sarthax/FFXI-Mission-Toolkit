"""Live Database Editor for the Packetlyzer Analyzer (PyQt6).

Provides a QDockWidget for creating and modifying packet definitions
at runtime. Supports field row CRUD (add, reorder, delete), pre-population
from selected packets, confirmation dialogs for unsaved changes, validation,
and persistence to XML with decoder reload.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 12.6
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analyzer.lookup import LookupManager
from analyzer.packet_db import FieldDefinition, PacketDB, PacketDefinition

if TYPE_CHECKING:
    from analyzer.decoder import PacketDecoder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported field types (from Requirement 7.2 / 11.6)
# ---------------------------------------------------------------------------

SUPPORTED_FIELD_TYPES = [
    "byte", "uint16", "uint32", "int8", "int16", "int32",
    "float", "bits", "t", "a", "pos", "dir", "ms", "ip",
]

# Regex for valid field names: 1-64 alphanumeric/underscore characters
_NAME_PATTERN = re.compile(r'^[A-Za-z0-9_]{1,64}$')

_MAX_FIELD_ROWS = 256
_MAX_DESCRIPTION_CHARS = 128


def _get_monospace_font(size: int = 10) -> QFont:
    """Get the preferred monospace font."""
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


class LiveEditorWidget(QWidget):
    """Inner widget content for the Live Editor dock."""

    def __init__(
        self,
        packet_db: PacketDB,
        lookup_mgr: LookupManager,
        decoder: Optional["PacketDecoder"] = None,
        on_redecode: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._packet_db = packet_db
        self._lookup_mgr = lookup_mgr
        self._decoder = decoder
        self._on_redecode = on_redecode
        self._has_unsaved_changes = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Opcode input ---
        form = QFormLayout()
        form.setSpacing(4)

        self._opcode_input = QLineEdit()
        self._opcode_input.setPlaceholderText("e.g. 0028")
        self._opcode_input.setMaxLength(4)
        self._opcode_input.textChanged.connect(self._mark_dirty)
        form.addRow("Opcode (hex):", self._opcode_input)

        # --- Description input ---
        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText("Packet description")
        self._desc_input.setMaxLength(_MAX_DESCRIPTION_CHARS)
        self._desc_input.textChanged.connect(self._mark_dirty)
        form.addRow("Description:", self._desc_input)

        # --- Direction combo ---
        self._dir_combo = QComboBox()
        self._dir_combo.addItems(["s2c", "c2s"])
        self._dir_combo.currentTextChanged.connect(self._mark_dirty)
        form.addRow("Direction:", self._dir_combo)

        layout.addLayout(form)

        # --- Field table ---
        self._field_table = QTableWidget(0, 5)
        self._field_table.setHorizontalHeaderLabels(["Type", "Name", "Pos", "Bits", "Lookup"])
        self._field_table.setFont(_get_monospace_font(9))
        self._field_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._field_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._field_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._field_table)

        # --- Field buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_field_row)
        btn_layout.addWidget(add_btn)

        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_field_row)
        btn_layout.addWidget(del_btn)

        up_btn = QPushButton("Move Up")
        up_btn.clicked.connect(self._move_field_up)
        btn_layout.addWidget(up_btn)

        down_btn = QPushButton("Move Down")
        down_btn.clicked.connect(self._move_field_down)
        btn_layout.addWidget(down_btn)

        layout.addLayout(btn_layout)

        # --- Error label ---
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ff6464; font-size: 9pt;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # --- Save button ---
        self._save_btn = QPushButton("Save Definition")
        self._save_btn.setStyleSheet(
            "QPushButton { background-color: #327878; color: white; padding: 6px; }"
            "QPushButton:hover { background-color: #3c9090; }"
        )
        self._save_btn.clicked.connect(self._save)
        layout.addWidget(self._save_btn)

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    @property
    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    def populate_from_packet(self, packet: dict) -> None:
        """Pre-populate editor from a selected packet (Req 11.2).

        If there are unsaved changes, shows a confirmation dialog first.
        """
        if self._has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Discard Changes",
                "Discard unsaved changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._load_packet(packet)

    # ---------------------------------------------------------------------------
    # Internal state
    # ---------------------------------------------------------------------------

    def _mark_dirty(self) -> None:
        self._has_unsaved_changes = True

    def _load_packet(self, packet: dict) -> None:
        """Load a packet's definition into the editor fields."""
        direction = packet.get("direction", "s2c")
        opcode_str = packet.get("opcode", "0000")

        self._opcode_input.setText(opcode_str)
        self._dir_combo.setCurrentText(direction)
        self._has_unsaved_changes = False

        # Look up existing definition
        try:
            opcode_int = int(opcode_str, 16)
        except (ValueError, TypeError):
            opcode_int = 0

        definition = self._packet_db.get_definition(direction, opcode_int)

        # Block signals while loading to avoid marking dirty
        self._opcode_input.blockSignals(True)
        self._desc_input.blockSignals(True)
        self._dir_combo.blockSignals(True)

        if definition:
            self._desc_input.setText(definition.description[:_MAX_DESCRIPTION_CHARS])
            self._populate_field_table(definition.fields)
        else:
            self._desc_input.setText("")
            self._field_table.setRowCount(0)

        self._opcode_input.blockSignals(False)
        self._desc_input.blockSignals(False)
        self._dir_combo.blockSignals(False)

        self._has_unsaved_changes = False
        self._error_label.setVisible(False)

    def _populate_field_table(self, fields: list) -> None:
        """Fill the field table from a list of FieldDefinition objects."""
        self._field_table.setRowCount(len(fields))
        lookup_names = [""] + self._lookup_mgr.get_table_names()

        for row, f in enumerate(fields):
            # Type combo
            type_combo = QComboBox()
            type_combo.addItems(SUPPORTED_FIELD_TYPES)
            type_combo.setCurrentText(f.type)
            type_combo.currentTextChanged.connect(self._mark_dirty)
            self._field_table.setCellWidget(row, 0, type_combo)

            # Name
            name_item = QTableWidgetItem(f.name)
            self._field_table.setItem(row, 1, name_item)

            # Pos
            pos_item = QTableWidgetItem(str(f.pos))
            self._field_table.setItem(row, 2, pos_item)

            # Bits
            bits_str = str(f.bits) if f.bits is not None else ""
            bits_item = QTableWidgetItem(bits_str)
            self._field_table.setItem(row, 3, bits_item)

            # Lookup combo
            lookup_combo = QComboBox()
            lookup_combo.addItems(lookup_names)
            lookup_combo.setCurrentText(f.lookup if f.lookup else "")
            lookup_combo.currentTextChanged.connect(self._mark_dirty)
            self._field_table.setCellWidget(row, 4, lookup_combo)

    # ---------------------------------------------------------------------------
    # Field row operations (Req 11.9)
    # ---------------------------------------------------------------------------

    def _add_field_row(self) -> None:
        if self._field_table.rowCount() >= _MAX_FIELD_ROWS:
            QMessageBox.warning(self, "Limit", f"Maximum {_MAX_FIELD_ROWS} fields allowed.")
            return

        row = self._field_table.rowCount()
        self._field_table.insertRow(row)
        lookup_names = [""] + self._lookup_mgr.get_table_names()

        # Type combo
        type_combo = QComboBox()
        type_combo.addItems(SUPPORTED_FIELD_TYPES)
        type_combo.currentTextChanged.connect(self._mark_dirty)
        self._field_table.setCellWidget(row, 0, type_combo)

        # Name, Pos, Bits
        self._field_table.setItem(row, 1, QTableWidgetItem(""))
        self._field_table.setItem(row, 2, QTableWidgetItem("0"))
        self._field_table.setItem(row, 3, QTableWidgetItem(""))

        # Lookup combo
        lookup_combo = QComboBox()
        lookup_combo.addItems(lookup_names)
        lookup_combo.currentTextChanged.connect(self._mark_dirty)
        self._field_table.setCellWidget(row, 4, lookup_combo)

        self._mark_dirty()

    def _delete_field_row(self) -> None:
        row = self._field_table.currentRow()
        if row >= 0:
            self._field_table.removeRow(row)
            self._mark_dirty()

    def _move_field_up(self) -> None:
        row = self._field_table.currentRow()
        if row > 0:
            self._swap_rows(row, row - 1)
            self._field_table.selectRow(row - 1)
            self._mark_dirty()

    def _move_field_down(self) -> None:
        row = self._field_table.currentRow()
        if row >= 0 and row < self._field_table.rowCount() - 1:
            self._swap_rows(row, row + 1)
            self._field_table.selectRow(row + 1)
            self._mark_dirty()

    def _swap_rows(self, row_a: int, row_b: int) -> None:
        """Swap two rows in the field table."""
        # Read values from both rows
        a_data = self._read_row(row_a)
        b_data = self._read_row(row_b)
        # Write swapped
        self._write_row(row_a, b_data)
        self._write_row(row_b, a_data)

    def _read_row(self, row: int) -> dict:
        """Read field data from a table row."""
        type_combo = self._field_table.cellWidget(row, 0)
        type_val = type_combo.currentText() if type_combo else "byte"
        name_item = self._field_table.item(row, 1)
        name_val = name_item.text() if name_item else ""
        pos_item = self._field_table.item(row, 2)
        pos_val = pos_item.text() if pos_item else "0"
        bits_item = self._field_table.item(row, 3)
        bits_val = bits_item.text() if bits_item else ""
        lookup_combo = self._field_table.cellWidget(row, 4)
        lookup_val = lookup_combo.currentText() if lookup_combo else ""
        return {
            "type": type_val,
            "name": name_val,
            "pos": pos_val,
            "bits": bits_val,
            "lookup": lookup_val,
        }

    def _write_row(self, row: int, data: dict) -> None:
        """Write field data to a table row."""
        type_combo = self._field_table.cellWidget(row, 0)
        if type_combo:
            type_combo.setCurrentText(data["type"])
        name_item = self._field_table.item(row, 1)
        if name_item:
            name_item.setText(data["name"])
        pos_item = self._field_table.item(row, 2)
        if pos_item:
            pos_item.setText(data["pos"])
        bits_item = self._field_table.item(row, 3)
        if bits_item:
            bits_item.setText(data["bits"])
        lookup_combo = self._field_table.cellWidget(row, 4)
        if lookup_combo:
            lookup_combo.setCurrentText(data["lookup"])

    # ---------------------------------------------------------------------------
    # Validation (Req 11.6, 11.10)
    # ---------------------------------------------------------------------------

    def _validate(self) -> list[str]:
        """Validate all fields. Returns list of error messages (empty = valid)."""
        errors = []

        if self._field_table.rowCount() == 0:
            errors.append("At least one field definition is required.")
            return errors

        seen_names: set[str] = set()

        for i in range(self._field_table.rowCount()):
            row_num = i + 1
            data = self._read_row(i)

            # Validate pos
            try:
                pos_val = int(data["pos"])
                if pos_val < 0:
                    errors.append(f"Row {row_num}: pos must be non-negative.")
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: pos must be a non-negative integer.")

            # Validate type
            if data["type"] not in SUPPORTED_FIELD_TYPES:
                errors.append(f"Row {row_num}: type '{data['type']}' not supported.")

            # Validate name
            name = data["name"]
            if not name:
                errors.append(f"Row {row_num}: name must not be empty.")
            elif not _NAME_PATTERN.match(name):
                if len(name) > 64:
                    errors.append(f"Row {row_num}: name exceeds 64 characters.")
                else:
                    errors.append(f"Row {row_num}: name must be alphanumeric/underscore only.")
            else:
                if name in seen_names:
                    errors.append(f"Row {row_num}: duplicate name '{name}'.")
                else:
                    seen_names.add(name)

            # Validate bits
            bits_str = data["bits"].strip()
            if bits_str:
                try:
                    bits_val = int(bits_str)
                    if bits_val < 1 or bits_val > 32:
                        errors.append(f"Row {row_num}: bits must be 1–32.")
                except (ValueError, TypeError):
                    errors.append(f"Row {row_num}: bits must be an integer 1–32.")

        return errors

    # ---------------------------------------------------------------------------
    # Save logic (Req 11.4, 11.5, 11.7, 11.8)
    # ---------------------------------------------------------------------------

    def _save(self) -> None:
        """Validate and save the current definition."""
        errors = self._validate()
        if errors:
            self._error_label.setText("\n".join(errors))
            self._error_label.setVisible(True)
            return

        self._error_label.setVisible(False)

        # Build definition
        opcode_str = self._opcode_input.text().strip()
        try:
            opcode_int = int(opcode_str, 16)
        except (ValueError, TypeError):
            opcode_int = 0

        direction = self._dir_combo.currentText()
        description = self._desc_input.text().strip()

        fields = []
        for i in range(self._field_table.rowCount()):
            data = self._read_row(i)
            try:
                pos_val = int(data["pos"])
            except (ValueError, TypeError):
                pos_val = 0

            bits_val = None
            if data["bits"].strip():
                try:
                    bits_val = int(data["bits"])
                except (ValueError, TypeError):
                    bits_val = None

            lookup_val = data["lookup"] if data["lookup"] else None
            fields.append(FieldDefinition(
                name=data["name"],
                type=data["type"],
                pos=pos_val,
                bits=bits_val,
                lookup=lookup_val,
            ))

        definition = PacketDefinition(
            opcode=opcode_int,
            direction=direction,
            description=description,
            fields=fields,
        )

        # Check if overwriting (Req 11.7)
        existing = self._packet_db.get_definition(direction, opcode_int)
        if existing is not None:
            reply = QMessageBox.question(
                self,
                "Overwrite Definition",
                f"Overwrite existing definition? (Current: {len(existing.fields)} fields, New: {len(fields)} fields)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save (Req 11.4)
        try:
            self._packet_db.set_definition(direction, opcode_int, definition)
            self._packet_db.save_xml()
        except Exception as e:
            logger.error("Failed to save definition: %s", e)
            self._error_label.setText(f"Save failed: {e}")
            self._error_label.setVisible(True)
            return

        # Reload decoder (Req 11.5)
        try:
            if self._decoder is not None:
                self._decoder.reload()
        except Exception as e:
            logger.error("Decoder reload failed: %s", e)
            self._error_label.setText(f"Reload failed: {e}")
            self._error_label.setVisible(True)
            return

        # Re-decode
        if self._on_redecode is not None:
            try:
                self._on_redecode()
            except Exception as e:
                logger.error("Re-decode failed: %s", e)

        self._has_unsaved_changes = False
        self._error_label.setVisible(False)


class LiveEditor(QDockWidget):
    """Dockable Live Database Editor panel.

    Toggle with E key or toolbar button (Req 11.1).
    """

    def __init__(
        self,
        packet_db: PacketDB,
        lookup_mgr: LookupManager,
        decoder: Optional["PacketDecoder"] = None,
        on_redecode: Optional[Callable[[], None]] = None,
        parent=None,
    ):
        super().__init__("Live DB Editor", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setMinimumWidth(380)

        self._editor_widget = LiveEditorWidget(
            packet_db, lookup_mgr, decoder, on_redecode, self
        )
        self.setWidget(self._editor_widget)

    @property
    def has_unsaved_changes(self) -> bool:
        return self._editor_widget.has_unsaved_changes

    def populate_from_packet(self, packet: dict) -> None:
        """Pre-populate editor from a selected packet."""
        self._editor_widget.populate_from_packet(packet)
