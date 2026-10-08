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


def test_reflow():
    win = make_window()
    settle(win)
    # Every settings-panel combo must be horizontally Ignored (precedent: encoder_combo).
    bad = [c for c in win.settings_tabs.findChildren(QComboBox)
           if c.sizePolicy().horizontalPolicy() != QSizePolicy.Policy.Ignored]
    check(f"all settings-panel combos Ignored ({len(bad)} non-Ignored)", not bad)
    # GPU label: objectName + word wrap (spec: measurable rule, hint width 202).
    hw = win.findChild(QLabel, "hwLabel")
    check("hwLabel present with objectName", hw is not None)
    check("hwLabel word-wraps", hw is not None and hw.wordWrap())
    # Shortened labels, full copy in tooltips.
    check("radio shortened", win.output_same_radio.text() == "Same as source")
    check("radio tooltip keeps full copy",
          win.output_same_radio.toolTip() == "Same as source (preserve structure)")
    check("checkbox shortened",
          win.flat_output_check.text() == "Flat output (single folder)")
    check("checkbox tooltip keeps full copy",
          win.flat_output_check.toolTip()
          == "Flat output (dump all files in one folder)")
    # Subtitles mega-row split: ext_opts_layout must NOT be nested in ext_btn_layout.
    btn_lay = win.findChild(mw.QHBoxLayout, "ext_btn_layout")
    opts_lay = win.findChild(mw.QHBoxLayout, "ext_opts_layout")
    check("ext_btn_layout found", btn_lay is not None)
    check("ext_opts_layout found", opts_lay is not None)
    check("ext_opts_layout NOT nested in ext_btn_layout",
          btn_lay is not None and opts_lay is not None
          and btn_lay.indexOf(opts_lay) == -1)
    # Post-reflow floors (font-dependent soft bounds from the spec table).
    check(f"sub_group min < 300 ({win.sub_group.minimumSizeHint().width()})",
          win.sub_group.minimumSizeHint().width() < 300)
    win.settings_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    check(f"audio hug < 200 ({hug(win)})", hug(win) < 200)
    win.close()
    del win
    gc.collect()


def main():
    app = QApplication.instance() or QApplication([])
    test_helper_truth_table()
    test_reflow()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
