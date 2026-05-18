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
