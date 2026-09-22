"""Packetlyzer — FFXI Packet Capture and Analysis Tool.

Main entry point for the Analyzer application. Ties together the socket
server, packet decoder, configuration, and PyQt6 display.

Usage:
    python packetlyzer.py [--port PORT] [--import-xipackets PATH] [--import-xievents PATH]
"""

import argparse
import logging
import os
import queue
import sys
import time
from typing import Optional

from analyzer.config import Config
from analyzer.decoder import PacketDecoder
from analyzer.lookup import LookupManager
from analyzer.packet_db import PacketDB
from analyzer.server import PacketServer, validate_port

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "packetlyzer_config.json")
_DB_XML_PATH = os.path.join(_BASE_DIR, "packetlyzer_db.xml")
_FFXI_XML_PATH = os.path.join(_BASE_DIR, "ffxi.xml")
_EXT_JSON_PATH = os.path.join(_BASE_DIR, "packetlyzer_ext.json")
_SIGNALS_DB_PATH = os.path.join(_BASE_DIR, "signals_db.json")
_LOOKUP_DIR = os.path.join(_BASE_DIR, "lookup")
_SQL_DIR = os.path.join(os.path.dirname(_BASE_DIR), "FFXI_TestServer", "sql")  # Default; overridden if not found

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Parsed namespace with port, import_xipackets, and import_xievents.
    """
    parser = argparse.ArgumentParser(
        prog="packetlyzer",
        description="Packetlyzer — FFXI Packet Capture and Analysis Tool",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="TCP port to listen on (1024-65535). Overrides config file.",
    )
    parser.add_argument(
        "--import-xipackets",
        metavar="PATH",
        default=None,
        help="Import XiPackets markdown files from the given world directory.",
    )
    parser.add_argument(
        "--import-xievents",
        metavar="PATH",
        default=None,
        help="Import XiEvents markdown files from the given OpCodes directory.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Import handlers
# ---------------------------------------------------------------------------


def handle_import_xipackets(path: str) -> None:
    """Run XiPackets import and exit.

    Args:
        path: Path to the XiPackets world directory.
    """
    from analyzer.importer import XiPacketsImporter

    db = PacketDB(_DB_XML_PATH, _EXT_JSON_PATH)
    importer = XiPacketsImporter()
    added, updated = importer.import_from(path, db)
    print(f"XiPackets import complete: {added} added, {updated} updated.")
    sys.exit(0)


def handle_import_xievents(path: str) -> None:
    """Run XiEvents import and exit.

    Args:
        path: Path to the XiEvents OpCodes directory.
    """
    from analyzer.importer import XiEventsImporter

    importer = XiEventsImporter()
    count = importer.import_from(path, _EXT_JSON_PATH)
    print(f"XiEvents import complete: {count} event opcodes imported.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Dark theme stylesheet
# ---------------------------------------------------------------------------

_DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QSplitter::handle {
    background-color: #45475a;
    width: 2px;
}
QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #242436;
    gridline-color: #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    border: none;
}
QTableView::item {
    padding: 2px 4px;
}
QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 4px;
}
QTreeWidget {
    background-color: #1e1e2e;
    alternate-background-color: #242436;
    border: none;
}
QTreeWidget::item {
    padding: 2px;
}
QPlainTextEdit {
    background-color: #1e1e2e;
    color: #bac2de;
    border: none;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 6px 12px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}
QToolBar {
    background-color: #181825;
    border: none;
    spacing: 6px;
    padding: 4px;
}
QToolButton {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    padding: 4px 10px;
    border-radius: 3px;
}
QToolButton:hover {
    background-color: #45475a;
}
QToolButton:checked {
    background-color: #585b70;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    padding: 5px 12px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #45475a;
}
QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 3px 6px;
    border-radius: 2px;
}
QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 3px;
    border-radius: 2px;
}
QComboBox:hover {
    border: 1px solid #89b4fa;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QDockWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #181825;
    padding: 6px;
}
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
}
QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QFormLayout {
    background-color: #1e1e2e;
}
QLabel {
    color: #cdd6f4;
}
QCheckBox {
    color: #cdd6f4;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QMessageBox {
    background-color: #1e1e2e;
}
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #1e1e2e;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QTableWidget {
    background-color: #1e1e2e;
    alternate-background-color: #242436;
    gridline-color: #313244;
    selection-background-color: #45475a;
    border: none;
}
"""


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------


class PacketlyzerWindow:
    """Main application window (QMainWindow) with all UI components."""

    def __init__(
        self,
        config: Config,
        packet_db: PacketDB,
        lookup_mgr: LookupManager,
        decoder: PacketDecoder,
        packet_queue: queue.Queue,
        server: PacketServer,
        msg_resolver=None,
        signal_db=None,
        npc_lookup=None,
    ):
        from PyQt6.QtCore import QTimer, Qt
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import (
            QApplication,
            QMainWindow,
            QSplitter,
            QStatusBar,
        )

        from analyzer.bottom_panel import BottomPanel
        from analyzer.detail_panel import DetailPanel
        from analyzer.display import PacketListWidget
        from analyzer.exporter import PacketExporter
        from analyzer.history_panel import HistoryPanel
        from analyzer.live_editor import LiveEditor

        self._config = config
        self._packet_queue = packet_queue
        self._server = server
        self._msg_resolver = msg_resolver
        self._signal_db = signal_db
        self._paused = False
        self._pause_buffer: list[dict] = []

        # --- Main window ---
        self._window = QMainWindow()
        self._window.setWindowTitle("Packetlyzer")
        self._window.resize(config.window_width, config.window_height)

        # --- Layout: Left column (packet list + bottom panel) | Right (detail panel) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._window.setCentralWidget(main_splitter)

        # Left column: vertical splitter (top: packet list, bottom: tabs)
        left_vsplitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(left_vsplitter)

        # Top-left: Packet list widget (no longer split with history)
        self._packet_list = PacketListWidget(config, packet_db, decoder)
        left_vsplitter.addWidget(self._packet_list)

        # History panel — created here but housed inside BottomPanel as a tab
        self._history_panel = HistoryPanel()

        # Bottom-left: bottom panel (logging tabs, etc.) — with history as first tab
        self._bottom_panel = BottomPanel(config=config, signal_db=signal_db, history_panel=self._history_panel)
        left_vsplitter.addWidget(self._bottom_panel)

        # Restore saved filter state
        if config.blocked_opcodes or config.passed_opcodes:
            self._bottom_panel.filters_tab.load_state(
                config.blocked_opcodes or [], config.apply_filters_to_logging,
                config.filter_mode, config.passed_opcodes or []
            )

        # 65% top / 35% bottom for the left column
        left_vsplitter.setSizes([650, 350])

        # Right: detail panel (full height)
        self._detail_panel = DetailPanel(decoder, lookup_mgr, npc_lookup)
        if signal_db:
            self._detail_panel.set_signal_db(signal_db)
        main_splitter.addWidget(self._detail_panel)

        # 60/40 split for left column vs detail panel
        main_splitter.setSizes([600, 400])

        # Connect packet selection to history panel and detail panel
        self._packet_list.packet_selected.connect(self._on_packet_selected)
        self._packet_list.packet_updated.connect(self._on_packet_updated)
        self._history_panel.packet_pinned.connect(self._on_history_pinned)
        self._history_panel.packet_unpinned.connect(self._on_history_unpinned)

        # Connect capture buttons (in tab bar corner)
        self._bottom_panel.clear_requested.connect(self._on_clear_history)

        # Connect reverse engineer tab signals
        if self._bottom_panel.re_tab:
            self._detail_panel.bytes_selected.connect(self._on_bytes_selected)
            self._bottom_panel.re_tab.signal_saved.connect(self._on_signal_changed)
            self._bottom_panel.re_tab.signal_deleted.connect(self._on_signal_changed)

        # Connect export tab
        self._bottom_panel.export_tab.export_requested.connect(self._on_export_requested)

        # Connect settings tab (theme changes)
        if self._bottom_panel.settings_tab:
            self._bottom_panel.settings_tab.theme_changed.connect(self._on_theme_changed)

        # --- Status bar ---
        self._status_bar = QStatusBar()
        self._status_bar.setFont(QFont("Cascadia Mono", 9))
        self._window.setStatusBar(self._status_bar)
        self._status_bar.showMessage(f"Listening on port {config.port}")

        # --- Live Editor (dock widget) ---
        self._live_editor = LiveEditor(
            packet_db, lookup_mgr, decoder,
            on_redecode=self._redecode_selected,
        )
        self._live_editor.setVisible(False)
        self._window.addDockWidget(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.DockWidgetArea.RightDockWidgetArea,
            self._live_editor,
        )

        # --- Exporter ---
        self._exporter = PacketExporter(on_status=self._show_export_status)

        # --- QTimer for polling packet queue (16ms ≈ 60fps) ---
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(16)

        # --- Selected packet tracking for editor ---
        self._selected_packet: Optional[dict] = None

    def show(self) -> None:
        """Show the main window."""
        self._window.show()

    def save_config(self) -> None:
        """Save configuration on exit."""
        # Update window size from actual size
        size = self._window.size()
        self._config.window_width = size.width()
        self._config.window_height = size.height()

        # Save filter state
        blocked, apply_to_log, filter_mode, passed = self._bottom_panel.filters_tab.save_state()
        self._config.blocked_opcodes = blocked
        self._config.passed_opcodes = passed
        self._config.apply_filters_to_logging = apply_to_log
        self._config.filter_mode = filter_mode

        # Save last known zone for resolver bootstrap
        if self._msg_resolver and self._msg_resolver.current_zone_id > 0:
            self._config.last_zone_id = self._msg_resolver.current_zone_id

        try:
            self._config.save(_CONFIG_PATH)
            logger.info("Configuration saved to %s", _CONFIG_PATH)
        except OSError as e:
            logger.error("Failed to save configuration: %s", e)

    # ---------------------------------------------------------------------------
    # Slots
    # ---------------------------------------------------------------------------

    def _on_packet_selected(self, packet: dict) -> None:
        """Handle packet selection from the main list."""
        self._selected_packet = packet
        # Update detail panel
        self._detail_panel.set_packet(packet)
        # Update history panel with this opcode's history
        direction = packet.get("direction", "")
        opcode = packet.get("opcode", "")
        all_packets = self._packet_list.model.packets
        self._history_panel.set_opcode_filter(direction, opcode, all_packets)
        # Update live editor if visible
        if self._live_editor.isVisible():
            self._live_editor.populate_from_packet(packet)
        # Update reverse engineer tab context
        if self._bottom_panel.re_tab:
            data_hex = packet.get("data", "")
            try:
                raw = bytes.fromhex(data_hex)
            except ValueError:
                raw = b""
            self._bottom_panel.re_tab.set_packet_context(direction, opcode, raw)
        # Feed history packets to the detail panel for slider/byte tracker
        matching = [
            p for p in all_packets
            if p.get("direction") == direction and p.get("opcode") == opcode
        ]
        self._detail_panel.set_history_packets(matching)

    def _on_history_pinned(self, packet: dict) -> None:
        """Handle a specific packet being pinned from the history panel."""
        self._detail_panel.set_packet(packet)
        # Navigate the detail panel's slider to the pinned packet
        self._detail_panel.navigate_to_packet(packet)

    def _on_packet_updated(self, packet: dict) -> None:
        """Handle detail-only update (no history rebuild) from fixed mode auto-update."""
        self._selected_packet = packet
        self._detail_panel.set_packet(packet)
        if self._live_editor.isVisible():
            self._live_editor.populate_from_packet(packet)

    def _on_history_unpinned(self) -> None:
        """Handle history deselection — revert detail to latest for the opcode."""
        if self._selected_packet:
            self._detail_panel.set_packet(self._selected_packet)

    def _on_clear_history(self) -> None:
        """Clear all packet history from memory."""
        self._packet_list.clear_packets()
        self._history_panel.clear_filter()
        self._detail_panel.clear()
        self._status_bar.showMessage("Packet history cleared", 3000)

    def _on_bytes_selected(self, offset: int, length: int) -> None:
        """Handle byte selection from the hex dump — forward to RE tab and detail panel tracker."""
        if self._bottom_panel.re_tab:
            self._bottom_panel.re_tab.set_selection(offset, length)
        # Update the detail panel's byte tracker
        self._detail_panel.track_bytes(offset, length)

    def _on_signal_changed(self) -> None:
        """Handle signal saved/deleted — re-decode the current packet."""
        if self._selected_packet:
            self._detail_panel.set_packet(self._selected_packet)

    def _open_settings(self) -> None:
        """Open the settings dialog (legacy — now handled by Settings tab)."""
        pass

    def _start_export(self) -> None:
        """Legacy export (now handled by Export tab)."""
        pass

    def _toggle_editor(self) -> None:
        """Toggle the live editor dock widget."""
        self._live_editor.setVisible(not self._live_editor.isVisible())

    def _toggle_pause(self, checked: bool) -> None:
        """Toggle pause/resume of packet consumption (legacy toolbar handler)."""
        self._paused = checked
        if not checked:
            # Flush buffered packets
            for pkt in self._pause_buffer:
                self._packet_list.append_packet(pkt)
            self._pause_buffer.clear()

    def _on_export_requested(self, path: str, fmt: str) -> None:
        """Handle export request from the Export tab."""
        packets = self._packet_list.visible_packets
        if not packets:
            self._bottom_panel.export_tab.set_status("No packets to export")
            return

        self._exporter.export_visible(packets, path, fmt)
        self._bottom_panel.export_tab.set_status(f"Exported {len(packets)} packets")

    def _on_theme_changed(self, theme_name: str) -> None:
        """Apply a new color theme to the application."""
        from analyzer.themes import THEMES, generate_stylesheet
        from PyQt6.QtWidgets import QApplication

        theme = THEMES.get(theme_name)
        if theme:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(generate_stylesheet(theme))
            self._config.theme = theme_name

    def _redecode_selected(self) -> None:
        """Re-decode the currently selected packet after DB save."""
        if self._selected_packet:
            self._detail_panel.set_packet(self._selected_packet)

    def _show_export_status(self, message: str, duration: float) -> None:
        """Show export status in the status bar."""
        self._status_bar.showMessage(message, int(duration * 1000))

    def _poll_queue(self) -> None:
        """Consume packets from the server queue."""
        count = 0
        while not self._packet_queue.empty() and count < 100:
            try:
                msg = self._packet_queue.get_nowait()
            except queue.Empty:
                break

            try:
                # Process ALL messages through the resolver for zone tracking
                # (zone change events have type=="event", not "packet")
                if self._msg_resolver:
                    self._msg_resolver.process_packet(msg)

                if msg.get("type") == "packet":
                    # Validate/fix timestamp — if missing or clearly not epoch,
                    # stamp with current local time
                    ts = msg.get("timestamp", 0)
                    if not isinstance(ts, (int, float)) or ts < 946684800000:
                        # 946684800000 = Jan 1, 2000 in ms — anything below is invalid
                        msg["timestamp"] = int(time.time() * 1000)

                    # Resolve dialog text for this packet
                    if self._msg_resolver:
                        resolved = self._msg_resolver.resolve(msg)
                        if resolved:
                            msg["_resolved_text"] = resolved

                    opcode = msg.get("opcode", "")

                    # Check opcode filter — drop before entering memory
                    if self._bottom_panel.is_opcode_blocked(opcode):
                        # Still log if filter doesn't apply to logging
                        if not self._bottom_panel.filters_tab.apply_to_logging:
                            self._bottom_panel.log_packet(msg)
                        count += 1
                        continue

                    if self._paused:
                        self._pause_buffer.append(msg)
                    elif not self._bottom_panel.is_capturing:
                        # Capture paused — still log but don't store in memory
                        self._bottom_panel.log_packet(msg)
                    else:
                        self._packet_list.append_packet(msg)
                        # Feed history panel if it matches the current filter
                        self._history_panel.append_if_matches(msg)
                        # Auto-update detail panel slider if new packet matches current opcode
                        if self._selected_packet:
                            sel_dir = self._selected_packet.get("direction", "")
                            sel_op = self._selected_packet.get("opcode", "")
                            if msg.get("direction") == sel_dir and msg.get("opcode") == sel_op:
                                self._detail_panel.append_history_packet(msg)
                        # Log packet if logging is active
                        self._bottom_panel.log_packet(msg)
            except Exception:
                pass  # Don't let a single bad packet kill the poll timer

            count += 1


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the Packetlyzer Analyzer.

    Initialization order:
    1. Parse CLI arguments
    2. Load configuration from packetlyzer_config.json
    3. Initialize PacketDB (XML + ext JSON) and LookupManager
    4. Initialize Decoder
    5. Start socket server (before GUI)
    6. Initialize PyQt6 application and main window
    7. Run event loop
    8. Save config on clean exit
    """
    args = parse_args(argv)

    # --- Handle import-only modes (run and exit) ---
    if args.import_xipackets:
        handle_import_xipackets(args.import_xipackets)
        return

    if args.import_xievents:
        handle_import_xievents(args.import_xievents)
        return

    # --- Load configuration (Req 13.1) ---
    config = Config.load(_CONFIG_PATH)
    logger.info("Configuration loaded from %s", _CONFIG_PATH)

    # --- Determine port: CLI overrides config ---
    if args.port is not None:
        port = validate_port(args.port)
        config.port = port
    else:
        port = config.port

    # --- Load Packet_DB (Req 8.5: full DB before server accepts connections) ---
    logger.info("Loading packet database...")
    # Load ffxi.xml first (has rich VieweD scripting: loops, conditionals, etc.)
    # Then merge packetlyzer_db.xml on top (XiPackets imports for new opcodes only)
    if os.path.isfile(_FFXI_XML_PATH):
        db_path = _FFXI_XML_PATH
        logger.info("Primary database: %s", db_path)
        packet_db = PacketDB(db_path, _EXT_JSON_PATH)
        # Merge packetlyzer_db.xml for opcodes not in ffxi.xml
        if os.path.isfile(_DB_XML_PATH):
            logger.info("Merging supplementary database: %s", _DB_XML_PATH)
            supplement_db = PacketDB(_DB_XML_PATH)
            merged_count = 0
            for key, defn in supplement_db._definitions.items():
                if key not in packet_db._definitions:
                    packet_db._definitions[key] = defn
                    merged_count += 1
            logger.info("Merged %d additional definitions from supplementary DB", merged_count)
    elif os.path.isfile(_DB_XML_PATH):
        db_path = _DB_XML_PATH
        logger.info("Using database: %s", db_path)
        packet_db = PacketDB(db_path, _EXT_JSON_PATH)
    else:
        db_path = _DB_XML_PATH  # Will error with clear message
        packet_db = PacketDB(db_path, _EXT_JSON_PATH)

    # --- Load Lookup Tables ---
    lookup_mgr = LookupManager(_LOOKUP_DIR)

    # --- Initialize Decoder ---
    decoder = PacketDecoder(_FFXI_XML_PATH, _EXT_JSON_PATH, _LOOKUP_DIR, packet_db=packet_db)
    logger.info("Decoder initialized")

    # --- Initialize NPC Lookup (entity ID → name resolution) ---
    from analyzer.npc_lookup import NPCLookup

    # Try multiple possible SQL directory locations
    npc_lookup = None
    sql_candidates = [
        _SQL_DIR,
        os.path.join(os.path.expanduser("~"), "FFXI_TestServer", "sql"),
        r"C:\Users\rodin\FFXI_TestServer\sql",
    ]
    for sql_path in sql_candidates:
        if os.path.isdir(sql_path) and os.path.isfile(os.path.join(sql_path, "npc_list.sql")):
            npc_lookup = NPCLookup(sql_path, lookup_mgr=lookup_mgr)
            logger.info("NPC Lookup loaded: %d entities from %s", npc_lookup.entry_count, sql_path)
            break
    if npc_lookup is None:
        # Still create with lookup_mgr for item/zone/model resolution
        npc_lookup = NPCLookup(None, lookup_mgr=lookup_mgr)
        logger.info("NPC Lookup: npc_list.sql not found, entity ID resolution disabled (lookup tables still active)")

    # --- Initialize FFXI DAT resolver and Message resolver ---
    from analyzer.ffxi_dat import FFXIDatResolver
    from analyzer.message_resolver import MessageResolver
    from analyzer.signal_db import SignalDB

    ffxi_path = config.ffxi_path if config.ffxi_path else None
    dat_resolver = FFXIDatResolver(ffxi_path)
    msg_resolver = MessageResolver(dat_resolver)
    if dat_resolver.is_available:
        logger.info("FFXI DAT resolver ready: %s", dat_resolver.ffxi_path)
        # Bootstrap with last known zone so resolution works before first zone packet
        if config.last_zone_id > 0:
            msg_resolver.set_zone(config.last_zone_id)
            logger.info("Resolver bootstrapped with last zone: %d", config.last_zone_id)
    else:
        logger.info("FFXI DAT resolver not available (dialog text resolution disabled)")

    # --- Initialize Signal Database ---
    signal_db = SignalDB(_SIGNALS_DB_PATH)
    logger.info("Signal database: %d signals loaded", signal_db.signal_count)

    # --- Start socket server BEFORE GUI (Req 5.2) ---
    packet_queue: queue.Queue = queue.Queue()
    server = PacketServer("127.0.0.1", port, packet_queue)
    server.start()
    logger.info("Socket server started on port %d", port)

    # --- Initialize PyQt6 application ---
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Apply color theme from config
    from analyzer.themes import THEMES, generate_stylesheet
    theme = THEMES.get(config.theme, THEMES["Dark"])
    app.setStyleSheet(generate_stylesheet(theme))

    # --- Create and show main window ---
    window = PacketlyzerWindow(config, packet_db, lookup_mgr, decoder, packet_queue, server, msg_resolver, signal_db, npc_lookup)
    window.show()

    # --- Run event loop ---
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        exit_code = 0
    finally:
        # --- Cleanup ---
        server.stop()
        window._bottom_panel.shutdown()
        window.save_config()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
