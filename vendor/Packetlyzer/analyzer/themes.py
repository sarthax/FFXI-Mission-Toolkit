"""Color Theme System for the Packetlyzer Analyzer.

Provides predefined theme palettes (Dark, Light, FFXI) and generates
Qt stylesheets from theme definitions. Users can switch themes at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThemePalette:
    """A color palette defining all UI colors for a theme."""

    name: str

    # Base colors
    bg_primary: str        # Main background
    bg_secondary: str      # Panel/sidebar background
    bg_tertiary: str       # Nested elements (tables, inputs)
    bg_selected: str       # Selection highlight

    # Text colors
    text_primary: str      # Main text
    text_secondary: str    # Muted/subtitle text
    text_accent: str       # Highlighted/active text

    # Borders and separators
    border: str            # General borders
    separator: str         # Splitter/divider lines

    # Packet direction colors
    s2c_bg: str            # Server-to-client row background
    s2c_text: str          # Server-to-client text
    c2s_bg: str            # Client-to-server row background
    c2s_text: str          # Client-to-server text

    # Accent colors
    accent_blue: str       # Links, selections
    accent_green: str      # Success, connected
    accent_red: str        # Error, danger
    accent_yellow: str     # Warning, paused
    accent_peach: str      # Special highlights

    # Scrollbar
    scrollbar_bg: str
    scrollbar_handle: str

    # Header/toolbar
    header_bg: str
    header_text: str

    # Tab bar
    tab_bg: str
    tab_active_bg: str
    tab_text: str
    tab_active_text: str


# ---------------------------------------------------------------------------
# Theme Definitions
# ---------------------------------------------------------------------------

THEME_DARK = ThemePalette(
    name="Dark",
    bg_primary="#1e1e2e",
    bg_secondary="#181825",
    bg_tertiary="#242436",
    bg_selected="#45475a",
    text_primary="#cdd6f4",
    text_secondary="#a6adc8",
    text_accent="#89b4fa",
    border="#313244",
    separator="#313244",
    s2c_bg="#1e2030",
    s2c_text="#89b4fa",
    c2s_bg="#1e2a1e",
    c2s_text="#a6e3a1",
    accent_blue="#89b4fa",
    accent_green="#40a02b",
    accent_red="#d20f39",
    accent_yellow="#df8e1d",
    accent_peach="#fab387",
    scrollbar_bg="#1e1e2e",
    scrollbar_handle="#45475a",
    header_bg="#2a2d3c",
    header_text="#c8d0f0",
    tab_bg="#181825",
    tab_active_bg="#1e1e2e",
    tab_text="#a6adc8",
    tab_active_text="#cdd6f4",
)

THEME_LIGHT = ThemePalette(
    name="Light",
    bg_primary="#eff1f5",
    bg_secondary="#e6e9ef",
    bg_tertiary="#dce0e8",
    bg_selected="#bcc0cc",
    text_primary="#4c4f69",
    text_secondary="#6c6f85",
    text_accent="#1e66f5",
    border="#ccd0da",
    separator="#ccd0da",
    s2c_bg="#dde5f5",
    s2c_text="#1e66f5",
    c2s_bg="#ddf5dd",
    c2s_text="#40a02b",
    accent_blue="#1e66f5",
    accent_green="#40a02b",
    accent_red="#d20f39",
    accent_yellow="#df8e1d",
    accent_peach="#fe640b",
    scrollbar_bg="#e6e9ef",
    scrollbar_handle="#9ca0b0",
    header_bg="#ccd0da",
    header_text="#4c4f69",
    tab_bg="#e6e9ef",
    tab_active_bg="#eff1f5",
    tab_text="#6c6f85",
    tab_active_text="#4c4f69",
)

THEME_FFXI = ThemePalette(
    name="FFXI",
    bg_primary="#0a0a14",
    bg_secondary="#0f0f1e",
    bg_tertiary="#141428",
    bg_selected="#2a2a4a",
    text_primary="#d4c4a0",
    text_secondary="#8a7a5a",
    text_accent="#c8a84c",
    border="#2a2a3e",
    separator="#2a2a3e",
    s2c_bg="#0a0f1e",
    s2c_text="#6ca0dc",
    c2s_bg="#0a1e0f",
    c2s_text="#6cdc6c",
    accent_blue="#6ca0dc",
    accent_green="#4caa4c",
    accent_red="#cc4444",
    accent_yellow="#ccaa44",
    accent_peach="#dca06c",
    scrollbar_bg="#0a0a14",
    scrollbar_handle="#3a3a5a",
    header_bg="#14142a",
    header_text="#c8a84c",
    tab_bg="#0f0f1e",
    tab_active_bg="#0a0a14",
    tab_text="#8a7a5a",
    tab_active_text="#d4c4a0",
)

# All available themes
THEMES: dict[str, ThemePalette] = {
    "Dark": THEME_DARK,
    "Light": THEME_LIGHT,
    "FFXI": THEME_FFXI,
}

THEME_NAMES: list[str] = list(THEMES.keys())


def generate_stylesheet(theme: ThemePalette) -> str:
    """Generate a complete Qt stylesheet from a theme palette.

    Args:
        theme: The ThemePalette to generate styles from.

    Returns:
        A Qt CSS stylesheet string.
    """
    return f"""
QMainWindow {{
    background-color: {theme.bg_primary};
}}
QWidget {{
    background-color: {theme.bg_primary};
    color: {theme.text_primary};
}}
QLabel {{
    color: {theme.text_primary};
}}
QTabWidget::pane {{
    border: 1px solid {theme.border};
    background-color: {theme.bg_primary};
}}
QTabBar::tab {{
    background-color: {theme.tab_bg};
    color: {theme.tab_text};
    padding: 6px 12px;
    border: 1px solid {theme.border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: {theme.tab_active_bg};
    color: {theme.tab_active_text};
    border-bottom: 2px solid {theme.accent_blue};
}}
QTabBar::tab:hover {{
    background-color: {theme.bg_selected};
}}
QLineEdit {{
    background-color: {theme.bg_tertiary};
    color: {theme.text_primary};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 4px 8px;
}}
QLineEdit:focus {{
    border-color: {theme.accent_blue};
}}
QPushButton {{
    background-color: {theme.bg_selected};
    color: {theme.text_primary};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 4px 12px;
}}
QPushButton:hover {{
    background-color: {theme.accent_blue};
    color: {theme.bg_primary};
}}
QPushButton:pressed {{
    background-color: {theme.bg_tertiary};
}}
QComboBox {{
    background-color: {theme.bg_tertiary};
    color: {theme.text_primary};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 4px 8px;
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {theme.bg_secondary};
    color: {theme.text_primary};
    selection-background-color: {theme.bg_selected};
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {theme.bg_tertiary};
    color: {theme.text_primary};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 2px 4px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 16px;
    border-left: 1px solid {theme.border};
    background-color: {theme.bg_selected};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: {theme.accent_blue};
}}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {{
    background-color: {theme.bg_tertiary};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    width: 8px;
    height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {theme.text_primary};
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 16px;
    border-left: 1px solid {theme.border};
    border-top: 1px solid {theme.border};
    background-color: {theme.bg_selected};
}}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {theme.accent_blue};
}}
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background-color: {theme.bg_tertiary};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    width: 8px;
    height: 8px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {theme.text_primary};
}}
QCheckBox {{
    color: {theme.text_primary};
}}
QRadioButton {{
    color: {theme.text_primary};
}}
QGroupBox {{
    border: 1px solid {theme.border};
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    color: {theme.text_secondary};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QListWidget {{
    background-color: {theme.bg_tertiary};
    color: {theme.text_primary};
    border: 1px solid {theme.border};
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: {theme.bg_selected};
}}
QTreeWidget, QTreeView {{
    background-color: {theme.bg_tertiary};
    alternate-background-color: {theme.bg_secondary};
    color: {theme.text_primary};
    border: none;
    selection-background-color: {theme.bg_selected};
}}
QTreeWidget::item:selected, QTreeView::item:selected {{
    background-color: {theme.bg_selected};
}}
QHeaderView::section {{
    background-color: {theme.bg_secondary};
    color: {theme.text_secondary};
    padding: 4px;
    border: none;
    border-right: 1px solid {theme.border};
    border-bottom: 1px solid {theme.border};
}}
QPlainTextEdit {{
    background-color: {theme.bg_tertiary};
    color: {theme.text_primary};
    border: none;
}}
QTableWidget {{
    background-color: {theme.bg_tertiary};
    alternate-background-color: {theme.bg_secondary};
    gridline-color: {theme.border};
    selection-background-color: {theme.bg_selected};
    border: none;
}}
QTableView {{
    background-color: {theme.bg_tertiary};
    alternate-background-color: {theme.bg_secondary};
    gridline-color: {theme.border};
    selection-background-color: {theme.bg_selected};
    border: none;
}}
QSplitter::handle {{
    background-color: {theme.separator};
}}
QStatusBar {{
    background-color: {theme.bg_secondary};
    color: {theme.text_secondary};
}}
QScrollBar:vertical {{
    background-color: {theme.scrollbar_bg};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background-color: {theme.scrollbar_handle};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: {theme.scrollbar_bg};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background-color: {theme.scrollbar_handle};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QMessageBox {{
    background-color: {theme.bg_primary};
}}
QDialog {{
    background-color: {theme.bg_primary};
}}
"""
