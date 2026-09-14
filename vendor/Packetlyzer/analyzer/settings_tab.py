"""Settings Tab for the Packetlyzer Analyzer (PyQt6).

Inline settings panel with theme selector and configuration fields.
Replaces the old popup dialog approach.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from analyzer.themes import THEME_NAMES


def _get_font(size: int = 9) -> QFont:
    for family in ("Cascadia Mono", "Consolas", "Courier New"):
        font = QFont(family, size)
        if font.exactMatch() or family == "Courier New":
            return font
    return QFont("monospace", size)


class SettingsTab(QWidget):
    """Inline settings tab with theme selector and config fields.

    Signals:
        theme_changed(str): Emitted when user selects a different theme.
        settings_applied(): Emitted when settings are saved/applied.
    """

    theme_changed = pyqtSignal(str)
    settings_applied = pyqtSignal()

    def __init__(self, config, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()
        self._populate_from_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Theme Section ---
        theme_group = QGroupBox("Appearance")
        theme_group.setFont(_get_font(9))
        theme_layout = QHBoxLayout(theme_group)

        theme_layout.addWidget(QLabel("Color Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(THEME_NAMES)
        self._theme_combo.setFont(_get_font(9))
        self._theme_combo.setFixedWidth(120)
        self._theme_combo.currentTextChanged.connect(self._on_theme_selected)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()

        layout.addWidget(theme_group)

        # --- Network/General Section ---
        general_group = QGroupBox("General")
        general_group.setFont(_get_font(9))
        form = QFormLayout(general_group)
        form.setSpacing(6)

        # Port
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setFont(_get_font(9))
        self._port_spin.setFixedWidth(100)
        form.addRow("Listen Port:", self._port_spin)

        # Max Packets
        self._max_packets_spin = QSpinBox()
        self._max_packets_spin.setRange(100, 100000)
        self._max_packets_spin.setSingleStep(500)
        self._max_packets_spin.setFont(_get_font(9))
        self._max_packets_spin.setFixedWidth(100)
        form.addRow("Max Packets:", self._max_packets_spin)

        # Auto Scroll
        self._auto_scroll_check = QCheckBox("Enable")
        self._auto_scroll_check.setFont(_get_font(9))
        form.addRow("Auto Scroll:", self._auto_scroll_check)

        layout.addWidget(general_group)

        # --- FFXI Path Section ---
        ffxi_group = QGroupBox("FFXI Installation")
        ffxi_group.setFont(_get_font(9))
        ffxi_layout = QHBoxLayout(ffxi_group)

        self._ffxi_path_input = QLineEdit()
        self._ffxi_path_input.setFont(_get_font(9))
        self._ffxi_path_input.setPlaceholderText("Auto-detect (leave empty)")
        ffxi_layout.addWidget(self._ffxi_path_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_ffxi_path)
        ffxi_layout.addWidget(browse_btn)

        layout.addWidget(ffxi_group)

        # --- Apply Button ---
        btn_layout = QHBoxLayout()
        self._apply_btn = QPushButton("Apply Settings")
        self._apply_btn.setFixedWidth(120)
        self._apply_btn.setStyleSheet(
            "QPushButton { background-color: #40a02b; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #4cb533; }"
        )
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        self._status_label = QLabel("")
        self._status_label.setFont(_get_font(9))
        self._status_label.setStyleSheet("color: #a6adc8;")
        btn_layout.addWidget(self._status_label)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _populate_from_config(self) -> None:
        """Load current config values into the form."""
        self._theme_combo.setCurrentText(self._config.theme)
        self._port_spin.setValue(self._config.port)
        self._max_packets_spin.setValue(self._config.max_packets)
        self._auto_scroll_check.setChecked(self._config.auto_scroll)
        self._ffxi_path_input.setText(self._config.ffxi_path)

    def _on_theme_selected(self, theme_name: str) -> None:
        """Handle theme selection — emit signal for live preview."""
        self._config.theme = theme_name
        self.theme_changed.emit(theme_name)

    def _browse_ffxi_path(self) -> None:
        """Open a directory picker for the FFXI install path."""
        current = self._ffxi_path_input.text().strip()
        start_dir = current if current else "C:/"
        folder = QFileDialog.getExistingDirectory(
            self, "Select FFXI Install Directory", start_dir
        )
        if folder:
            self._ffxi_path_input.setText(folder)

    def _on_apply(self) -> None:
        """Apply all settings to config."""
        self._config.port = self._port_spin.value()
        self._config.max_packets = self._max_packets_spin.value()
        self._config.auto_scroll = self._auto_scroll_check.isChecked()
        self._config.ffxi_path = self._ffxi_path_input.text().strip()
        self._config.theme = self._theme_combo.currentText()

        self._status_label.setText("Settings applied")
        self.settings_applied.emit()
