# Agent Notes

## XDG Icon/Start Menu Integration Pattern
When a PyQt6 app on Linux has no taskbar/start menu icon:

**Root cause**: The icon file is usually too large (2048×2048, 5MB) and not installed to XDG paths.

**Fix** (see `utils/xdg_integration.py` and `ui/main_window.py:launch()`):
1. Create a module that on launch:
   - Copies `.desktop` file to `~/.local/share/applications/` with correct `Exec` path
   - Scales the icon (e.g. using Pillow or QPixmap) to standard sizes (256/128/64/48/32)
   - Installs scaled icons to `~/.local/share/icons/hicolor/{size}x{size}/apps/`
   - Runs `gtk-update-icon-cache` + `update-desktop-database`
2. In Qt app, register icon theme paths so `QIcon.fromTheme("appname")` resolves
3. In `.desktop` file: use `Icon=appname` + `StartupWMClass=appname`
4. In Qt: call `app.setDesktopFileName("appname")` and scale down the QPixmap when loading

## Per-Track Audio Override Pattern
When adding per-track audio encoder configuration:

1. **Data flow**: `_file_info_cache` stores `audio_streams` list (from `MediaInfo.audio_streams`) → `AudioTrackDialog` reads it → user configures per-track → `self.audio_track_overrides` dict stored on MainWindow → passed as `audio_track_overrides` to `ConversionSettings` → `_build_command` generates per-track `--audio 1,2,3 --aencoder 1:copy,2:aac` args.

2. **Key files**: `ui/main_window.py` (AudioTrackDialog class, `_open_audio_tracks_dialog`), `core/converter.py` (ConversionSettings.audio_track_overrides, _build_command switch logic).

3. **Override dict format**: `{track_index: {'encoder': 'aac', 'bitrate': 128}}` — empty dict means all tracks use the global `audio_encoder`/`audio_bitrate`.

4. **HandBrakeCLI syntax**: `--audio 1,2,3` selects tracks, per-track `--aencoder 1:copy,2:aac` and `--ab 1:128` specify per-track settings.

5. **Default behavior**: When `audio_track_overrides` is None/empty, falls back to `--all-audio --aencoder <global> --ab <global_bitrate>`.

## Programmatic ilst Builder Pattern (for MKV → MP4 metadata)
When a non-MP4 source (MKV) is transcoded to MP4, HandBrakeCLI drops most metadata (especially non-standard keys like DIRECTOR, WRITTEN_BY). The fix builds a full Apple `ilst` atom from ffprobe-extracted tags.

**Data flow**: `_copy_metadata()` → `probe_tags(source)` → `_extract_cover_art(source)` → `_build_ilst_from_tags(tags)` → `_add_cover_to_ilst()` → `_inject_ilst(dest_path, ilst)` → `_apply_faststart`.

**Key files**: `core/converter.py` (`_build_ilst_from_tags`, `_inject_ilst`, `_build_text_data`, `_build_int_data`, `_build_cover_data`, `_build_freeform_atom`, `_build_mean_name_atom`, `_build_4cc_item`, `_add_cover_to_ilst`, `_extract_cover_art`).

**Map logic** (`_build_ilst_from_tags` at `core/converter.py:428`):
1. Normalize key to lowercase, strip.
2. Map MKV aliases: `collection/title→show`, `season/part_number→season_number`, `episode/part_number→episode_id`, `episode/title→episode_number`, `summary→synopsis`, `date_released→date`, `date_release→date`, `season.part_num→season_number`, `episode.part_num→episode_id`.
3. If mapped key is in `_4CC` dict, emit a standard 4-byte atom (`©nam`, `©ART`, `tvsh`, `tvsn`, `tves`, `tven`, `ldes`, `©day`, `©gen`, etc.) with either text (flags=1) or integer (flags=0x15) `data` atom.
4. If unmapped, emit a `----` freeform atom with `mean=com.apple.iTunes`, `name=<ORIGINAL_KEY>`, `data=<value>` (UTF-8 text).
5. Integer tags: `tvsn` (season), `tves` (episode number). `tven` (episode title) is text.

**Cover art** (`_extract_cover_art` at `core/converter.py:525`): uses `ffprobe -show_streams` to find attachment with "cover"/"poster" in filename (or first JPEG/PNG attachment), then `ffmpeg -dump_attachment:t` to extract image bytes. Builds `covr` atom with `data` flags=0xD (JPEG) or 0xE (PNG), inserted at front of ilst via `_add_cover_to_ilst`.

**Injection** (`_inject_ilst` at `core/converter.py:487`): reads dest as bytearray, finds `moov→udta→meta→ilst` path (creating missing containers with `_build_hdlr()`), replaces/inserts ilst, updates parent atom sizes, writes back. Uses exact same insertion logic as `_binary_replace_ilst` but takes pre-built ilst instead of extracting from source.

**ffprobe key mapping** (ffmpeg 6.1.1 mov.c):
| Apple 4CC | ffprobe key | Type   |
|-----------|-------------|--------|
| `tvsn`    | `season_number` | int |
| `tves`    | `episode_sort` | int |
| `tven`    | `episode_id`   | text |
| `tvsh`    | `show`         | text |

**Test command**: `python3 -c "import py_compile; py_compile.compile('core/converter.py', doraise=True)"` — syntax check only. Real test: convert an MKV, probe output.

## Output Format Radio Wiring Pattern (v9.6.2 fix)
Bug: selecting MKV via the Format radio looked checked but output was still `.mp4`.
**Root cause**: only `mp4_radio` had a `.toggled` handler; `mkv_radio` had none, so `self.format` stayed the config default (`'mp4'`).

**The rule — every format radio MUST have its own `.toggled` handler** (`ui/main_window.py` around line 916-925):
- mp4_radio: `self.mp4_radio.toggled.connect(lambda c: self._set_format('mp4') if c else None)`
- mkv_radio: `self.mkv_radio.toggled.connect(lambda c: self._set_format('mkv') if c else None)`
- The `if c else None` guard makes it recursion-safe when `_set_format` re-checks the widget (`setChecked` on the already-checked widget does not re-emit, and the guard drops the false branch).

**Data flow**: `self.format` (`ui/main_window.py:323`, init from config) → `ConversionSettings(output_format=self.format)` (~line 1602) → `--format mp4|mkv` in `_build_command` → `_resolve_output` picks `.mp4`/`.mkv` extension.

**Menu path** (Settings → Format) calls `_set_format()` directly and always worked — which made the radio bug look intermittent.

**Test**: `/tmp/opencode/test_format_radio.py` reproduces both paths (radio + menu) and flips 10× to catch desync. Run with `QT_QPA_PLATFORM=offscreen`.

## Tool Auto-Updater Pattern (v9.7.0)
Keeps encoding tools at their official latest from inside the app.

**Data flow**: `MainWindow._check_tools_startup()` → `ToolUpdaterWorker` (QThread) → `ToolUpdater` (`utils/tool_updater.py`):
1. `ensure_bin_dir_on_path()` prepends `~/.local/share/vconv/tools/bin` to `PATH` at startup — so `shutil.which`/subprocess call sites automatically pick up the newest downloads.
2. Per tool `status()` → `_github_latest(repo)` (Guessed via GitHub releases `latest` API, cached per repo) → compare installed vs `latest_version`.
3. Auto-install (startup, only for **ffmpeg** + **nvencc**, user-scope/no root): `update(tool_id)` → download asset → `_extract_strip` (single top dir) / `dpkg-deb -x` → symlink binary → `BIN_DIR`; old version dirs cleaned.

**Key file**: `utils/tool_updater.py`; workers `ToolUpdaterWorker`/`ToolInstallWorker` + `ToolsDialog` in `ui/main_window.py`; Settings menu toggles `general/auto_update_tools` (default True) → `act_auto_tools`.

**Asset gotchas (tested in `tests/test_tool_updater.py`)**:
- BtbN ffmpeg builds: `ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz` (note the trailing `-8.1`); tag is `latest` → parse **asset name**, not tag. Exclude `-shared`/`-master` assets.
- NVEncC: `nvencc_9.38_amd64.deb`; version from tag.
- HandBrakeCLI prints `HandBrake 1.7.2` (regex must allow optional `CLI`); **no official Linux prebuilt tarball** → `update('handbrake')` tries Flatpak `fr.handbrake.HandBrakeCLI`, else reports latest and relies on apt.
- Distro versions like `6.1.1-3ubuntu5` parse fine via `updater.parse_version` (stops at first non-int suffix).
- Install dir: `~/.local/share/vconv/tools/{ffmpeg-8.1,nvencc-9.38}`; bin symlinks in `tools/bin/`.

## Encoder Capability Engine (v9.7.0)
`core/encoder.py` is a runtime-probed capability engine, not a hardcoded map.
- `probe_handbrake_encoders()` parses `HandBrakeCLI --help` encoder list (cached) → `HB_FAMILY_IDS[family] = (8bit_id, 10bit_id)` → `get_available_encoders()`.
- NVENC family ids map `nvenc_h265`→NVEncC `--codec h265`; `_nvidia_supports_av1()` gated to RTX 4-digit ≥4000 (Turing has no AV1).
- `get_recommended_encoder()` priority: GPU AV1 > GPU HEVC > NVEncC > x265; `get_badge()` returns `★ Best for your GPU` / `★ Best`.
- UI: encoder combo built from availability with badges; auto-selects recommended as initial default only when config encoder absent (`recommend, never force`).

## Output Container Verification
To confirm a converted file really is MP4 vs MKV:
- `ffprobe -v error -show_entries format=format_name -of default=noprint_wrappers=1:nokey=1 <file>` → prints `mp4` / `matroska,webm` (MKV shows `matroska`).

## Known Issues / Queue Design Flaws (REPORTED, NOT FIXED)
Verified during the v9.6.2 format-bug investigation. Do not fix unless explicitly asked:

1. **`_start_queue` ignores per-job settings** (`ui/main_window.py:~1816`): each queue job stores its own `job.settings` and `job.output_path`, but `_start_queue` discards them and re-derives everything from the *current* UI state at start time. So a job queued as MKV converts as MP4 if the user switches the radio before clicking Start. Fix idea: `_start_queue` should seed `ConversionSettings` from `job.settings` (per job) instead of one global settings object.
2. **Queue output-path display desync**: queue table's output path is computed via `generate_output_path` (in-place next to source) even when a custom output directory is set → the table shows a path different from where the file is actually written.
3. **`core/validator.py:146` `validate_batch`** hardcodes `.mp4` in output-extension logic — **dead code** (never called anywhere). Either wire it up or delete it.
4. **`utils/updater.py:94`** hardcoded `User-Agent: vconv-update-checker/9.2.2` — stale; should import `__version__` from `utils/version.py`.
5. **Docs staleness**: `docs/upgrade_audit.md` header says "Current version: v9.2.1" (historical audit snapshot — arguably fine); `docs/future_plan.md` release table is stale.
6. **Presets** (`presets/default_presets.json`) contain NO `format` key — presets cannot select output format. If a user expects a preset to set MP4/MKV, it won't.

## Version Management
- **Single source of truth**: `utils/version.py` (`__version__` and `VERSION`). `vconv.py`, `ui/main_window.py` (window title, status bar, About), and title/status use it via import.
- Docs that carry the version: `docs/user_guide.md` (header + footer), `docs/user_guide.ar.md` (header + footer), `README.md`, `CHANGELOG.md`, `vconv.desktop` (`Comment=`).
- Release steps are in `docs/release_process.md` — always produce `.deb`, `.AppImage`, + source; builds go to `dist/`.
