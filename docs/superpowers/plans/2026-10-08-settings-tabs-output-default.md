# Settings Tabs (Option C) + Custom-Folder Default — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Update the Progress Log (bottom) and tick boxes as you go** — this file is the resume point after a crash/handoff.

**Goal:** Reorganize the left settings panel into Video | Audio | Subtitles tabs (approved Option C) and pre-fill the Custom output folder with the last-used path or the user's XDG Videos folder, without changing any setting behavior.

**Architecture:** Pure container restructure inside `_create_left_panel` (a `QTabWidget` replaces the flat group stack; every widget/signal/attribute untouched) + one new pure helper `default_videos_dir()` + one config-persistence hook (`defaults.output_dir`, currently dead) feeding the existing `output_dir_edit`.

**Tech Stack:** PyQt6, unittest-style check() test scripts (no pytest), configparser-backed `utils/config.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-settings-tabs-output-default-design.md` (approved, commit `4c4888d`).

**Ground rules (project):**
- Tests run with: `QT_QPA_PLATFORM=offscreen python3 tests/<file>.py`
- Never commit without green tests; record results in `docs/test-results/`.
- All anchors below are **unique strings**, not line numbers — line numbers drift; if an anchor doesn't match exactly, grep for it before improvising.
- Commit after every task (TDD: test first, RED, implement, GREEN, commit).

---

### Task 1: `default_videos_dir()` helper (TDD)

**Files:**
- Modify: `ui/main_window.py` (module level, insert before `class MainWindow(QMainWindow):` at line 595)
- Test: `tests/test_defaults_hardening.py`

- [ ] **Step 1: Add `import tempfile` is already present; add `from unittest import mock`** to `tests/test_defaults_hardening.py` imports (after `import re` block: `from unittest import mock`).

- [ ] **Step 2: Write the failing test** — add this function to `tests/test_defaults_hardening.py` (after `test_presets_preserve_source_audio`) and call it in `main()` after `test_presets_preserve_source_audio()`:

```python
def test_default_videos_dir():
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        (home / ".config").mkdir()
        (home / ".config" / "user-dirs.dirs").write_text(
            'XDG_VIDEOS_DIR="$HOME/Vidz"\n', encoding="utf-8")
        check("XDG user-dirs.dirs honored ($HOME expanded)",
              mw.default_videos_dir(home) == home / "Vidz")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        check("missing user-dirs.dirs falls back to ~/Videos",
              mw.default_videos_dir(home) == home / "Videos")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        (home / ".config").mkdir()
        (home / ".config" / "user-dirs.dirs").write_text(
            "# comment only\n", encoding="utf-8")
        check("missing XDG_VIDEOS_DIR key falls back to ~/Videos",
              mw.default_videos_dir(home) == home / "Videos")
```

In `main()`, add after `test_presets_preserve_source_audio()`:

```python
    test_default_videos_dir()
```

- [ ] **Step 3: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_defaults_hardening.py`
Expected: earlier checks PASS, then `AttributeError: module 'ui.main_window' has no attribute 'default_videos_dir'` (last test in main) — FAIL confirmed.

- [ ] **Step 4: Implement** — insert **before** `class MainWindow(QMainWindow):` (line 595):

```python
def default_videos_dir(home=None):
    """Resolve the logged-in user's XDG Videos directory; fallback ~/Videos.

    Reads ~/.config/user-dirs.dirs (freedesktop user-dirs) so localized or
    renamed video folders are honored. `home` is injectable for tests.
    """
    home = Path(home) if home else Path.home()
    try:
        text = (home / ".config" / "user-dirs.dirs").read_text(encoding="utf-8")
    except OSError:
        return home / "Videos"
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("XDG_VIDEOS_DIR"):
            _, _, value = line.partition("=")
            value = value.strip().strip('"')
            value = value.replace("$HOME", str(home))
            if value:
                return Path(value)
    return home / "Videos"


```

(`Path` is already imported in this module.)

- [ ] **Step 5: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_defaults_hardening.py`
Expected: `RESULT: ALL PASS (34 checks)` (31 + 3 new).

- [ ] **Step 6: Commit**

```bash
git add ui/main_window.py tests/test_defaults_hardening.py
git commit -m "feat(output): default_videos_dir() helper (XDG user-dirs, testable)"
```

---

### Task 2: Custom-folder seed + persistence (TDD)

**Files:**
- Modify: `ui/main_window.py` (output group seed ~line 1298; new `_remember_output_dir` before `_browse_output`; `_browse_output`; conversion start ~line 2085)
- Test: `tests/test_defaults_hardening.py`

- [ ] **Step 1: Write the failing tests** — add both functions to `tests/test_defaults_hardening.py` and call them in `main()` after `test_default_videos_dir()`:

```python
def test_custom_output_folder_seed():
    with tempfile.TemporaryDirectory() as d:
        cfg = Config(str(Path(d) / "vconv.conf"))
        cfg.load()
        with mock.patch.object(mw, "default_videos_dir",
                               return_value=Path("/home/u/Videos")):
            win = make_window(cfg)
        check("fresh config seeds XDG Videos folder",
              win.output_dir_edit.text() == "/home/u/Videos")
        check("radio stays on Same-as-source (fresh)",
              win.output_same_radio.isChecked())
        check("custom field disabled until Custom chosen",
              not win.output_dir_edit.isEnabled())
        win.close()
        del win
        gc.collect()
    with tempfile.TemporaryDirectory() as d:
        cfg = Config(str(Path(d) / "vconv.conf"))
        cfg.load()
        cfg.set("defaults", "output_dir", "/mnt/nas/exports")
        cfg.save()
        cfg2 = Config(str(Path(d) / "vconv.conf"))
        cfg2.load()
        win = make_window(cfg2)
        check("saved custom path wins over XDG default",
              win.output_dir_edit.text() == "/mnt/nas/exports")
        check("radio still Same-as-source (saved path)",
              win.output_same_radio.isChecked())
        win.close()
        del win
        gc.collect()


def test_remember_output_dir_persists():
    with tempfile.TemporaryDirectory() as d:
        cfg = Config(str(Path(d) / "vconv.conf"))
        cfg.load()
        win = make_window(cfg)
        win._remember_output_dir("/tmp/newdest")
        check("custom path persisted to config",
              str(cfg.get("defaults", "output_dir", "source")) == "/tmp/newdest")
        win._remember_output_dir("")
        check("empty path ignored (no overwrite)",
              str(cfg.get("defaults", "output_dir", "source")) == "/tmp/newdest")
        win._remember_output_dir("source")
        check("'source' token ignored",
              str(cfg.get("defaults", "output_dir", "source")) == "/tmp/newdest")
        win.close()
        del win
        gc.collect()
```

In `main()` add after `test_default_videos_dir()`:

```python
    test_custom_output_folder_seed()
    test_remember_output_dir_persists()
```

- [ ] **Step 2: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_defaults_hardening.py`
Expected: FAIL — fresh-config seed check gets `""` (field starts empty) and/or `_remember_output_dir` AttributeError.

- [ ] **Step 3: Implement (a) — seed the field.** In `_create_left_panel`, the output group, replace exactly:

```python
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setEnabled(False)
        self.output_dir_edit.setPlaceholderText("Select custom output folder...")
```

with:

```python
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setEnabled(False)
        seed_out = str(self.output_dir or 'source')
        if seed_out in ('', 'source'):
            seed_out = str(default_videos_dir())
        self.output_dir_edit.setText(seed_out)
        self.output_dir_edit.setPlaceholderText("Select custom output folder...")
```

(`self.output_dir` is read from `defaults.output_dir` in `__init__` at line 620 — already runs before the panel is built. The radio block below still calls `setChecked(True)` on `output_same_radio`; do not touch it.)

- [ ] **Step 4: Implement (b) — remember method.** Insert before `def _browse_output(self):`:

```python
    def _remember_output_dir(self, path):
        """Persist the last custom output folder (''/source ignored)."""
        path = str(path or '')
        if not path or path == 'source' or path == str(self.output_dir):
            return
        self.output_dir = path
        self.config.set('defaults', 'output_dir', path)
        self.config.save()

```

- [ ] **Step 5: Implement (c) — save on Browse.** In `_browse_output`, replace:

```python
        if folder:
            self.output_dir_edit.setText(folder)
```

with:

```python
        if folder:
            self.output_dir_edit.setText(folder)
            self._remember_output_dir(folder)
```

- [ ] **Step 6: Implement (d) — save on conversion start.** Around line 2085, replace:

```python
        if self.output_custom_radio.isChecked() and self.output_dir_edit.text():
            output_base = self.output_dir_edit.text()
            preserve_structure = not self.flat_output_check.isChecked()
```

with:

```python
        if self.output_custom_radio.isChecked() and self.output_dir_edit.text():
            output_base = self.output_dir_edit.text()
            preserve_structure = not self.flat_output_check.isChecked()
            self._remember_output_dir(output_base)
```

- [ ] **Step 7: Run to verify GREEN**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_defaults_hardening.py`
Expected: `RESULT: ALL PASS (42 checks)` (34 + 5 + 3).

- [ ] **Step 8: Commit**

```bash
git add ui/main_window.py tests/test_defaults_hardening.py
git commit -m "feat(output): custom-folder field seeds XDG Videos / last path, remembered on browse+convert"
```

---

### Task 3: Left panel → Video | Audio | Subtitles tabs (TDD)

**Files:**
- Modify: `ui/main_window.py` (`_create_left_panel` only, lines 1154–1462)
- Test: `tests/test_layout_dynamic.py`

- [ ] **Step 1: Update the test import** — in `tests/test_layout_dynamic.py`:

```python
from PyQt6.QtWidgets import QApplication, QScrollArea, QSplitter, QTabWidget
```

- [ ] **Step 2: Patch the no-squash test** — in `test_settings_panel_never_squashes`, replace:

```python
    sub = getattr(win, "sub_group", None)
```

with (the Subtitles page must be visible for a layout pass):

```python
    tabs0 = getattr(win, "settings_tabs", None)
    if tabs0 is not None:
        tabs0.setCurrentIndex(2)
        QApplication.processEvents()
    sub = getattr(win, "sub_group", None)
```

- [ ] **Step 3: Write the failing structure test** — add to `tests/test_layout_dynamic.py` (before `main`) and call it first in `main()`:

```python
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
```

In `main()` add as the **first** call:

```python
    test_settings_tabs_structure()
```

- [ ] **Step 4: Run to verify RED**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`
Expected: `[FAIL] settings_tabs is a QTabWidget` → exits 1.

- [ ] **Step 5: Implement (a) — tab scaffolding.** In `_create_left_panel`, replace:

```python
    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)
        layout.setContentsMargins(2, 2, 2, 2)
```

with:

```python
    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)
        layout.setContentsMargins(2, 2, 2, 2)

        tabs = QTabWidget()
        tabs.setObjectName("settings_tabs")
        video_page = QWidget()
        video_layout = QVBoxLayout(video_page)
        video_layout.setSpacing(6)
        video_layout.setContentsMargins(0, 6, 0, 0)
        audio_page = QWidget()
        audio_layout = QVBoxLayout(audio_page)
        audio_layout.setSpacing(6)
        audio_layout.setContentsMargins(0, 6, 0, 0)
        subs_page = QWidget()
        subs_layout = QVBoxLayout(subs_page)
        subs_layout.setSpacing(6)
        subs_layout.setContentsMargins(0, 6, 0, 0)
```

(`QTabWidget` is already imported — `ui/main_window.py:26`.)

- [ ] **Step 6: Implement (b) — re-home the eight groups.** Exact one-line replacements (each unique):

| old | new |
|---|---|
| `layout.addWidget(encoder_group)` | `video_layout.addWidget(encoder_group)` |
| `layout.addWidget(crop_group)` | `video_layout.addWidget(crop_group)` |
| `layout.addWidget(quality_group)` | `video_layout.addWidget(quality_group)` |
| `layout.addWidget(preset_group)` | `video_layout.insertWidget(0, preset_group)` |
| `layout.addWidget(output_group)` | `video_layout.addWidget(output_group)` |
| `layout.addWidget(format_group)` | `video_layout.addWidget(format_group)` |
| `layout.addWidget(audio_group)` | `audio_layout.addWidget(audio_group)` |
| `layout.addWidget(sub_group)` | `subs_layout.addWidget(sub_group)` |

Note `insertWidget(0, …)` for Preset — it is created *after* Encoder/Crop/Quality in code but must come **first** on the Video tab (mockup order: Preset → Encoder → Crop → Quality → Output → Format).

- [ ] **Step 7: Implement (c) — metadata into Output group.** Replace:

```python
        layout.addWidget(self.metadata_check)
```

with:

```python
        out_layout.addWidget(self.metadata_check)
```

(`out_layout = QVBoxLayout(output_group)` at line 1286, still in scope; renders "Preserve metadata" inside the Output box, exactly like the approved mockup.)

- [ ] **Step 8: Implement (d) — tab wiring tail.** Replace:

```python
        for wgt in panel.findChildren((QComboBox, QSlider)):
            wgt.installEventFilter(self)

        layout.addStretch()
        return panel
```

with:

```python
        video_layout.addStretch()
        audio_layout.addStretch()
        subs_layout.addStretch()
        tabs.addTab(video_page, "Video")
        tabs.addTab(audio_page, "Audio")
        tabs.addTab(subs_page, "Subtitles")
        layout.addWidget(tabs)

        for wgt in panel.findChildren((QComboBox, QSlider)):
            wgt.installEventFilter(self)

        return panel
```

(The wheel-guard loop stays **after** `addTab` — `findChildren` is recursive and all pages are parented by then, so combos/sliders on all three tabs are guarded.)

- [ ] **Step 9: Run to verify GREEN (layout)**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_layout_dynamic.py`
Expected: `RESULT: ALL PASS` (5 old + 10 new checks = 15).

- [ ] **Step 10: Run defaults tests (wheel-guard crosses tabs)**

Run: `QT_QPA_PLATFORM=offscreen python3 tests/test_defaults_hardening.py`
Expected: `RESULT: ALL PASS (42 checks)` — wheel-guard still hits preset/encoder/audio/quality widgets.

- [ ] **Step 11: Commit**

```bash
git add ui/main_window.py tests/test_layout_dynamic.py
git commit -m "feat(ui): settings panel becomes Video|Audio|Subtitles tabs (Option C)"
```

---

### Task 4: Full suite

- [ ] **Step 1: Run every test file**

```bash
for t in tests/test_*.py; do echo "=== $t ==="; QT_QPA_PLATFORM=offscreen python3 "$t" || exit 1; done
```

Expected: every file prints `RESULT: ALL PASS`; grand total = 246 prior checks + 3 (Task 1) + 8 (Task 2) + 10 (Task 3) = **267** (adjust to actual sum if prior counts drifted; record the real number).

- [ ] **Step 2: Syntax guard on touched source**

Run: `python3 -c "import py_compile; py_compile.compile('ui/main_window.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit anything straggling**

```bash
git status --short
# if dirty: git add -u && git commit -m "test: suite green for settings tabs + output default"
```

---

### Task 5: Documentation (do before push — user rule: document as you work)

**Files:** `CHANGELOG.md`, `AGENTS.md`, `docs/user_guide.md`, `docs/user_guide.ar.md`, `docs/test-results/2026-10-08-settings-tabs.md`

- [ ] **Step 1: CHANGELOG.md** — under `## [Unreleased]` → `### Added`, prepend these two bullets (before the tests bullet):

```markdown
- **Settings panel reorganized into tabs — Video | Audio | Subtitles** (`ui/main_window.py`, `self.settings_tabs`): matches the approved Option C mockup. Video holds Preset → Encoder → Crop & Color → Quality (RF) → Output → Format, with the "Preserve metadata" checkbox moved *inside* the Output box; Audio and Subtitles get their own pages. Every widget attribute, signal, WhatsThis and the wheel-guard are unchanged — container-only restructure; the panel still scrolls inside `settings_scroll`.
- **Custom output folder pre-fills the user's Videos folder** (`ui/main_window.py`, new `default_videos_dir()`): "Same as source" remains the default radio; the Custom field starts with the last custom path used (persisted in `defaults.output_dir` on Browse and on every custom-mode conversion) or the XDG `XDG_VIDEOS_DIR` from `~/.config/user-dirs.dirs` (fallback `~/Videos`) on first run.
```

Then update the existing `tests/test_defaults_hardening.py` bullet's check counts (31 → 42) and the suite total (246 → actual Task 4 total) to match reality.

- [ ] **Step 2: AGENTS.md** — in the "Responsive Window Sizing" section, replace the bullet:

```markdown
- **Settings panel lives in a `QScrollArea`** (`_create_central_widget`, `self.settings_scroll`): never remove it — the left panel's content is taller than small windows and Qt compresses the last boxes (Subtitles) without it. `self.sub_group` is exposed for `tests/test_layout_dynamic.py`.
```

with:

```markdown
- **Settings panel = tabs inside a `QScrollArea`** (`_create_central_widget`, `self.settings_scroll`): the panel's `self.settings_tabs` is a `QTabWidget` with **Video | Audio | Subtitles** pages (Video: Preset→Encoder→Crop→Quality→Output→Format, metadata checkbox inside Output). Never remove the scroll area — the Video page is taller than small windows. `self.settings_tabs` and `self.sub_group` are exposed for `tests/test_layout_dynamic.py` (the no-squash test switches to the Subtitles tab before measuring).
```

- [ ] **Step 3: docs/user_guide.md** — after the Metadata Preservation intro paragraph (the one ending `...checkbox in the left panel.`), add a blank line then:

```markdown
The left settings panel is organized into three tabs: **Video** (preset, encoder, crop & color, quality, output, format), **Audio**, and **Subtitles**.
```

And under `### Custom Folder`, after the line `All output goes to a single destination folder.`, add a blank line then:

```markdown
On startup, "Same as source" is selected by default. The custom-folder field is pre-filled with the last folder you used, or your system's Videos folder on first use — browse to change it; the choice is remembered for next time.
```

- [ ] **Step 4: docs/user_guide.ar.md** — after the metadata intro paragraph (ending `...في اللوحة اليسرى.`), add a blank line then:

```markdown
لوحة الإعدادات اليسرى منظمة في ثلاث ألسنة: **فيديو** (الإعداد المسبق، الترميز، القص، الجودة، الإخراج، الصيغة)، **صوت**، و**الترجمة**.
```

And under the `**مجلد مخصص مع الحفاظ على الهيكل:**` block (after its closing ``` fence, before `### إدارة قائمة الملفات`), add a blank line then:

```markdown
عند بدء التشغيل، تكون "نفس المصدر" مختارة افتراضياً. ويُملأ حقل المجلد المخصص بآخر مجلد استخدمته، أو بمجلد الفيديو الخاص بنظامك في أول تشغيل — يمكنك تغييره عبر زر التصفح، وتُحفظ اختيارك للمرة القادمة.
```

- [ ] **Step 5: Create `docs/test-results/2026-10-08-settings-tabs.md`** — template below; fill `RESULT`/numbers from the actual Task 4 run output and paste each file's summary line:

```markdown
# Test Results — Settings tabs (Option C) + custom-folder default

- **Date**: 2026-10-08
- **Spec**: docs/superpowers/specs/2026-10-08-settings-tabs-output-default-design.md
- **Plan**: docs/superpowers/plans/2026-10-08-settings-tabs-output-default.md
- **Suite**: `for t in tests/test_*.py; do QT_QPA_PLATFORM=offscreen python3 "$t" || exit 1; done`

## Results

| File | Result |
|------|--------|
| test_defaults_hardening.py | 42 checks PASS (31 old + 11 new: XDG helper 3, seed 5, remember 3) |
| test_layout_dynamic.py | 15 checks PASS (5 old + 10 new tabs structure) |
| <paste remaining 9 files from run> | ... |
| **Total** | **<paste grand total> checks — ALL PASS** |

## Manual/functional checks
- Radio defaults to Same-as-source; Custom field shows `~/Videos` (fresh) or last path.
- Tabs switch with mouse/keyboard; all settings behave identically after the move.

## Revert recipe
- `git revert <implementation commits>` (docs/plan are docs-only); config key `defaults.output_dir` is ignored by older builds — safe.
```

- [ ] **Step 6: Tick every completed box in this plan file**, append a Progress Log entry (see bottom), then commit:

```bash
git add CHANGELOG.md AGENTS.md docs/user_guide.md docs/user_guide.ar.md docs/test-results/2026-10-08-settings-tabs.md docs/superpowers/plans/2026-10-08-settings-tabs-output-default.md
git commit -m "docs: settings tabs + custom-folder default (guides, AGENTS, test results)"
```

- [ ] **Step 7: Push**

```bash
git -c credential.helper='!f(){ echo "username=oauth2"; echo "password=$(gh auth token)"; }; f' push origin main
```

Expected: `main -> main`, in sync with origin.

---

## Self-Review (written by planner)

1. **Spec coverage**: tabs restructure (Task 3), XDG helper (Task 1), seed+persist (Task 2), tests all three (Tasks 1–3), scroll-area/wheel-guard preservation (Task 3 Steps 8–10), docs incl. test-results (Task 5), rollback noted (Step 5 of Task 5). Non-goals (no tab persistence, no QSS, radio always same-as-source) are not implemented anywhere. ✔
2. **Placeholders**: none — all code/commands/anchors exact and verified against the live tree (anchors grepped 2026-10-08). ✔
3. **Type consistency**: `default_videos_dir(home=None)` used by Task 1 tests (positional) and Task 2 seed (no-arg) — consistent; `_remember_output_dir(path)` call sites match; `self.settings_tabs` name matches test. ✔

---

## Progress Log (append here as you go — resume point)

- 2026-10-08: Plan written & committed. Spec `4c4888d`. All anchors verified against working tree (main @ `f03b4e1` + spec commit). No implementation started yet.
