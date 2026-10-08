# Design: Dynamic sizing for settings panel + Activity Log

- **Date**: 2026-10-08
- **Status**: Approved by user (brainstorming session, visual companion)
- **Scope**: Small, two isolated layout fixes in `ui/main_window.py`
- **Supersedes**: nothing

## Problem

User report (v9.7.5, screenshot not readable by agent — confirmed via Q&A):

1. **Subtitle box squashed**: the left settings panel is a plain vertical
   `QVBoxLayout` stack of group boxes (Encoder → Crop → Quality → … → Audio →
   Subtitles → Metadata) with **no scroll area**. On shorter windows Qt
   compresses widgets below their natural height; Subtitles (second-to-last)
   collapses into a thin strip. Confirmed answer: *"B — squashed into a thin
   strip"*.
2. **Activity Log too small**: `log_text` is hard-capped with
   `setMaximumHeight(100)` (`ui/main_window.py:1556`) — only ≈2–3 lines fit.
   Confirmed answer: *"B — the log box itself is too small"*.

Scope confirmed with user: **just these two fixes, smallest change**
(answers: subtitle issue = B; log issue = B; scope = A).

## Goals

- Subtitles (and every left-panel box) always renders at its natural height —
  never compressed, never clipped, at any window size ≥ the minimum
  (760×520 per `_screen_window_bounds`).
- Activity Log is **dynamic**: starts ≈200 px tall and can be dragged to any
  height by the user (no fixed cap).
- Visually identical to today on tall windows (no regression for existing
  users).
- Every change documented and committed so the end product can be **reversed
  easily** if the user dislikes it (explicit user requirement).

## Non-goals (explicitly rejected for this change)

- Tab restructure of the left panel (Video | Audio | Subtitles) — **parked as
  fallback**: if the user dislikes the scroll-area result after testing, we
  revisit option C from the mockups (`.superpowers/brainstorm/…/left-panel-options.html`).
- Collapsible group boxes (option B, explored then dropped).
- Font / line-spacing changes in the log (user's issue was box size, not
  line spacing).
- Persisting the dragged log height to config (nice-to-have; add later on
  request).

## Design

### 1. Scrollable settings panel

In `MainWindow._create_central_widget()` (`ui/main_window.py:1108`):

- Wrap the widget returned by `_create_left_panel()` in a `QScrollArea`:
  - `setWidgetResizable(True)` — inner panel follows viewport width.
  - Frameless, `setHorizontalScrollBarPolicy(AlwaysOff)` — horizontal
    resizing stays controlled by the existing splitter only.
- Move `left_panel.setMinimumWidth(0)` and the
  `SizePolicy(Ignored, Expanding)` from the inner panel onto the **scroll
  area**, so the horizontal `QSplitter` (`setSizes([300, 950])`, stretch
  0/1) keeps dragging exactly as today.
- Inner panel keeps its current construction unchanged (all group boxes,
  `addStretch()` at the end, margins/spacing). For testability, the
  currently-local `sub_group` becomes `self.sub_group` (one-line
  assignment, no behavior change).
- Behavior: when the window is tall enough, the content fits and no
  scrollbar appears (zero visual change). When short, a vertical scrollbar
  appears and every box — Subtitles included — keeps its `sizeHint` height.

### 2. Draggable Activity Log

In `MainWindow._create_right_panel()` (`ui/main_window.py:1431`):

- Group the three existing sections (`files_group`, `queue_group`,
  `progress_group`) into one inner `QWidget` with the same `QVBoxLayout`
  (spacing 6, same margins).
- Wrap that inner widget + `log_group` in a vertical `QSplitter`:
  - `setSizes([rest, 200])` default — log starts ≈200 px (6–8 lines).
  - Stretch: top section `(1,)`, log `(0,)` — growing the window gives
    space to the top; the log only changes when dragged.
  - `setChildrenCollapsible(False)` — sections can't be collapsed to zero.
- Remove `self.log_text.setMaximumHeight(100)` (line 1556) and replace with
  `setMinimumHeight(60)` so the log never fully vanishes when dragged up.
- The log keeps its `QTextEdit`, `_log()` behavior, placeholder and
  retention toggle — no functional change.

### 3. Reversibility (user requirement)

- **Two atomic commits**, one per fix, so `git revert` can undo either
  independently:
  1. `fix(ui): scrollable settings panel (Subtitles no longer squashes)`
  2. `fix(ui): draggable Activity Log (remove 100px cap)`
- Spec committed before implementation (`docs/superpowers/specs/`).
- `CHANGELOG.md` `[Unreleased]` entry describing both changes.
- Test-results doc (`docs/test-results/YYYY-MM-DD-dynamic-layout.md`)
  recording before/after evidence and the exact revert commands.

## Testing

New `tests/test_layout_dynamic.py` (offscreen, `QT_QPA_PLATFORM=offscreen`):

1. **No-squash**: construct `MainWindow`, resize to the minimum
   (760×520), process events → assert the Subtitles group box height is at
   least its natural/`sizeHint` height (minus 1 px tolerance) — fails on the
   old layout, passes with the scroll area.
2. **Log not capped**: locate the log splitter, set its sizes tall →
   assert `log_text.height() > 150` (old code caps at 100 regardless of
   splitter sizes).
3. **Splitter present**: right panel contains a `QSplitter` with 2 children
   (content widget + log group).

Regression: the full existing suite (210 checks) must stay green.

## Fallback path

If the user dislikes the scroll-area result:
- Revisit **option C — tabs (Video | Audio | Subtitles)** from the stored
  mockup `.superpowers/brainstorm/80749-1791454498/content/left-panel-options.html`
  as a new brainstorm → new spec → new plan. The two commits above revert
  cleanly before that.

## Rollout

Normal release flow only when the user has tested and approved the working
tree result (`docs/release_process.md`): no release is cut until the user
confirms both fixes look right.
