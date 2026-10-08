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

from PyQt6.QtWidgets import QApplication, QScrollArea, QSplitter, QTabWidget
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
    tabs0 = getattr(win, "settings_tabs", None)
    if tabs0 is not None:
        tabs0.setCurrentIndex(2)
        QApplication.processEvents()
    sub = getattr(win, "sub_group", None)
    got = sub.height() if sub else 0
    want = sub.sizeHint().height() if sub else -1
    check(f"Subtitles box keeps natural height at 760x520 (got {got}/{want})",
          sub is not None and got >= want - 2)
    win.close()
    del win
    gc.collect()


def test_log_splitter_drives_log_height():
    win = make_window()
    win.show()
    win.resize(1250, 800)
    QApplication.processEvents()
    spl = getattr(win, "log_splitter", None)
    check("vertical 2-child log splitter exists",
          isinstance(spl, QSplitter)
          and spl.count() == 2
          and spl.orientation() == Qt.Orientation.Vertical)
    check("log_text has no fixed height cap",
          win.log_text.maximumHeight() > 1_000_000)
    spl.setSizes([400, 300])
    QApplication.processEvents()
    check(f"log grows with splitter (height={win.log_text.height()})",
          win.log_text.height() > 150)
    win.close()
    del win
    gc.collect()


def test_settings_tabs_structure():
    win = make_window()
    win.show()
    tabs = getattr(win, "settings_tabs", None)
    check("settings_tabs is a QTabWidget", isinstance(tabs, QTabWidget))
    check("3 tabs labeled Video/Audio/Subtitles",
          tabs is not None and tabs.count() == 3
          and [tabs.tabText(i) for i in range(3)] == ["Video", "Audio", "Subtitles"])
    if tabs is not None and tabs.count() == 3:
        video, audio, subs = tabs.widget(0), tabs.widget(1), tabs.widget(2)
        check("Preset on Video tab", video.isAncestorOf(win.preset_combo))
        check("Encoder on Video tab", video.isAncestorOf(win.encoder_combo))
        check("Crop on Video tab", video.isAncestorOf(win.crop_custom_radio))
        check("Quality on Video tab", video.isAncestorOf(win.quality_slider))
        check("Output on Video tab", video.isAncestorOf(win.output_dir_edit))
        check("Format on Video tab", video.isAncestorOf(win.mp4_radio))
        check("metadata checkbox inside Video tab (Output group)",
              video.isAncestorOf(win.metadata_check))
        check("Audio group on Audio tab", audio.isAncestorOf(win.audio_enc_combo))
        check("Subtitles group on Subtitles tab", subs.isAncestorOf(win.sub_group))
    win.close()
    del win
    gc.collect()


def main():
    app = QApplication.instance() or QApplication([])
    test_settings_tabs_structure()
    test_settings_panel_never_squashes()
    test_log_splitter_drives_log_height()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
