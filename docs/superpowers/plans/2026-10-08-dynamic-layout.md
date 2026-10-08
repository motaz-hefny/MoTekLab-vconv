# Dynamic Settings Panel + Activity Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the left settings panel scroll instead of squashing the Subtitles box, and turn the Activity Log into a draggable, uncapped panel.

**Architecture:** Two isolated layout changes in `ui/main_window.py`: (1) wrap the existing left panel in a `QScrollArea` (all size-policy/min-width hints move onto the scroll area so the horizontal splitter is unchanged); (2) group Files/Queue/Progress into one widget and pair it with the log in a vertical `QSplitter`, deleting the 100 px cap. Two independent atomic commits for reversibility (spec requirement).

**Tech Stack:** PyQt6, existing in-repo test style (`QT_QPA_PLATFORM=offscreen python3 tests/<file>.py`, `check()` counter, no pytest).

**Spec:** `docs/superpowers/specs/2026-10-08-dynamic-layout-design.md` (approved).

**File structure:**
- Modify: `ui/main_window.py` — `_create_central_widget()` (~line 1108), `_create_left_panel()` (~line 1338), `_create_right_panel()` (~line 1431), QtWidgets import block (~line 18)
- Create: `tests/test_layout_dynamic.py` — 2 test functions, 5 checks total
- Modify (docs task): `CHANGELOG.md`, `docs/user_guide.md`, `docs/user_guide.ar.md`, `AGENTS.md`, new `docs/test-results/2026-10-08-dynamic-layout.md`

**Expected test counts:** new file = 5 checks; full suite = 210 + 5 = **215 checks**.

---

### Task 1: Scrollable settings panel (TDD)

**Files:**
- Create: `tests/test_layout_dynamic.py`
- Modify: `ui/main_window.py` (import block line 18–30, `_create_central_widget` lines 1108–1129, `_create_left_panel` line 1338)

- [ ] **Step 1: Write the failing test file (test 1 only)**

Create `tests/test_layout_dynamic.py`:

```python
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

from PyQt6.QtWidgets import QApplication, QScrollArea, QSplitter
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
    sub = getattr(win, "sub_group", None)
    got = sub.height() if sub else 0
    want = sub.sizeHint().height() if sub else -1
    check(f"Subtitles box keeps natural height at 760x520 (got {got}/{want})",
          sub is not None and got >= want - 2)
    win.close()
    del win
    gc.collect()


def main():
    app = QApplication.instance() or QApplication([])
    test_settings_panel_never_squashes()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`
Expected: `[FAIL] left panel wrapped in QScrollArea` (exit 1 — `settings_scroll` doesn't exist yet).

- [ ] **Step 3: Add the `QScrollArea` import**

In `ui/main_window.py` (import block, ~line 25), change:

```python
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget,
```

to:

```python
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget, QScrollArea,
```

- [ ] **Step 4: Wrap the left panel in `_create_central_widget`**

In `ui/main_window.py`, replace the body of `_create_central_widget` (currently lines 1108–1129: `main_layout` … `splitter.setStretchFactor(1, 1)`) with:

```python
    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(True)
        main_layout.addWidget(splitter)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        # The left panel is taller than small windows; without a scroll area
        # Qt compresses the last boxes (Subtitles squashed — 2026-10-08).
        # Size hints live on the scroll area so the horizontal splitter
        # drags exactly as before (300/950, stretch 0/1).
        self.settings_scroll = QScrollArea()
        self.settings_scroll.setWidget(left_panel)
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setMinimumWidth(0)
        self.settings_scroll.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        splitter.addWidget(self.settings_scroll)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 950])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
```

(This removes the old `left_panel.setMinimumWidth(0)` / `left_panel.setSizePolicy(...)` lines — their role moves to `settings_scroll`.)

- [ ] **Step 5: Expose `sub_group` for the test**

In `_create_left_panel` (line 1338), change:

```python
        sub_group = QGroupBox("Subtitles")
        sub_layout = QVBoxLayout(sub_group)
```

to:

```python
        sub_group = QGroupBox("Subtitles")
        self.sub_group = sub_group  # exposed for tests/test_layout_dynamic.py
        sub_layout = QVBoxLayout(sub_group)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`
Expected: `[PASS] left panel wrapped in QScrollArea` + `[PASS] Subtitles box keeps natural height …` + `RESULT: ALL PASS (2 checks)`

- [ ] **Step 7: Commit fix 1 (independent revert unit)**

```bash
git add ui/main_window.py tests/test_layout_dynamic.py
git commit -m "fix(ui): scrollable settings panel (Subtitles no longer squashes)"
```

---

### Task 2: Draggable Activity Log (TDD)

**Files:**
- Modify: `tests/test_layout_dynamic.py` (append test 2)
- Modify: `ui/main_window.py` (`_create_right_panel` lines 1431–1561)

- [ ] **Step 1: Append the failing test**

Append to `tests/test_layout_dynamic.py` (before `main()`), and add `test_log_splitter_drives_log_height()` to the `main()` body after the first test:

```python
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
```

`main()` becomes:

```python
def main():
    app = QApplication.instance() or QApplication([])
    test_settings_panel_never_squashes()
    test_log_splitter_drives_log_height()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`
Expected: `[FAIL] vertical 2-child log splitter exists` (exit 1 — `log_splitter` doesn't exist yet; test 1 still passes).

- [ ] **Step 3: Restructure the right panel**

In `ui/main_window.py` `_create_right_panel` (lines 1431–1561), make exactly these edits:

**(a)** Change the three upper `layout.addWidget(...)` calls into a bundled widget. Replace:

```python
        layout.addWidget(files_group)

        queue_group = QGroupBox("Conversion Queue")
```

with:

```python
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setSpacing(6)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(files_group)

        queue_group = QGroupBox("Conversion Queue")
```

**(b)** Replace:

```python
        layout.addWidget(queue_group)

        progress_group = QGroupBox("Progress")
```

with:

```python
        top_layout.addWidget(queue_group)

        progress_group = QGroupBox("Progress")
```

**(c)** Replace the progress + log tail (from `layout.addWidget(progress_group)` through `return panel`) with:

```python
        top_layout.addWidget(progress_group)

        log_group = QGroupBox("Activity Log")
        log_group.setWhatsThis(
            "<b>Activity Log</b><br>Live encoding messages for the current "
            "session. Drag the separator above this panel to make the log "
            "taller or shorter.")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(4, 4, 4, 4)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(60)
        self.log_text.setPlaceholderText("Encoding activity will appear here...")
        log_layout.addWidget(self.log_text)

        # Draggable log: no fixed 100px cap — the user decides the height.
        self.log_splitter = QSplitter(Qt.Orientation.Vertical)
        self.log_splitter.setChildrenCollapsible(False)
        self.log_splitter.addWidget(top_widget)
        self.log_splitter.addWidget(log_group)
        self.log_splitter.setStretchFactor(0, 1)
        self.log_splitter.setStretchFactor(1, 0)
        self.log_splitter.setSizes([420, 200])
        layout.addWidget(self.log_splitter)

        return panel
```

This deletes the old `self.log_text.setMaximumHeight(100)` line (replaced by `setMinimumHeight(60)`).

- [ ] **Step 4: Run the test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`
Expected: `RESULT: ALL PASS (5 checks)`.

- [ ] **Step 5: Commit fix 2 (independent revert unit)**

```bash
git add ui/main_window.py tests/test_layout_dynamic.py
git commit -m "fix(ui): draggable Activity Log (remove 100px cap)"
```

---

### Task 3: Full regression

- [ ] **Step 1: Run the entire suite**

Run:
```bash
for f in tests/test_*.py; do echo "--- $f"; QT_QPA_PLATFORM=offscreen timeout 120 python3 "$f" 2>&1 | grep -E "RESULT|FAIL"; done
```
Expected: 9 files, all `ALL PASS`, totals
`23+6+36+14+16+5+12+85+8 = 215 checks`, **zero** `[FAIL]`.

- [ ] **Step 2: Syntax check**

Run: `python3 -m py_compile ui/main_window.py tests/test_layout_dynamic.py`
Expected: silent success.

---

### Task 4: Documentation (CHANGELOG, help/user guides, AGENTS, test log)

**Files:**
- Modify: `CHANGELOG.md` (top, after the version-adherence header)
- Modify: `docs/user_guide.md:881` (### Logs)
- Modify: `docs/user_guide.ar.md:584` (### سجلات التشغيل)
- Modify: `AGENTS.md` (## Responsive Window Sizing section, end)
- Create: `docs/test-results/2026-10-08-dynamic-layout.md`

- [ ] **Step 1: CHANGELOG `[Unreleased]` entry**

Insert directly after the `adheres to [Semantic Versioning]…` line in `CHANGELOG.md`:

```markdown
## [Unreleased]

### Fixed
- **Subtitle box squashed on shorter windows** (`ui/main_window.py`): the left settings panel is now wrapped in a `QScrollArea` (`self.settings_scroll`) — every settings box (Subtitles included) always keeps its natural height and a scrollbar appears instead of Qt compressing the boxes. Horizontal splitter behavior (300/950) is unchanged.
- **Activity Log cramped at 100 px** (`ui/main_window.py`): removed the hard `setMaximumHeight(100)`; Files/Queue/Progress and the Activity Log now sit in a vertical `QSplitter` (`self.log_splitter`, non-collapsible, default ≈200 px) — drag the separator to give the log any height.
```

- [ ] **Step 2: In-app help (What's This) — already added in Task 2 Step 3(c)**

Verify only: `grep -n "Drag the separator above this panel" ui/main_window.py` → 1 match (on `log_group.setWhatsThis`).

- [ ] **Step 3: English user guide**

In `docs/user_guide.md`, under the `### Logs` heading (line 881 — the paragraph starting `Location: ~/.config/vconv/logs/vconv.log`), append after that section's bullet list (before the `---` that precedes `## Command Line Interface`):

```markdown
The main window also has an in-app **Activity Log** panel (bottom-right)
showing live encoding messages. Drag the separator above it to resize — it
starts about 200 px tall and has no fixed limit.
```

- [ ] **Step 4: Arabic user guide**

In `docs/user_guide.ar.md`, under `### سجلات التشغيل` (line 584), after its bullet list (`- تغييرات الإعدادات`), append:

```markdown

تحتوي النافذة الرئيسية أيضًا على لوحة **سجل النشاط** (أسفل اليمين) تعرض رسائل الترميز الفورية. اسحب الفاصل فوقها لتعديل الحجم؛ يبدأ بارتفاع حوالي 200 بكسل ولا يوجد حد أقصى له.
```

- [ ] **Step 5: AGENTS.md rule (so future agents don't undo it)**

At the end of the `## Responsive Window Sizing (v9.7.2)` section in `AGENTS.md` (before `## Encoder Capability Engine`), append:

```markdown
- **Settings panel lives in a `QScrollArea`** (`_create_central_widget`, `self.settings_scroll`): never remove it — the left panel's content is taller than small windows and Qt compresses the last boxes (Subtitles) without it. `self.sub_group` is exposed for `tests/test_layout_dynamic.py`.
- **Activity Log has no height cap**: `log_group` sits in `self.log_splitter` (vertical, `setChildrenCollapsible(False)`, default ≈200 px, stretch only to the upper sections). Do not re-add `setMaximumHeight` on `self.log_text`.
```

- [ ] **Step 6: Test-results / reversibility log**

Create `docs/test-results/2026-10-08-dynamic-layout.md` with (fill SHAs from Steps in Tasks 1–2 — read them via `git log --oneline -3`):

```markdown
# Dynamic settings panel + Activity Log — 2026-10-08 (unreleased)

## Problem (user report)
- Subtitles box squashed into a thin strip on the user's window size (confirmed
  via Q&A: left panel has no scroll area, Qt compresses last boxes).
- Activity Log hard-capped at 100 px → only 2–3 visible lines ("text crowded").
- Screenshot not readable by agent; answers captured in brainstorm session
  (mockups: .superpowers/brainstorm/80749-1791454498/content/).

## Changes
1. Left panel wrapped in QScrollArea (`self.settings_scroll`) — boxes always
   keep natural height; horizontal splitter unchanged.
2. Right panel restructured: Files+Queue+Progress | Activity Log in vertical
   QSplitter (`self.log_splitter`), `setMaximumHeight(100)` removed,
   `setMinimumHeight(60)`, default sizes [420, 200], no children collapsible.

## Tests
- New: tests/test_layout_dynamic.py — 5 checks (scroll present; Subtitles
  keeps sizeHint at 760×520; splitter vertical/2-child; no height cap; log
  grows >150 px when splitter set to 300).
- Suite: 215 checks green (was 210).
Run: QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py

## Reversibility (each fix is an independent commit)
- Revert scroll panel:  git revert --no-edit <TASK1_SHA>
- Revert log splitter: git revert --no-edit <TASK2_SHA>
(docs in the same revert pass if desired: this file + CHANGELOG/guides lines.)

## Docs updated
CHANGELOG [Unreleased]; user_guide.md §Logs; user_guide.ar.md §سجلات التشغيل;
AGENTS.md (Responsive Window Sizing rules); in-app WhatsThis on Activity Log.
```

*(Replace `<TASK1_SHA>`/`<TASK2_SHA>` with the real hashes from `git log --oneline -4`.)*

- [ ] **Step 7: Commit docs**

```bash
git add CHANGELOG.md docs/user_guide.md docs/user_guide.ar.md AGENTS.md docs/test-results/2026-10-08-dynamic-layout.md
git commit -m "docs: changelog + user guides + AGENTS rules for dynamic layout fixes"
```

---

### Task 5: Acceptance handoff (no release yet)

- [ ] **Step 1: Stop the visual companion server**

Run: `/home/motaz/.cache/opencode/packages/superpowers@git+https:/github.com/obra/superpowers.git/node_modules/superpowers/skills/brainstorming/scripts/stop-server.sh /home/motaz/WebProjects/Video_Convert/.superpowers/brainstorm/80749-1791454498`

- [ ] **Step 2: Present results to the user for acceptance testing**

Tell the user: both fixes are committed with tests (215 green), docs updated, and ask them to run the app (`QT_QPA_PLATFORM` not needed — real session), verify (a) Subtitles box full height at any window size / resize small, (b) drag the log separator taller/shorter, (c) WhatsThis help on the Activity Log (What's This → click the log panel). **No release is cut until they approve** (spec rule). If they dislike the scroll panel → revisit tabs (option C) per spec fallback.
