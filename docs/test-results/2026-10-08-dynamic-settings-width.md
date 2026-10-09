# Test results — dynamic settings width (2026-10-08)

Spec: `docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md`

| Test | Command | Result |
|---|---|---|
| New width tests | `QT_QPA_PLATFORM=offscreen python3 tests/test_settings_width_dynamic.py` | RESULT: ALL PASS (31 checks) |
| Full suite | `for f in tests/test_*.py; do …` | RESULT: ALL PASS (315 checks, 13 files) |

## Real measurements (offscreen, current HEAD)

- Startup hug: **W = 239 px (Video)** — matches the video tab's hug target H
  (239) exactly; no fixed-300 split remains.
- Per-tab hints: Video H/F = **239/239**, Audio H = **190**, Subtitles F = **237**.
- Full per-file counts: analyzer_attached_pic 16, conversion_flags 23,
  defaults_hardening 42, e2e_format 6, encoder_engine 36, format_radio 14,
  layout_dynamic 16, self_update 16, settings_width_dynamic 31,
  thread_lifecycle 10, tools_startup_smoke 12, tool_updater 85, tool_worker 8.

## Notes

- Startup hug observed: W = 239 px (Video), Audio H = 190, Subtitles F = 237.
- Any assertion adjusted in older tests: **none** — `test_layout_dynamic.py` and
  `test_defaults_hardening.py` were already written to accept dynamic sizing
  and passed unchanged.
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