# Test results — Fahhim theme (2026-10-08)

Spec: `docs/superpowers/specs/2026-10-08-fahhim-theme-design.md`

| Test | Command | Result |
|---|---|---|
| New theme tests | `QT_QPA_PLATFORM=offscreen python3 tests/test_theme.py` | RESULT: ALL PASS (43 checks) |
| QSS parse warnings | `… 2>/tmp/qss_warn.log; grep -ci "could not parse" /tmp/qss_warn.log` | 0 |
| Full suite | `for f in tests/test_*.py; do …` | RESULT: ALL PASS (**358 checks, 14 files**) |
| Real-display smoke | `python3 /tmp/opencode/theme_smoke.py` (xcb on `DISPLAY=:0`) | SMOKE RESULT: ALL PASS (10 checks) |

## Per-file counts (full suite, 358 total)

analyzer_attached_pic 16, conversion_flags 23, defaults_hardening 42,
e2e_format 6, encoder_engine 36, format_radio 14, layout_dynamic 16,
self_update 16, settings_width_dynamic 31, theme 43, thread_lifecycle 10,
tools_startup_smoke 12, tool_updater 85, tool_worker 8.

## Real measurements

- **Offscreen render** (`test_window_renders_theme_colors`): light menubar pixel
  `r=247` (rose family, `>200`); dark menubar pixel `r=42` (crimson-black, `<60`).
- **Real-display smoke (xcb, `DISPLAY=:0`)** — automated, 10/10:
  - platform is `xcb`; light menubar pixel `r=247`.
  - Settings → Appearance submenu present with exactly `['Light','Dark','System']`.
  - Triggering **Dark** live-switches the app stylesheet (`#e5534b`), the window
    render goes dark (`r=42`) and the choice persists (`appearance.theme='dark'`).
  - A `QDialog` parented to the window inherits the app-wide theme (dark card,
    `r=0` at the corner) — dialogs need no per-dialog stylesheet.
  - Panel hug on the real platform: `W=233 ≈ H=233`.
  - `queue_start_btn` carries `objectName="primaryBtn"` (brand gradient rule).
- **System-follow**: `resolve()` unit-mapped for Dark/Light, and
  `QStyleHints.colorSchemeChanged` is connected exactly once (module-guarded).
  The real OS scheme cannot be flipped in CI; the live OS-follow path is the
  only item not exercised end-to-end here.

## Notes

- `tests/test_settings_width_dynamic.py` now applies the theme in `main()` to
  mirror `launch()`; see
  `docs/test-results/2026-10-08-dynamic-settings-width.md` for the themed vs
  pre-theme width numbers.
- **Remaining manual check (real display, by a human):** open Tools & Encoders
  and Audio Tracks dialogs and confirm they render themed (they inherit the
  app-wide stylesheet by construction, and a generic `QDialog` was verified
  programmatically), and toggle **System** while the OS is in light vs dark.
