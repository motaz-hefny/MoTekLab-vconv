"""Fahhim theme for vconv — Rosé (light) / Crimson (dark) / system-follow.

Palette source: ~/WebProjects/Fahhim/src/index.css (tokens copied verbatim).
This module is the single source of truth for colors — widget code must
never hardcode hex values (rule enforced by the source scan in
tests/test_theme.py; see AGENTS.md "Fahhim Theme Pattern").
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPalette, QColor

PALETTES = {
    'light': {
        'background': '#fdf6f5', 'foreground': '#251320',
        'card': '#ffffff', 'card_fg': '#251320',
        'primary': '#be123c', 'primary_fg': '#ffffff',
        'secondary': '#f7ebe9', 'secondary_fg': '#251320',
        'muted': '#f7ebe9', 'muted_fg': '#7d5f6a',
        'accent': '#fdecf0', 'accent_fg': '#881337',
        'border': '#ecd9dc', 'input': '#ecd9dc',
        'destructive': '#b91c1c',
        'grad_start': '#f43f5e', 'grad_mid': '#e11d48', 'grad_end': '#be123c',
        'info': '#0369a1', 'success': '#2ECC71', 'subtle': '#7d5f6a',
    },
    'dark': {
        'background': '#140e0c', 'foreground': '#f4e3dd',
        'card': '#1c1310', 'card_fg': '#f4e3dd',
        'primary': '#e5534b', 'primary_fg': '#200a08',
        'secondary': '#2a1a15', 'secondary_fg': '#f4e3dd',
        'muted': '#221613', 'muted_fg': '#a4847a',
        'accent': '#2a1a15', 'accent_fg': '#f0c3ba',
        'border': '#33201b', 'input': '#221613',
        'destructive': '#ff7a6b',
        'grad_start': '#c22b23', 'grad_mid': '#e5534b', 'grad_end': '#c22b23',
        'info': '#00B4D8', 'success': '#5fc26a', 'subtle': '#a4847a',
    },
}

_active = 'light'
_state = {'app': None, 'mode': None, 'connected': False, 'fusion': False}


def resolve(mode, system_scheme=None):
    """Map a config mode + OS scheme to a concrete palette name."""
    if mode == 'system':
        return 'dark' if system_scheme == Qt.ColorScheme.Dark else 'light'
    return mode if mode in PALETTES else 'light'


def current_palette():
    """Palette dict of the theme currently applied (light until first apply)."""
    return PALETTES[_active]


def active_theme():
    """Return the concrete active theme name ('light' or 'dark')."""
    return _active


def current_mode(config):
    return config.get('appearance', 'theme', 'system')


def set_mode(config, mode):
    config.set('appearance', 'theme', mode)
    config.save()


def build_stylesheet(theme_name):
    """Fahhim QSS for one theme. CSS braces are doubled (f-string)."""
    p = PALETTES[theme_name]
    return f"""
QWidget {{ background: transparent; color: {p['foreground']}; }}
QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog, QSplitter, QWidget#centralWidget, QWidget#rightPanel {{ background-color: {p['background']}; color: {p['foreground']}; }}
QDialog, QMessageBox {{ background-color: {p['background']}; color: {p['foreground']}; }}
QMessageBox QLabel {{ background-color: transparent; color: {p['foreground']}; font-size: 13px; }}
QMenuBar {{ background: {p['secondary']}; color: {p['foreground']}; border-bottom: 1px solid {p['border']}; }}
QMenuBar::item:selected {{ background: {p['accent']}; color: {p['accent_fg']}; }}
QMenu {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; }}
QMenu::item {{ padding: 4px 24px 4px 12px; }}
QMenu::item:selected {{ background: {p['primary']}; color: {p['primary_fg']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 2px 6px; }}
QGroupBox {{ border: 1px solid {p['border']}; border-radius: 6px; margin-top: 12px; padding-top: 8px; background: {p['card']}; color: {p['foreground']}; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px; background-color: {p['card']}; color: {p['accent_fg']}; border-radius: 3px; }}
QTabWidget::pane {{ border: 1px solid {p['border']}; background: {p['card']}; top: -1px; }}
QTabBar::tab {{ background: {p['secondary']}; color: {p['muted_fg']}; padding: 5px 14px; border: 1px solid {p['border']}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {p['card']}; color: {p['primary']}; border-bottom: 2px solid {p['primary']}; }}
QComboBox {{ background: {p['secondary']}; color: {p['foreground']}; border: 1px solid {p['border']}; border-radius: 5px; padding: 3px 8px; }}
QComboBox:hover {{ border-color: {p['primary']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; selection-background-color: {p['primary']}; selection-color: {p['primary_fg']}; }}
QCheckBox {{ spacing: 6px; color: {p['foreground']}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {p['border']}; border-radius: 3px; background: {p['card']}; }}
QCheckBox::indicator:checked {{ background: {p['primary']}; border-color: {p['primary']}; }}
QCheckBox::indicator:hover {{ border-color: {p['primary']}; }}
QRadioButton {{ spacing: 6px; color: {p['foreground']}; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border: 1px solid {p['border']}; border-radius: 7px; background: {p['card']}; }}
QRadioButton::indicator:checked {{ background: {p['primary']}; border-color: {p['primary']}; }}
QLineEdit, QTextEdit {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; border-radius: 5px; padding: 3px 6px; selection-background-color: {p['primary']}; selection-color: {p['primary_fg']}; }}
QPlainTextEdit {{ background: {p['background']}; color: {p['foreground']}; border: 1px solid {p['border']}; border-radius: 5px; padding: 4px; selection-background-color: {p['primary']}; selection-color: {p['primary_fg']}; }}
QSlider::groove:horizontal {{ height: 5px; background: {p['muted']}; border: 1px solid {p['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {p['primary']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: {p['primary']}; border: 2px solid {p['card']}; }}
QTableView, QTableWidget {{ background: {p['card']}; alternate-background-color: {p['secondary']}; color: {p['foreground']}; border: 1px solid {p['border']}; gridline-color: {p['border']}; selection-background-color: {p['accent']}; selection-color: {p['accent_fg']}; }}
QHeaderView::section {{ background: {p['secondary']}; color: {p['muted_fg']}; border: none; border-right: 1px solid {p['border']}; border-bottom: 1px solid {p['border']}; padding: 4px 6px; }}
QListWidget {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; }}
QListWidget::item:selected {{ background: {p['accent']}; color: {p['accent_fg']}; }}
QScrollBar:vertical {{ background: {p['secondary']}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p['muted_fg']}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: {p['secondary']}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p['muted_fg']}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {p['border']}; }}
QSplitter::handle:hover {{ background: {p['primary']}; }}
QProgressBar {{ background: {p['muted']}; border: 1px solid {p['border']}; border-radius: 5px; text-align: center; color: {p['foreground']}; }}
QProgressBar::chunk {{ background: {p['success']}; border-radius: 4px; }}
QToolTip {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['primary']}; padding: 4px 8px; }}
QStatusBar {{ background: {p['secondary']}; color: {p['foreground']}; border-top: 1px solid {p['border']}; }}
QToolBar {{ background: {p['secondary']}; border-bottom: 1px solid {p['border']}; spacing: 4px; padding: 2px; }}
QToolButton {{ background: transparent; border: none; border-radius: 4px; padding: 4px 6px; color: {p['foreground']}; }}
QToolButton:hover {{ background: {p['accent']}; }}
QScrollArea {{ background: transparent; border: none; }}
QPushButton {{ background: {p['secondary']}; color: {p['secondary_fg']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ background: {p['accent']}; color: {p['accent_fg']}; border-color: {p['primary']}; }}
QPushButton:disabled {{ color: {p['muted_fg']}; background: {p['muted']}; }}
QPushButton#primaryBtn {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['grad_start']}, stop:0.5 {p['grad_mid']}, stop:1 {p['grad_end']}); color: {p['primary_fg']}; border: none; font-weight: bold; padding: 7px 16px; }}
QPushButton#primaryBtn:hover {{ background: {p['grad_mid']}; }}
QLabel#hwLabel {{ color: {p['info']}; font-size: 11px; }}
QLabel#statusLabel {{ color: {p['success']}; font-weight: bold; font-size: 13px; }}
QLabel#audioTracksStatus {{ color: {p['subtle']}; font-size: 10px; }}
QLabel#efficiencyHintLabel {{ color: {p['accent_fg']}; font-size: 11px; padding: 5px 8px; border-radius: 4px; background: {p['secondary']}; border: 1px solid {p['border']}; }}
QToolButton#themeToggleBtn {{ font-size: 14px; padding: 2px 8px; border: 1px solid {p['border']}; border-radius: 4px; background: {p['card']}; color: {p['foreground']}; }}
QToolButton#themeToggleBtn:hover {{ background: {p['accent']}; border-color: {p['primary']}; }}
"""


def build_palette(theme_name):
    """Build a QPalette matching the Fahhim theme tokens."""
    p = PALETTES[theme_name]
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(p['background']))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(p['foreground']))
    pal.setColor(QPalette.ColorRole.Base, QColor(p['card']))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p['secondary']))
    pal.setColor(QPalette.ColorRole.Text, QColor(p['foreground']))
    pal.setColor(QPalette.ColorRole.Button, QColor(p['secondary']))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(p['foreground']))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(p['primary']))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(p['primary_fg']))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p['card']))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p['foreground']))
    return pal


def apply_theme(app, mode):
    """Apply the Fahhim stylesheet app-wide; returns the concrete theme used.

    mode: 'light' | 'dark' | 'system'. System resolves from
    QStyleHints.colorScheme() and re-applies live on colorSchemeChanged.
    """
    global _active
    if app is None:
        return resolve(mode)
    scheme = None
    if mode == 'system':
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
        except Exception:
            scheme = None
    resolved = resolve(mode, scheme)
    _active = resolved
    if not _state['fusion']:
        app.setStyle('Fusion')
        _state['fusion'] = True
    app.setPalette(build_palette(resolved))
    app.setStyleSheet(build_stylesheet(resolved))
    _state['app'] = app
    _state['mode'] = mode
    if mode == 'system' and not _state['connected']:
        QGuiApplication.styleHints().colorSchemeChanged.connect(_on_system_scheme)
        _state['connected'] = True
    return resolved


def _on_system_scheme(_scheme):
    if _state['mode'] == 'system' and _state['app'] is not None:
        apply_theme(_state['app'], 'system')
