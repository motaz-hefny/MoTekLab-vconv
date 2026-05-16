# Upgrade Audit — vconv → MoTekLab Video Encoder

Comprehensive project audit conducted 2026-05-16 by opencode.

> **Next version name:** "MoTekLab Video Encoder"
> **Current version:** v9.2.1

---

## 🔴 CRITICAL — Fix Immediately

### 1. Config Memory Mutation Bug
**File:** `utils/config.py:74-77, 178-183`
**Problem:** `DEFAULT_CONFIG.copy()` is a **shallow copy**. Nested dicts (e.g. `DEFAULT_CONFIG['general']['language']`) are shared references. When the user changes language, it mutates the original `DEFAULT_CONFIG` permanently. Any subsequent `reset_to_defaults()` call returns garbage.
**Fix:** Replace `DEFAULT_CONFIG.copy()` with `copy.deepcopy(DEFAULT_CONFIG)`.

### 2. requirements.txt Is Dangerously Wrong
**File:** `requirements.txt`
**Problem:** Lists `pysimplegui>=4.65.0` (unused — removed in v9.0) and **missing** `PyQt6` and `markdown` — both required. A new developer cloning the project and running `pip install -r requirements.txt` will install the wrong framework.
**Fix:** Remove `pysimplegui`, add `PyQt6` and `markdown`.

### 3. Bash Script Shadows PATH Variable
**File:** `vconv` (Bash), line 110
**Problem:** `local PATH="$1"` — overrides the system `PATH` variable inside the function. All subsequent command lookups (find, yad, grep, etc.) will fail inside this function.
**Fix:** Rename the parameter variable to `local file_path="$1"`.

### 4. Version String Chaos
**Files:** Multiple — `vconv.py:3` (docstring `9.0.0`), `core/__init__.py:17` (`9.0.0`), `ui/main_window.py:227` (`9.0.0`), `README.md:24` (`9.1.0`), `vconv.desktop:2` (`9.1`)
**Problem:** 5 different version strings across the codebase. The actual release was `9.2.0`. This caused confusion during debugging and inconsistent About dialogs. (Fixed in 9.2.1 — now centralized in `utils/version.py`.)
**Fix:** Centralize version in a single constant (e.g. `vconv/__init__.py` or `vconv.py`), import everywhere. Then update `README.md`, `vconv.desktop`, `SPEC.md` to match.

---

## 🟠 HIGH PRIORITY — Fix This Week

### 5. `--recursive` CLI Flag Cannot Be Disabled
**File:** `vconv.py:54`
**Problem:** `add_argument('--recursive', ..., action='store_true', default=True)` — Since the default is `True` and `store_true` sets the value to `True` when the flag is present, there is **no way** to disable recursion from the command line.
**Fix:** Use `action=BooleanOptionalAction` (Python 3.9+) or define both `--recursive` / `--no-recursive`.

### 6. setup_logging Clears All Handlers on Every Call
**File:** `utils/logging.py:49`
**Problem:** `logger.handlers.clear()` removes ALL handlers. If a module adds a custom handler and then any code calls `setup_logging()` again, those handlers disappear silently.
**Fix:** Check `if logger.handlers: return` — only configure once.

### 7. ConversionWorker Thread Safety (Data Race)
**File:** `ui/main_window.py` — `self.files` list accessed from main thread and worker thread with no lock.
**Problem:** `self.files` is modified in `scan_folder` (main thread) and read in `_start_queue`/`_start_conversion` (worker thread). No mutex or queue synchronization.
**Fix:** Copy `self.files` before starting the worker, or protect with `QMutex`/`threading.Lock`. Consider using `QUEUE_ITEMS` signals instead of shared state.

### 8. Requires PyQt6 Handler Timeout (Hung HandBrakeCLI)
**File:** `core/converter.py:228-230` — `stdout.readline()` blocks indefinitely.
**Problem:** If HandBrakeCLI hangs or crashes silently, the UI thread-pool worker will block forever. No timeout or kill-switch.
**Fix:** Add `select.select()` timeout or use `QProcess` instead of `subprocess.Popen` (Qt has built-in timeout and signal handling).

### 9. validator.py Missing Video Extensions
**File:** `core/validator.py:41-43`
**Problem:** `SUPPORTED_EXTENSIONS` does not include `.ts`, `.m2ts`, `.mts`, `.vob` — but `vconv.py:32` and `main_window.py` both include them. This means validator rejects valid MTS/VOB files.
**Fix:** Define video extensions ONCE in a shared constant (e.g. `core/constants.py`), import everywhere.

### 10. Preset Dropdown Missing web_optimized & mobile
**Files:** `presets/default_presets.json` defines `web_optimized` and `mobile` presets; `ui/main_window.py:423` combo box does NOT list them.
**Fix:** Add `web_optimized` and `mobile` to the preset combo, and make `_apply_preset()` apply all preset fields (encoder, resolution, audio — currently only applies quality).

### 11. `_apply_preset()` Ignores Most Preset Fields
**File:** `ui/main_window.py:880-893`
**Problem:** Only reads `quality` from the preset. Ignores `encoder`, `format`, `audio_encoder`, `audio_bitrate`, `resolution`, `advanced` params that are all defined in the preset JSON.
**Fix:** Read and apply all preset fields. Critical for `nvenc_*` presets to work correctly.

### 12. Remove/Archive Legacy Bash Files
**Files:** `vconv` (Bash, 411 lines), `convert.sh.base` (309 lines), `vconv.conf` (legacy bash format)
**Problem:** These coexist confusingly with the Python codebase. A developer running `./vconv` gets the Bash version, not the Python version.
**Fix:** Move to `legacy/` directory, update `README.md` to point to `vconv.py`, and add a warning note.

---

## 🟡 MEDIUM PRIORITY — Fix Before Next Release

### 13. Version Bump for Next Release (MoTekLab Video Encoder)
**Files:** All version references across project
**Problem:** The next release should change the name from "vconv" to "MoTekLab Video Encoder" and bump version.
**Fix:** Update window title, About dialog, desktop file, README, CLI help text, version strings.

### 14. SPEC.md and ROADMAP.md Outdated
**Files:** `SPEC.md` (references PySimpleGUI, version 8.0), `ROADMAP.md` (references PySimpleGUI, doesn't reflect current version history)
**Fix:** Rewrite to reflect PyQt6 reality and current version. Or archive and create new spec.

### 15. Arabic User Guide Version Discrepancy
**File:** `docs/user_guide.ar.md:644` says bug fixed in "v9.2.0", English version says "v9.1.0"
**Fix:** Align with English version. Also audit for other content differences between the two guides (Arabic is missing several sections).

### 16. QueueManager Thread Safety
**File:** `core/queue.py`
**Problem:** `QueueManager` is not thread-safe. `save_queue` writes to file, `load_queue` reads, and `reorder_job` modifies the list — all from different threads with no synchronization.
**Fix:** Add `threading.Lock` to all public methods that access `self.jobs`.

### 17. i18n Language Fallback Mutates self.lang
**File:** `utils/i18n.py:66`
**Problem:** When `ar_eg` is requested but only `ar.json` exists, `self.lang` is mutated from `'ar_eg'` to `'ar'`. Subsequent `set_language('ar_eg')` calls think they already loaded `ar_eg` and return the wrong translations.
**Fix:** Store the fallback language separately from the requested language.

### 18. Queue Save Perf — Writes Entire File on Every Operation
**File:** `core/queue.py:136-137`
**Problem:** Every `add_job()`, `update_job()`, `remove_job()` writes the entire queue to disk. With large queues (50+ files), this causes unnecessary I/O.
**Fix:** Add debouncing — save at most once per second, or only on explicit save and app exit.

### 19. Duplicate launch() Functions
**Files:** `vconv.py` and `ui/main_window.py` both define a `launch()` function.
**Problem:** Two implementations of app initialization with slightly different logic. `vconv.py` handles CLI args and passes to GUI; `main_window.py`'s `launch()` ignores CLI args entirely.
**Fix:** Keep one canonical `launch()` in `main_window.py`, import and call from `vconv.py`.

### 20. update Checker — Pre-release Suffix Handling
**File:** `utils/updater.py:33-38`
**Problem:** `parse_version('v9.2.0-rc1')` returns `(9, 2, 0)` — same as the stable release. So `is_newer()` won't notify about release candidates.
**Fix:** Strip pre-release suffixes for comparison, or add a separate `is_prerelease()` check.

---

## 🟢 LOW PRIORITY — Nice to Have

### 21. Splash Screen Not Implemented
**Files:** `public/vconv-splash.png` exists (800×480), but no code shows it on startup.
**Fix:** Implement `QSplashScreen` in `main_window.py`'s `launch()`.

### 22. Drag-and-Drop on Main Window
**File:** `ui/main_window.py` — no `setAcceptDrops(True)` or `dragEnterEvent`/`dropEvent` overrides.
**Fix:** Add drop handling so users can drag video files/folders onto the window.

### 23. Theme System Not Implemented
**Files:** `themes/` directory doesn't exist. `SPEC.md` mentions theme loading, `dependencies_checker` references `apply_theme()`, but no code exists.
**Fix:** Create `themes/` directory with `dark.json`/`light.json` stylesheets, implement loading logic.

### 24. Test Code in `if __name__ == "__main__"` Blocks
**Files:** `core/converter.py:238-245`, `core/encoder.py:308-313`, `core/analyzer.py:195-201`, `ui/main_window.py:1266-1270`
**Problem:** Test code scattered across source files. Can't be run with a test runner.
**Fix:** Move to `tests/` directory, write proper pytest unit tests.

### 25. `setup.py` Not pip-Compatible
**File:** `setup.py` — no `setuptools.setup()` call, custom installer instead.
**Fix:** Add proper `setup()` call for `pip install .` compatibility.

### 26. Hardcoded Paths Everywhere
**Problem:** `~/vconv_debug.log`, `~/.config/vconv/`, `/opt/vconv/vconv.py`, `/opt/vconv/vconv-icon-256.png` — all hardcoded.
**Fix:** Support `$VCONV_CONFIG_DIR` env var, use `xdg.BaseDirectory` for XDG compliance.

### 27. Type Hints Missing
**Problem:** Many functions lack type hints, especially in `core/` and legacy `utils/` modules.
**Fix:** Add type hints systematically across the codebase.

---

## Summary

| Priority | Items | Target |
|----------|-------|--------|
| 🔴 Critical | 4 bugs (config, requirements, PATH, version) | Fix NOW |
| 🟠 High | 8 items (CLI, threads, missing presets, legacy files) | This week |
| 🟡 Medium | 8 items (rename, docs, i18n, queue, perf) | Before next release |
| 🟢 Low | 7 items (splash, drag-drop, themes, tests) | Nice to have |
