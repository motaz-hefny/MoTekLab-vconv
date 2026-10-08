# Design: Settings panel as tabs (Option C) + custom-folder default

- **Date**: 2026-10-08
- **Status**: Approved by user (brainstorming Q&A; look approved via Option C mockup)
- **Scope**: One UI restructure + one output-folder default, mostly in `ui/main_window.py`
- **Supersedes**: the "tab restructure parked" decision in `2026-10-08-dynamic-layout-design.md` (scroll area itself stays)

## Problem

The left settings panel is a single vertical stack of 8 group boxes. The user
tried the shipped Option A (scrollable panel) and, after seeing the Option C
mockup (`…/content/option-c-tabs.html`), prefers the tabbed layout: **"I like
the look of Option C more for the GUI so lets shift to it."**

Separately, the Output group's Custom-folder field starts empty every launch,
so choosing a destination always requires browsing: **"leave the default as
Same as source, but let the custom folder default to the logged-in user's
default video folder."**

## Goals

- Left panel reorganized into a top tab bar: **Video | Audio | Subtitles**,
  matching the approved mockup's composition and group order exactly.
- Radio defaults to *Same as source* (unchanged), and the Custom-folder field
  is pre-filled: last custom path used (remembered across sessions), else the
  user's XDG Videos directory.
- Zero behavior change to any settings value, signal, WhatsThis, conversion
  command building, or the wheel-guard.
- Tests + docs updated in the same change; full suite green.

## Non-goals (explicitly out of scope)

- Persisting the selected tab (always opens on Video) or the radio selection
  (always Same-as-source, per user).
- Custom styling of tabs (native Qt/platform tab look, no QSS).
- Changing where conversion writes when *Same as source* is active.
- Flat-output / format / any other setting semantics.
- Removing `settings_scroll` (the QScrollArea stays as a safety net — Video
  page has 6 groups and can exceed a 520-px-tall window).

## Design

### 1. Tab restructure (`ui/main_window.py`, `_create_left_panel`)

- `panel = QWidget()` keeps its `QVBoxLayout`; on it sits
  `self.settings_tabs = QTabWidget` (attribute exposed for tests).
- Pages (`QWidget` + `QVBoxLayout`, zero margins):
  - **Video**: Preset → Encoder → Crop & Color (v9.7) → Quality (RF) →
    Output → Format (exact mockup order; today's code order is Encoder →
    Crop → Quality → Preset → Output → Format — groups get re-appended).
  - **Audio**: Audio group.
  - **Subtitles**: Subtitles group.
- Pure container move: every widget attribute (`self.encoder_combo`,
  `self.sub_group`, `self.output_dir_edit`, …), every signal connection,
  WhatsThis/tooltips, and the `_on_audio_encoder_changed` init call are
  created exactly as today — only their parent layout changes.
- Wheel-guard: the `panel.findChildren((QComboBox, QSlider))` install loop
  runs at the end of `_create_left_panel` as today; `findChildren` is
  recursive, so widgets on all three pages are guarded.
- `settings_scroll` continues to wrap the returned panel (unchanged call
  site in `_create_central_widget`).
- Startup lands on tab 0 (Video). No `currentChanged` handlers.

### 2. Custom-folder default + memory

- New helper `default_videos_dir()` (module-level in `ui/main_window.py`,
  pure-function, unit-testable): parse `~/.config/user-dirs.dirs` for
  `XDG_VIDEOS_DIR="<path>"` (expand `$HOME`, strip quotes); if the file or
  key is missing, return `Path.home() / "Videos"`.
- Config key `defaults.output_dir` (default `'source'`, read today but never
  written anywhere) becomes the **last custom path** store:
  - Startup: seed `self.output_dir_edit` with the saved value if it is a
    non-`source` string; otherwise with `default_videos_dir()`. The field
    stays disabled until *Custom folder* is checked (unchanged).
  - Save (`config.set('defaults', 'output_dir', path)` + `config.save()`):
    when the user picks a folder via the 📁 Browse button, and when a
    conversion starts with *Custom folder* active (covers paths typed in
    manually).
- `output_same_radio.setChecked(True)` stays — radio never auto-switches.
- If the saved/XDG directory doesn't exist yet, still show the path
  (conversion already creates output dirs with `mkdir(parents=True)`).

### 3. Tests

- `tests/test_layout_dynamic.py` (extend, layout owner):
  - Existing no-squash check must **activate the Subtitles tab** before
    measuring `sub_group` height (a hidden page has no layout pass).
  - New: `settings_tabs` is a `QTabWidget` with count 3, labels
    `Video/Audio/Subtitles`; Preset+Encoder+Crop+Quality+Output+Format
    widgets are descendants of page 0, Audio group of page 1, `sub_group`
    of page 2; wheel-guard still blocks a wheel tick on a Video-tab combo
    and on the Audio-tab combo.
- `tests/test_defaults_hardening.py` (extend, defaults owner):
  - `default_videos_dir()` unit checks: XDG file with
    `XDG_VIDEOS_DIR="$HOME/Movies"` (monkeypatched HOME) → `…/Movies`;
    missing file → `~/Videos`.
  - Startup seed: fresh config → field shows XDG Videos path; saved
    `defaults.output_dir=/tmp/nas` → field shows `/tmp/nas`; radio still
    Same-as-source in both cases.

### 4. Docs

- `CHANGELOG.md` `[Unreleased]`: two entries (tabs; custom-folder default +
  memory) + test counts.
- `AGENTS.md`: amend the Responsive Window Sizing rule (scroll area now wraps
  the tab widget — still never remove); add a one-liner to the hardening
  section that the tabs are the panel's container.
- New `docs/test-results/2026-10-08-settings-tabs.md` after implementation:
  test matrix, screenshots optional, revert recipe (spec + plan commits +
  `git revert` range).
- `docs/user_guide.md` / `.ar.md`: Settings-panel description gains the tab
  wording (left-panel section), custom-folder default documented.

## Error handling / edge cases

- `user-dirs.dirs` malformed or unreadable → fall back to `~/Videos`
  (helper wraps reads in `try/except OSError`, returns fallback).
- Config contains a stale custom path whose directory was deleted → still
  seeded (path display only; mkdir happens at conversion time).
- Very short windows → Video page scrolls inside `settings_scroll` exactly
  as the whole panel does today.

## Rollback

Single revert of the implementation commit (spec/plan are docs-only); no
data migration — `defaults.output_dir` unused by any older version, so an
older build simply ignores it.
