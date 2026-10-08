# Test Results — AV1 black-screen bug (cover-art stream broke bit-depth probe)

- **Date**: 2026-10-08
- **Report**: "AV1 conversion plays audio but the video is a black screen" (VLC 3.0.20, source `Coven Academy - S01E01` on CIFS `//192.168.1.2/raid`)
- **Suite command**:
  ```bash
  for t in tests/test_*.py; do QT_QPA_PLATFORM=offscreen python3 "$t" || exit 1; done
  ```

## Root cause chain (systematic-debugging Phase 1)

1. **App bug — `core/analyzer.py` `_parse_probe_data`**: the source MKV carries an embedded
   cover as a real stream (`index=3 mjpeg 2000x3000 disposition.attached_pic=1 filename=cover.jpg`).
   The video loop took the **last** `codec_type=='video'` stream with no `attached_pic` filter,
   so the cover's fields overwrote the AV1 track: `bit_depth=8`, `video_codec=MJPEG`.
   → `_effective_bit_depth` fell back to 8 → HandBrake got `--encoder svt_av1` (8-bit)
   instead of `svt_av1_10bit`, despite the source being `yuv420p10le` (10-bit) and the
   "Preserve source bit depth" checkbox defaulting to ON.
2. **Environment bug (VLC/NVIDIA, not vconv)**: VLC 3.0.20 + NVIDIA VDPAU (driver 595.91.07)
   renders **8-bit AV1 black** with zero log errors; 10-bit AV1 is rejected by VDPAU and
   falls back to the software dav1d decoder, which plays fine.

## Evidence

| Step | Result |
|------|--------|
| ffprobe on CIFS vs local clip | identical: `av1 / Main / yuv420p10le` (probe itself is healthy) |
| `MediaAnalyzer().analyze(CIFS)` **before fix** | `codec=MJPEG pix_fmt=yuvj422p bit_depth=8 2000x3000` |
| `analyze()` on local clip (no cover stream) | `bit_depth=10` — why existing tests never caught it |
| ffmpeg decode of app-produced 8-bit file | 0 errors, YAVG matches source exactly → bitstream valid |
| VLC hw decode (`vout` on `:0`, default settings) | window center luma **0.0** = pure black (truth frame: 43.9) |
| VLC `--avcodec-hw=none` control, same file | center luma **39.0** = correct video |
| VLC log (both runs) | no decode errors — only a benign "buffer deadlock prevented" |
| VLC hw on **10-bit** output | renders: 15/15 frames, luma 17.7–39.3, decoder `dav1d` (software fallback) |

## Fix

`core/analyzer.py` — in `_parse_probe_data`, video branch:

- skip streams with `disposition.attached_pic` or `timed_thumbnails` (cover art/thumbnails),
- parse only the first real video stream (`if info.video_codec: continue`),
- **never `break` the outer loop** — audio/subtitle streams are collected after the video stream.

## Verification

- **New**: `tests/test_analyzer_attached_pic.py` — **16 checks** (fixture-based, mocked
  `subprocess.run`): cover ignored, no-cover regression, cover-only file, and end-to-end
  `_effective_bit_depth` + `_build_command` → `svt_av1_10bit`.
- **Live (real CIFS source)**: `analyze()` → `AV1 / yuv420p10le / depth=10`;
  `_build_command` → `--encoder svt_av1_10bit`.
- **Full pipeline artifact** (`svt_av1_10bit` encode + `_copy_metadata`): stream stays
  `yuv420p10le`, 0 decode errors, 70 tags preserved; VLC hw decode renders 15/15 frames
  (luma 17.7–39.3, same as source).
- **Full suite**: **284 checks, ALL PASS, 12 files** (was 268/11).

| File | Checks | Result |
|------|--------|--------|
| test_analyzer_attached_pic.py | **16** (new) | PASS |
| test_conversion_flags.py | 23 | PASS |
| test_defaults_hardening.py | 42 | PASS |
| test_e2e_format.py | 6 | PASS |
| test_encoder_engine.py | 36 | PASS |
| test_format_radio.py | 14 | PASS |
| test_layout_dynamic.py | 16 | PASS |
| test_self_update.py | 16 | PASS |
| test_thread_lifecycle.py | 10 | PASS |
| test_tools_startup_smoke.py | 12 | PASS |
| test_tool_updater.py | 85 | PASS |
| test_tool_worker.py | 8 | PASS |
| **Total** | **284** | **ALL PASS** |

## Notes / not fixed here (report-only)

- VLC+VDPAU's 8-bit AV1 black screen is a VLC/NVIDIA issue, not vconv's — workaround:
  VLC → Tools → Preferences → Video → Hardware-accelerated decoding → off
  (`--avcodec-hw=none`), or keep bit-depth preservation on (outputs 10-bit, plays).
- The `-x` advanced string, metadata path and HandBrake pipeline were all exonerated
  (ffmpeg: zero decode errors; luma identical to source at every second).
- Reproduction artifacts (deleted after the session): `/tmp/opencode/av1bug/`.

## Revert recipe

- `git revert` the analyzer fix + this doc + CHANGELOG/AGENTS entries; the test file
  reverts with them (it fails against the pre-fix analyzer by design).
