# Design: Fahhim theme for vconv (Rosé light + Crimson dark, system-follow)

- **Date**: 2026-10-08
- **Status**: Approved by user (brainstorming: scope A "whole app, both themes like Fahhim", Approach A "app-wide QSS + palette dict", Sections 1–3 approved)
- **Scope**: new `ui/theme.py`, small hooks in `vconv.py` / `ui/main_window.py`, config key, docs
- **Palette source**: `~/WebProjects/Fahhim/src/index.css` (Fahhim's own tokens — Rosé light / Crimson dark / brand gradient)
- **Companion spec**: `2026-10-08-dynamic-settings-width-design.md` (independent features, same file touched; may ship in one cycle)

## Problem

vconv has **no theme at all**: it renders in the system Qt style, plus three
hardcoded inline colors (`ui/main_window.py:1251` `#00B4D8`,
`:1404` `#888`, `:1619` `#2ECC71`). The user wants the whole app — main
window, menus, tabs, tables, log, **and every dialog** — to adopt Fahhim's
brand look with Light/Dark/System switching like Fahhim's `ThemeContext`.

## Goals

1. Whole-app theming with Fahhim's exact palette values (hex spot-checked by
   tests): Rosé light, Crimson dark.
2. Three modes: **light | dark | system** (default `system`); System follows
   the OS live (`QStyleHints.colorSchemeChanged`, verified available in the
   installed Qt 6.11).
3. One mechanism, applied before first paint; dialogs inherit automatically.
4. Brand gradient on primary actions (Start Conversion, Apply-style buttons).
5. No geometry/layout/behavior changes; wheel-guard, log HTML color-coding,
   and all signals untouched.
6. Fully testable offscreen; docs updated; full suite green.

## Non-goals

- Recoloring icons/emoji or changing widget geometry.
- A theme editor / user-defined colors / third Fahhim theme (premium teal is
  a Fahhim preview variant — out).
- Restyling native OS file dialogs beyond what Qt applies automatically.
- Per-widget theme overrides or QSS cascading complexity.

## Design

### 1. `ui/theme.py` (new module)

```python
PALETTES = {
  'light': {  # Fahhim Rosé
    'background': '#fdf6f5', 'foreground': '#251320',
    'card': '#ffffff',       'card_fg': '#251320',
    'primary': '#be123c',    'primary_fg': '#ffffff',
    'secondary': '#f7ebe9',  'secondary_fg': '#251320',
    'muted': '#f7ebe9',      'muted_fg': '#7d5f6a',
    'accent': '#fdecf0',     'accent_fg': '#881337',
    'border': '#ecd9dc',     'input': '#ecd9dc',
    'destructive': '#b91c1c',
    'grad_start': '#f43f5e', 'grad_mid': '#e11d48', 'grad_end': '#be123c',
    'info': '#00B4D8', 'success': '#2ECC71', 'subtle': '#7d5f6a',
  },
  'dark': {   # Fahhim Crimson
    'background': '#140e0c', 'foreground': '#f4e3dd',
    'card': '#1c1310',       'card_fg': '#f4e3dd',
    'primary': '#e5534b',    'primary_fg': '#200a08',
    'secondary': '#2a1a15',  'secondary_fg': '#f4e3dd',
    'muted': '#221613',      'muted_fg': '#a4847a',
    'accent': '#2a1a15',     'accent_fg': '#f0c3ba',
    'border': '#33201b',     'input': '#221613',
    'destructive': '#ff7a6b',
    'grad_start': '#c22b23', 'grad_mid': '#e5534b', 'grad_end': '#c22b23',
    'info': '#00B4D8', 'success': '#5fc26a', 'subtle': '#a4847a',
  },
}
```

(`info/success/subtle` are functional tokens Fahhim doesn't define; values
chosen to stay legible on both backgrounds. `subtle` adopts each theme's
`muted_fg`.)

API:

- `resolve(mode, system_scheme) -> 'light' | 'dark'` — pure, testable.
- `build_stylesheet(theme) -> str` — QSS with tokens interpolated.
- `apply_theme(app, mode, config=None) -> str` — sets `Fusion` once, applies
  the stylesheet; when `mode == 'system'` resolves via
  `QGuiApplication.styleHints().colorScheme()` and connects
  `colorSchemeChanged` (guarded against duplicate connections) so the app
  re-themes live when the OS switches. Returns the concrete theme applied.
- `current_mode(config)` / `set_mode(config, mode)` — persistence helpers.

### 2. Hooks

- `vconv.py` `launch()`: `apply_theme(app, current_mode(cfg))` **before**
  `MainWindow(...)` — first paint is themed.
- `ui/main_window.py`: **Settings → Appearance** submenu → Light / Dark /
  System (`QActionGroup`, checkable, `system` checked by default; triggering
  any action calls `apply_theme` + persists via `set_mode`).
- Replace the three inline `setStyleSheet(...)` color literals with the
  `info` / `success` / `subtle` tokens (same visual values) — source test
  asserts `#00B4D8` no longer appears in `ui/main_window.py`.

### 3. Widget coverage (QSS targets)

Window + menubar/menus; `QGroupBox`; `QTabWidget`/`QTabBar`; `QComboBox`
(border, drop-down, popup `QAbstractItemView` rows); `QCheckBox` /
`QRadioButton` indicators; `QPushButton` — default variant plus a
`.primary`/objectName-marked variant carrying the **brand gradient**
(`Start Conversion`, dialog Apply/OK primaries); `QLineEdit`; `QSlider`
groove/handle (RF); files + queue `QTableWidget`; activity-log
`QPlainTextEdit` (default text color only — HTML spans keep their explicit
colors); `QScrollBar`; `QSplitter` handles; `QProgressBar`; `QToolTip`;
`QStatusBar`; `QScrollArea`; `QMessageBox` and all custom dialogs (inherit
the application stylesheet automatically).

## Testing

New `tests/test_theme.py` (`QT_QPA_PLATFORM=offscreen`):

1. Both palettes contain the full required token key set.
2. Fahhim hex spot-checks: light `background #fdf6f5`, `primary #be123c`,
   `border #ecd9dc`; dark `background #140e0c`, `primary #e5534b`,
   `border #33201b`; gradients match `src/index.css`.
3. `build_stylesheet('light') != build_stylesheet('dark')`; each contains
   its palette's primary hex.
4. `apply_theme`: `app.styleSheet()` non-empty; switching light→dark changes
   it; `resolve('system', …)` maps `ColorScheme.Dark → 'dark'`,
   `Light → 'light'`.
5. Persistence: `set_mode('dark')` → reload → `current_mode() == 'dark'`.
6. Appearance submenu exists with exactly 3 checkable actions; triggering
   "Dark" applies the dark stylesheet and persists.
7. MainWindow smoke-constructs with the stylesheet applied (stub workers).
8. Source scan: `#00B4D8` / `#2ECC71` / `setStyleSheet` literals gone from
   `ui/main_window.py` (tokens used instead).
9. Full suite (284 checks + any width-feature tests) stays green —
   wheel-guard and layout files must pass untouched.

## Docs (same change)

- `CHANGELOG.md` → Unreleased entry (Fahhim theme + Appearance menu).
- `AGENTS.md` → "Fahhim Theme Pattern (ui/theme.py)" section (tokens are the
  single source of truth; new hardcoded colors are a rule violation).
- `docs/test-results/2026-10-08-fahhim-theme.md`.
- `docs/user_guide.md` + `docs/user_guide.ar.md`: one line for
  Settings → Appearance.

## Revert recipe

- `git revert` implementation commits; config key `appearance/theme` is
  ignored by older builds (no migration). Spec is docs-only.
