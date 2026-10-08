#!/usr/bin/env python3
"""
Format Selection Radio Tests

Verifies the output-format radio group (MP4/MKV) stays in sync with
`MainWindow.format` — regression test for the v9.6.2 bug where clicking
the MKV radio looked checked but output was still saved as .mp4.

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_format_radio.py
"""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from core.validator import generate_output_path
from utils.config import Config
from utils.i18n import I18n
from ui.main_window import MainWindow

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


def main():
    app = QApplication([])
    win = MainWindow(Config(), I18n(lang="en"))
    win.show()

    check(f"Initial format is config default ('mp4')", win.format == 'mp4')
    check(f"Initial mp4_radio checked", win.mp4_radio.isChecked())
    check(f"Initial mkv_radio unchecked", not win.mkv_radio.isChecked())

    # --- Direct radio click path (the v9.6.2 bug) ---
    win.mkv_radio.setChecked(True)
    check(f"MKV radio click sets format='mkv'", win.format == 'mkv')
    check(f"MKV radio checked", win.mkv_radio.isChecked())
    check(f"MP4 radio unchecked", not win.mp4_radio.isChecked())

    win.mp4_radio.setChecked(True)
    check(f"MP4 radio click sets format='mp4'", win.format == 'mp4')
    check(f"MP4 radio checked", win.mp4_radio.isChecked())
    check(f"MKV radio unchecked", not win.mkv_radio.isChecked())

    # --- Menu / programmatic path (always worked) ---
    win._set_format('mkv')
    check(f"_set_format('mkv') works (menu path)", win.format == 'mkv')
    win._set_format('mp4')
    check(f"_set_format('mp4') works (menu path)", win.format == 'mp4')

    # --- Output extension follows format ---
    d = tempfile.mkdtemp()
    src = os.path.join(d, "video.mkv")
    open(src, "w").close()
    check(f"generate_output_path format='mkv' -> .mkv",
          generate_output_path(src, format='mkv').endswith('.mkv'))
    check(f"generate_output_path format='mp4' -> .mp4",
          generate_output_path(src, format='mp4').endswith('.mp4'))

    # --- Flip-flop stress test (no desync / infinite recursion) ---
    desync = False
    for _ in range(10):
        win.mkv_radio.setChecked(True)
        if win.format != 'mkv' or not win.mkv_radio.isChecked() or win.mp4_radio.isChecked():
            desync = True
            break
        win.mp4_radio.setChecked(True)
        if win.format != 'mp4' or not win.mp4_radio.isChecked() or win.mkv_radio.isChecked():
            desync = True
            break
    check("10x radio flip-flop: no desync", not desync)

    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())