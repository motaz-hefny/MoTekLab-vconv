#!/usr/bin/env python3
"""
Fahhim theme tests (unreleased): Rosé light / Crimson dark / system-follow.
Spec: docs/superpowers/specs/2026-10-08-fahhim-theme-design.md

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py
"""
import gc
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel
import ui.theme as theme
import ui.main_window as mw
from utils.config import Config
from utils.i18n import I18n

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


class _StubWorker(mw.QThread):
    status_ready = pyqtSignal(object)
    update_found = pyqtSignal(object)
    auto_updated = pyqtSignal(object)
    done = pyqtSignal()
    result = pyqtSignal(object, bool, str)
    progress = pyqtSignal(float, str)

    def __init__(self, *a, **k):
        super().__init__()

    def start(self, *a, **k):
        return None


def make_window():
    mw.UpdateCheckWorker = _StubWorker
    mw.ToolUpdaterWorker = _StubWorker
    mw.ToolInstallWorker = _StubWorker
    tmp = tempfile.TemporaryDirectory(prefix="vconv_theme_")
    cfg = Config(str(Path(tmp.name) / "vconv.conf"))
    win = mw.MainWindow(cfg, I18n(lang="en"))
    win._theme_test_tmp = tmp
    return win


REQUIRED = {
    'background', 'foreground', 'card', 'card_fg', 'primary', 'primary_fg',
    'secondary', 'secondary_fg', 'muted', 'muted_fg', 'accent', 'accent_fg',
    'border', 'input', 'destructive', 'grad_start', 'grad_mid', 'grad_end',
    'info', 'success', 'subtle',
}


def test_palette_tokens_and_fahhim_hexes():
    for name in ('light', 'dark'):
        missing = REQUIRED - set(theme.PALETTES[name])
        check(f"{name} palette complete ({sorted(missing)})", not missing)
    L, D = theme.PALETTES['light'], theme.PALETTES['dark']
    check("light bg #fdf6f5", L['background'] == '#fdf6f5')
    check("light primary #be123c", L['primary'] == '#be123c')
    check("light border #ecd9dc", L['border'] == '#ecd9dc')
    check("light gradient f43f5e/e11d48/be123c",
          (L['grad_start'], L['grad_mid'], L['grad_end'])
          == ('#f43f5e', '#e11d48', '#be123c'))
    check("dark bg #140e0c", D['background'] == '#140e0c')
    check("dark primary #e5534b", D['primary'] == '#e5534b')
    check("dark border #33201b", D['border'] == '#33201b')
    check("dark gradient c22b23/e5534b/c22b23",
          (D['grad_start'], D['grad_mid'], D['grad_end'])
          == ('#c22b23', '#e5534b', '#c22b23'))


def test_build_stylesheet():
    ls = theme.build_stylesheet('light')
    ds = theme.build_stylesheet('dark')
    check("light stylesheet substantial", len(ls) > 1500)
    check("stylesheets differ light vs dark", ls != ds)
    check("light sheet carries light primary", '#be123c' in ls)
    check("dark sheet carries dark primary", '#e5534b' in ds)
    check("primaryBtn gradient rule present",
          'qlineargradient' in ls and 'QPushButton#primaryBtn' in ls)
    check("objectName rules present",
          all(s in ls for s in ('QLabel#hwLabel', 'QLabel#statusLabel',
                                'QLabel#audioTracksStatus')))


def test_resolve_system_mapping():
    check("system + Dark -> dark",
          theme.resolve('system', Qt.ColorScheme.Dark) == 'dark')
    check("system + Light -> light",
          theme.resolve('system', Qt.ColorScheme.Light) == 'light')
    check("dark passthrough", theme.resolve('dark', Qt.ColorScheme.Light) == 'dark')
    check("light passthrough",
          theme.resolve('light', Qt.ColorScheme.Dark) == 'light')
    check("unknown mode falls back to light",
          theme.resolve('purple') == 'light')


def test_apply_theme_switches_stylesheet():
    app = QApplication.instance() or QApplication([])
    t1 = theme.apply_theme(app, 'light')
    check("apply light returns light", t1 == 'light')
    check("light stylesheet on app", '#be123c' in app.styleSheet())
    t2 = theme.apply_theme(app, 'dark')
    check("apply dark returns dark", t2 == 'dark')
    check("dark stylesheet on app", '#e5534b' in app.styleSheet())
    check("current_palette follows active theme",
          theme.current_palette()['primary'] == '#e5534b')


def test_config_persistence():
    tmp = tempfile.TemporaryDirectory(prefix="vconv_theme_cfg_")
    path = str(Path(tmp.name) / "vconv.conf")
    cfg = Config(path)
    cfg.load()
    check("fresh config default mode is system",
          theme.current_mode(cfg) == 'system')
    theme.set_mode(cfg, 'dark')
    cfg2 = Config(path)
    cfg2.load()
    check("dark persisted across reload", theme.current_mode(cfg2) == 'dark')
    tmp.cleanup()


def main():
    app = QApplication.instance() or QApplication([])
    test_palette_tokens_and_fahhim_hexes()
    test_build_stylesheet()
    test_resolve_system_mapping()
    test_apply_theme_switches_stylesheet()
    test_config_persistence()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
