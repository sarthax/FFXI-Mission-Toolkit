"""Settings Dialog for the Packetlyzer Analyzer (PyQt6).

Provides a QDialog for viewing and modifying all configuration values.
Validates inputs against defined ranges with inline error indicators.

Requirements: 13.5, 13.6
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from analyzer.config import Config


# Validation ranges (matching config.py)
_RANGES = {
    "window_width": (400, 3840),
    "window_height": (300, 2160),
    "port": (1024, 65535),
    "max_packets": (100, 100000),
}


class SettingsDialog(QDialog):
    """Settings dialog for viewing and modifying configuration.

    Provides:
    - View/modify all config values (Req 13.5)
    - OK/Cancel buttons
    - Inline validation with red error messages (Req 13.6)
    """

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()
        self._populate_from_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Form layout for fields
        form = QFormLayout()
        form.setSpacing(8)

        # Window Width
        self._width_input = QLineEdit()
        self._width_error = self._make_error_label()
        width_container = self._make_field_with_error(self._width_input, self._width_error)
        form.addRow("Window Width (400–3840):", width_container)

        # Window Height
        self._height_input = QLineEdit()
        self._height_error = self._make_error_label()
        height_container = self._make_field_with_error(self._height_input, self._height_error)
        form.addRow("Window Height (300–2160):", height_container)

        # Port
        self._port_input = QLineEdit()
        self._port_error = self._make_error_label()
        port_container = self._make_field_with_error(self._port_input, self._port_error)
        form.addRow("Port (1024–65535):", port_container)

        # Max Packets
        self._max_packets_input = QLineEdit()
        self._max_packets_error = self._make_error_label()
        max_container = self._make_field_with_error(self._max_packets_input, self._max_packets_error)
        form.addRow("Max Packets (100–100000):", max_container)

        # Filter String
        self._filter_input = QLineEdit()
        self._filter_input.setMaxLength(256)
        self._filter_error = self._make_error_label()
        filter_container = self._make_field_with_error(self._filter_input, self._filter_error)
        form.addRow("Filter String:", filter_container)

        # Auto Scroll
        self._auto_scroll_check = QCheckBox("Enable auto-scroll")
        form.addRow("Auto Scroll:", self._auto_scroll_check)

        # FFXI Install Path
        ffxi_container = QWidget()
        ffxi_layout = QHBoxLayout(ffxi_container)
        ffxi_layout.setContentsMargins(0, 0, 0, 0)
        ffxi_layout.setSpacing(4)
        self._ffxi_path_input = QLineEdit()
        self._ffxi_path_input.setPlaceholderText("Auto-detect (leave empty) or set path")
        ffxi_layout.addWidget(self._ffxi_path_input)
        ffxi_browse_btn = QPushButton("Browse")
        ffxi_browse_btn.setFixedWidth(70)
        ffxi_browse_btn.clicked.connect(self._browse_ffxi_path)
        ffxi_layout.addWidget(ffxi_browse_btn)
        form.addRow("FFXI Install Path:", ffxi_container)

        layout.addLayout(form)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _make_error_label(self) -> QLabel:
        """Create a red error label (initially hidden)."""
        label = QLabel("")
        label.setStyleSheet("color: #ff6464; font-size: 9pt;")
        label.setVisible(False)
        return label

    def _make_field_with_error(self, input_widget: QLineEdit, error_label: QLabel) -> QWidget:
        """Wrap an input field and error label in a vertical container."""
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)
        vbox.addWidget(input_widget)
        vbox.addWidget(error_label)
        return container

    def _populate_from_config(self) -> None:
        """Load current config values into the form fields."""
        self._width_input.setText(str(self._config.window_width))
        self._height_input.setText(str(self._config.window_height))
        self._port_input.setText(str(self._config.port))
        self._max_packets_input.setText(str(self._config.max_packets))
        self._filter_input.setText(self._config.filter_string)
        self._auto_scroll_check.setChecked(self._config.auto_scroll)
        self._ffxi_path_input.setText(self._config.ffxi_path)

    def _validate(self) -> bool:
        """Validate all fields. Returns True if all valid."""
        valid = True

        # Validate numeric fields
        checks = [
            (self._width_input, self._width_error, "window_width"),
            (self._height_input, self._height_error, "window_height"),
            (self._port_input, self._port_error, "port"),
            (self._max_packets_input, self._max_packets_error, "max_packets"),
        ]

        for input_w, error_w, key in checks:
            text = input_w.text().strip()
            min_val, max_val = _RANGES[key]

            if not text:
                error_w.setText("Value required")
                error_w.setVisible(True)
                valid = False
                continue

            try:
                val = int(text)
            except ValueError:
                error_w.setText("Must be an integer")
                error_w.setVisible(True)
                valid = False
                continue

            if val < min_val or val > max_val:
                error_w.setText(f"Must be {min_val}–{max_val}")
                error_w.setVisible(True)
                valid = False
            else:
                error_w.setVisible(False)

        # Validate filter string length
        if len(self._filter_input.text()) > 256:
            self._filter_error.setText("Max 256 characters")
            self._filter_error.setVisible(True)
            valid = False
        else:
            self._filter_error.setVisible(False)

        return valid

    def _browse_ffxi_path(self) -> None:
        """Open a directory picker for the FFXI install path."""
        current = self._ffxi_path_input.text().strip()
        start_dir = current if current else "C:/"
        folder = QFileDialog.getExistingDirectory(
            self, "Select FFXI Install Directory", start_dir
        )
        if folder:
            self._ffxi_path_input.setText(folder)

    def _on_ok(self) -> None:
        """Validate and apply changes."""
        if not self._validate():
            return

        # Apply to config
        self._config.window_width = int(self._width_input.text().strip())
        self._config.window_height = int(self._height_input.text().strip())
        self._config.port = int(self._port_input.text().strip())
        self._config.max_packets = int(self._max_packets_input.text().strip())
        self._config.filter_string = self._filter_input.text()
        self._config.auto_scroll = self._auto_scroll_check.isChecked()
        self._config.ffxi_path = self._ffxi_path_input.text().strip()

        self.accept()
