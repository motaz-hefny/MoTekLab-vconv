# Defaults hardening verification — 2026-10-08 (unreleased)

## Scope
Acceptance report after the v9.7.5 dynamic-layout work: user saw **AAC** instead
of the copy default, **RF 24** instead of 27, AV1 conversion failing with
**HandBrakeCLI exit 3**, and no ★-badge recommended encoder. TDD (RED → GREEN),
no production code before a failing test.

## Root causes (all confirmed empirically)

| Symptom | Root cause | Fix |
|---|---|---|
| x265/AV1-HEVC conversions exit 3 | `core/converter.py` default `-x` had `subme=9` (x264-valid, x265 max = 7 → HB rejects whole command); same value in 4 x265 presets JSON | `subme=7` in converter + presets |
| Encoder flipped AV1 → x265, RF 27 → 24, copy → AAC | Qt routes wheel events to the widget **under the cursor** regardless of focus — scrolling the settings panel ticked the unguarded combos/slider | `eventFilter` swallows `QWheelEvent` on every `QComboBox`/`QSlider` child of the left panel |
| ★ badge never auto-selected | `encoder_combo.currentTextChanged` connected **before** the `addItem` loop → first `addItem` fired signal, clobbered config `auto` → recommendation logic saw a concrete encoder and skipped | connect moved after items exist |
| Configured audio default ignored | `self.audio_encoder` hardcoded `'copy'` at init (asymmetric with quality) | read `defaults.audio_encoder`/`audio_bitrate`, apply to combos |
| "RF 24" seen in Help | stale WhatsThis text (balanced 25 / high_quality 22 / tv_show 24 vs JSON 27/23/27) | WhatsThis synced to JSON |

Defaults were **never modified**: offscreen dump showed slider 27, combo
`copy`, `~/.config/vconv/vconv.conf` = `quality 27, audio_encoder copy,
encoder auto` before and after all test runs.

## Evidence

### HandBrakeCLI exit matrix (real HB 1.7.2, sample 2 s testsrc MP4)
```
-x "...subme=7..." → exit 0, out_new.mp4 written (HEVC/mp4, ffprobe clean)
-x "...subme=9..." → exit 3   ← the reported bug, reproduced exactly
```
Earlier bisection: `--quality 99`→3, bad `--crop`→3, `svt_av1 --quality 64`→3,
`subme=9`→3; `subme=7`→0; x264 with `subme=9`→0 (explains "works for H.264").

### Wheel repro (pre-fix, offscreen `QWheelEvent` send)
`preset_combo fast→balanced`, encoder first→second item, audio `copy→aac`,
slider `27→28/26` — one event each, no focus. Post-fix: unchanged.

### Race trace (pre-fix)
line 1152 connect → `addItem` #1 fires → `_on_encoder_changed('nvenc_h264')`
→ `self.encoder` = `nvenc_h264` → line 1156 `wanted != 'auto'` → no
recommendation. Post-fix: `win.encoder == nvenc_h265` + combo shows
`NVIDIA HEVC (NVENC)   ★ Best for your GPU`.

## TDD
`tests/test_defaults_hardening.py` written first → observed RED in order:
1. `default -x has no subme=9` (converter) → fix → GREEN
2. `preset … subme<=7` (4 presets) → fix → GREEN
3. `wheel ignored on QComboBox ('fast' -> 'balanced')` → fix → GREEN
4. `config 'auto' resolves to recommended (nvenc_h265)` → fix → GREEN
5. `saved audio default aac is restored at startup` → fix → GREEN
6. `WhatsThis for balanced states RF 27 (found 25)` → fix → GREEN

## Tests (`QT_QPA_PLATFORM=offscreen`)
| File | Checks |
|---|---|
| test_conversion_flags | 23 |
| **test_defaults_hardening (NEW)** | **21** |
| test_e2e_format | 6 |
| test_encoder_engine | 36 |
| test_format_radio | 14 |
| test_layout_dynamic | 5 |
| test_self_update | 16 |
| test_thread_lifecycle | 10 |
| test_tools_startup_smoke | 12 |
| test_tool_updater | 85 |
| test_tool_worker | 8 |
| **Total** | **236 green (11 files)** |

`py_compile` clean for `core/converter.py`, `ui/main_window.py`,
`tests/test_defaults_hardening.py`.

## Files changed
- `core/converter.py` — default `-x` `subme=9` → `7`
- `presets/default_presets.json` — 4× `"subme": 9` → `7` (x265 presets only)
- `ui/main_window.py` — QEvent import; `eventFilter` + install on left-panel
  combos/slider; encoder connect moved after `addItem`; audio encoder/bitrate
  from config + combo apply; preset WhatsThis RF numbers synced
- `tests/test_defaults_hardening.py` — new, 21 checks
- `CHANGELOG.md`, this file, `AGENTS.md`

## Open question
All presets ship `audio_encoder: "aac"` (deliberate?) — if presets should
preserve source audio too, change to `"copy"`; left as-is pending user input.
