# Test results — dynamic settings width (2026-10-08)

Spec: `docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md`

| Test | Command | Result |
|---|---|---|
| New width tests | `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py` | RESULT: ALL PASS (31 checks) |
| Full suite | `for f in tests/test_*.py; do …` | RESULT: ALL PASS (315 checks, 13 files) |

## Real measurements (offscreen)

Two measurement sets, because the later Fahhim-theme task (Tasks 5–7) changed
the app's widget metrics (Fusion style + QSS padding/fonts). The width feature
logic is identical; only the px values move.

**Baseline (unthemed, Task 4 HEAD)** — `Origin/main` before the theme:

- Startup hug: **W = 239 px (Video)**, matching H(239); no fixed-300 split.
- Per-tab hints: Video H/F = **239/239**, Audio H = **190**, Subtitles F = **237**.

**Current (themed, after Task 7)** — `test_settings_width_dynamic.py` now
applies the Fahhim theme in `main()` to mirror `launch()` (which themes before
`MainWindow` is built). Re-measured offscreen:

- Startup hug: **W = 233 px (Video)** — matches H(233) exactly.
- Per-tab hints: Video H/F = **233/233**, Audio H/F = **204/160**,
  Subtitles H/F = **280/229**, Subtitles group min = **225**.
- Still all relative invariants hold: `H(Audio) < H(Video)`,
  `W(Audio) < W(Video)`, `F(Audio) < F(Video)`, `F(Subtitles) < 300`, and
  startup `W ≈ H`.

- Full per-file counts (baseline run): analyzer_attached_pic 16, conversion_flags
  23, defaults_hardening 42, e2e_format 6, encoder_engine 36, format_radio 14,
  layout_dynamic 16, self_update 16, settings_width_dynamic 31,
  thread_lifecycle 10, tools_startup_smoke 12, tool_updater 85, tool_worker 8
  (315 checks). `test_theme.py` (43 checks) was added in the theme task; the
  recomputed grand total is recorded in
  `docs/test-results/2026-10-08-fahhim-theme.md`.

## Notes

- Startup hug observed: themed W = 233 px (Video); Audio H = 204, Subtitles F = 229.
- Assertions adjusted in older tests: **one** — `test_settings_width_dynamic.py`
  gained the theme application + the Audio soft bound moved `190 < 200` →
  `204 < 215`. Rationale: `ui/main_window.py` no longer sets the `hwLabel`
  inline font (Task 7 moved it to the `QLabel#hwLabel` QSS rule), so an
  *unthemed* `MainWindow` measured a larger Video `sizeHint` (292) than the
  splitter could fit (274). The real app always themes at `launch()`, so the
  test now does the same. `test_layout_dynamic.py` and
  `test_defaults_hardening.py` still pass unchanged.
- **`_HugTabWidget` deviation (see the plan's "Execution deviations" section in
  `docs/superpowers/plans/2026-10-08-dynamic-width-and-fahhim-theme.md`)**: the
  plan assumed `QTabWidget.sizeHint()` returns the *current* page's hint, but
  Qt 6.11 returns the **max over all pages** (`qtabwidget.cpp`), so the hug
  target would have been permanently the widest tab (284 px) and the per-tab
  assertions could never pass. Task 2 added a module-level `_HugTabWidget(QTabWidget)`
  overriding **both** `sizeHint()` and `minimumSizeHint()` to hug the current
  page (recomputing Qt's padding, tab-bar floor preserved, `currentChanged →
  updateGeometry`), and `settings_tabs` is built from it. Measured offscreen:
  Video H/F = 239/239, Audio = 190/172, Subtitles = 284/237.