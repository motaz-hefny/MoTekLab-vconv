#!/usr/bin/env python3
"""
Dynamic settings-panel width tests (unreleased): content-hug + reflow.
Spec: docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py
"""
import gc
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QSizePolicy
from PyQt6.QtCore import pyqtSignal
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
    """No-network stand-in for the three startup workers (pattern from test_layout_dynamic)."""
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
    tmp = tempfile.TemporaryDirectory(prefix="vconv_width_")
    cfg = Config(str(Path(tmp.name) / "vconv.conf"))
    win = mw.MainWindow(cfg, I18n(lang="en"))
    win._width_test_tmp = tmp  # keep alive with the window
    return win


def settle(win):
    """Show the window and fire the startup-hug QTimer.singleShot(0)."""
    win.show()
    for _ in range(3):
        QApplication.processEvents()


def left_w(win):
    return win.splitter.sizes()[0]


def hug(win):
    return win.settings_tabs.sizeHint().width()


def floor(win):
    return win.settings_tabs.minimumSizeHint().width()


def test_helper_truth_table():
    A = mw.MainWindow._left_width_action
    check("manual + below floor -> floor", A(180, 240, 210, True) == 210)
    check("manual + above floor -> None (sticky)", A(300, 240, 210, True) is None)
    check("manual + equal floor -> None", A(210, 240, 210, True) is None)
    check("auto + differs -> hug", A(300, 240, 210, False) == 240)
    check("auto + equal -> None", A(240, 240, 210, False) is None)


def main():
    app = QApplication.instance() or QApplication([])
    test_helper_truth_table()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
