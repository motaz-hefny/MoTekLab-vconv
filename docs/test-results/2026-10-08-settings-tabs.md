# Test Results — Settings tabs (Option C) + custom-folder default

- **Date**: 2026-10-08
- **Spec**: `docs/superpowers/specs/2026-10-08-settings-tabs-output-default-design.md` (`4c4888d`)
- **Plan**: `docs/superpowers/plans/2026-10-08-settings-tabs-output-default.md` (`ed746e5`)
- **Suite command**:
  ```bash
  for t in tests/test_*.py; do QT_QPA_PLATFORM=offscreen python3 "$t" || exit 1; done
  ```

## Results — full suite: **268 checks, ALL PASS, 11 files** (was 246 before this feature)

| File | Checks | Result |
|------|--------|--------|
| test_conversion_flags.py | 23 | PASS |
| test_defaults_hardening.py | **42** (was 31: +3 XDG helper, +5 seed, +3 remember) | PASS |
| test_e2e_format.py | 6 | PASS |
| test_encoder_engine.py | 36 | PASS |
| test_format_radio.py | 14 | PASS |
| test_layout_dynamic.py | **16** (was 5: +11 tab-structure checks) | PASS |
| test_self_update.py | 16 | PASS |
| test_thread_lifecycle.py | 10 | PASS |
| test_tools_startup_smoke.py | 12 | PASS |
| test_tool_updater.py | 85 | PASS |
| test_tool_worker.py | 8 | PASS |
| **Total** | **268** | **ALL PASS** |

## New checks added by this feature

- **`default_videos_dir()`**: XDG `user-dirs.dirs` honored (`$HOME` expanded), missing file → `~/Videos`, file without key → `~/Videos`.
- **Custom-folder seed**: fresh config → field shows XDG Videos path (mocked); saved `defaults.output_dir` wins; radio stays *Same-as-source* in both cases; field stays disabled until Custom is checked.
- **Persistence**: `_remember_output_dir()` writes `defaults.output_dir` on Browse/conversion; `''` and `'source'` never overwrite a saved path.
- **Tabs**: `settings_tabs` is a `QTabWidget`, 3 tabs labeled Video/Audio/Subtitles; Preset/Encoder/Crop/Quality/Output/Format + metadata checkbox all on Video; Audio group on Audio; `sub_group` on Subtitles; no-squash test switches to Subtitles tab before measuring; wheel-guard still blocks wheels on all four tabbed widgets (42-check defaults file covers this).

## Functional notes (offscreen)

- Wheel-guard verified programmatically (preset/encoder/audio combos + RF slider unchanged after wheel events) — the `findChildren` guard loop now runs after `addTab`, so pages are parented and covered.
- Persistence path verified against a temp `vconv.conf` (set → save → reload → seed).

## Deviations from plan (recorded during execution)

- Plan forgot `self.settings_tabs = tabs` (spec required it) — added during Task 3 Step 5.
- Structure test yields 11 checks, not the planned 10 → totals 268, not the predicted 267.
- Arabic guide anchors corrected: tabs note → after `## إعدادات الترميز` (plan said metadata para); custom-folder note → under `### مجلد مخصص` (plan said the line-154 block).

## Revert recipe

- `git revert` the three implementation commits (`2bf91e6`, `8bb543f`, `8738b64`) + docs commit; spec/plan are docs-only.
- Config key `defaults.output_dir` is ignored by older builds — no data migration, rollback-safe.
