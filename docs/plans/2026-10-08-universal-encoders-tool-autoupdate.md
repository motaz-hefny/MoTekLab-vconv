# Plan: Universal Encoders + In-App Tool Auto-Download/Updater (v9.7.0)

> Status: **COMPLETE — v9.7.0 published 2026-10-08.** Release: https://github.com/motaz-hefny/MoTekLab-vconv/releases/tag/v9.7.0 (`.deb` + `.AppImage` uploaded; in-app updater verified reporting 9.7.0). Notes: the old remote PAT was dead (stale `https://ghp_…@` URL) — remote URL cleaned to `https://github.com/motaz-hefny/MoTekLab-vconv.git`, pushes now need a live credential (e.g. `gh auth setup-git` or a fresh PAT).

## Goal (from user directives)

1. **All encoding methods available** — CPU (x264/x265/SVT-AV1 + 10-bit) and GPU (NVENC H.264/HEVC + 10-bit, GPU AV1 where hardware supports it, QSV/AMF where present, plus **rigaya NVEncC**) — chosen dynamically by each user's hardware.
2. **Every tool auto-downloadable and updatable from within the app**, simply.
3. **Recommend the best encoding method** for detected hardware — **but never force it**. Show a **"Best" mark/badge** on each encoder entry depending on hardware.
4. **Preserve source quality**: keep **bit depth** (10-bit) and **resolution** (stop HandBrake auto-crop over-cropping) — fixes the "bigger file, lower quality" issue.
5. Tool updater manages **HandBrake + ffmpeg + NVEnc** (always latest).
6. **Version**: published = **v9.6.1**; staged local = 9.6.2. Bump to **v9.7.0** (new features) → commit → build → release.

---

## Current-state findings (file:line)

| Area | Location | Problem |
|---|---|---|
| AV1 hidden on NVIDIA | `core/encoder.py:95` `_detect_nvidia()` returns `["nvenc_h265","nvenc_h264","x264","x265"]` | no AV1 → SVT-AV1 not in dropdown on user's box |
| AV1 invalid id | `core/encoder.py` `HB_ENCODER_MAP['libsvtav1'] = 'libsvtav1'` | HandBrake rejects → `ERROR: Invalid video encoder (libsvtav1)` (verified) |
| AV1 real id | `HandBrakeCLI --help` | supports **`svt_av1`**, **`svt_av1_10bit`** (CPU only) |
| No 10-bit encoders | `ui/main_window.py:357` `_build_encoder_map`, `:1594` | only 8-bit encoders exposed → 10-bit source down-converted |
| No bit-depth detection | `core/analyzer.py:19` `MediaInfo` | no `pix_fmt`/`bit_depth` field |
| Over-crop / "downscale" | `core/converter.py` `_build_command` | emits **no** crop flags → HandBrake `autocrop=60/60` → 1080→**960**; ffmpeg sees ~4px bars → ~56px/edge of real picture lost |
| Size/quality | measured | 10-bit AV1 @1215 kb/s → 8-bit x264 @2319 kb/s (~2×) + lost height |
| Tool update via apt only | `core/handbrake_manager.py`, `ui/main_window.py:1862/1909` | apt HandBrake = **1.7.2**, official latest = **1.11.2** → can never reach latest |
| NVEnc not integrated | — | rigaya NVEncC not detected/used |
| GPU limit | RTX 2060 SUPER (Turing) | **no NVENC AV1** (needs RTX 40+/Ada) → AV1 here = CPU `svt_av1` |

---

## Design

### 1. Encoder capability engine — `core/encoder.py`

- Fix `HB_ENCODER_MAP` ids: `svt_av1`, `svt_av1_10bit`, `x264_10bit`, `x265_10bit`, `nvenc_h265_10bit`, `nvenc_av1`.
- Expand `ENCODER_INFO` (+ `bit_depth` support flag, `gpu: bool`).
- `HardwareDetector`:
  - **NVIDIA**: detect GPU model → parse series → `nvenc_av1_supported` (Ada/RTX40+ only). `encoders_available` = CPU set + NVENC set (+ GPU AV1 if capable). CPU `svt_av1` always included (CPU fallback).
  - QSV/AMD branches likewise include their AV1/10-bit capabilities where supported.
  - CPU-only branch keeps x264/x265/svt_av1.
- **NVEncC integration**: if `NVEncC`/`NVEncC64` detected → add `nvencc_h264`, `nvencc_hevc`, `nvencc_av1` (AV1 gated by GPU capability probe via `NVEncC --capabilities`).
- New API:
  - `available_encoders()` → all supported for this machine
  - `best_for_hardware()` → recommended id (prefer GPU; GPU-AV1 if capable else NVENC HEVC; else CPU svt_av1/x265)
  - `supports_10bit(encoder)`, `is_hardware_encoder()` updated

### 2. Recommendation + "Best" badge — `ui/main_window.py`

- `_build_encoder_map()` built from capability engine (also fix `:1594` list).
- Label format in dropdown: `★ {name} — Best for your GPU` / ` (GPU)` / ` (CPU)` / ` (10-bit)`.
  - **★ Best** badge placed on `best_for_hardware()` result (and GPU marks on HW encoders).
- **Recommend, don't force**: auto-select best only as the **initial default** (config `defaults/encoder`); user can change freely and choice persists.
- Crop group: **Auto / Preserve full frame / Custom** — **default = full frame** (stops 1080→960).
- **Preserve source bit depth** checkbox (default ON) → picks matching `*_10bit` encoder.
- SVT-AV1 **preset** selector (0–12) → `--encoder-preset`.
- Wire into `ConversionSettings(...)` at `ui/main_window.py:1597`.

### 3. Bit-depth preservation — `core/analyzer.py`, `core/converter.py`

- `MediaInfo += pix_fmt, bit_depth` (parse `yuv420p10le` → 10).
- `ConversionSettings += preserve_bit_depth, crop_mode, crop_custom, encoder_preset`.
- `_build_command`:
  - emit `--crop-mode none` (full) or `--crop t:b:l:r` (custom), default full.
  - if `preserve_bit_depth` and source is 10-bit → use `*_10bit` variant of chosen codec.
  - emit `--encoder-preset N` for SVT-AV1.

### 4. Tool auto-updater — new `utils/tool_updater.py` + integration

Registry (id, display, github repo, asset regex, installed-version detect, install method):

| Tool | Source | Asset / method | Installed detect |
|---|---|---|---|
| HandBrake | `HandBrake/HandBrake` (latest **1.11.2**) | **no official Linux prebuilt** → prefer flatpak `fr.handbrake.HandBrakeCLI` (verify), else apt fallback; expose latest info | `HandBrakeCLI --version` |
| ffmpeg | `BtbN/FFmpeg-Builds` | `ffmpeg-n*-latest-linux64-gpl.tar.xz` → extract to `~/.local/share/vconv/tools/ffmpeg/` + PATH shim | `ffmpeg -version` |
| NVEnc | `rigaya/NVEnc` (latest **9.38**) | `nvencc_*_amd64.deb` (pkexec dpkg) or extract `NVEncC64` to tools dir | `NVEncC --version` |

- `ToolUpdateWorker(QThread)` on startup: check all, compare, optionally **auto-download** (config `general/auto_update_tools`, default ON) — non-blocking (mirror `UpdateCheckWorker` pattern, `ui/main_window.py:1976`).
- **Settings → Tools panel**: per tool — current version, status, **Update/Install** button, "always auto-update" toggle (simple/easy UX).
- Reuse GitHub API style from `utils/updater.py:16`.
- Rewire `_ensure_handbrake_cli` (`:1862`) and `_ensure_ffmpeg` (`:1909`) to route through tool manager; keep prompts as fallback.

---

## Implementation order

1. **Version bump** → **9.7.0**: `utils/version.py`, `docs/user_guide.md` + `.ar` (header/footer), `README.md`, `vconv.desktop`, `CHANGELOG.md` (9.7.0 entry).
2. `core/encoder.py` — capability engine, id fixes, best/badge API, NVEncC detection.
3. `core/analyzer.py` — `pix_fmt`/`bit_depth`.
4. `core/converter.py` — new `ConversionSettings` fields + `_build_command` crop/10-bit/preset flags.
5. `ui/main_window.py` — encoder dropdown badges, best auto-select, crop group, bit-depth checkbox, SVT-AV1 preset, wire settings.
6. `utils/tool_updater.py` + `ToolUpdateWorker` + Settings Tools panel; rewire `_ensure_*`.
7. **Tests** (`tests/`): encoder mapping/best/badges, crop args, 10-bit args, tool_updater asset parsing (mock HTTP); keep `test_format_radio.py` + `test_e2e_format.py` green. **Done**: `tests/test_tool_updater.py` (24), `tests/test_tools_startup_smoke.py` (10), `tests/test_encoder_engine.py` (36), `tests/test_conversion_flags.py` (23) — all green; existing suites still 6/6 + 14/14; total **113 checks**. Test files use hermetic temp config (no user-state pollution).
8. **Docs**: `docs/user_guide.md` + `.ar` (AV1, 10-bit, crop, tool updater), `AGENTS.md` patterns, `CHANGELOG.md`, `docs/test-results/` entry — **done**.
9. **Build** → `dist/vconv_9.7.0_all.deb` + `dist/vconv-9.7.0-x86_64.AppImage` — **pending**.

## Testing plan

- Unit: encoder map, recommendation, badge selection, crop/bit-depth command flags.
- Real short encode: AV1 (CPU) + HEVC (GPU) → assert **1920×1080 kept** and **10-bit out** (`pix_fmt`).
- GUI offscreen: ★ Best present & auto-selected; changing selection persists; crop default = full frame.
- Tool updater: mock JSON/assets; real network check optional/manual.
- Regression: existing format + e2e tests must pass.

## Release plan (v9.7.0)

- Bump → tests pass → results recorded in `docs/test-results/` → docs current. **Done** (`docs/test-results/2026-10-08-v970-encoders-tools.md`).
- Tool updater nuisances found during impl: BtbN ffmpeg assets carry a `-<ver>` suffix (`ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz`), HandBrakeCLI prints its version as `HandBrake 1.7.2` (no `CLI` token), apt ffmpeg `6.1.1-3ubuntu5` needs distro-suffix-safe parsing — all covered in `tests/test_tool_updater.py`.
- `git commit -m "v9.7.0: universal encoders, 10-bit/crop preservation, in-app tool updater"` — **done** (`efd7f1d`).
- `git tag v9.7.0` → `git push origin main --tags` — **done**.
- Build both artifacts → create GitHub release **v9.7.0** → upload `.deb` + `.AppImage`. — **done**.
- Verify in-app auto-update (`utils/updater.py` reads latest release) reports 9.7.0. — **done** (`available=False@latest=9.7.0`).

## Risks / notes

- **HandBrake Linux latest**: no official prebuilt tarball (only Win/mac/flatpak/source). Plan uses flatpak if available else apt; document the limitation honestly.
- **NVEncC AV1**: gated by GPU — on Turing it will be marked unavailable (correct behavior).
- **Scope is large** → land in ordered commits; full test suite before any release.
