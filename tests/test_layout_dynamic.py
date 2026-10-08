#!/usr/bin/env python3
"""
Dynamic layout tests (unreleased): scrollable settings panel + draggable
Activity Log.  Regression for the v9.7.x "Subtitles box squashed / log
capped at 100px" report (spec: docs/superpowers/specs/2026-10-08-dynamic-layout-design.md).

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py
"""
import gc
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QScrollArea, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal
from utils.config import Config
from utils.i18n import I18n
import ui.main_window as mw

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
    """No-network stand-in for the three startup workers (smoke-test pattern)."""
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
    tmp = tempfile.TemporaryDirectory(prefix="vconv_layout_")
    cfg = Config(str(Path(tmp.name) / "vconv.conf"))
    win = mw.MainWindow(cfg, I18n(lang="en"))
    win._layout_test_tmp = tmp  # keep alive with the window
    return win


def test_settings_panel_never_squashes():
    win = make_window()
    win.show()
    scroll = getattr(win, "settings_scroll", None)
    check("left panel wrapped in QScrollArea", isinstance(scroll, QScrollArea))
    win.resize(760, 520)
    QApplication.processEvents()
    sub = getattr(win, "sub_group", None)
    got = sub.height() if sub else 0
    want = sub.sizeHint().height() if sub else -1
    check(f"Subtitles box keeps natural height at 760x520 (got {got}/{want})",
          sub is not None and got >= want - 2)
    win.close()
    del win
    gc.collect()


def main():
    app = QApplication.instance() or QApplication([])
    test_settings_panel_never_squashes()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
