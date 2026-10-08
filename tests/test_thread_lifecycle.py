#!/usr/bin/env python3
"""
QThread lifecycle regression tests (v9.7.5 fix)

The v9.7.4 autoclose: clicking Refresh in Tools & Encoders killed the whole
app. Root cause (proved by coredump 2026-10-08 11:41:08, SIGABRT,
`python3 /opt/vconv/vconv.py --gui`):

    ToolsDialog._refresh_done is connected to ToolUpdaterWorker's custom
    `done` signal, which is emitted INSIDE run() — before the OS thread has
    exited. The slot did `self._refresh_worker = None`, the refcount hit 0,
    sip deleted the C++ QThread while it was still running, and Qt called
    qFatal("QThread: Destroyed while thread is still running") → abort().

    backtrace: QMessageLogger::fatal → sipQThread::~sipQThread →
               sipWrapper_dealloc → PyObject_SetAttr (the `= None`) →
               PyQtSlot::call (queued signal delivery)

These tests make the race DETERMINISTIC by using a worker that emits its
completion signal and then lingers (keeps the OS thread alive) — exactly the
window the real code hits. Before the fix the process is aborted by Qt; after
the fix every site joins (wait()) or parks the thread before dropping the
last reference.

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_thread_lifecycle.py
"""
import gc
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication

import ui.main_window as mw

PASS = 0
LINGER = 0.4


def check(cond, msg):
    global PASS
    if not cond:
        raise AssertionError(msg)
    PASS += 1


class StubConfig:
    def get(self, section, key, default=None):
        return default

    def set(self, *args):
        pass

    def save(self):
        pass


class LingeringRefreshWorker(mw.ToolUpdaterWorker):
    """Emits `done` like the real worker, then keeps the OS thread alive.

    The real bug window is the few microseconds between `done.emit()` inside
    run() and the thread actually exiting; LINGER widens it so the main
    thread deterministically processes the queued slot while the thread is
    still running.
    """

    def run(self):
        self.done.emit()
        time.sleep(LINGER)


class LingeringInstallWorker(mw.ToolInstallWorker):
    """Emits result + `finished`, then lingers before exiting run()."""

    def run(self):
        st = SimpleNamespace(tool_id="ffmpeg", display="ffmpeg",
                             installed_version="8.1", latest_version="8.1",
                             update_available=False, note="")
        self.result.emit(st, True, "ok")
        self.finished.emit()          # same "just before exit" point as Qt
        time.sleep(LINGER)


class InstantRefreshWorker(mw.ToolUpdaterWorker):
    """Completion-only refresh worker: no network, thread exits right away."""

    def run(self):
        self.done.emit()


class NoModalMessageBox:
    """QMessageBox stub — offscreen tests must never block on a modal."""

    @staticmethod
    def information(*args, **kwargs):
        return None

    @staticmethod
    def warning(*args, **kwargs):
        return None

    @staticmethod
    def question(*args, **kwargs):
        return None


def pump_until(app, predicate, timeout=8.0):
    deadline = time.time() + timeout
    while not predicate():
        if time.time() > deadline:
            raise AssertionError("timed out pumping events")
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


def make_dialog(mw_module):
    return mw_module.ToolsDialog(StubConfig())


def test_refresh_done_joins_running_thread():
    """refresh() completion must join the OS thread before the ref dies."""
    app = QApplication.instance() or QApplication([])
    orig = mw.ToolUpdaterWorker
    mw.ToolUpdaterWorker = LingeringRefreshWorker
    try:
        dlg = make_dialog(mw)          # __init__ calls refresh() with our fake
        # Pre-fix: processing `done` runs _refresh_done → `= None` → sip
        # deletes the running QThread → Qt qFatal → the process ABORTS here.
        pump_until(app, lambda: dlg._refresh_worker is None)
        check(True, "refresh worker retired without crash")
        # Dialog must remain fully usable: run a second refresh cycle.
        dlg.refresh()
        pump_until(app, lambda: dlg._refresh_worker is None)
        check(True, "second refresh cycle clean")
        del dlg
    finally:
        mw.ToolUpdaterWorker = orig


def test_install_worker_discard_joins_thread():
    """_install_workers must join before dropping the worker reference."""
    app = QApplication.instance() or QApplication([])
    orig_refresh = mw.ToolUpdaterWorker
    orig_install = mw.ToolInstallWorker
    orig_box = mw.QMessageBox
    mw.ToolUpdaterWorker = InstantRefreshWorker   # dialog __init__: no network
    mw.ToolInstallWorker = LingeringInstallWorker # the racing install worker
    mw.QMessageBox = NoModalMessageBox            # result handler must not block
    try:
        dlg = make_dialog(mw)
        dlg._on_update_clicked("ffmpeg")     # real code path for Update click
        # Pre-fix: `finished` → discard → last ref gone while worker sleeps
        # in run() → qFatal → abort.
        pump_until(app, lambda: len(dlg._install_workers) == 0)
        check(True, "install worker discarded without crash")
        del dlg
        gc.collect()
    finally:
        mw.ToolUpdaterWorker = orig_refresh
        mw.ToolInstallWorker = orig_install
        mw.QMessageBox = orig_box


def test_close_dialog_while_refresh_running():
    """Closing the dialog mid-refresh must not delete a running QThread.

    _show_tools_dialog lets `dlg` fall out of scope right after exec()
    returns; if the refresh worker is still running, dialog destruction
    would drop the last reference → same qFatal crash.
    """
    app = QApplication.instance() or QApplication([])
    orig = mw.ToolUpdaterWorker
    mw.ToolUpdaterWorker = LingeringRefreshWorker
    try:
        dlg = make_dialog(mw)
        worker = dlg._refresh_worker
        check(worker is not None, "refresh running before close")
        dlg.done(0)                      # what accept/reject/X all funnel into
        del dlg
        gc.collect()
        # Worker must have been parked (or joined), not freed while running.
        zombies = getattr(mw, "_ZOMBIE_THREADS", None)
        check(zombies is not None, "zombie registry exists")
        check(worker in zombies or not worker.isRunning(),
              "closing dialog did not drop a running thread")
        # Let it retire for real; nothing may crash while it finishes.
        deadline = time.time() + 8.0
        while zombies and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        check(not zombies, "zombie threads retired after close")
        check(not worker.isRunning(), "worker exited")
    finally:
        mw.ToolUpdaterWorker = orig


def test_park_finished_thread_is_immediate():
    """Parking an already-finished thread must not linger in the registry."""
    app = QApplication.instance() or QApplication([])
    t = InstantRefreshWorker(False)
    t.start()
    t.wait()
    mw._park(t)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()
    check(t not in mw._ZOMBIE_THREADS, "finished thread retired immediately")
    check(not t.isRunning(), "thread stopped")


def main():
    test_refresh_done_joins_running_thread()
    test_install_worker_discard_joins_thread()
    test_close_dialog_while_refresh_running()
    test_park_finished_thread_is_immediate()
    print(f"RESULT: ALL PASS ({PASS} checks)")


if __name__ == "__main__":
    main()
