#!/usr/bin/env python3
"""
Tools Startup Smoke Test (v9.7.0)

Verifies the MainWindow wiring for the Tool Updater without touching the
network: stubs the background workers and checks the Settings menu actions
and the Tools dialog trigger exist and behave.

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_tools_startup_smoke.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
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


class _StubWorker(QThread):
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


def main():
    app = QApplication([])

    # Stub the three workers that do network I/O at startup
    mw.UpdateCheckWorker = _StubWorker
    mw.ToolUpdaterWorker = _StubWorker
    mw.ToolInstallWorker = _StubWorker

    # Hermetic config: temp file so test toggles never pollute the user's
    # real ~/.config/vconv.conf (which would break the next run's defaults).
    tmp = tempfile.TemporaryDirectory(prefix="vconv_smoke_")
    cfg = Config(str(Path(tmp.name) / "vconv.conf"))
    win = mw.MainWindow(cfg, I18n(lang="en"))
    win.show()

    check("act_auto_tools menu action exists", hasattr(win, "act_auto_tools"))
    auto = cfg.get('general', 'auto_update_tools', True)
    check("auto_update_tools defaults to True", auto is True)
    check("act_auto_tools matches config", win.act_auto_tools.isChecked() == auto)

    # Toggle persists
    win.act_auto_tools.trigger()
    check("toggling act_auto_tools flips config",
          cfg.get('general', 'auto_update_tools') is not auto)

    # _show_tools_dialog opens ToolsDialog (stubbed worker -> no network)
    dlg = mw.ToolsDialog(cfg)
    check("ToolsDialog row count == 3", len(dlg.rows) == 3)
    check("ToolsDialog has auto_check", hasattr(dlg, "auto_check"))
    for tid in ("ffmpeg", "nvencc", "handbrake"):
        check(f"ToolsDialog rows include {tid}", tid in dlg.rows)

    # _ensure_ffmpeg no longer apt-updates; logs only
    win._ensure_ffmpeg()
    check("_ensure_ffmpeg returns (no crash)", True)

    # _shutdown_workers (closeEvent) must join still-running owned threads —
    # freeing a running QThread makes Qt abort the app (2026-10-08 crash).
    class _LingeringThread(QThread):
        def run(self):
            time.sleep(0.4)

    lw = _LingeringThread()
    win.worker = lw
    lw.start()
    win._shutdown_workers()
    check("_shutdown_workers joins running threads", not lw.isRunning())

    win.worker = None
    win._tools_worker = None
    win._update_worker = None
    win._update_install_worker = None
    win._shutdown_workers()
    check("_shutdown_workers tolerates None workers", True)

    tmp.cleanup()

    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())