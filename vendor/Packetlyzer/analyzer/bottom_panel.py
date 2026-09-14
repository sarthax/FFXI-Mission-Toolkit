"""Bottom Panel — Tabbed panel below the main splitter.

Provides logging controls, capture controls, and opcode filters via tabs.
"""

import os
import threading
import queue as _queue
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Hex dump formatting (matches addons-1-master capture format)
# ---------------------------------------------------------------------------


def format_hex_dump(data: bytes) -> str:
    """Format raw bytes into a hex dump matching the capture addon style.

    Args:
        data: Raw packet bytes.

    Returns:
        Multi-line hex dump string with header and row-number offsets.
    """
    lines: list[str] = []
    # Header
    lines.append(
        "        |  0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F"
        "      | 0123456789ABCDEF"
    )
    lines.append(
        "    ---------------------------------------------------------"
        "  ----------------------"
    )

    for row_num in range(0, len(data), 16):
        chunk = data[row_num: row_num + 16]

        # Hex portion
        hex_parts: list[str] = []
        for b in chunk:
            hex_parts.append(f"{b:02X}")
        hex_str = " ".join(hex_parts)
        # Pad to full 16 columns if short
        if len(chunk) < 16:
            hex_str += "   " * (16 - len(chunk))

        # ASCII portion
        ascii_parts: list[str] = []
        for b in chunk:
            if 0x20 <= b <= 0x7E:
                ascii_parts.append(chr(b))
            else:
                ascii_parts.append(".")
        ascii_str = "".join(ascii_parts)

        row_idx = row_num // 16
        lines.append(
            f"    {row_idx} | {hex_str}  {row_idx} | {ascii_str}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PacketLogger — background file I/O
# ---------------------------------------------------------------------------


class PacketLogger:
    """Handles writing packet logs to disk on a background thread.

    Maintains file handles for full, incoming, outgoing, and per-opcode logs.
    All writes are queued and processed asynchronously to avoid blocking the GUI.
    """

    def __init__(self) -> None:
        self._log_folder: str = ""
        self._active: bool = False
        self._write_queue: _queue.Queue = _queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._packet_count: int = 0
        self._file_handles: dict[str, object] = {}

    @property
    def packet_count(self) -> int:
        """Number of packets logged in the current session."""
        return self._packet_count

    @property
    def is_active(self) -> bool:
        """Whether the logger is currently writing packets."""
        return self._active

    @property
    def log_folder(self) -> str:
        """Current log folder path."""
        return self._log_folder

    def start(self, log_folder: str) -> None:
        """Start logging to the given folder.

        Creates the folder structure and opens file handles.

        Args:
            log_folder: Absolute path to the log output directory.
        """
        self._log_folder = log_folder
        self._packet_count = 0

        # Create directory structure
        os.makedirs(log_folder, exist_ok=True)
        os.makedirs(os.path.join(log_folder, "incoming"), exist_ok=True)
        os.makedirs(os.path.join(log_folder, "outgoing"), exist_ok=True)

        # Open main log files
        self._file_handles = {
            "full": open(os.path.join(log_folder, "full.log"), "a", encoding="utf-8"),
            "incoming": open(os.path.join(log_folder, "incoming.log"), "a", encoding="utf-8"),
            "outgoing": open(os.path.join(log_folder, "outgoing.log"), "a", encoding="utf-8"),
        }

        self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop logging and close all file handles."""
        self._active = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._close_handles()

    def resume(self) -> None:
        """Resume logging to the same folder (append mode)."""
        if not self._log_folder:
            return
        # Reopen handles in append mode
        self._file_handles = {
            "full": open(
                os.path.join(self._log_folder, "full.log"), "a", encoding="utf-8"
            ),
            "incoming": open(
                os.path.join(self._log_folder, "incoming.log"), "a", encoding="utf-8"
            ),
            "outgoing": open(
                os.path.join(self._log_folder, "outgoing.log"), "a", encoding="utf-8"
            ),
        }
        self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()

    def log_packet(self, packet: dict) -> None:
        """Queue a packet for writing.

        Args:
            packet: Packet dict with keys: direction, opcode, raw_bytes (or data).
        """
        if not self._active:
            return
        self._write_queue.put(packet)

    def _writer_loop(self) -> None:
        """Background thread: drain the write queue and write to files."""
        while not self._stop_event.is_set():
            try:
                packet = self._write_queue.get(timeout=0.1)
            except _queue.Empty:
                continue
            self._write_packet(packet)

        # Drain remaining items on stop
        while not self._write_queue.empty():
            try:
                packet = self._write_queue.get_nowait()
                self._write_packet(packet)
            except _queue.Empty:
                break

    def _write_packet(self, packet: dict) -> None:
        """Write a single packet to the appropriate log files."""
        direction = packet.get("direction", "incoming").lower()
        if direction not in ("incoming", "outgoing"):
            direction = "incoming"

        opcode_raw = packet.get("opcode", "0x000")
        # Normalize opcode to int
        if isinstance(opcode_raw, str):
            try:
                opcode_int = int(opcode_raw, 16) if opcode_raw.startswith("0x") else int(opcode_raw)
            except (ValueError, TypeError):
                opcode_int = 0
        else:
            opcode_int = int(opcode_raw)

        opcode_str = f"0x{opcode_int:03X}"

        # Get raw bytes
        raw = packet.get("raw_bytes") or packet.get("data") or b""
        if isinstance(raw, str):
            # Hex string — convert to bytes
            try:
                raw = bytes.fromhex(raw.replace(" ", "").replace("\n", ""))
            except (ValueError, TypeError):
                raw = b""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hex_dump = format_hex_dump(raw)

        entry = f"[{timestamp}] {direction} packet {opcode_str}:\n{hex_dump}\n\n"

        # Write to full.log
        fh = self._file_handles.get("full")
        if fh and not fh.closed:
            fh.write(entry)
            fh.flush()

        # Write to direction log
        dir_fh = self._file_handles.get(direction)
        if dir_fh and not dir_fh.closed:
            dir_entry = f"[{timestamp}] Packet {opcode_str}:\n{hex_dump}\n\n"
            dir_fh.write(dir_entry)
            dir_fh.flush()

        # Write to per-opcode file
        opcode_dir = os.path.join(self._log_folder, direction)
        opcode_file = os.path.join(opcode_dir, f"{opcode_str}.log")
        try:
            with open(opcode_file, "a", encoding="utf-8") as f:
                per_entry = f"[{timestamp}]\n{hex_dump}\n\n"
                f.write(per_entry)
        except OSError:
            pass

        self._packet_count += 1

    def _close_handles(self) -> None:
        """Close all open file handles."""
        for fh in self._file_handles.values():
            try:
                if fh and not fh.closed:
                    fh.close()
            except OSError:
                pass
        self._file_handles.clear()


# ---------------------------------------------------------------------------
# LoggingTab — UI for log controls
# ---------------------------------------------------------------------------


class LoggingTab(QWidget):
    """Logging controls tab: folder selection, start/stop/resume, status."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._logger = PacketLogger()
        self._state: str = "stopped"  # stopped | logging | paused

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Row 1: Log folder selector ---
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Log folder:")
        folder_layout.addWidget(folder_label)

        default_path = os.path.join(_BASE_DIR, "logs")
        self._folder_input = QLineEdit(default_path)
        self._folder_input.setFont(QFont("Cascadia Mono", 9))
        self._folder_input.setMinimumWidth(300)
        folder_layout.addWidget(self._folder_input, stretch=1)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)

        layout.addLayout(folder_layout)

        # --- Row 2: Control buttons ---
        btn_layout = QHBoxLayout()

        self._start_btn = QPushButton("Start")
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #40a02b; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #4cb533; }"
            "QPushButton:disabled { background-color: #45475a; color: #6c7086; }"
        )
        self._start_btn.clicked.connect(self._start_logging)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #d20f39; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #e0164a; }"
            "QPushButton:disabled { background-color: #45475a; color: #6c7086; }"
        )
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_logging)
        btn_layout.addWidget(self._stop_btn)

        self._resume_btn = QPushButton("Resume")
        self._resume_btn.setStyleSheet(
            "QPushButton { background-color: #df8e1d; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #e89b2a; }"
            "QPushButton:disabled { background-color: #45475a; color: #6c7086; }"
        )
        self._resume_btn.setEnabled(False)
        self._resume_btn.clicked.connect(self._resume_logging)
        btn_layout.addWidget(self._resume_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # --- Row 3: Status and packet count ---
        status_layout = QHBoxLayout()

        self._status_label = QLabel("Not logging")
        self._status_label.setStyleSheet("QLabel { color: #a6adc8; }")
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        self._count_label = QLabel("0 packets logged")
        self._count_label.setStyleSheet("QLabel { color: #a6adc8; }")
        status_layout.addWidget(self._count_label)

        layout.addLayout(status_layout)
        layout.addStretch()

        # Timer to update packet count display
        self._count_timer = QTimer(self)
        self._count_timer.timeout.connect(self._update_count)
        self._count_timer.start(500)

    @property
    def is_logging(self) -> bool:
        """Whether logging is currently active."""
        return self._state == "logging"

    def log_packet(self, packet: dict) -> None:
        """Forward a packet to the logger (called from main window).

        Args:
            packet: Packet dict to log.
        """
        if self._state == "logging":
            self._logger.log_packet(packet)

    def shutdown(self) -> None:
        """Clean up resources on application exit."""
        if self._logger.is_active:
            self._logger.stop()

    # --- Private slots ---

    def _browse_folder(self) -> None:
        """Open a directory picker for the log folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Log Folder", self._folder_input.text()
        )
        if folder:
            self._folder_input.setText(folder)

    def _start_logging(self) -> None:
        """Start a new logging session."""
        folder = self._folder_input.text().strip()
        if not folder:
            return
        self._logger.start(folder)
        self._state = "logging"
        self._update_buttons()
        self._status_label.setText(f"Logging to: {folder}")
        self._status_label.setStyleSheet("QLabel { color: #40a02b; }")

    def _stop_logging(self) -> None:
        """Stop the current logging session."""
        self._logger.stop()
        self._state = "paused"
        self._update_buttons()
        self._status_label.setText("Logging paused")
        self._status_label.setStyleSheet("QLabel { color: #df8e1d; }")

    def _resume_logging(self) -> None:
        """Resume the paused logging session."""
        self._logger.resume()
        self._state = "logging"
        self._update_buttons()
        folder = self._folder_input.text().strip()
        self._status_label.setText(f"Logging to: {folder}")
        self._status_label.setStyleSheet("QLabel { color: #40a02b; }")

    def _update_buttons(self) -> None:
        """Update button enabled states based on current logging state."""
        self._start_btn.setEnabled(self._state == "stopped")
        self._stop_btn.setEnabled(self._state == "logging")
        self._resume_btn.setEnabled(self._state == "paused")

    def _update_count(self) -> None:
        """Periodically update the packet count label."""
        count = self._logger.packet_count
        self._count_label.setText(f"{count} packets logged")


# ---------------------------------------------------------------------------
# CaptureTab — memory capture controls
# ---------------------------------------------------------------------------


class CaptureTab(QWidget):
    """Capture controls tab: max packets setting, play/pause, clear history.

    Signals:
        capture_paused(): Emitted when capture is paused (stop collecting).
        capture_resumed(): Emitted when capture is resumed.
        clear_requested(): Emitted when the user clicks Clear History.
        max_packets_changed(int): Emitted when the user changes the max packets value.
    """

    capture_paused = pyqtSignal()
    capture_resumed = pyqtSignal()
    clear_requested = pyqtSignal()
    max_packets_changed = pyqtSignal(int)

    def __init__(self, max_packets: int = 5000, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._capturing = True  # Start in "playing" state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Row 1: Max packets setting ---
        max_layout = QHBoxLayout()
        max_label = QLabel("Max Packets in Memory:")
        max_label.setFont(QFont("Cascadia Mono", 9))
        max_layout.addWidget(max_label)

        self._max_spin = QSpinBox()
        self._max_spin.setRange(100, 100000)
        self._max_spin.setSingleStep(500)
        self._max_spin.setValue(max_packets)
        self._max_spin.setFont(QFont("Cascadia Mono", 9))
        self._max_spin.setFixedWidth(120)
        self._max_spin.valueChanged.connect(self._on_max_changed)
        max_layout.addWidget(self._max_spin)

        max_layout.addStretch()
        layout.addLayout(max_layout)

        # --- Row 2: Play/Pause and Clear buttons ---
        btn_layout = QHBoxLayout()

        self._play_pause_btn = QPushButton("Pause")
        self._play_pause_btn.setFixedWidth(100)
        self._play_pause_btn.setStyleSheet(
            "QPushButton { background-color: #df8e1d; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #e89b2a; }"
        )
        self._play_pause_btn.clicked.connect(self._toggle_capture)
        btn_layout.addWidget(self._play_pause_btn)

        self._clear_btn = QPushButton("Clear History")
        self._clear_btn.setFixedWidth(120)
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #d20f39; color: #1e1e2e; font-weight: bold; }"
            "QPushButton:hover { background-color: #e0164a; }"
        )
        self._clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self._clear_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # --- Row 3: Status ---
        self._status_label = QLabel("Capturing packets")
        self._status_label.setStyleSheet("QLabel { color: #40a02b; }")
        self._status_label.setFont(QFont("Cascadia Mono", 9))
        layout.addWidget(self._status_label)

        layout.addStretch()

    @property
    def is_capturing(self) -> bool:
        """Whether capture is currently active (not paused)."""
        return self._capturing

    @property
    def max_packets(self) -> int:
        """Current max packets value."""
        return self._max_spin.value()

    def _toggle_capture(self) -> None:
        """Toggle between capturing and paused states."""
        self._capturing = not self._capturing
        if self._capturing:
            self._play_pause_btn.setText("Pause")
            self._play_pause_btn.setStyleSheet(
                "QPushButton { background-color: #df8e1d; color: #1e1e2e; font-weight: bold; }"
                "QPushButton:hover { background-color: #e89b2a; }"
            )
            self._status_label.setText("Capturing packets")
            self._status_label.setStyleSheet("QLabel { color: #40a02b; }")
            self.capture_resumed.emit()
        else:
            self._play_pause_btn.setText("Play")
            self._play_pause_btn.setStyleSheet(
                "QPushButton { background-color: #40a02b; color: #1e1e2e; font-weight: bold; }"
                "QPushButton:hover { background-color: #4cb533; }"
            )
            self._status_label.setText("Capture paused — packets are being discarded")
            self._status_label.setStyleSheet("QLabel { color: #df8e1d; }")
            self.capture_paused.emit()

    def _on_clear(self) -> None:
        """Emit signal to clear all packet history."""
        self.clear_requested.emit()

    def _on_max_changed(self, value: int) -> None:
        """Emit signal when max packets value changes."""
        self.max_packets_changed.emit(value)


# ---------------------------------------------------------------------------
# FiltersTab — opcode filter management
# ---------------------------------------------------------------------------


class FiltersTab(QWidget):
    """Filters tab: manage opcode filter lists with Blocked/Passed modes.

    Each mode has its own independent opcode list:
      - Blocked: Listed opcodes are dropped (everything else passes).
      - Passed: Only listed opcodes are allowed (everything else is dropped).

    Signals:
        filters_changed(set): Emitted when the filter list changes.
    """

    filters_changed = pyqtSignal(set)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._blocked_opcodes: set[str] = set()
        self._passed_opcodes: set[str] = set()
        self._mode: str = "blocked"  # "blocked" or "passed"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Row 0: Mode selector ---
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Filter Mode:")
        mode_label.setFont(QFont("Cascadia Mono", 9))
        mode_layout.addWidget(mode_label)

        from PyQt6.QtWidgets import QRadioButton
        self._mode_blocked_radio = QRadioButton("Blocked")
        self._mode_blocked_radio.setFont(QFont("Cascadia Mono", 9))
        self._mode_blocked_radio.setChecked(True)
        self._mode_blocked_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_blocked_radio)

        self._mode_passed_radio = QRadioButton("Passed")
        self._mode_passed_radio.setFont(QFont("Cascadia Mono", 9))
        self._mode_passed_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_passed_radio)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        self._update_radio_styles()

        # --- Row 1: Add opcode input ---
        add_layout = QHBoxLayout()

        add_label = QLabel("Opcode (hex):")
        add_label.setFont(QFont("Cascadia Mono", 9))
        add_layout.addWidget(add_label)

        self._opcode_input = QLineEdit()
        self._opcode_input.setFont(QFont("Cascadia Mono", 9))
        self._opcode_input.setPlaceholderText("e.g. 0015 or 0x0015")
        self._opcode_input.setFixedWidth(150)
        self._opcode_input.returnPressed.connect(self._add_opcode)
        add_layout.addWidget(self._opcode_input)

        self._add_btn = QPushButton("Add")
        self._add_btn.setFixedWidth(60)
        self._add_btn.clicked.connect(self._add_opcode)
        add_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.setFixedWidth(130)
        self._remove_btn.clicked.connect(self._remove_selected)
        add_layout.addWidget(self._remove_btn)

        add_layout.addStretch()
        layout.addLayout(add_layout)

        # --- Opcode list ---
        self._opcode_list = QListWidget()
        self._opcode_list.setFont(QFont("Cascadia Mono", 9))
        self._opcode_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._opcode_list.setMaximumHeight(150)
        layout.addWidget(self._opcode_list)

        # --- Apply to logging checkbox ---
        self._apply_to_logging = QCheckBox("Apply filters to Logging")
        self._apply_to_logging.setFont(QFont("Cascadia Mono", 9))
        self._apply_to_logging.setChecked(False)
        layout.addWidget(self._apply_to_logging)

        # --- Info label ---
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("QLabel { color: #6c7086; font-size: 9px; }")
        layout.addWidget(self._info_label)
        self._update_info_label()

        layout.addStretch()

    @property
    def blocked_opcodes(self) -> set[str]:
        """Current active filter opcode set (for the active mode)."""
        if self._mode == "blocked":
            return self._blocked_opcodes.copy()
        return self._passed_opcodes.copy()

    @property
    def filter_mode(self) -> str:
        """Current filter mode: 'blocked' or 'passed'."""
        return self._mode

    @property
    def apply_to_logging(self) -> bool:
        """Whether the filter should also apply to packet logging."""
        return self._apply_to_logging.isChecked()

    def is_blocked(self, opcode: str) -> bool:
        """Check if an opcode should be dropped based on current mode and lists.

        Args:
            opcode: Opcode string (e.g. "0015", "000d").

        Returns:
            True if the opcode should be dropped.
        """
        if not opcode:
            return False

        # Normalize: ensure lowercase 4-char hex without prefix
        normalized = str(opcode).lower().removeprefix("0x").zfill(4)

        if self._mode == "blocked":
            if not self._blocked_opcodes:
                return False
            return normalized in self._blocked_opcodes
        else:
            # Passed mode: drop if NOT in the passed list
            if not self._passed_opcodes:
                return False  # Empty pass list = no filtering
            return normalized not in self._passed_opcodes

    def _on_mode_changed(self, checked: bool) -> None:
        """Handle mode radio button toggle — switch displayed list."""
        if self._mode_blocked_radio.isChecked():
            new_mode = "blocked"
        else:
            new_mode = "passed"

        if new_mode == self._mode:
            return

        self._mode = new_mode
        self._update_radio_styles()
        self._update_info_label()
        self._refresh_list_display()

    def _update_radio_styles(self) -> None:
        """Apply red/green coloring to the active radio button."""
        if self._mode == "blocked":
            self._mode_blocked_radio.setStyleSheet(
                "QRadioButton { color: #f38ba8; font-weight: bold; }"  # Red
            )
            self._mode_passed_radio.setStyleSheet(
                "QRadioButton { color: #a6adc8; }"  # Muted
            )
        else:
            self._mode_blocked_radio.setStyleSheet(
                "QRadioButton { color: #a6adc8; }"  # Muted
            )
            self._mode_passed_radio.setStyleSheet(
                "QRadioButton { color: #a6e3a1; font-weight: bold; }"  # Green
            )

    def _update_info_label(self) -> None:
        """Update the info label based on current mode."""
        if self._mode == "blocked":
            self._info_label.setText(
                "Blocked mode: Listed opcodes are dropped before entering memory. "
                "Everything else passes through."
            )
        else:
            self._info_label.setText(
                "Passed mode: ONLY listed opcodes are allowed through. "
                "Everything else is dropped. Use this to focus on specific packets."
            )

    def _refresh_list_display(self) -> None:
        """Refresh the QListWidget to show the opcodes for the active mode."""
        self._opcode_list.clear()
        active_set = self._blocked_opcodes if self._mode == "blocked" else self._passed_opcodes
        for opcode_str in sorted(active_set):
            item = QListWidgetItem(f"0x{opcode_str.upper()}")
            item.setData(Qt.ItemDataRole.UserRole, opcode_str)
            self._opcode_list.addItem(item)

    def _add_opcode(self) -> None:
        """Add the opcode from the input field to the active mode's list."""
        raw = self._opcode_input.text().strip().lower()
        if not raw:
            return

        # Normalize: strip 0x prefix, zero-pad to 4 chars
        raw = raw.replace("0x", "").lstrip("0") or "0"
        try:
            opcode_int = int(raw, 16)
        except ValueError:
            return  # Invalid hex

        opcode_str = f"{opcode_int:04x}"

        active_set = self._blocked_opcodes if self._mode == "blocked" else self._passed_opcodes

        if opcode_str in active_set:
            self._opcode_input.clear()
            return  # Already in list

        active_set.add(opcode_str)
        item = QListWidgetItem(f"0x{opcode_str.upper()}")
        item.setData(Qt.ItemDataRole.UserRole, opcode_str)
        self._opcode_list.addItem(item)
        self._opcode_input.clear()
        try:
            self.filters_changed.emit(active_set.copy())
        except TypeError:
            pass

    def _remove_selected(self) -> None:
        """Remove selected opcodes from the active mode's list."""
        selected = self._opcode_list.selectedItems()
        if not selected:
            return

        active_set = self._blocked_opcodes if self._mode == "blocked" else self._passed_opcodes

        for item in selected:
            opcode_str = item.data(Qt.ItemDataRole.UserRole)
            active_set.discard(opcode_str)
            self._opcode_list.takeItem(self._opcode_list.row(item))
        try:
            self.filters_changed.emit(active_set.copy())
        except TypeError:
            pass

    def load_state(self, blocked_opcodes: list[str], apply_to_logging: bool = False,
                   filter_mode: str = "blocked", passed_opcodes: list[str] = None) -> None:
        """Restore filter state from saved config.

        Args:
            blocked_opcodes: List of opcode hex strings for blocked list.
            apply_to_logging: Whether to apply filters to logging.
            filter_mode: "blocked" or "passed".
            passed_opcodes: List of opcode hex strings for passed list.
        """
        # Load blocked list
        for opcode_str in blocked_opcodes:
            opcode_str = opcode_str.lower().zfill(4)
            self._blocked_opcodes.add(opcode_str)

        # Load passed list
        if passed_opcodes:
            for opcode_str in passed_opcodes:
                opcode_str = opcode_str.lower().zfill(4)
                self._passed_opcodes.add(opcode_str)

        self._apply_to_logging.setChecked(apply_to_logging)

        # Set mode
        self._mode = filter_mode if filter_mode in ("blocked", "passed") else "blocked"
        if self._mode == "blocked":
            self._mode_blocked_radio.setChecked(True)
        else:
            self._mode_passed_radio.setChecked(True)
        self._update_radio_styles()
        self._update_info_label()
        self._refresh_list_display()

    def save_state(self) -> tuple[list[str], bool, str, list[str]]:
        """Return current filter state for saving to config.

        Returns:
            Tuple of (blocked_opcodes, apply_to_logging, filter_mode, passed_opcodes).
        """
        return (
            sorted(self._blocked_opcodes),
            self._apply_to_logging.isChecked(),
            self._mode,
            sorted(self._passed_opcodes),
        )


# ---------------------------------------------------------------------------
# BottomPanel — main tabbed container
# ---------------------------------------------------------------------------


class BottomPanel(QTabWidget):
    """Bottom panel tab widget containing all control tabs."""

    # Signals forwarded from the inline capture buttons
    capture_paused = pyqtSignal()
    capture_resumed = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, config=None, signal_db=None, history_panel=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._capturing = True

        # History tab (first tab — passed in from outside)
        from analyzer.history_panel import HistoryPanel
        self._history_tab: Optional[HistoryPanel] = history_panel
        if self._history_tab is not None:
            self.addTab(self._history_tab, "History")

        # Logging tab
        self._logging_tab = LoggingTab()
        self.addTab(self._logging_tab, "Logging")

        # Filters tab
        self._filters_tab = FiltersTab()
        self.addTab(self._filters_tab, "Filters")

        # Export tab
        from analyzer.export_tab import ExportTab
        self._export_tab = ExportTab()
        self.addTab(self._export_tab, "Export")

        # Settings tab
        from analyzer.settings_tab import SettingsTab
        self._settings_tab = SettingsTab(config) if config else None
        if self._settings_tab:
            self.addTab(self._settings_tab, "Settings")

        # Reverse Engineer tab
        from analyzer.reverse_engineer_tab import ReverseEngineerTab
        self._re_tab: Optional[ReverseEngineerTab] = None
        if signal_db is not None:
            self._re_tab = ReverseEngineerTab(signal_db)
            self.addTab(self._re_tab, "Reverse Engineer")

        # --- Right-side corner buttons (Pause/Play + Clear History) ---
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setFixedSize(70, 22)
        self._pause_btn.setStyleSheet(
            "QPushButton { background-color: #df8e1d; color: #1e1e2e; font-weight: bold; font-size: 9px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #e89b2a; }"
        )
        self._pause_btn.clicked.connect(self._toggle_capture)
        corner_layout.addWidget(self._pause_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedSize(60, 22)
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #d20f39; color: #1e1e2e; font-weight: bold; font-size: 9px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #e0164a; }"
        )
        self._clear_btn.clicked.connect(self._on_clear)
        corner_layout.addWidget(self._clear_btn)

        self.setCornerWidget(corner_widget, Qt.Corner.TopRightCorner)

    @property
    def logging_tab(self) -> LoggingTab:
        """Access the logging tab instance."""
        return self._logging_tab

    @property
    def filters_tab(self) -> FiltersTab:
        """Access the filters tab instance."""
        return self._filters_tab

    @property
    def history_tab(self):
        """Access the history tab instance (may be None)."""
        return self._history_tab

    @property
    def re_tab(self):
        """Access the reverse engineer tab instance (may be None)."""
        return self._re_tab

    @property
    def export_tab(self):
        """Access the export tab instance."""
        return self._export_tab

    @property
    def settings_tab(self):
        """Access the settings tab instance (may be None)."""
        return self._settings_tab

    @property
    def is_capturing(self) -> bool:
        """Whether capture is active (not paused)."""
        return self._capturing

    def _toggle_capture(self) -> None:
        """Toggle between capturing and paused states."""
        self._capturing = not self._capturing
        if self._capturing:
            self._pause_btn.setText("Pause")
            self._pause_btn.setStyleSheet(
                "QPushButton { background-color: #df8e1d; color: #1e1e2e; font-weight: bold; font-size: 9px; border-radius: 3px; }"
                "QPushButton:hover { background-color: #e89b2a; }"
            )
            self.capture_resumed.emit()
        else:
            self._pause_btn.setText("Play")
            self._pause_btn.setStyleSheet(
                "QPushButton { background-color: #40a02b; color: #1e1e2e; font-weight: bold; font-size: 9px; border-radius: 3px; }"
                "QPushButton:hover { background-color: #4cb533; }"
            )
            self.capture_paused.emit()

    def _on_clear(self) -> None:
        """Emit signal to clear packet history."""
        self.clear_requested.emit()

    def log_packet(self, packet: dict) -> None:
        """Forward a packet to the logging tab (respects filter-applies-to-logging).

        Args:
            packet: Packet dict to log.
        """
        # If "Apply filters to Logging" is checked, skip filtered opcodes
        if self._filters_tab.apply_to_logging:
            opcode = packet.get("opcode", "")
            if self._filters_tab.is_blocked(opcode):
                return
        self._logging_tab.log_packet(packet)

    @property
    def is_logging(self) -> bool:
        """Whether logging is currently active."""
        return self._logging_tab.is_logging

    def is_opcode_blocked(self, opcode: str) -> bool:
        """Check if an opcode is in the blocklist."""
        return self._filters_tab.is_blocked(opcode)

    def shutdown(self) -> None:
        """Clean shutdown of all tabs."""
        self._logging_tab.shutdown()
