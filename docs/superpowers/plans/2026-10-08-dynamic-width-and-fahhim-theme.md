# Dynamic Settings Width + Fahhim Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the left settings panel hug the active tab (content-hug + reflow, fixed 300 px gone) and retheme the whole app with Fahhim's Rosé/Crimson palette plus Light/Dark/System switching.

**Architecture:** Two approved specs implemented as two independent, shippable halves in one cycle. Width: pure helper `_left_width_action` + event wiring on the existing horizontal splitter + a reflow pass in `_create_left_panel`. Theme: new `ui/theme.py` (palette dict → app-wide QSS) applied in `launch()` before first paint, with a Settings → Appearance menu and OS-following system mode. All tests offscreen (`QT_QPA_PLATFORM=offscreen`); no network; no config migrations.

**Tech Stack:** Python 3, PyQt6 (Qt 6.11), existing `utils/config.py`, existing test harness style (`tests/test_layout_dynamic.py` stub-worker pattern — plain scripts, `check()` helper, no pytest).

**Specs (build contracts):**
- `docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md`
- `docs/superpowers/specs/2026-10-08-fahhim-theme-design.md`

**Baseline:** 284 checks green across 12 test files (`b65dc4a`/`5d90606` era). Record final counts in `docs/test-results/`.

---

## Execution deviations (recorded during build)

1. **`_HugTabWidget` subclass added (Task 2, commit `59e3dd2` + fix `b46510a`).** The plan assumed `QTabWidget.sizeHint()` returns the *current* page's hint. In Qt 6.11 it returns the **max over all pages** (`qtabwidget.cpp`), so the plan's hug target H was permanently the widest tab (284 px) and Task 3's per-tab assertions could not pass. Resolution: a module-level `_HugTabWidget(QTabWidget)` overrides **both** `sizeHint()` and `minimumSizeHint()` to hug the current page (recomputing Qt's own padding formula, tab-bar floor preserved, `currentChanged → updateGeometry`), and `settings_tabs` is constructed from it. Measured offscreen: Video H/F = 239/239, Audio = 190/172, Subtitles = 284/237. No test/helper changes were needed.
2. **Check-count arithmetic.** This plan's per-task "N checks" tallies were off; the authoritative counts are the ones recorded in `docs/test-results/2026-10-08-dynamic-settings-width.md` (width 31) and `docs/test-results/2026-10-08-fahhim-theme.md` (theme 43).
3. **Theme changes the width test's measurements (Task 7, integration fix).** The plan said Part A's layout tests "pass untouched", but Task 7 moved `hwLabel`'s font from an inline `setStyleSheet` into the `QLabel#hwLabel` QSS rule. An **unthemed** `MainWindow` (as the width test built) then measured a Video `sizeHint` of 292 that the default splitter could not fit → `W(274) ≠ H(292)`. Since the real app always themes at `launch()`, `tests/test_settings_width_dynamic.py` now calls `theme.apply_theme(app, 'light')` in `main()` and its Audio soft bound moved `< 200` → `< 215` (themed Audio hug = 204). Themed per-tab hints (Video 233/233, Audio 204/160, Subtitles 280/229) are recorded in the width test-results doc, AGENTS, and the width spec. Product behavior is unchanged; only the measurement baseline moved.
4. **`ui/theme.py` dropped the spec's optional `apply_theme(config=…)` parameter (Task 5).** No caller needed it — persistence lives in `set_mode(config, mode)`.

---

## File Structure

| File | Role | Touched by |
|---|---|---|
| `ui/main_window.py` | width controller (helper + 4 slots), reflow pass, Appearance menu, `_set_theme`, objectNames, token colors, `launch()` theme hook | Tasks 1–3, 6–7 |
| `tests/test_settings_width_dynamic.py` | NEW — width tests (26 checks) | Tasks 1–3 |
| `ui/theme.py` | NEW — Fahhim palettes, `resolve`, `build_stylesheet`, `apply_theme`, `current/set_mode`, `current_palette` | Task 5 |
| `tests/test_theme.py` | NEW — theme tests (~40 checks) | Tasks 5–7 |
| `utils/config.py` | `DEFAULT_CONFIG['appearance']['theme'] = 'system'` | Task 6 |
| `CHANGELOG.md`, `AGENTS.md`, `docs/user_guide.md`, `docs/user_guide.ar.md`, `docs/test-results/2026-10-08-*.md` | docs | Tasks 4, 8 |

Commit identity for every commit (standing rule):
`git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "…"`

---

## Part A — Dynamic settings width

### Task 1: Pure helper `_left_width_action` (RED → GREEN → commit)

**Files:**
- Create: `tests/test_settings_width_dynamic.py`
- Modify: `ui/main_window.py` (after `eventFilter`, before `_create_left_panel`, ~line 1174)

- [ ] **Step 1: Write the failing test file (helper truth table only)**

```python
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
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py`
Expected: traceback ending `AttributeError: type object 'MainWindow' has no attribute '_left_width_action'` (exit ≠ 0).

- [ ] **Step 3: Implement the helper**

In `ui/main_window.py`, immediately after the `eventFilter` method (ends ~line 1174, right before `def _create_left_panel`), insert:

```python
    @staticmethod
    def _left_width_action(current, hug, floor, manual):
        """Next left-panel width, or None = leave the splitter alone.

        Truth table (spec 2026-10-08-dynamic-settings-width):
        manual + W < F  -> F   (never clip)
        manual + W >= F -> None (sticky: keep the user's width)
        auto            -> H   (hug; None when already there)
        """
        if manual:
            if current < floor:
                return floor
            return None
        if hug != current:
            return hug
        return None
```

- [ ] **Step 4: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py`
Expected: `RESULT: ALL PASS (5 checks)`

- [ ] **Step 5: Commit**

```bash
git add tests/test_settings_width_dynamic.py ui/main_window.py
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "feat(ui): pure _left_width_action helper for dynamic panel width"
```

### Task 2: Content reflow (RED → GREEN → commit)

**Files:**
- Modify: `ui/main_window.py` (`_create_left_panel`: hw label ~1250, output labels ~1325/1350, subtitles layouts ~1460–1488, combo loop before line ~1508)
- Test: `tests/test_settings_width_dynamic.py` (append)

- [ ] **Step 1: Append the failing reflow tests**

Append this to `tests/test_settings_width_dynamic.py` (before `main()`), and extend `main()` to call it:

```python
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
```

`main()` becomes:

```python
def main():
    app = QApplication.instance() or QApplication([])
    test_helper_truth_table()
    test_reflow()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py`
Expected: first failure `\[FAIL\] all settings-panel combos Ignored (5 non-Ignored)` (av1/preset/audio-encoder/bitrate/sub combos not Ignored yet). Exit ≠ 0.

- [ ] **Step 3: Implement the reflow (four edits in `_create_left_panel`)**

Edit 3a — hw label (~line 1250), add objectName, **keep** the existing `setStyleSheet` (Task 7 replaces it with a QSS token rule):

```python
        hw_label = QLabel(hw_text)
        hw_label.setObjectName("hwLabel")
        hw_label.setStyleSheet("color: #00B4D8; font-size: 11px;")
        hw_label.setWordWrap(True)
```

Edit 3b — shorten the two floor-setting labels (~lines 1325 and 1350). Replace the constructor lines:

```python
        self.output_same_radio = QRadioButton("Same as source")
        self.output_same_radio.setToolTip("Same as source (preserve structure)")
```

```python
        self.flat_output_check = QCheckBox("Flat output (single folder)")
        self.flat_output_check.setToolTip("Flat output (dump all files in one folder)")
```

(If either widget already has a tooltip elsewhere in its constructor block, keep that text and append the full-copy sentence — the test asserts the tooltip equals exactly the full copy shown above, so ensure the tooltip ends up as the exact strings in the tests. Preserve all other lines — WhatsThis, signals, `setChecked` — untouched.)

Edit 3c — split the Subtitles mega-row (~lines 1460–1488). Add objectNames and re-nest:

```python
        ext_btn_layout = QHBoxLayout()
        ext_btn_layout.setObjectName("ext_btn_layout")
        ext_btn_layout.setSpacing(4)
        ...  # (existing addWidget calls for add/remove/clear buttons unchanged)
        ext_opts_layout = QHBoxLayout()
        ext_opts_layout.setObjectName("ext_opts_layout")
        ...  # (existing addWidget calls for burn/default checkboxes unchanged)
        # Was: ext_btn_layout.addLayout(ext_opts_layout)  — drove the 369 px row.
        sub_layout.addLayout(ext_btn_layout)
        sub_layout.addLayout(ext_opts_layout)
```

(The exact edit: delete the line `ext_btn_layout.addLayout(ext_opts_layout)` and add `sub_layout.addLayout(ext_opts_layout)` directly after `sub_layout.addLayout(ext_btn_layout)`.)

Edit 3d — Ignored policy loop, immediately **before** the existing wheel-guard loop (~line 1508):

```python
        # Content reflow: combos must not set the panel's minimum width
        # (spec 2026-10-08-dynamic-settings-width; encoder_combo is the precedent).
        for combo in panel.findChildren(QComboBox):
            combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        for wgt in panel.findChildren((QComboBox, QSlider)):
            wgt.installEventFilter(self)
```

(Order matters: reflow first, wheel-guard loop stays last — spec §3.)

- [ ] **Step 4: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py`
Expected: `RESULT: ALL PASS (15 checks)` (5 helper + 10 reflow).

- [ ] **Step 5: Commit**

```bash
git add tests/test_settings_width_dynamic.py ui/main_window.py
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "feat(ui): settings-panel content reflow (split row, Ignored combos, shorter labels)"
```

### Task 3: Width controller + startup hug (RED → GREEN → commit)

**Files:**
- Modify: `ui/main_window.py` (`_create_central_widget` ~1137–1162; new methods after `_left_width_action`)
- Test: `tests/test_settings_width_dynamic.py` (append)

- [ ] **Step 1: Append the failing controller tests**

Append (before `main()`), and extend `main()`:

```python
def test_startup_hugs_video():
    win = make_window()
    settle(win)
    h, w = hug(win), left_w(win)
    check(f"startup W({w}) ~= H(video)({h})", abs(w - h) <= 8)
    check(f"startup W({w}) < fixed 300", w < 300)
    check("floor installed on settings_scroll",
          win.settings_scroll.minimumWidth() == floor(win))
    win.close()
    del win
    gc.collect()


def test_tab_switch_shrinks_and_grows():
    win = make_window()
    settle(win)
    w_video, h_video = left_w(win), hug(win)
    win.settings_tabs.setCurrentIndex(1)  # Audio
    QApplication.processEvents()
    w_audio, h_audio = left_w(win), hug(win)
    check(f"audio switch: W({w_audio}) ~= H({h_audio})", abs(w_audio - h_audio) <= 8)
    check("H(audio) < H(video)", h_audio < h_video)
    check("W(audio) < W(video)", w_audio < w_video)
    win.settings_tabs.setCurrentIndex(2)  # Subtitles
    QApplication.processEvents()
    f_subs = floor(win)
    check(f"subs switch: W({left_w(win)}) >= F({f_subs})", left_w(win) >= f_subs)
    check(f"F(subs)({f_subs}) < 300 (reflow holds)", f_subs < 300)
    win.close()
    del win
    gc.collect()


def test_manual_sticky_and_never_clip():
    win = make_window()
    settle(win)
    # A real drag: splitterMoved fires with _width_applying False -> manual.
    win.splitter.splitterMoved.emit(330, 0)
    check("manual flag set by drag", win._manual_width is True)
    win.splitter.setSizes([330, 900])
    QApplication.processEvents()
    w_before = left_w(win)
    win.settings_tabs.setCurrentIndex(1)  # Audio: H ~190 < 330
    QApplication.processEvents()
    check(f"sticky: W kept at {w_before} ({left_w(win)})", left_w(win) == w_before)
    # Never-clip: park W at the current (audio) floor, switch to the wider
    # Subtitles floor -> controller must grow W to F(subs).
    win.splitter.setSizes([floor(win), 900])
    QApplication.processEvents()
    w_small, f_audio = left_w(win), floor(win)
    win.settings_tabs.setCurrentIndex(2)
    QApplication.processEvents()
    check(f"never-clip: W grew {w_small} -> {left_w(win)} >= F(subs) {floor(win)}",
          left_w(win) >= floor(win) and floor(win) >= f_audio)
    win.close()
    del win
    gc.collect()


def test_programmatic_hug_never_sets_manual():
    win = make_window()
    settle(win)
    win.settings_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    win.settings_tabs.setCurrentIndex(0)
    QApplication.processEvents()
    check("hug writes keep manual=False", win._manual_width is False)
    win.close()
    del win
    gc.collect()
```

`main()` becomes:

```python
def main():
    app = QApplication.instance() or QApplication([])
    test_helper_truth_table()
    test_reflow()
    test_startup_hugs_video()
    test_tab_switch_shrinks_and_grows()
    test_manual_sticky_and_never_clip()
    test_programmatic_hug_never_sets_manual()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py`
Expected: `AttributeError: 'MainWindow' object has no attribute 'splitter'` inside `test_startup_hugs_video` (or earlier check failure); exit ≠ 0.

- [ ] **Step 3: Wire the controller in `_create_central_widget`**

Replace this block (currently ~lines 1158–1162):

```python
        splitter.addWidget(self.settings_scroll)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 950])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
```

with:

```python
        splitter.addWidget(self.settings_scroll)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Dynamic width controller (spec 2026-10-08-dynamic-settings-width).
        # W = sizes()[0], M = self._manual_width (session-only), H = tabs.sizeHint(),
        # F = tabs.minimumSizeHint() installed on settings_scroll. The former
        # fixed setSizes([300, 950]) is replaced by the startup hug below.
        self.splitter = splitter
        self._manual_width = False
        self._width_applying = False
        self.settings_tabs.currentChanged.connect(self._on_settings_tab_changed)
        splitter.splitterMoved.connect(self._on_settings_splitter_moved)
        QTimer.singleShot(0, self._apply_initial_width)
```

(`QTimer` is already imported at line 29. `settings_tabs` exists because `_create_left_panel` ran at line 1141.)

- [ ] **Step 4: Add the four controller methods**

Immediately after `_left_width_action` (the static helper from Task 1), still before `_create_left_panel`:

```python
    def _current_width_params(self):
        """(H hug, F floor) for the active tab; floor clamped to the window."""
        hug_w = self.settings_tabs.sizeHint().width()
        floor = self.settings_tabs.minimumSizeHint().width()
        right_min = self.splitter.widget(1).minimumSizeHint().width() or 1
        floor = max(1, min(floor, max(1, self.splitter.width() - right_min)))
        return hug_w, floor

    def _apply_width(self):
        hug_w, floor = self._current_width_params()
        self.settings_scroll.setMinimumWidth(floor)
        new_w = self._left_width_action(
            self.splitter.sizes()[0], hug_w, floor, self._manual_width)
        if new_w is None:
            return
        sizes = self.splitter.sizes()
        sizes[0] = new_w
        right_min = self.splitter.widget(1).minimumSizeHint().width() or 1
        sizes[1] = max(sizes[1], right_min)
        self._width_applying = True
        try:
            self.splitter.setSizes(sizes)
        finally:
            self._width_applying = False

    def _on_settings_tab_changed(self, _index):
        self._apply_width()

    def _on_settings_splitter_moved(self, _pos, _index):
        # Only real user drags reach here unguarded; programmatic hugs set
        # _width_applying around setSizes and must never mark manual.
        if not self._width_applying:
            self._manual_width = True

    def _apply_initial_width(self):
        self._manual_width = False
        self._apply_width()
```

- [ ] **Step 5: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py`
Expected: `RESULT: ALL PASS (26 checks)` (5 + 10 + 11).

- [ ] **Step 6: Regression — run the whole existing suite**

Run:

```bash
for f in tests/test_*.py; do echo "== $f"; QT_QPA_PLATFORM=offscreen python3 "$f" || exit 1; done
```

Expected: every file prints `RESULT: ALL PASS` (previous 284 checks + new 26). If `test_layout_dynamic.py` or `test_defaults_hardening.py` fail on an old fixed-300 assumption, fix the assertion deliberately (they were written to accept dynamic sizing) and note the reason in the test-results doc — do NOT reintroduce fixed constants.

- [ ] **Step 7: Commit**

```bash
git add tests/test_settings_width_dynamic.py ui/main_window.py
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "feat(ui): dynamic settings width — startup hug, tab-switch re-hug, sticky manual drag"
```

### Task 4: Width docs + test results (commit)

**Files:**
- Modify: `CHANGELOG.md`, `AGENTS.md`, `docs/user_guide.md`, `docs/user_guide.ar.md`
- Create: `docs/test-results/2026-10-08-dynamic-settings-width.md`

- [ ] **Step 1: Record test results**

Create `docs/test-results/2026-10-08-dynamic-settings-width.md`:

```markdown
# Test results — dynamic settings width (2026-10-08)

Spec: `docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md`

| Test | Command | Result |
|---|---|---|
| New width tests | `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py` | RESULT: ALL PASS (26 checks) |
| Full suite | `for f in tests/test_*.py; do …` | RESULT: ALL PASS (<fill from run> checks, 13 files) |

Notes (fill from the runs):
- Startup hug observed: W = <n> px (Video), Audio H = <n>, Subtitles F = <n>.
- Any assertion adjusted in older tests: <list or "none">
```

Fill the `<…>` fields from the actual Step-5/Step-6 outputs of Task 3 (real numbers only).

- [ ] **Step 2: CHANGELOG entry**

In `CHANGELOG.md`, under `## [Unreleased]` → `### Added`, insert as the **first** bullet (above the tabs bullet):

```markdown
- **Settings panel hugs the active tab — dynamic width + content reflow** (`ui/main_window.py`): the left panel sizes itself to the active tab's content instead of the fixed 300 px split — H (`settings_tabs.sizeHint()`) is the hug target, F (`minimumSizeHint()`) is the drag floor installed on `settings_scroll`, and a manual splitter drag is sticky for the session (the panel only moves on its own when content would clip). Reflow makes F small: every settings combo is `Ignored` horizontally, the Subtitles mega-row was split (`ext_opts_layout` no longer nested in `ext_btn_layout`), and two floor-setting labels were shortened with the full copy moved to tooltips. New pure helper `MainWindow._left_width_action`; new `tests/test_settings_width_dynamic.py` (26 checks). Panel still scrolls vertically; stretch stays 0/1; no config keys.
```

- [ ] **Step 3: AGENTS.md pattern section**

Append to `AGENTS.md` (after the "Responsive Window Sizing (v9.7.2)" section):

```markdown
## Dynamic Settings Width Pattern (H/F/M)
The left settings panel hugs the active tab instead of sitting at fixed 300 px (spec `docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md`; tests `tests/test_settings_width_dynamic.py`). Three values, recomputed per event, never cached, never persisted:
- **H** = `settings_tabs.sizeHint().width()` (hug target) · **F** = `settings_tabs.minimumSizeHint().width()` (drag floor, installed via `settings_scroll.setMinimumWidth(F)`) · **W** = `splitter.sizes()[0]` · **M** = `self._manual_width` (session-only).
- Pure helper `MainWindow._left_width_action(current, hug, floor, manual)` returns the new width or `None` — ALL event logic lives there (truth table unit-tested; same pattern as `_screen_window_bounds`). Never branch on width outside it.
- Wiring in `_create_central_widget`: `settings_tabs.currentChanged` → `_apply_width()`; `splitter.splitterMoved` → `M=True` guarded by `_width_applying` (programmatic hugs must never mark manual); startup `QTimer.singleShot(0, _apply_initial_width)`. Floor is clamped to `splitter width − right-panel minimum` in `_current_width_params`.
- Reflow keeps F small: every settings-panel `QComboBox` is `Ignored` horizontally (loop right BEFORE the wheel-guard loop in `_create_left_panel` — wheel-guard stays last); `ext_opts_layout` must stay its own row in `sub_layout` (never re-nested in `ext_btn_layout`); long non-wrappable copy (radios/checkboxes) goes: short visible text + full text in tooltip.
- Window resize keeps stretch 0/1; width/M are session-only (no config keys).
```

- [ ] **Step 4: User guides (one line each)**

`docs/user_guide.md` — under `## Encoder Settings`, append this sentence to the intro paragraph (the one beginning "The left settings panel is organized into three tabs"):

```markdown
 The panel also sizes itself to the active tab — it shrinks on Audio, grows on Subtitles, and never clips; drag the divider to pin a width (a pinned width stays until you restart vconv).
```

`docs/user_guide.ar.md` — under `## إعدادات الترميز`, append to the intro paragraph (the one beginning "لوحة الإعدادات اليسرى منظمة في ثلاث ألسنة"):

```markdown
كما أن اللوحة تتكيّف مع التبويب النشط — تضيق في تبويب الصوت وتكبر في تبويب الترجمة ولا تُقصّ أبداً؛ اسحب الفاصل لتثبيت عرض يبقى حتى إعادة تشغيل vconv.
```

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md AGENTS.md docs/user_guide.md docs/user_guide.ar.md docs/test-results/2026-10-08-dynamic-settings-width.md
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "docs: dynamic settings width — changelog, AGENTS pattern, guides, test results"
```

---

## Part B — Fahhim theme

### Task 5: `ui/theme.py` + unit tests (RED → GREEN → commit)

**Files:**
- Create: `tests/test_theme.py`
- Create: `ui/theme.py`

- [ ] **Step 1: Write the failing unit tests**

```python
#!/usr/bin/env python3
"""
Fahhim theme tests (unreleased): Rosé light / Crimson dark / system-follow.
Spec: docs/superpowers/specs/2026-10-08-fahhim-theme-design.md

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py
"""
import gc
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel
import ui.theme as theme
import ui.main_window as mw
from utils.config import Config
from utils.i18n import I18n

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
    tmp = tempfile.TemporaryDirectory(prefix="vconv_theme_")
    cfg = Config(str(Path(tmp.name) / "vconv.conf"))
    win = mw.MainWindow(cfg, I18n(lang="en"))
    win._theme_test_tmp = tmp
    return win


REQUIRED = {
    'background', 'foreground', 'card', 'card_fg', 'primary', 'primary_fg',
    'secondary', 'secondary_fg', 'muted', 'muted_fg', 'accent', 'accent_fg',
    'border', 'input', 'destructive', 'grad_start', 'grad_mid', 'grad_end',
    'info', 'success', 'subtle',
}


def test_palette_tokens_and_fahhim_hexes():
    for name in ('light', 'dark'):
        missing = REQUIRED - set(theme.PALETTES[name])
        check(f"{name} palette complete ({sorted(missing)})", not missing)
    L, D = theme.PALETTES['light'], theme.PALETTES['dark']
    check("light bg #fdf6f5", L['background'] == '#fdf6f5')
    check("light primary #be123c", L['primary'] == '#be123c')
    check("light border #ecd9dc", L['border'] == '#ecd9dc')
    check("light gradient f43f5e/e11d48/be123c",
          (L['grad_start'], L['grad_mid'], L['grad_end'])
          == ('#f43f5e', '#e11d48', '#be123c'))
    check("dark bg #140e0c", D['background'] == '#140e0c')
    check("dark primary #e5534b", D['primary'] == '#e5534b')
    check("dark border #33201b", D['border'] == '#33201b')
    check("dark gradient c22b23/e5534b/c22b23",
          (D['grad_start'], D['grad_mid'], D['grad_end'])
          == ('#c22b23', '#e5534b', '#c22b23'))


def test_build_stylesheet():
    ls = theme.build_stylesheet('light')
    ds = theme.build_stylesheet('dark')
    check("light stylesheet substantial", len(ls) > 1500)
    check("stylesheets differ light vs dark", ls != ds)
    check("light sheet carries light primary", '#be123c' in ls)
    check("dark sheet carries dark primary", '#e5534b' in ds)
    check("primaryBtn gradient rule present",
          'qlineargradient' in ls and 'QPushButton#primaryBtn' in ls)
    check("objectName rules present",
          all(s in ls for s in ('QLabel#hwLabel', 'QLabel#statusLabel',
                                'QLabel#audioTracksStatus')))


def test_resolve_system_mapping():
    check("system + Dark -> dark",
          theme.resolve('system', Qt.ColorScheme.Dark) == 'dark')
    check("system + Light -> light",
          theme.resolve('system', Qt.ColorScheme.Light) == 'light')
    check("dark passthrough", theme.resolve('dark', Qt.ColorScheme.Light) == 'dark')
    check("light passthrough",
          theme.resolve('light', Qt.ColorScheme.Dark) == 'light')
    check("unknown mode falls back to light",
          theme.resolve('purple') == 'light')


def test_apply_theme_switches_stylesheet():
    app = QApplication.instance() or QApplication([])
    t1 = theme.apply_theme(app, 'light')
    check("apply light returns light", t1 == 'light')
    check("light stylesheet on app", '#be123c' in app.styleSheet())
    t2 = theme.apply_theme(app, 'dark')
    check("apply dark returns dark", t2 == 'dark')
    check("dark stylesheet on app", '#e5534b' in app.styleSheet())
    check("current_palette follows active theme",
          theme.current_palette()['primary'] == '#e5534b')


def test_config_persistence():
    tmp = tempfile.TemporaryDirectory(prefix="vconv_theme_cfg_")
    path = str(Path(tmp.name) / "vconv.conf")
    cfg = Config(path)
    cfg.load()
    check("fresh config default mode is system",
          theme.current_mode(cfg) == 'system')
    theme.set_mode(cfg, 'dark')
    cfg2 = Config(path)
    cfg2.load()
    check("dark persisted across reload", theme.current_mode(cfg2) == 'dark')
    tmp.cleanup()


def main():
    app = QApplication.instance() or QApplication([])
    test_palette_tokens_and_fahhim_hexes()
    test_build_stylesheet()
    test_resolve_system_mapping()
    test_apply_theme_switches_stylesheet()
    test_config_persistence()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py`
Expected: `ModuleNotFoundError: No module named 'ui.theme'` (exit ≠ 0).

- [ ] **Step 3: Implement `ui/theme.py`**

Create `ui/theme.py` with this exact content:

```python
"""Fahhim theme for vconv — Rosé (light) / Crimson (dark) / system-follow.

Palette source: ~/WebProjects/Fahhim/src/index.css (tokens copied verbatim).
This module is the single source of truth for colors — widget code must
never hardcode hex values (rule enforced by the source scan in
tests/test_theme.py; see AGENTS.md "Fahhim Theme Pattern").
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

PALETTES = {
    'light': {
        'background': '#fdf6f5', 'foreground': '#251320',
        'card': '#ffffff', 'card_fg': '#251320',
        'primary': '#be123c', 'primary_fg': '#ffffff',
        'secondary': '#f7ebe9', 'secondary_fg': '#251320',
        'muted': '#f7ebe9', 'muted_fg': '#7d5f6a',
        'accent': '#fdecf0', 'accent_fg': '#881337',
        'border': '#ecd9dc', 'input': '#ecd9dc',
        'destructive': '#b91c1c',
        'grad_start': '#f43f5e', 'grad_mid': '#e11d48', 'grad_end': '#be123c',
        'info': '#00B4D8', 'success': '#2ECC71', 'subtle': '#7d5f6a',
    },
    'dark': {
        'background': '#140e0c', 'foreground': '#f4e3dd',
        'card': '#1c1310', 'card_fg': '#f4e3dd',
        'primary': '#e5534b', 'primary_fg': '#200a08',
        'secondary': '#2a1a15', 'secondary_fg': '#f4e3dd',
        'muted': '#221613', 'muted_fg': '#a4847a',
        'accent': '#2a1a15', 'accent_fg': '#f0c3ba',
        'border': '#33201b', 'input': '#221613',
        'destructive': '#ff7a6b',
        'grad_start': '#c22b23', 'grad_mid': '#e5534b', 'grad_end': '#c22b23',
        'info': '#00B4D8', 'success': '#5fc26a', 'subtle': '#a4847a',
    },
}

_active = 'light'
_state = {'app': None, 'mode': None, 'connected': False, 'fusion': False}


def resolve(mode, system_scheme=None):
    """Map a config mode + OS scheme to a concrete palette name."""
    if mode == 'system':
        return 'dark' if system_scheme == Qt.ColorScheme.Dark else 'light'
    return mode if mode in PALETTES else 'light'


def current_palette():
    """Palette dict of the theme currently applied (light until first apply)."""
    return PALETTES[_active]


def current_mode(config):
    return config.get('appearance', 'theme', 'system')


def set_mode(config, mode):
    config.set('appearance', 'theme', mode)
    config.save()


def build_stylesheet(theme_name):
    """Fahhim QSS for one theme. CSS braces are doubled (f-string)."""
    p = PALETTES[theme_name]
    return f"""
QMainWindow {{ background: {p['background']}; }}
QDialog {{ background: {p['card']}; color: {p['foreground']}; }}
QWidget {{ background: transparent; color: {p['foreground']}; }}
QMenuBar {{ background: {p['secondary']}; color: {p['foreground']}; border-bottom: 1px solid {p['border']}; }}
QMenuBar::item:selected {{ background: {p['accent']}; color: {p['accent_fg']}; }}
QMenu {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; }}
QMenu::item {{ padding: 4px 24px 4px 12px; }}
QMenu::item:selected {{ background: {p['primary']}; color: {p['primary_fg']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 2px 6px; }}
QGroupBox {{ border: 1px solid {p['border']}; border-radius: 6px; margin-top: 10px; padding-top: 8px; background: {p['card']}; color: {p['foreground']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {p['accent_fg']}; }}
QTabWidget::pane {{ border: 1px solid {p['border']}; background: {p['card']}; top: -1px; }}
QTabBar::tab {{ background: {p['secondary']}; color: {p['muted_fg']}; padding: 5px 14px; border: 1px solid {p['border']}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {p['card']}; color: {p['primary']}; border-bottom: 2px solid {p['primary']}; }}
QComboBox {{ background: {p['secondary']}; color: {p['foreground']}; border: 1px solid {p['border']}; border-radius: 5px; padding: 3px 8px; }}
QComboBox:hover {{ border-color: {p['primary']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; selection-background-color: {p['primary']}; selection-color: {p['primary_fg']}; }}
QCheckBox {{ spacing: 6px; color: {p['foreground']}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {p['border']}; border-radius: 3px; background: {p['card']}; }}
QCheckBox::indicator:checked {{ background: {p['primary']}; border-color: {p['primary']}; }}
QCheckBox::indicator:hover {{ border-color: {p['primary']}; }}
QRadioButton {{ spacing: 6px; color: {p['foreground']}; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border: 1px solid {p['border']}; border-radius: 7px; background: {p['card']}; }}
QRadioButton::indicator:checked {{ background: {p['primary']}; border-color: {p['primary']}; }}
QLineEdit, QTextEdit {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; border-radius: 5px; padding: 3px 6px; selection-background-color: {p['primary']}; selection-color: {p['primary_fg']}; }}
QPlainTextEdit {{ background: {p['background']}; color: {p['foreground']}; border: 1px solid {p['border']}; border-radius: 5px; padding: 4px; selection-background-color: {p['primary']}; selection-color: {p['primary_fg']}; }}
QSlider::groove:horizontal {{ height: 5px; background: {p['muted']}; border: 1px solid {p['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {p['primary']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: {p['primary']}; border: 2px solid {p['card']}; }}
QTableView, QTableWidget {{ background: {p['card']}; alternate-background-color: {p['secondary']}; color: {p['foreground']}; border: 1px solid {p['border']}; gridline-color: {p['border']}; selection-background-color: {p['accent']}; selection-color: {p['accent_fg']}; }}
QHeaderView::section {{ background: {p['secondary']}; color: {p['muted_fg']}; border: none; border-right: 1px solid {p['border']}; border-bottom: 1px solid {p['border']}; padding: 4px 6px; }}
QListWidget {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['border']}; }}
QListWidget::item:selected {{ background: {p['accent']}; color: {p['accent_fg']}; }}
QScrollBar:vertical {{ background: {p['secondary']}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p['muted_fg']}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: {p['secondary']}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p['muted_fg']}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {p['border']}; }}
QSplitter::handle:hover {{ background: {p['primary']}; }}
QProgressBar {{ background: {p['muted']}; border: 1px solid {p['border']}; border-radius: 5px; text-align: center; color: {p['foreground']}; }}
QProgressBar::chunk {{ background: {p['success']}; border-radius: 4px; }}
QToolTip {{ background: {p['card']}; color: {p['foreground']}; border: 1px solid {p['primary']}; padding: 4px 8px; }}
QStatusBar {{ background: {p['secondary']}; color: {p['foreground']}; border-top: 1px solid {p['border']}; }}
QToolBar {{ background: {p['secondary']}; border-bottom: 1px solid {p['border']}; spacing: 4px; padding: 2px; }}
QToolButton {{ background: transparent; border: none; border-radius: 4px; padding: 4px 6px; color: {p['foreground']}; }}
QToolButton:hover {{ background: {p['accent']}; }}
QScrollArea {{ background: transparent; border: none; }}
QPushButton {{ background: {p['secondary']}; color: {p['secondary_fg']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ background: {p['accent']}; color: {p['accent_fg']}; border-color: {p['primary']}; }}
QPushButton:disabled {{ color: {p['muted_fg']}; background: {p['muted']}; }}
QPushButton#primaryBtn {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['grad_start']}, stop:0.5 {p['grad_mid']}, stop:1 {p['grad_end']}); color: {p['primary_fg']}; border: none; font-weight: bold; padding: 7px 16px; }}
QPushButton#primaryBtn:hover {{ background: {p['grad_mid']}; }}
QLabel#hwLabel {{ color: {p['info']}; font-size: 11px; }}
QLabel#statusLabel {{ color: {p['success']}; font-weight: bold; font-size: 13px; }}
QLabel#audioTracksStatus {{ color: {p['subtle']}; font-size: 10px; }}
"""


def apply_theme(app, mode):
    """Apply the Fahhim stylesheet app-wide; returns the concrete theme used.

    mode: 'light' | 'dark' | 'system'. System resolves from
    QStyleHints.colorScheme() and re-applies live on colorSchemeChanged.
    """
    global _active
    if app is None:
        return resolve(mode)
    scheme = None
    if mode == 'system':
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
        except Exception:
            scheme = None
    resolved = resolve(mode, scheme)
    _active = resolved
    if not _state['fusion']:
        app.setStyle('Fusion')
        _state['fusion'] = True
    app.setStyleSheet(build_stylesheet(resolved))
    _state['app'] = app
    _state['mode'] = mode
    if mode == 'system' and not _state['connected']:
        QGuiApplication.styleHints().colorSchemeChanged.connect(_on_system_scheme)
        _state['connected'] = True
    return resolved


def _on_system_scheme(_scheme):
    if _state['mode'] == 'system' and _state['app'] is not None:
        apply_theme(_state['app'], 'system')
```

(Note: the spec's optional `config` argument on `apply_theme` is dropped — no caller needs it; persistence lives in `set_mode`.)

- [ ] **Step 4: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py`
Expected: `RESULT: ALL PASS (26 checks)`

- [ ] **Step 5: Verify Qt can parse the stylesheet (no silent QSS errors)**

Run:

```bash
QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py 2>/tmp/qss_warn.log >/tmp/qss_out.log; grep -ci "could not parse\|error in" /tmp/qss_warn.log || true
```

Expected: `0` (no "Could not parse stylesheet" warnings). If non-zero, fix the offending rule in `build_stylesheet` and re-run Step 4.

- [ ] **Step 6: Commit**

```bash
git add ui/theme.py tests/test_theme.py
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "feat(theme): Fahhim palettes + app-wide QSS builder (ui/theme.py)"
```

### Task 6: Startup hook + config default (RED → GREEN → commit)

**Files:**
- Modify: `utils/config.py` (`DEFAULT_CONFIG`)
- Modify: `ui/main_window.py` (`launch()` ~2707, import block)
- Test: `tests/test_theme.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_theme.py` (before `main()`), and extend `main()`:

```python
def test_default_config_section():
    check("DEFAULT_CONFIG has appearance.theme == system",
          Config.DEFAULT_CONFIG.get('appearance', {}).get('theme') == 'system')


def test_launch_applies_theme():
    src = (ROOT / 'ui' / 'main_window.py').read_text()
    check("launch() applies theme before MainWindow",
          'apply_theme(app, current_mode(config))' in src)
```

`main()` call order (final, used by Task 7 too):

```python
def main():
    app = QApplication.instance() or QApplication([])
    test_palette_tokens_and_fahhim_hexes()
    test_build_stylesheet()
    test_resolve_system_mapping()
    test_apply_theme_switches_stylesheet()
    test_config_persistence()
    test_default_config_section()
    test_launch_applies_theme()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py`
Expected: `[FAIL] DEFAULT_CONFIG has appearance.theme == system` (exit ≠ 0) — the launch check would also fail but the run stops at first failure.

- [ ] **Step 3: Implement**

Edit 3a — `utils/config.py`, add the section to `DEFAULT_CONFIG` (after the `'general'` block):

```python
        'appearance': {
            'theme': 'system'
        },
```

Edit 3b — `ui/main_window.py` import block, after the existing `from utils.version import …` line:

```python
from ui.theme import apply_theme, current_mode, current_palette, set_mode
```

Edit 3c — `launch()` in `ui/main_window.py` (~line 2707), right after `app.setDesktopFileName("vconv")`:

```python
    apply_theme(app, current_mode(config))
```

- [ ] **Step 4: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py`
Expected: `RESULT: ALL PASS (28 checks)`

- [ ] **Step 5: Commit**

```bash
git add utils/config.py ui/main_window.py tests/test_theme.py
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "feat(theme): apply Fahhim theme at launch + appearance config default"
```

### Task 7: Appearance menu + token colors (RED → GREEN → commit)

**Files:**
- Modify: `ui/main_window.py` (QActionGroup import ~line 33; menu ~line 1006; `_set_theme` near `_set_language` ~2377; objectName/setStyleSheet at ~1251/1404/1619; About ~2674–2688; tools note ~424; queue start button ~1597)
- Test: `tests/test_theme.py` (append)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_theme.py` (before `main()`), and extend `main()`:

```python
def test_no_hardcoded_colors_in_main_window():
    src = (ROOT / 'ui' / 'main_window.py').read_text()
    check("no #00B4D8 in ui/main_window.py", '#00B4D8' not in src)
    check("no #2ECC71 in ui/main_window.py", '#2ECC71' not in src)
    check("no #888 inline label color in ui/main_window.py", "'color: #888" not in src)
    check("no #777 HTML color in ui/main_window.py", '#777' not in src)
    check("primaryBtn marked on queue start button",
          'queue_start_btn.setObjectName("primaryBtn")' in src)


def test_appearance_menu_and_switching():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, 'light')
    win = make_window()
    win.show()
    QApplication.processEvents()
    settings_menu = None
    for a in win.menuBar().actions():
        if a.menu() and 'Settings' in a.text().replace('&', ''):
            settings_menu = a.menu()
            break
    check("Settings menu found", settings_menu is not None)
    appear = None
    if settings_menu is not None:
        for a in settings_menu.actions():
            if a.menu() and 'Appearance' in a.text():
                appear = a.menu()
                break
    check("Appearance submenu exists", appear is not None)
    labels = [a.text() for a in appear.actions()] if appear else []
    check(f"Light/Dark/System actions ({labels})",
          labels == ['Light', 'Dark', 'System'])
    dark_act = [a for a in appear.actions() if a.text() == 'Dark'][0]
    dark_act.trigger()
    QApplication.processEvents()
    check("trigger Dark applies dark stylesheet", '#e5534b' in app.styleSheet())
    check("trigger Dark persists to config",
          theme.current_mode(win.config) == 'dark')
    check("Dark action checked", dark_act.isChecked())
    win.close()
    del win
    gc.collect()


def test_window_renders_theme_colors():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, 'light')
    win = make_window()
    win.show()
    QApplication.processEvents()
    c_light = win.grab().toImage().pixelColor(5, 5)  # menubar strip
    check(f"light render is rose-family (r={c_light.red()})",
          c_light.isValid() and c_light.red() > 200)
    win.close()
    del win
    gc.collect()
    theme.apply_theme(app, 'dark')
    win = make_window()
    win.show()
    QApplication.processEvents()
    c_dark = win.grab().toImage().pixelColor(5, 5)
    check(f"dark render is crimson-black-family (r={c_dark.red()})",
          c_dark.isValid() and c_dark.red() < 60)
    win.close()
    del win
    gc.collect()
```

`main()` final form:

```python
def main():
    app = QApplication.instance() or QApplication([])
    test_palette_tokens_and_fahhim_hexes()
    test_build_stylesheet()
    test_resolve_system_mapping()
    test_apply_theme_switches_stylesheet()
    test_config_persistence()
    test_default_config_section()
    test_launch_applies_theme()
    test_no_hardcoded_colors_in_main_window()
    test_appearance_menu_and_switching()
    test_window_renders_theme_colors()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py`
Expected: `[FAIL] no #00B4D8 in ui/main_window.py` (first new failure; exit ≠ 0).

- [ ] **Step 3: Implement — seven edits in `ui/main_window.py`**

Edit 3a — import (line ~33):

```python
from PyQt6.QtGui import QAction, QActionGroup, QFont, QKeySequence, QIcon, QPixmap, QShortcut
```

Edit 3b — Appearance submenu, inserted directly after `lang_menu.addAction(act_lang_ar)` (~line 1006):

```python
        settings_menu.addSeparator()
        appearance_menu = settings_menu.addMenu("&Appearance")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        current_theme = current_mode(self.config)
        for mode, label in (("light", "Light"), ("dark", "Dark"),
                            ("system", "System")):
            act_theme = QAction(label, self, checkable=True)
            act_theme.setData(mode)
            act_theme.triggered.connect(
                lambda checked=False, m=mode: self._set_theme(m))
            self._theme_group.addAction(act_theme)
            appearance_menu.addAction(act_theme)
            if current_theme == mode:
                act_theme.setChecked(True)
```

Edit 3c — `_set_theme` method, right after `_set_language` (~line 2385):

```python
    def _set_theme(self, mode):
        """Appearance menu: persist + re-apply the Fahhim theme live."""
        set_mode(self.config, mode)
        apply_theme(QApplication.instance(), mode)
        for act in self._theme_group.actions():
            act.setChecked(act.data() == mode)
```

Edit 3d — the three inline `setStyleSheet` calls become objectNames (QSS rules from `build_stylesheet` take over; they carry identical font-size/weight):

- ~line 1250: `hw_label.setObjectName("hwLabel")` already added in Task 2 — **delete** the line `hw_label.setStyleSheet("color: #00B4D8; font-size: 11px;")`.
- ~line 1404: replace `self.audio_tracks_status.setStyleSheet("color: #888; font-size: 10px;")` with `self.audio_tracks_status.setObjectName("audioTracksStatus")`.
- ~line 1619: replace `self.status_label.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 13px;")` with `self.status_label.setObjectName("statusLabel")`.

Edit 3e — About dialog HTML links (~lines 2674–2688). Replace the two label builders:

```python
        _link = current_palette()['info']
        info_layout.addWidget(QLabel(
            f'Powered by <a href="https://handbrake.fr" style="color: {_link};">HandBrakeCLI</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="https://ffmpeg.org" style="color: {_link};">FFmpeg</a>'
            f' &nbsp;|&nbsp; '
            f'<a href="https://ffmpeg.org/ffprobe.html" style="color: {_link};">FFprobe</a>'
            f' &nbsp;|&nbsp; Built with <a href="https://www.qt.io/qt-for-python" style="color: {_link};">PyQt6</a>'
        ))
```

```python
        website = QLabel(f'<a href="https://moteklab.com" style="color: {_link};">🌐 moteklab.com</a>')
```

Edit 3f — Tools dialog note (~line 424): replace `#777` with the subtle token:

```python
            text += f"<br><span style='color:{current_palette()['subtle']}'>{st.note}</span>"
```

Edit 3g — queue start button (~line 1597), add objectName on the next line:

```python
        self.queue_start_btn = QPushButton("▶ Start Queue")
        self.queue_start_btn.setObjectName("primaryBtn")
```

- [ ] **Step 4: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py`
Expected: `RESULT: ALL PASS (40 checks)` (28 + 5 source + 6 menu + 2 render — count from the actual output).

- [ ] **Step 5: Commit**

```bash
git add ui/main_window.py tests/test_theme.py
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "feat(theme): Settings > Appearance menu, token colors, primaryBtn gradient"
```

### Task 8: Theme docs + final full suite + push (commit, push)

**Files:**
- Modify: `CHANGELOG.md`, `AGENTS.md`, `docs/user_guide.md`, `docs/user_guide.ar.md`
- Create: `docs/test-results/2026-10-08-fahhim-theme.md`

- [ ] **Step 1: Run the FULL suite (both features, all files)**

Run:

```bash
for f in tests/test_*.py; do echo "== $f"; QT_QPA_PLATFORM=offscreen python3 "$f" || exit 1; done
```

Expected: all 14 files print `RESULT: ALL PASS`. Capture the grand total and per-file numbers.

- [ ] **Step 2: Record theme test results**

Create `docs/test-results/2026-10-08-fahhim-theme.md`:

```markdown
# Test results — Fahhim theme (2026-10-08)

Spec: `docs/superpowers/specs/2026-10-08-fahhim-theme-design.md`

| Test | Command | Result |
|---|---|---|
| New theme tests | `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py` | RESULT: ALL PASS (<n> checks) |
| QSS parse warnings | `… 2>/tmp/qss_warn.log; grep -ci "could not parse" /tmp/qss_warn.log` | 0 |
| Full suite | `for f in tests/test_*.py; do …` | RESULT: ALL PASS (<n> checks, 14 files) |

Notes (fill from the runs):
- Render check: light menubar pixel r=<n> (rose), dark r=<n> (crimson-black).
- Live system-follow: `QStyleHints.colorSchemeChanged` connected once (module-guarded); exercised by `resolve()` unit mapping (offscreen cannot flip the real OS scheme).
- Manual check (real display, after install/run): Settings → Appearance switches all three modes; dialogs inherit the stylesheet.
```

- [ ] **Step 3: CHANGELOG entry**

In `CHANGELOG.md` under `## [Unreleased]` → `### Added`, insert as the **first** bullet (above the dynamic-width bullet added in Task 4):

```markdown
- **Fahhim theme: Rosé (light) / Crimson (dark) with Settings → Appearance** (`ui/theme.py`, new): whole-app QSS generated from Fahhim's exact palette tokens (light `#fdf6f5` bg / `#be123c` primary, dark `#140e0c` bg / `#e5534b` primary, brand-gradient primary buttons), applied in `launch()` before the first paint — dialogs inherit it automatically. **Settings → Appearance → Light / Dark / System** (default System follows the OS live via `QStyleHints.colorSchemeChanged`); persisted as `appearance.theme`. The hardcoded inline colors (GPU label, status, tracks, About links, tools note) moved to `info/success/subtle` tokens — no hardcoded hex remains in `ui/main_window.py`. New `tests/test_theme.py`.
```

- [ ] **Step 4: AGENTS.md pattern section**

Append to `AGENTS.md` (after the "Dynamic Settings Width Pattern" section added in Task 4):

```markdown
## Fahhim Theme Pattern (ui/theme.py)
vconv is themed with Fahhim's palette (Rosé light / Crimson dark). **`ui/theme.py` is the single source of truth for colors — hardcoding a hex in widget code is a rule violation** (enforced by the source scan in `tests/test_theme.py`).
- `PALETTES['light'|'dark']` copied verbatim from `~/WebProjects/Fahhim/src/index.css` (tokens: background/foreground/card*/primary*/secondary*/muted*/accent*/border/input/destructive/grad_*/info/success/subtle). `build_stylesheet(theme)` emits the app-wide QSS (CSS braces doubled — f-string).
- `apply_theme(app, mode)` is called in `launch()` BEFORE MainWindow is constructed (first paint themed). It sets the Fusion style once, and `mode='system'` (default) resolves via `QStyleHints.colorScheme()` and subscribes `colorSchemeChanged` for live OS-follow (connection is module-guarded — connect exactly once).
- Persistence: `appearance/theme` via `set_mode()`/`current_mode()`; UI: Settings → Appearance (`QActionGroup`, Light/Dark/System), handler `_set_theme`.
- Widget-embedded colors use **objectNames + QSS rules** (`QLabel#hwLabel`, `QLabel#statusLabel`, `QLabel#audioTracksStatus`) so a live theme switch recolors them; HTML links use `current_palette()['info']` at build time. Primary actions get `setObjectName("primaryBtn")` → gradient rule.
- Never add a global `font-size` QSS rule — width H/F measurements are font-sensitive (dynamic-width pattern above).
```

- [ ] **Step 5: User guides (Appearance menu)**

`docs/user_guide.md` — under `## Settings Management`, insert before `### Saving Defaults`:

```markdown
### Appearance (Theme)

**Settings → Appearance** switches the whole app between **Light (Rosé)**, **Dark (Crimson)** and **System** (follows your operating system and switches live). The choice is stored as `appearance.theme` in `~/.config/vconv/vconv.conf`.
```

`docs/user_guide.ar.md` — under `## إدارة الإعدادات`, insert before `### حفظ الإعدادات الافتراضية`:

```markdown
### المظهر (الثيم)

**إعدادات → المظهر** يبدّل التطبيق كاملاً بين **الفاتح (روزيه)** و**الداكن (قرمزي)** و**النظام** (يتبع إعدادات نظامك ويبدّل فوراً). يُحفظ الاختيار في `appearance.theme` داخل `~/.config/vconv/vconv.conf`.
```

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md AGENTS.md docs/user_guide.md docs/user_guide.ar.md docs/test-results/2026-10-08-fahhim-theme.md
git -c user.name="$(git log -1 --format=%an)" -c user.email="$(git log -1 --format=%ae)" commit -m "docs: Fahhim theme — changelog, AGENTS pattern, guides, test results"
```

- [ ] **Step 7: Push**

```bash
git -c credential.helper='!f(){ echo "username=oauth2"; echo "password=$(gh auth token)"; }; f' push origin main
```

Expected: `main -> main` up to date with `origin/main`.

- [ ] **Step 8: Visual smoke on a real display (publish gate)**

Run `python3 vconv.py --gui` (or the installed app), then verify and note the result in the test-results file: menubar/tabs/combos render Rosé; Settings → Appearance → Dark switches to Crimson live; System follows the OS; Start Queue button shows the brand gradient; dialogs (Tools & Encoders, Audio Tracks) inherit the theme; panel hugs Video/Audio/Subtitles and a manual drag sticks.

---

## Self-Review (completed by the planner)

1. **Spec coverage** — width spec §1 reflow → Task 2; §2 controller (helper/events/startup/clamp) → Tasks 1+3; §3 edge cases → `_current_width_params` clamp + wheel-guard ordering note; testing items 1–8 → Tasks 1–4; docs → Task 4. Theme spec §1 palettes/resolve/apply/system → Task 5; §2 hooks/menu/persistence → Tasks 6–7; §3 widget coverage → QSS in Task 5 + objectNames Task 7; testing items 1–9 → Tasks 5–8 (item 7 MainWindow smoke = menu/render tests; item 9 = Task 8 suite run); docs → Tasks 4/8.
2. **Placeholder scan** — the only `<fill…>` fields are in test-results templates and must be replaced with real run numbers before the docs commits (explicit steps say so).
3. **Type consistency** — `_left_width_action(current, hug, floor, manual)` static, used via `mw.MainWindow._left_width_action` in tests and `self._left_width_action` in `_apply_width`; theme API (`resolve`, `build_stylesheet`, `apply_theme(app, mode)`, `current_mode`, `set_mode`, `current_palette`, `PALETTES`) matches every call site in Tasks 6–7; test helpers (`settle`, `left_w`, `hug`, `floor`) defined once in Task 1 and reused unchanged.
