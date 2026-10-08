#!/usr/bin/env python3
"""
ToolUpdaterWorker runtime test (v9.7.0 fix)

Regression test for the ImportError bug: `ToolUpdaterWorker.run()` did
`from utils.tool_updater import ToolUpdater, TOOL_IDS`, but `TOOL_IDS` is a
class attribute (`ToolUpdater.TOOL_IDS`), not a module-level name — so the
worker died before emitting any status, leaving the Tools & Encoders dialog
stuck on "checking…".

This test executes the *real* `run()` body (no network) with a fake
`ToolUpdater` so future regressions surface as a hard failure.

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_tool_worker.py
"""
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from utils import tool_updater as tu_mod
from ui.main_window import ToolUpdaterWorker

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


TOOL_IDS = ("ffmpeg", "nvencc", "handbrake")


def make_status(tid, update_available=True):
    return SimpleNamespace(
        tool_id=tid,
        display=tid,
        installed_version="9.9.9",
        latest_version="10.0.0",
        update_available=update_available,
        installed_path="/fake",
        note="",
    )


class FakeUpdater:
    """No-network stand-in: status() always 'outdated', update() succeeds."""

    TOOL_IDS = TOOL_IDS
    calls = {"status": 0, "update": 0}

    def status(self, tid):
        self.calls["status"] += 1
        return make_status(tid)

    def update(self, tid):
        self.calls["update"] += 1
        return True


def main():
    app = QApplication([])

    original = tu_mod.ToolUpdater
    try:
        tu_mod.ToolUpdater = FakeUpdater

        worker = ToolUpdaterWorker(auto_update_tools=True)
        statuses = []
        auto = []
        done = []

        worker.status_ready.connect(statuses.append)
        worker.auto_updated.connect(auto.append)
        worker.done.connect(lambda: done.append(True))

        # Run synchronously on the caller thread — exercises the full run()
        # body, including the exact import statement that used to raise.
        worker.run()

        seen = {s.tool_id for s in statuses}
        check("worker.run() imports ToolUpdater and iterates TOOL_IDS without error",
              statuses)
        check("status emitted for all 3 tools", seen == set(TOOL_IDS))
        check("auto_update_tools=True auto-updates only ffmpeg+nvencc",
              FakeUpdater.calls["update"] == 2)
        check("auto_updated emitted for the 2 auto-installed tools", len(auto) == 2)
        check("done emitted exactly once", len(done) == 1)

        # False -> no auto-install
        FakeUpdater.calls["update"] = 0
        worker2 = ToolUpdaterWorker(auto_update_tools=False)
        done2 = []
        worker2.done.connect(lambda: done2.append(True))
        worker2.run()
        check("auto_update_tools=False performs no updates", FakeUpdater.calls["update"] == 0)
        check("worker with auto_update off still finishes", len(done2) == 1)
    finally:
        tu_mod.ToolUpdater = original

    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())