# Tools dialog Refresh kills the app (QThread destroyed while running) — 2026-10-08 (v9.7.5)

## Report
While testing v9.7.4 the user clicked **Refresh** in Tools & Encoders; the
**entire application exited silently** (no error dialog, no log entry).

## Evidence
- **Coredump**: `/var/lib/systemd/coredump/core.python3.1001.9c88bc481c2b455cab2a2c7a8e933046.54469.1791448868000000.zst`
  — PID 54469, `python3 /opt/vconv/vconv.py --gui` started 11:40:37,
  **SIGABRT at 11:41:08** (EEST).
- `coredumpctl debug 54469` backtrace:
  `QMessageLogger::fatal` → `sipQThread::~sipQThread` →
  `forgetObject/sipWrapper_dealloc` → `PyObject_SetAttr` → `PyQtSlot::call`.
  Qt's message: **`QThread: Destroyed while thread '' is still running`**.
- `~/.config/vconv/logs/vconv.log` has **no entry** — `qFatal` aborts the
  process without passing through Python logging.

## Root cause
`ToolUpdaterWorker.run()` emits its custom `done` signal from the `finally`
block — **inside the thread**, i.e. *before the OS thread has exited*. The
slot `ToolsDialog._refresh_done` then ran:

```python
self._refresh_worker = None   # last Python reference dropped
```

Python immediately destroyed the C++ `QThread` that was still running → Qt
called `qFatal` → `abort()`.

Signals such as `done` (emitted in `run()`) and `QThread.finished` mean
"thread is *about* to exit"; only `wait()` proves it exited.

## Bug-class inventory (same pattern, all in `ui/main_window.py`)
| # | Site | Status |
|---|------|--------|
| 1 | `ToolsDialog._refresh_done` — `= None` while thread still in `run()` | **confirmed crash** |
| 2 | `ToolUpdaterWorker` install `finished` → `_install_workers.discard(worker)` | same pattern |
| 3 | Dialog teardown — closing the dialog (refresh running) frees its attrs | same pattern |
| 4 | `_check_for_updates_now/_startup` reassign `self._update_worker` | same pattern |
| 5 | `self.worker = ConversionWorker(...)` reassignment | same pattern |
| 6 | `_start_auto_update` reassigns `self._update_install_worker` (never initialized) | same pattern |
| 7 | `MainWindow.closeEvent` frees the window (owner of all workers) with no join | same pattern |

## Fix (`ui/main_window.py`)
- New module helpers: `_ZOMBIE_THREADS` registry, `_park(worker)` (hold the
  reference, join on `finished`, idempotent) and `_retire_parked(worker)`
  (`wait()` then release). `_park(None)` is a no-op.
- `ToolsDialog._refresh_done`: keep a local ref, clear the attr, **`wait()`**
  before scope exit.
- `ToolsDialog.done(int)` override: parks refresh + install workers on *any*
  close path (Accept/Reject/Esc/X — all funnel through `done()`); close stays
  non-blocking.
- `_retire_install_worker`: joins on `finished` before `discard` (idempotent).
- `_park(old)` before every worker-attribute reassignment (`self.worker`,
  `self._update_worker`, `self._update_install_worker`); the latter is now
  initialized to `None` in `MainWindow.__init__`.
- `MainWindow._shutdown_workers()` called from `closeEvent`: `wait(5000)` per
  owned worker, park on timeout.
- Also fixed stale dialog copy from the 9.7.4 HandBrake behavior change
  ("update it via Flatpak or your package manager" note, tooltip).

## Tests
- **Pre-fix reproduction** (old code + `tests/test_thread_lifecycle.py`
  approach): process **core dumped** with the exact Qt message above —
  deterministic, race window of 0.4 s (worker emits completion, then sleeps).
- **Post-fix**:
  - `tests/test_thread_lifecycle.py` — **10 checks green** (refresh join,
    install retire, close-dialog-mid-refresh, park-of-finished-thread).
  - `tests/test_tools_startup_smoke.py` — **12 checks green** (+2:
    `_shutdown_workers` joins a running thread; tolerates `None` workers).
- **Full suite: 210 checks green** across 9 files
  (23+6+36+14+16+10+12+85+8), `QT_QPA_PLATFORM=offscreen`.

## Known residual edge (accepted)
A worker still running after the 5 s shutdown wait is parked; if it outlives
interpreter teardown the exit can still abort. In practice startup checks
finish in seconds, so this bounds the risk.

## Verification command
`QT_QPA_PLATFORM=offscreen python3 tests/test_thread_lifecycle.py`
→ `RESULT: ALL PASS (10 checks)`
