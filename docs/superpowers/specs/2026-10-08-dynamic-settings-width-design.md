# Design: Dynamic settings-panel width (content-hug + reflow)

- **Date**: 2026-10-08
- **Status**: Approved by user (brainstorming Q&A: behavior C, stickiness C, approach A, reflow rules + label shortening "ok on all", Sections 1–3 approved)
- **Scope**: `ui/main_window.py` (left-panel construction + a small width controller), one new test file, docs
- **Builds on**: `2026-10-08-dynamic-layout-design.md` (keeps `settings_scroll` vertical scroll; replaces the fixed horizontal sizing)

## Problem

The left settings panel sits at a fixed `300 / 950` splitter split. Measured
(offscreen, default font):

| Page | natural width | vs 300 px panel |
|---|---|---|
| Video | 270 | fits, ~30 px dead space |
| Audio | 168 | **~130 px dead space** |
| Subtitles | 393 | **clipped** (h-scroll off) |

The width is forced by row layout sums, not by the widgets users touch:

- **Subtitles 393**: one H-row = `➕ Add + ❌ + 🗑` (158) + `Burn external +
  Set as default` (207) side by side = 369 (`ext_btn_layout` nests
  `ext_opts_layout`).
- **Video 270**: Output group — radio `Same as source (preserve structure)`
  (226) + checkbox `Flat output (dump all files in one folder)` (246);
  neither can wrap in Qt.
- **Audio 168**: `Tracks...` button + labels.
- Combos contribute content-driven widths (AV1 Speed row 227, etc.).

User requirements (verbatim intent): panel must be **dynamic** — hug the
active tab's content (shrink *and* grow), respond to splitter drags, and the
**contents must reflow** (word-wrap into 2 lines, widgets shrink) rather than
forcing the panel wider; **not** by reducing the font size.

## Goals

1. Hug per tab: panel width follows the active tab's natural width — shrinks
   on narrow tabs, grows when a wider tab would otherwise clip.
2. Manual splitter position is sticky for the session; the panel only moves
   on its own when the active tab's content would be cut off.
3. Content reflow so `N` itself shrinks: wrapped labels, flexible combos, the
   Subtitles row split in two, shorter floor-setting labels (tooltips keep the
   full text).
4. Never clip: a hard floor (Qt `minimumWidth`) always equals the active
   tab's achievable minimum.
5. All logic unit-testable offscreen; full suite green; docs updated.

## Non-goals

- Font-size changes (explicitly rejected by user).
- Left panel absorbing window-resize growth (stretch stays 0/1).
- Persisting width or `M` across restarts (session-only; config untouched).
- Right side, vertical scroll area, wheel-guard, signal/WhatsThis behavior.
- A generic flow/wrap layout engine (only the one Subtitles row is split).
- Translating widget copy (English strings stay, as today).

## Design

### 1. Content reflow (`_create_left_panel`)

| Rule | Applies to | Effect |
|---|---|---|
| `setWordWrap(True)` on descriptive `QLabel`s whose `sizeHint().width() > 150` | GPU status label (`🖥️ NVIDIA GeForce…`, hint 202) and any other label found by that measurable rule | wraps to 2 lines as width tightens; extra height absorbed by `settings_scroll` |
| horizontal `Ignored` size policy on **every** `QComboBox` inside the settings panel | preset, crop, AV1 speed, audio encoder/bitrate, subtitle mode, … (encoder combo already has it — `ui/main_window.py:1201` is the precedent) | combos contribute ~0 to layout minimum; text elides when squeezed; popups unaffected |
| Split the Subtitles mega-row | move `ext_opts_layout` (Burn external / Set as default) from inside `ext_btn_layout` to its own row in `sub_layout` | group min ≈ 369 → ≈ 225 |
| Shorten floor-setting copy | `Flat output (dump all files in one folder)` → `Flat output (single folder)` (full text → tooltip); `Same as source (preserve structure)` → `Same as source` (full text → tooltip) | Video floor ≈ 270 → ≈ 220 (metadata checkbox 202 becomes the driver) |
| Sliders / line edits / lists | none | already flexible (Quality group min 93, path row 81, list 70) |

Checkboxes/radios cannot wrap — shortening is the only lever, hence the two
label changes above (no other copy changes).

### 2. Width controller

Two values, recomputed per event (never cached, never persisted):

- **`H = self.settings_tabs.sizeHint().width()`** — natural width → hug target.
- **`F = self.settings_tabs.minimumSizeHint().width()`** — achievable minimum
  (wrapped labels collapse to word width, `Ignored` combos drop out, split
  rows stand alone) → installed as `self.settings_scroll.setMinimumWidth(F)`.

Refinement of approved Section 1: the single `N` is now `H` for hug and `F`
for the drag floor; when content can't shrink they coincide.

State: `W` (splitter `sizes()[0]`), `M` (manual flag, session-only).

| Event | Action |
|---|---|
| Startup | `M=false`; `W ← H(Video)`; floor `← F(Video)` |
| Tab switch → `(H', F')` | floor `← F'`; if `M=false` → `W ← H'` (shrink or grow); if `M=true` and `W < F'` → `W ← F'` (never clip); else keep `W` |
| User drags handle | `M=true`; Qt enforces `W ≥ F` during the drag |
| Window resize | stretch unchanged (0/1); sanity clamp `F ≤ splitter width − right-panel minimum` before applying |

Implementation:

- Pure helper `MainWindow._left_width_action(current, hug, floor, manual) →
  int | None` — returns the new width or `None` ("leave as is"). All truth-
  table rows tested directly (same pattern as `_screen_window_bounds`).
- Event wiring: `settings_tabs.currentChanged` → recompute + apply;
  `splitter.splitterMoved` → set `M=true` **only when not inside a
  programmatic apply** (guard flag, so hug writes never mark manual).
- The horizontal `QSplitter` stays the same object with stretch `0 / 1` and
  `setChildrenCollapsible(True)`; only the initial `setSizes([300, 950])` is
  replaced by the startup hug.

Post-reflow targets (asserted by tests, exact px font-dependent):

| Tab | H (hug) | F (floor) |
|---|---|---|
| Video | ≈ 233 (metadata checkbox drives F) | ≈ 233 |
| Audio | ≈ 204 — the tab bar is the universal floor | ≈ 160 |
| Subtitles | ≈ 280 | ≈ 229 |

Measured values are font/style dependent: the numbers above are the **themed**
(Fahhim, Tasks 5–7) measurements; the pre-theme baseline was Video 239/239,
Audio 190/172, Subtitles 284/237. The invariants (`H(Audio) < H(Video)`,
`F(Audio) < F(Video)`, `F(Subtitles) < 300`, startup `W ≈ H`) hold in both.

### 3. Edge cases

- **Tiny window**: `F` clamped to `splitter width − right-panel minimum`;
  window minimum (760×520) makes this belt-and-braces.
- **Size-hint staleness**: `H`/`F` computed at event time (Qt recalculates on
  demand); no listeners beyond `currentChanged`.
- **First show**: hug applied in `_create_central_widget` after
  `setSizes`; layout settles on `show()` — covered by an offscreen test.
- **Wheel-guard / signals**: untouched — the reflow pass runs inside
  `_create_left_panel` before the existing `findChildren` guard loop, which
  stays last.

## Testing

New `tests/test_settings_width_dynamic.py` (stub-worker pattern from
`test_layout_dynamic.py`, `QT_QPA_PLATFORM=offscreen`):

1. Startup: `W ≈ H(Video)` and `W < 300` (regression: no fixed 300).
2. Audio switch (no manual): `W` shrinks to ≈ `H(Audio)`; `H(Audio) < H(Video)`.
3. Subtitles switch: `W ≥ F(Subtitles)`; `F(Subtitles) < 300` (reflow works).
4. Manual stickiness: programmatic "drag" → mark manual → tab switches keep `W`.
5. Never-clip: manual `W < F'` on switch → grows to `F'`.
6. Pure helper truth table: all `(manual × H/F comparison)` rows.
7. Reflow asserts: Subtitles group `minimumSizeHint < 300`; Audio page `< 215`
   (themed; was `< 200` pre-theme);
   GPU label `wordWrap()`; every settings-panel combo horizontal policy
   `Ignored`; `ext_opts_layout` is not nested in `ext_btn_layout`;
   shortened labels present, full copy in tooltips.
8. Existing suite (284 checks) stays green; `test_layout_dynamic` and
   `test_defaults_hardening` may assert old constants → update deliberately,
   recording why.

Expected new-check count and final suite total recorded in
`docs/test-results/` after implementation.

## Docs (same change)

- `CHANGELOG.md` → Unreleased → Fixed/Added entry (dynamic width + reflow).
- `AGENTS.md` → pattern section "Dynamic Settings Width Pattern (H/F/M)".
- `docs/test-results/2026-10-08-dynamic-settings-width.md`.
- One-line notes in `docs/user_guide.md` + `docs/user_guide.ar.md`
  (settings section): the panel sizes itself to the active tab.

## Revert recipe

- `git revert` the implementation + this spec's follow-up commits; no config
  keys, no migrations, no signal-contract changes — rollback-safe by
  construction.
