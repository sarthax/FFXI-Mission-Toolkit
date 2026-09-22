"""Export Tab for the Packetlyzer Analyzer (PyQt6).

Inline export controls — select format, destination, and export visible packets.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _get_font(size: int = 9) -> QFont:
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


class ExportTab(QWidget):
    """Export controls tab: select format, path, and export packets.

    Signals:
        export_requested(str, str): Emitted with (file_path, format).
    """

    export_requested = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Format selection ---
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["JSONL", "Text (Hex Dump)"])
        self._format_combo.setFont(_get_font(9))
        self._format_combo.setFixedWidth(150)
        fmt_layout.addWidget(self._format_combo)
        fmt_layout.addStretch()
        layout.addLayout(fmt_layout)

        # --- File path ---
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save to:"))
        self._path_input = QLineEdit()
        self._path_input.setFont(_get_font(9))
        self._path_input.setPlaceholderText("Select export file...")
        path_layout.addWidget(self._path_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # --- Export button ---
        btn_layout = QHBoxLayout()
        self._export_btn = QPushButton("Export Visible Packets")
        self._export_btn.setFixedWidth(180)
        self._export_btn.setStyleSheet(
            "QPushButton { background-color: #40a02b; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #4cb533; }"
        )
        self._export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self._export_btn)

        self._status_label = QLabel("")
        self._status_label.setFont(_get_font(9))
        self._status_label.setStyleSheet("color: #a6adc8;")
        btn_layout.addWidget(self._status_label)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

    def set_status(self, message: str) -> None:
        """Update the export status label."""
        self._status_label.setText(message)

    def _browse_path(self) -> None:
        """Open a file save dialog."""
        fmt = self._format_combo.currentText()
        if "JSONL" in fmt:
            filter_str = "JSONL files (*.jsonl);;All files (*.*)"
        else:
            filter_str = "Text files (*.txt);;All files (*.*)"

        path, _ = QFileDialog.getSaveFileName(self, "Export Packets", "", filter_str)
        if path:
            self._path_input.setText(path)

    def _on_export(self) -> None:
        """Trigger export with current settings."""
        path = self._path_input.text().strip()
        if not path:
            self._status_label.setText("Please select a file path")
            return

        fmt = "jsonl" if "JSONL" in self._format_combo.currentText() else "txt"
        self.export_requested.emit(path, fmt)
