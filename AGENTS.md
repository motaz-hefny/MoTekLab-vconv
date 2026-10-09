# Agent Notes

## Single-Version Start Menu Pattern (installed-aware XDG)
When a `.deb`-installed copy and a dev checkout (or AppImage) coexist, the Start Menu launcher often pins the FIRST app that ran — not the installed one. Rule enforced at `utils/xdg_integration.py:ensure_xdg_integration`:

1. **Installed-aware detection**: if `/opt/vconv/vconv.py` exists (deb install), the launcher's `Exec` is ALWAYS `python3 /opt/vconv/vconv.py --gui` regardless of which instance called `ensure_xdg_integration`. `Comment=` is patched to the *installed* version read from `/opt/vconv/utils/version.py`.
2. **Deb layout differs from dev**: the deb has no `public/` dir and ships no `.desktop` template. Icon probe order for installed mode: `/opt/vconv/vconv-icon-256.png` → `/opt/vconv/public/…` → system `holicolor/256x256/apps/vconv.png`. Template falls back to the source tree that shipped the module (`Path(__file__).parent.parent / "vconv.desktop"`).
3. **Always theme-ize the icon**: rewrite `Icon=` to `Icon=vconv` (never an absolute deb path).
4. Call sites: `ui/main_window.py:~2425` `ensure_xdg_integration(Path(__file__).parent.parent)` (= `/opt/vconv` when installed).
5. Manual regeneration: `cp utils/xdg_integration.py /opt/vconv/utils/ && python3 -c "…ensure_xdg_integration(Path('/opt/vconv'))"`.

## In-place Self-Update Pattern (v9.7.2)
**Data flow**: Help → Check for Updates → `_show_update_dialog` → `🔄 Update & Restart` → `_start_auto_update` → `UpdateInstallWorker(QThread)` → `utils/self_update.py`:
`fetch_release_assets()` (GitHub releases/latest API) → `detect_install_mode()` (`$APPIMAGE`→appimage; `/opt/vconv/vconv.py` exists→deb; else dev) → `select_asset_for_mode()` (`*_all.deb` / `*.AppImage`) → `download_asset()` (urllib chunked, streamed to `<temp>.part`, progress callbacks) → install → `relaunch_app()` then `QTimer.singleShot(1500, quit)`.

**Install mechanisms**:
- **deb**: `pkexec dpkg -i <deb>` (polkit prompt). Without `pkexec` → clean failure message, falls back to opening the release page.
- **AppImage**: `os.rename(current→.old)` then `os.replace(downloaded→current)` (+chmod +x).
- **dev checkout**: dialog refuses auto-install, opens release page instead (never install over source).

**Rollout gotcha (10-08 test)**: an app version built BEFORE the self-update feature (i.e. v9.7.1 and older) runs the OLD update dialog — its button opens the release page in the browser, so the user experiences "click update → manual download". The auto-install button only exists in **v9.7.2+**. When a user reports that from the Start Menu app, check the INSTALLED version (`/opt/vconv/utils/version.py`); if < 9.7.2, the fix is to upgrade once (via the dev checkout's auto-update flow, or `pkexec dpkg -i`), after which the installed app permanently has the self-update feature.

**Key files**: `utils/self_update.py` (new), `ui/main_window.py` (`UpdateInstallWorker`, `_start_auto_update`, `_on_update_install_finished`, `QProgressDialog`). Mode detection uses the installed layout, NOT the process CWD — works even when `/opt/vconv` runs its own utils via `sys.path`.

**Test strategy** (`tests/test_self_update.py`, 16 checks): API call mocked (`mock.patch urlopen`), downloads via `file://` URIs, failure paths short-circuit (patched `pkexec`/`APPIMAGE`). Never touches network or `~/.config`.

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
- HandBrakeCLI prints `HandBrake 1.7.2` (regex must allow optional `CLI`); **HandBrake ships no prebuilt Linux CLI at all** (GitHub releases: Win/macOS binaries + source + a GUI-only `fr.handbrake.ghb` Flatpak; the app id `fr.handbrake.HandBrakeCLI` does NOT exist on Flathub; apt on Mint 22.2/noble = 1.7.2). `status_handbrake()` uses `_find_linux_cli_asset(assets)` — no Linux asset ⇒ `update_available=False` + an explanatory `note`; `_install_handbrake()` downloads/symlinks a Linux asset only if one ever appears, else returns an honest `error_cb` message (NEVER a flatpak attempt — a bare `flatpak install flathub …` is also ambiguous when flathub exists in both system and user installations).
- Distro versions like `6.1.1-3ubuntu5` parse fine via `updater.parse_version` (stops at first non-int suffix).
- Install dir: `~/.local/share/vconv/tools/{ffmpeg-8.1,nvencc-9.38}`; bin symlinks in `tools/bin/`.

**Fixes (10-08, verified live)**:
- **NVEncC binary is LOWERCASE `usr/bin/nvencc`** in the 9.38 deb — `_find_nvenc_binary()` scans case-insensitively (`nvencc`/`nvencc64`); the old case-sensitive `rglob("NVEncC")` made every manual update fail with "NVEncC binary not found in package" after a successful download.
- **NVEncC disclaimer**: `--version` prints `NVEnc (x64) 9.38 (r4176)` → parse with `_NVENC_VER_RE` = `NVEnc\s*\(x(?:64|86)\)\s*([^\s]+)`; the old `NVEncC <ver>` regex never matched, so a good install still showed an empty version and the dialog kept offering Update.
- **Concurrency guard**: `_reserve_install`/`_release_install` per tool — the startup auto-update and a manual dialog Update can no longer both write the same tool dir; the second attempt gets `error_cb` "already running (startup auto-update?)".
- **Real errors now surface**: `_download`/`_install_*`/`update()` pipe the reason through an `error_cb` arg into the dialog; `tool_updater` logs via a `vconv.*` child logger so messages reach `~/.config/vconv/logs/vconv.log`. `ui/main_window.py` MUST keep its module logger `logger = get_logger("ui.main_window")` — before it existed, the `UpdateInstallWorker` except-path raised `NameError` inside the worker.
- **HandBrake Update was always doomed (v9.7.4)**: the dialog offered `update('handbrake')` (1.7.2 → 1.11.2) although no Linux HandBrakeCLI build exists upstream — the install tried `flatpak install -y flathub fr.handbrake.HandBrakeCLI`, which failed twice over (app id not on Flathub; flathub configured in both system+user ⇒ "No remote chosen to resolve 'flathub'"). Fixed by gating `update_available` on `_find_linux_cli_asset()` + replacing the flatpak path with an honest message. Dead `FLATPAK_CLI_HELPER` constant removed from `core/handbrake_manager.py`. (The separate apt path `_ensure_handbrake_cli` → `HandBrakeManager.check_for_update()` was always honest — apt candidate == installed ⇒ no update.)

## QThread Lifetime Rule (v9.7.5 crash fix)
Never drop the last Python reference to a still-running `QThread`: Python destroys the C++ object, Qt calls `qFatal("QThread: Destroyed while thread is still running")` and **aborts the whole app** (real coredump 2026-10-08 11:41:08, SIGABRT — clicking Refresh in Tools & Encoders; `_refresh_done` did `self._refresh_worker = None` while the thread was still inside `run()`; `qFatal` never reaches `~/.config/vconv/logs/vconv.log`).

Rule enforced in `ui/main_window.py`:
- Module helpers `_park(worker)` / `_ZOMBIE_THREADS` / `_retire_parked(worker)`: hand the registry the reference; it joins on `finished` and only then releases. `_park(None)` is a no-op; joining an already-finished thread returns instantly.
- **Any clear/overwrite of a worker attribute must `wait()` or `_park()` first**: `ToolsDialog._refresh_done` (local ref → attr `= None` → `wait()`), `ToolsDialog.done(int)` override (parks refresh + install workers on every close path — Accept/Reject/Esc/X all funnel through `done()`; non-blocking), `_retire_install_worker` (`wait()` then `discard`, idempotent), reassignments of `self.worker` / `self._update_worker` / `self._update_install_worker` (park old first; all four initialized to `None` in `__init__`), and `MainWindow._shutdown_workers()` from `closeEvent` (`wait(5000)` per owned worker, park on timeout).
- Signals emitted from inside `run()`/finally (`ToolUpdaterWorker.done`) or Qt's `QThread.finished` mean "thread is *about* to exit" — only `wait()` proves it exited.
- Residual edge (accepted): a worker still running after the 5 s shutdown wait is parked; if it outlives interpreter teardown the exit can still abort — bounded in practice (startup checks finish in seconds).
- Tests: `tests/test_thread_lifecycle.py` (pre-fix: deterministic core dump with the exact Qt message; post-fix: 10 checks) and `tests/test_tools_startup_smoke.py` (`_shutdown_workers`, 12 checks). Full suite 210 checks at v9.7.5 (215 after dynamic-layout, **246 after defaults hardening incl. preset-audio**, 2026-10-08). Run: `QT_QPA_PLATFORM=offscreen python3 tests/<file>.py`.

## Settings Defaults Hardening Rules (unreleased, 2026-10-08 acceptance bugs)
Five rules that came out of the "defaults changed to AAC / RF 24 / AV1→x265 / exit 3" reports. Enforced in `ui/main_window.py`, `core/converter.py`, `presets/default_presets.json`; tested by `tests/test_defaults_hardening.py` (31 checks).

1. **Wheel-guard (never remove)**: Qt delivers wheel events to the widget *under the cursor* regardless of focus — scrolling the settings panel silently ticked combos/slider (encoder AV1→x265, audio copy→aac, RF 27→24). `MainWindow.eventFilter` swallows `QEvent.Type.Wheel` on every `QComboBox`/`QSlider`, and `_create_left_panel` installs it on **all** such children just before `return panel` — a new settings combo/slider added under that panel is guarded automatically; one added elsewhere must `installEventFilter(self)` explicitly. Click/keyboard still work.
2. **Connect AFTER `addItem`**: connecting `currentTextChanged` before the item loop lets the first `addItem` fire the signal and clobber the config value (`'auto'` → first encoder) before startup logic reads it — this killed the recommended-encoder auto-select. Pattern: populate → connect → apply config/wanted value.
3. **x265 sub-options must be in x265's range**: `subme` valid 0–7 for x265 (x264 allows 9). Default `-x` string in `_build_command` and any preset `advanced` entry with `subme > 7` makes HandBrakeCLI abort with **exit 3** before encoding. When adding x265/x264 tuning keys, verify against the encoder's own range, not x264's.
4. **Config defaults are applied at init, symmetrically**: `self.quality`/`self.encoder`/`self.audio_encoder`/`self.audio_bitrate` all read `defaults.*` from config, and the corresponding widget is set to that value after its signals are connected (audio: `audio_enc_combo.setCurrentText` + explicit `_on_audio_encoder_changed` call). Never hardcode a startup value; the combo is the UI mirror of `self.*`.
5. **Presets preserve source audio**: every entry in `presets/default_presets.json` must keep `audio_encoder: "copy"` (decision 2026-10-08 — applying a preset must not silently re-encode to AAC; RF/encoder preset changes only). Guarded by `test_presets_preserve_source_audio`.

## Responsive Window Sizing (v9.7.2)
The 1250×800 default / 1100×700 minimum were too big for small laptops (up to ~1366×768, 1024×600). Rule in `ui/main_window.py`:
- `_screen_window_bounds(avail_w, avail_h)` returns `(min, default)` shrunk to fit: floor min (760,520); default never below min. Design sizes kept on big screens.
- `_apply_screen_sizing()` sets only `setMinimumSize` (must NOT `resize()` — `_load_window_geometry` later restores saved geometry, clamped to screen + never restored off-screen).
- `launch()` bumps the base font +1pt only when screen ≥1920×1080 (guarded on `pointSize() > 0`).
- Pure helper keeps UI sizing unit-testable offscreen (no `QApplication` needed).
- **Settings panel = tabs inside a `QScrollArea`** (`_create_central_widget`, `self.settings_scroll`): the panel's `self.settings_tabs` is a `QTabWidget` with **Video | Audio | Subtitles** pages (Video: Preset→Encoder→Crop→Quality→Output→Format, metadata checkbox inside Output). Never remove the scroll area — the Video page is taller than small windows. `self.settings_tabs` and `self.sub_group` are exposed for `tests/test_layout_dynamic.py` (the no-squash test switches to the Subtitles tab before measuring).
- **Activity Log has no height cap**: `log_group` sits in `self.log_splitter` (vertical, `setChildrenCollapsible(False)`, default ≈200 px, stretch only to the upper sections). Do not re-add `setMaximumHeight` on `self.log_text`.

## Dynamic Settings Width Pattern (H/F/M)
The left settings panel hugs the active tab instead of sitting at fixed 300 px (spec `docs/superpowers/specs/2026-10-08-dynamic-settings-width-design.md`; tests `tests/test_settings_width_dynamic.py`). Three values, recomputed per event, never cached, never persisted:
- **H** = `settings_tabs.sizeHint().width()` (hug target) · **F** = `settings_tabs.minimumSizeHint().width()` (drag floor, installed via `settings_scroll.setMinimumWidth(F)`) · **W** = `splitter.sizes()[0]` · **M** = `self._manual_width` (session-only).
- Pure helper `MainWindow._left_width_action(current, hug, floor, manual)` returns the new width or `None` — ALL event logic lives there (truth table unit-tested; same pattern as `_screen_window_bounds`). Never branch on width outside it.
- **`settings_tabs` MUST be a `_HugTabWidget` (module-level subclass), not a plain `QTabWidget`.** Qt 6.11's `QTabWidget.sizeHint()` AND `minimumSizeHint()` expand over ALL tab pages (`qtabwidget.cpp`), so a plain widget can never hug the active tab. `_HugTabWidget` overrides both to hug the current page (recomputing Qt's padding, tab-bar floor preserved, `currentChanged → updateGeometry`). Measured offscreen: Video H/F 239/239, Audio 190/172, Subtitles 284/237.
- Wiring in `_create_central_widget`: `settings_tabs.currentChanged` → `_apply_width()`; `splitter.splitterMoved` → `M=True` guarded by `_width_applying` (programmatic hugs must never mark manual); startup `QTimer.singleShot(0, _apply_initial_width)`. Floor is clamped to `splitter width − right-panel minimum` in `_current_width_params`.
- Reflow keeps F small: every settings-panel `QComboBox` is `Ignored` horizontally (loop right BEFORE the wheel-guard loop in `_create_left_panel` — wheel-guard stays last); `ext_opts_layout` must stay its own row in `sub_layout` (never re-nested in `ext_btn_layout`); long non-wrappable copy (radios/checkboxes) goes: short visible text + full text in tooltip.
- Window resize keeps stretch 0/1; width/M are session-only (no config keys).

## Encoder Capability Engine (v9.7.0)
`core/encoder.py` is a runtime-probed capability engine, not a hardcoded map.
- `probe_handbrake_encoders()` parses `HandBrakeCLI --help` encoder list (cached) → `HB_FAMILY_IDS[family] = (8bit_id, 10bit_id)` → `get_available_encoders()`.
- NVENC family ids map `nvenc_h265`→NVEncC `--codec h265`; `_nvidia_supports_av1()` gated to RTX 4-digit ≥4000 (Turing has no AV1).
- `get_recommended_encoder()` priority: GPU AV1 > GPU HEVC > NVEncC > x265; `get_badge()` returns `★ Best for your GPU` / `★ Best`.
- UI: encoder combo built from availability with badges; auto-selects recommended as initial default only when config encoder absent (`recommend, never force`).

## MediaAnalyzer Cover-Art Stream Rule (2026-10-08 AV1 black-screen fix)
`core/analyzer.py:_parse_probe_data` parses ffprobe JSON for the bit-depth probe (`_probe_source_bit_depth` → `_effective_bit_depth` → `svt_av1` vs `svt_av1_10bit`), the UI file-info sites (`ui/main_window.py:~793/1759/1978`) and the CLI `--analyze`. Rule (regression-tested by `tests/test_analyzer_attached_pic.py`, 16 checks):

1. **Cover art is a fake video stream**: embedded covers arrive as `codec_type=video` with `disposition.attached_pic=1` (e.g. `mjpeg 2000x3000 filename=cover.jpg`). Always skip `attached_pic` and `timed_thumbnails` streams.
2. **First real video stream wins** (`if info.video_codec: continue`). Never `break` the outer loop — audio/subtitle streams are collected *after* the video stream in ffprobe order.
3. **Why it matters (bug chain)**: the old last-video-wins loop made a 10-bit `yuv420p10le` source probe as `bit_depth=8` → HandBrake got `svt_av1` (8-bit) → VLC 3.0.20 + NVIDIA VDPAU renders **8-bit AV1 black with zero log errors** (ffmpeg says the file is fine; `--avcodec-hw=none` plays it). 10-bit AV1 makes VDPAU reject/fall back to software `dav1d` → plays. Detection test: local copies of a file may lack the cover stream (ffmpeg `-c copy` drops it) — always probe the ORIGINAL file.
4. **VLC/VDPau workaround (report-only, environment bug)**: VLC → Video → Hardware-accelerated decoding → off; vconv's fix is to output 10-bit as promised.

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
