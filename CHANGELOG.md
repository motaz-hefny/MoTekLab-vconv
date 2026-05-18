# Changelog

All notable changes to the vconv project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [9.6.1] - 2026-05-18

### Added
- **Full metadata preservation for non-MP4 sources (MKV → MP4)**: When the source is not MP4 (e.g. MKV), metadata is now preserved via a programmatic ilst builder. Tags are extracted with ffprobe, mapped to Apple iTunes 4-byte codes (©nam, ©ART, tvsh, tvsn, tves, tven, etc.), and injected as a binary `ilst` atom directly into the output. Non-standard tags are stored as `----` freeform atoms with `com.apple.iTunes` mean.
- **Cover art preservation (covr atom)**: Cover art embedded in MKV sources (as attachments, attached_pic disposition, or MJPEG/PNG video streams with cover/poster filenames) is extracted via ffmpeg and injected into the MP4 `ilst` atom as a `covr` data atom (JPEG/PNG with proper type flags).
- **MKV tag alias mapping**: Dot-notation and slash-notation MKV tag names (`EPISODE.PART_NUM`, `SEASON.PART_NUM`, `EPISODE/PART_NUMBER`, `SEASON/PART_NUMBER`, `COLLECTION/TITLE`, `DATE_RELEASE`) are mapped to standard Apple codes for proper display in media players (VLC, MetaX).
- **Metadata preserve/restore toggle**: New checkbox in the left panel — "Preserve metadata from source". When enabled (default), metadata is preserved after encoding. When disabled, encoding completes faster without post-processing.
- **Binary ilst replacement for MP4 sources**: When source and output are both MP4, the `ilst` atom is copied byte-for-byte from source to output, preserving ALL metadata including custom `----` atoms (iTunEXTC, iTunMOVI), cover art, and Apple 4-byte tags.
- **Pure-Python faststart (moov atom relocation)**: Implements `_apply_faststart` that moves the `moov` atom to the front of the file via binary manipulation. Preserves all atom content byte-for-byte (unlike ffmpeg which re-parses and drops non-standard metadata atoms). Updates `stco`/`co64` chunk offsets for valid playback.
- **GVFS/SMB support**: Full metadata preservation pipeline works on network mounts (GVFS/SMB) by caching source to local temp directory before processing.

### Changed
- **Metadata pipeline**: Complete rework — now 4 strategies in order: (1) Binary ilst replacement (local MP4), (2) Built ilst from tags (non-MP4), (3) ffmpeg map_metadata fallback, (4) Explicit ffprobe-then-ffmpeg fallback.
- **Version**: 9.6.0 → 9.6.1

### Fixed
- **Metadata dropped on MKV → MP4 conversion**: HandBrakeCLI drops almost all metadata when transcoding non-MP4 to MP4 (especially custom tags like DIRECTOR, WRITTEN_BY). Now preserved via programmatic ilst builder with both standard and freeform atoms.
- **Cover art lost on MKV → MP4**: Cover artwork (poster) was dropped during transcoding. Now extracted and re-injected as `covr` atom.
- **Date_Released/Date_Release tags not appearing**: MKV alias mapping now maps `date_release` and `date_released` to Apple `©day`.
- **Dot-notation tag names not recognized**: Added `season.part_num`, `episode.part_num`, `episode.part_num` to the MKV alias mapping.

---

## [9.5.8] - 2026-05-17

### Added
- **Metadata preservation via ffmpeg**: After HandBrakeCLI finishes encoding, `ffmpeg` is used to copy all metadata tags (title, date, genre, comments, etc.) from the source file to the encoded output. Uses stream copy (no re-encode) and `-movflags +faststart` for web-optimized MP4. Works on any HandBrakeCLI version (the `--preserve-metadata` flag requires ≥1.8.0, but the user has 1.7.2). Falls back silently if ffmpeg is unavailable.

---

## [9.5.7] - 2026-05-17

### Fixed
- **`--encoder auto` passed to HandBrakeCLI**: Encoder combo's `currentTextChanged` signal was connected AFTER items were added, so the initial selection never fired the handler. `self.encoder` stayed at the config default `'auto'` (invalid encoder). Moved signal connection before `addItem()` calls. Also added a safety fallback in `_start_conversion` that resolves `'auto'` to the recommended encoder.

---

## [9.5.6] - 2026-05-17

### Fixed
- **HandBrakeCLI exits instantly with no output**: Removed `--preserve-metadata` flag which is only supported on HandBrakeCLI ≥1.8.0. Older versions (Ubuntu/Fedora repos) silently fail when this flag is passed. Removed `--verbose 1` (space-separated arg format may confuse older getopt parsers). Matches the working command structure from v9.2.2.
- **Left panel still not resizable**: Removed "✅" and "(Recommended)" text from encoder combo items (drove `minimumSizeHint()` to ~300px). Badge moved to the hardware label below the combo. Set left panel to `Ignored` horizontal size policy so `QSplitter` is free to resize.
- **Encoder combo `"Recommended"` reference removed**: `_start_conversion` no longer checks for "(Recommended)" text in the combo (text no longer contains it).
- **`--all-audio` + `--audio` conflict**: Fixed flag ordering — per-track audio overrides now use `--audio` WITHOUT `--all-audio`. When no overrides, `--all-audio` is used alone.

---

## [9.5.5] - 2026-05-17

### Added
- **Per-track audio configuration**: New "Tracks..." button in the Audio section opens a dialog showing all audio streams from the first file. Each track can be assigned its own encoder (or left as global default). Overrides are applied per-track via `--audio` + per-track `--aencoder`/`--ab` in the HandBrakeCLI command.
- **All audio streams stored in cache**: File analysis now stores every audio track's index, codec, channels, language, and title instead of only the first track.
- **Verbose HandBrakeCLI logging**: Added `--verbose=1` to the HandBrakeCLI command and output capture on success (not just on failure) for better debugging.
- **Output file verification**: Post-conversion check confirms the output file exists and has non-zero size. Missing/empty files are reported as failures.

### Fixed
- **Left panel minimum width**: Removed the setMinimumWidth(400) constraint and added `QSplitter.setChildrenCollapsible(True)` + `Ignored` size policy on the encoder combo so the left panel can be freely resized via the splitter handle.
- **Subtitle default changed to "all"**: The embedded subtitle mode now defaults to `all` (keep every subtitle track from source) instead of `copy` (filter by language list).
- **GVFS/SMB write warning**: Logs a warning when output path is on a GVFS/FUSE mount, suggesting a local output directory.

### Changed
- **Audio encoder command**: When per-track overrides are set, `_build_command` generates `--audio 1,2,3 --aencoder 1:copy,2:aac` instead of `--all-audio --aencoder copy`.

---

## [9.5.4] - 2026-05-17

### Added
- **All audio tracks preserved**: Added `--all-audio` to HandBrakeCLI command so multi-audio files (e.g. English 5.1 + Arabic 2.0 + commentary) keep every track instead of only the first.
- **Output file verification**: After a "successful" conversion, the app now checks that the output file was actually created and has non-zero size. If the file is missing or empty, the conversion is marked as failed with a clear error message.
- **GVFS/SMB write warning**: When the output path is on a GVFS/FUSE mount (e.g. network share via `smb-share:`), a warning is logged suggesting a local output directory.

### Fixed
- **Output path collision**: When input format matches output format (e.g. `.mp4` → `mp4`) and "Same as source" is selected, the generated output path previously overlapped with the input file. The rename logic now explicitly avoids colliding with the input.
- **Left panel minimum width**: Removed `setMinimumWidth(400)` that prevented the file list panel from being resized smaller via the splitter.

---

## [9.5.2] - 2026-05-17

### Fixed
- **External subtitle paths with commas crash encoding**: GVFS/SMB paths (e.g. `smb-share:server=192.168.1.2,share=raid/...`) contain commas which HandBrakeCLI interprets as delimiters in `--srt-file`. Converter now detects comma-containing paths and creates temporary symlinks with sanitized names. Symlinks are cleaned up after each conversion.
- **Language switching message misleading**: Updated to clarify the interface is primarily English-only; only the Help Browser uses the selected language.

---

## [9.5.1] - 2026-05-17

### Fixed
- **HandBrakeCLI error reporting**: Output buffer increased from 100 to 500 lines. Error message increased from 500 to 3000 chars. Full CLI command now included in error output.
- **Activity log commands**: Full HandBrakeCLI command is now logged to the activity log panel before each file starts encoding, making it easy to reproduce and debug issues.
- **Per-file error storage**: Failed files store their full error message, shown as a tooltip on the status cell.

---

## [9.5.0] - 2026-05-17

### Added
- **Pause/Resume encoding**: Pause button (⏸) sends SIGSTOP to the running HandBrakeCLI process; Resume (▶) sends SIGCONT. Fully reversible mid-file.
- **Skip current file**: Skip button (⏭) cancels the current file and advances to the next in the batch.
- **Activity log panel**: A QTextEdit log area below the progress section shows real-time timestamped activity. Log entries auto-scroll.
- **Log retention option**: Settings → "Retain Activity Logs" (off by default) keeps log entries between sessions for troubleshooting.
- **Busy cursor**: Wait cursor displays during file analysis when adding/importing videos.
- **File info columns**: The file table now has 7 resizable columns: File, Size, Video codec, Audio codec, Resolution, Duration, Status. Media info is analyzed automatically when files are added.
- **Resizable columns**: All columns use Interactive resize mode. Widths are saved to config on close and restored on launch. Right-click the table header → "Reset Column Widths" restores defaults.
- **Keyboard shortcuts**: Delete/Backspace removes selected files, subtitles, or queue entries depending on focus.
- **Error reporting**: Failed conversions now show the HandBrakeCLI error output (up to 500 chars) in both the status label and activity log. Output buffer captures last 100 lines.
- **Converter pause/resume/skip**: `Converter.pause()`, `Converter.resume()`, `Converter.skip_current()` exposed through ConversionWorker.

### Changed
- **File table**: Expanded from 4 to 7 columns. Status column moved to index 6.
- **closeEvent**: Saves column widths. Clears log unless retention is enabled.
- **ConversionWorker**: Added `pause()`, `resume()`, `skip_current()` methods. `run()` handles skip by cancelling current file and moving to next.

---

## [9.4.0] - 2026-05-17

### Added
- **Per-file subtitle linking**: Subtitle files are now linked to individual media files rather than applied globally. `self.file_subtitles: dict[str, list]` maps each media path to its own subtitle list. File table selection updates the subtitle list display.
- **Auto-match subtitles on folder import**: When scanning a folder for video files, subtitle files matching by Plex-style naming (`video.srt`, `video.eng.srt`, `video.ara.srt`) are automatically linked to their corresponding video files.
- **Drop subtitles on selected file**: Dropping subtitle files now links them to the currently selected video file instead of the global list.
- **Folder name preserved in output**: `source_root` for dropped or added folders is now set to the parent of the folder, so the folder's own name is included in output path structure.

### Changed
- **Subtitle add/remove/clear operations**: All target the currently selected file's subtitle list.
- **ConversionWorker**: Accepts `file_subtitles` dict; sets per-file `external_srt_files` before conversion.

---

## [9.3.3] - 2026-05-17

### Added
- **Drag & drop for subtitles**: Dropping .srt/.ass/.ssa/.sub/.vtt files onto the window adds them to the external subtitles list with a language prompt (same as clicking the Add button).
- **Drag & drop for folders**: Dropping a folder (or multiple folders) recursively scans for video files and adds them all at once.

---

## [9.3.2] - 2026-05-17

### Fixed
- **Left panel group box titles still truncating**: Root cause was QGroupBox title elision — Qt's style internally elides titles when they contain wide characters (emoji), regardless of available panel width. Removed all emoji from group box titles. Now titles are short plain text ("Encoder", "Quality (RF)", "Preset", etc.) which never trigger elision.
- **Subtitle mode descriptions unclear**: Tooltip and What's This now explicitly explain that **copy** filters by language list while **all** ignores it. Updated both English and Arabic user guides with comparison tables.

---

## [9.3.1] - 2026-05-17

### Fixed
- **Audio bitrate missing in analysis**: ffprobe omits stream-level `bit_rate` for VBR/lossless audio (Vorbis, Opus, FLAC, PCM). Now falls back to MKV `BPS` tags, then overall format bitrate as last resort.

---

## [9.3.0] - 2026-05-17

### Fixed
- **Taskbar/start menu icon**: `StartupWMClass` mismatched Qt's lowercased WM_CLASS. Changed to `vconv`, added `app.setDesktopFileName("vconv")` for proper DE integration.
- **Desktop file validation**: `Version=9.2.2` is not a valid desktop entry spec version. Changed to `Version=1.0`.
- **Desktop file Icon path**: Changed to `Icon=vconv` + auto-install icons to XDG paths via new utils/xdg_integration.py.
- **5MB 2048×2048 icon**: The "256" icon was actually 2048×2048 and 5MB. Now scaled down to proper sizes on launch (256/128/64/48/32) — 72KB at 256px.
- **Media analysis missing audio info**: Now displays all audio tracks with codec, channels, language, track name, and bitrate.
- **Progress bar no encoding speed**: File progress bar now shows FPS while encoding.

### Added
- **Auto XDG integration** (`utils/xdg_integration.py`): On every launch, auto-installs desktop file to `~/.local/share/applications/` and scaled icons to `~/.local/share/icons/hicolor/` — start menu and taskbar icons work immediately without manual install.
- **QIcon theme registration**: Registers XDG icon directories with Qt's icon theme engine — `QIcon.fromTheme("vconv")` resolves correctly.
- **Drag and drop**: Dropping video files onto the main window now adds them to the conversion list. Supports multiple files via drag-and-drop.
- **Audio stream tracking**: `MediaInfo.audio_streams` captures every audio track (codec, channels, language, title, bitrate) instead of only the last one.

---

## [9.2.2] - 2026-05-16

### Changed
- **Rebranded**: Application renamed from "vconv" to **MoTekLab Video Encoder** everywhere in the UI, About dialog, desktop file, help browser, docs, and locales
- **Version**: 9.2.1 → 9.2.2

---

## [9.2.1] - 2026-05-16

### Fixed
- **Config mutation bug**: `DEFAULT_CONFIG.copy()` was shallow; nested dict modifications corrupted defaults permanently. Now uses `copy.deepcopy()`.
- **requirements.txt**: Listed `pysimplegui` (unused) instead of `PyQt6` and `markdown` (required). Now correct.
- **Version centralization**: Created `utils/version.py` — single source of truth, imported everywhere.
- **Legacy Bash scripts**: Moved `vconv`, `convert.sh.base`, `vconv.conf` to `legacy/` to eliminate confusion.
- **`--recursive` CLI flag**: Could not be disabled (`store_true` + `default=True`). Added `--no-recursive` flag.
- **`setup_logging` handler wipe**: Calling it multiple times no longer clears handlers added by other modules.
- **`VIDEO_EXTENSIONS` drift**: Defined once in `core/constants.py`, imported everywhere. Previously validator rejected `.ts`, `.m2ts`, `.mts`, `.vob`.
- **Missing presets in UI**: `web_optimized` and `mobile` now appear in the preset dropdown.
- **`_apply_preset` only set quality**: Now applies all preset fields (encoder, format, audio).
- **`_monitor_progress` no timeout**: Added `select.select()` with 1s timeout so hung HandBrakeCLI won't block forever.
- **Duplicate `launch()`**: `vconv.py` now imports `launch()` from `main_window.py` — single GUI startup path.
- **QueueManager thread safety**: Added `threading.Lock` to all 12 public methods.
- **i18n language fallback**: `set_language()` test-loads before swapping; corrupt/missing files preserve old translations.
- **SPEC.md / ROADMAP.md**: Marked as archival with notes pointing to `docs/upgrade_audit.md`.

### Changed
- **Version**: 9.2.0 → 9.2.1
- **README.md**: Updated project structure, version, install instructions
- **vconv.desktop**: `Version=9.1` → `9.2`

---

## [9.2.0] - 2026-05-16

### Added
- **Update Checker** (`utils/updater.py`): Background GitHub release check on startup, Check for Updates in Help menu, update dialog with release notes and direct download link, 24-hour cache
- **Check for Updates Toggle**: Settings menu checkable item (persists in config)
- **App Icon**: Custom neon-glass icon set as window, taskbar, and desktop file icon
- **About Dialog Banner**: Custom banner in redesigned About dialog
- **GitHub Social Preview**: Uploaded to release assets
- **Image Asset System**: `_asset_path()` helper for dev/.deb/AppImage modes
- **public/README.md**: Google Imagen-optimized prompts for all 6 image assets
- **Release Build Documentation**: `docs/release_process.md`

### Changed
- **Version**: 9.1.0 → 9.2.0
- **About Dialog**: Custom QDialog with banner, hardware info, website link
- **Desktop File**: Points to icon at `/opt/vconv/vconv-icon-256.png`
- **Release Artifacts**: .deb and AppImage bundle icons and banner

---

## [9.1.0] - 2026-05-16

### Fixed
- **Subtitle Passthrough**: Embedded subtitles now properly preserved using `--subtitle-lang-list` and `--all-subtitles`
- **External Subtitle Language Tagging**: Each external SRT/ASS file gets its own language code via per-file tuples
- **Multiple External Subtitles**: Fixed comma-separated format for `--srt-file`, `--srt-lang`, `--srt-default`, `--srt-burn`
- **Folder Structure Preservation**: source_root is now the folder the user selected; computed common ancestor was too deep
- **ConversionWorker arg mismatch**: preserve_structure bool was passed as 5th arg mapping to source_root — breaking all structure preservation
- **Arabic/Non-Latin SRT Characters**: Added `--srt-codeset UTF-8` for external SRT files (HandBrakeCLI defaults to latin1)
- **Help Browser Navigation**: Fixed heading ID mismatch — markdown toc extension generates different IDs than hardcoded anchors
- **Help Browser Code Block Leakage**: Heading parser now skips content inside ``` fenced code blocks
- **UI Layout Congestion**: Redesigned right panel with grouped sections (Files, Queue, Progress)
- **Queue Workflow**: "Add to Queue" button in Files area; if no selection, adds all files
- **Lambda Signal Handlers**: Fixed TypeError from PyQt6 signals passing bool to lambdas

### Added
- **Comprehensive Help System**:
  - New `ui/help_browser.py` with tree index, search bar, back/forward navigation
  - **Dual-language support**: English + Arabic (العربية) with RTL layout
  - Language toggle combo inside the help browser
  - Language selection in Settings menu
  - Dynamic TOC generation from actual markdown headings
  - Custom `_inject_heading_ids` to handle non-ASCII heading IDs (Arabic, Chinese)
  - New `docs/user_guide.md` massively expanded: **75 headings, 14 categories, 59KB**
  - New `docs/user_guide.ar.md`: Full Arabic translation: **60 headings, 14 categories**
  - Every edge case, scenario, and example documented (CLI, errors, performance, FAQ)
  - **Tooltips** on every interactive widget (encoder, quality, presets, audio, subtitles)
  - **What's This?** context help (Shift+F1) on key widgets
  - **F1** keyboard shortcut opens Help Browser
  - Help menu restructured: User Guide (F1), What's This?, Keyboard Shortcuts, About
  - About dialog includes moteklab.com website and F1/Shift+F1 instructions
- **SRT UTF-8 Encoding**: External subtitle files pass `--srt-codeset UTF-8` for proper Arabic/Chinese rendering
- **Per-File Subtitle Language**: Language dialog when adding external subtitles
- **Website in About**: moteklab.com link added to the About dialog
- **CLI Documentation**: Full command-line reference (22 options, examples, batch mode details) added to user_guide.md
- **README Rewrite**: Comprehensive update reflecting all v9.1.0 changes, project structure, CLI reference, encoders table, presets table

---

## [9.0.0] - 2026-05-16

### ⚠️ Breaking Changes

- **GUI Framework**: Migrated from PySimpleGUI to PyQt6
- **Threading Model**: Replaced event-loop threading with proper QThread workers
- **Window Management**: Native Qt window management replaces PySimpleGUI workarounds

### Added

#### PyQt6 Migration
- **QThread Workers**: Proper async conversion threading - no more UI freezes
- **Native Layouts**: Dynamic, responsive layouts using Qt layout managers
- **Tabbed Interface**: Files and Queue tabs for better organization
- **Per-file Progress**: Individual progress bars for each file in conversion
- **Queue Management**: Full job queue with start/pause/clear operations
- **Toolbar Actions**: Quick access to common operations
- **Menu System**: Native Qt menus with keyboard shortcuts

#### Core Improvements
- **ConversionWorker**: Dedicated QThread for HandBrakeCLI subprocess management
- **Real-time Progress**: Signals/slots pattern for thread-safe UI updates
- **QueueManager**: Persistent job queue with JSON storage
- **Job States**: Pending, Running, Completed, Failed, Cancelled states
- **File Table**: Detailed file list with size, duration, and status columns

### Fixed
- **UI Freezing**: Eliminated by moving conversion to background QThread
- **Window Position**: Proper Qt geometry management
- **Popup Errors**: Native Qt dialogs replace PySimpleGUI popups
- **Cancel/Stop**: Clean worker cancellation with proper cleanup
- **Linux Compatibility**: Native Qt6 eliminates all Linux-specific PySimpleGUI bugs

### Removed
- **PySimpleGUI Dependency**: Completely replaced with PyQt6
- **Event-loop Threading Hack**: Replaced with proper QThread workers
- **Window Workarounds**: Native Qt window management

---

## [8.2.0] - 2026-05-16

### Fixed
- **Window Position**: Fixed saving using `current_location()` with proper error handling
- **Popup Position**: Fixed "bad window path name" error by handling closed windows gracefully
- **Cancel vs Stop All**: Cancel now skips current file and continues; Stop All stops everything
- **UI State After Conversion**: Properly resets UI when conversion completes
- **Progress Bar**: Shows both file-level and overall progress
- **Folder Structure**: Default output preserves folder structure from source
- **Dynamic Resizing**: Added expand_x/expand_y for proper layout scaling
- **Subtitle Names**: Analyze now shows subtitle language and title
- **External Subtitles**: Added option to embed external SRT files
- **Last Folder Memory**: Fixed folder selection remembering last opened location
- **Floating Button on Close**: Fixed by using `enable_close_attempted_event`

### Added
- **External SRT Embedding**: Option to add external subtitle files during conversion
- **Folder Structure Preservation**: Default output maintains original folder hierarchy
- **Dump All Option**: Alternative to preserve structure - dump all files to single folder
- **Quick Access Folders**: Documents, Downloads, Videos, Movies, Desktop shortcuts
- **Folder Creation**: Create new folders directly in folder browser
- **Window Move Tracking**: Saves position on window move events

---

## [8.1.0] - 2026-05-15

### Fixed
- **Progress Bar**: Fixed thread-safe UI updates using `write_event_value()`
- **KeyError Crash**: Fixed crash during conversion from incorrect event data access
- **popup_warning Error**: Changed to `popup_ok()` (PySimpleGUI compatibility)
- **Window Position**: Improved position saving on window close
- **Audio Bitrate**: Now properly disabled when audio encoder is "copy"
- **Cancel vs Stop All**: Cancel skips current file, Stop All cancels all remaining
- **Help Menu**: All submenu items now functional
- **Folder Browser**: Added folder creation and quick access to common folders

### Added
- **Subtitle Info**: Analyze now shows subtitle count
- **Settings Management**: Save current as default, Reset to defaults
- **Default Folder**: Set/clear default folder in Settings menu
- **Last Folder Memory**: Remembers last opened folder
- **Log Analysis**: Added logging infrastructure for debugging
- **UI Responsiveness**: Added 100ms timeout for UI updates during conversion

---

## [8.0.0] - Unreleased

### ⚠️ Breaking Changes

- **Application Rewrite**: Migrated from Bash/yad to Python/PySimpleGUI
- **Config Format**: Changed from bash-style to JSON/INI
- **Minimum Requirements**: Python 3.8+ (previously bash)

### Added

#### Core Features
- **Modular Architecture**: Split into core/, ui/, utils/, presets/ modules
- **Python-based Application**: Full rewrite in Python 3
- **Dependency Checker**: Auto-detects missing tools with install options
- **Internal Download Option**: Download HandBrakeCLI directly if missing
- **Download Links**: Option to provide manual download links for user

#### Hardware Support
- **NVIDIA NVENC**: H.264 and H.265 GPU encoding (fastest)
- **Intel Quick Sync (QSV)**: H.264 and H.265 encoding (low power)
- **AMD VCE/VCN**: H.264 and H.265 encoding (good balance)
- **Auto GPU Detection**: Automatically detects and selects best encoder
- **Hardware Badge**: Shows detected hardware in status bar

#### Encoder Descriptions
- Added descriptive tooltips explaining each encoder's use case
- "Best for" recommendations for each encoder option
- Shows "Recommended" badge for auto-detected best encoder

#### File Handling
- **Smart Output Location**: Default output to same location as source
- **Custom Output Folder**: Option to save all files to specific folder
- **Filename Conflict Detection**: Checks all files BEFORE batch starts
- **Conflict Resolution UI**: Dialog to rename or overwrite existing files
- **Batch Pre-validation**: Validates all files before showing start button
- **Folder Scanning**: Recursive scan for TV show seasons

#### UI/UX
- **Tab-based Interface**: Convert, Analyze, Presets, Queue tabs
- **Theme Support**: Dark (default), Light, System themes
- **Multi-language Support**:
  - English (en)
  - Classical Arabic (ar) - RTL
  - Egyptian Arabic (ar_eg) - RTL
- **Window Position Memory**: Remembers last window position
- **Subtitle Options**: Copy all, Burn in, or remove
- **Audio Options**: Copy, re-encode, channel selection
- **Comprehensive Tooltips**: Help text on all UI elements
- **File Validation**: Check files before conversion

#### Installation
- **PATH Integration**: Adds to /usr/local/bin for CLI access
- **Start Menu Entry**: Adds to Multimedia category
- **Desktop Shortcut**: Optional desktop shortcut
- **RTL Layout**: Proper mirror layout for Arabic languages
- **Job Queue UI**: Full queue management window
- **Progress Indicators**: Real-time progress with percentage and ETA
- **Job Control**: Cancel individual jobs or all jobs

#### Features
- **Preset System**: Extensible preset library (Fast, Balanced, High, Archive)
- **Parallel Processing Option**: Optional multi-job processing (non-default)
- **Parallel Processing Warning**: Clear warning about speed trade-offs
- **Filter Options**: Denoise, deinterlace, crop, rotate
- **Subtitle Handling**: Track selection, burn-in, external SRT support
- **Audio Options**: Copy, AAC, AC3, E-AC3, MP3, FLAC with bitrate selection

#### Technical
- **Shellcheck Compliance**: Linted shell scripts (if used)
- **Enhanced Error Handling**: Try-catch blocks, graceful failures
- **Improved Logging**: Detailed application logs (~/.config/vconv/logs/)
- **Config Management**: JSON-based config with persistence
- **Resume Capability**: Save queue state for resume after restart

### Changed

- **Output Format Default**: MP4 remains default
- **Parallel Processing**: Disabled by default (was sequential)
- **Conflict Resolution**: "Ask" is default for single, "Auto-rename" for batch

### Deprecated

- Bash-based version (v7.x) - replaced by Python application

### Fixed

- All legacy Bash bugs resolved in new Python implementation

---

## [7.5] - 2026-02-14

### Fixed
- **Recursive Scan GUI**: Re-architected file loop to use in-memory arrays instead of pipe streams, solving vanishing GUI issue on 2nd file
- **Save Location**: Explicitly defaults to current working directory (`./vconv.conf`)

---

## [7.4] - 2026-02-14

### Fixed
- **Recursive Scan Stability**: Decoupled file finding and processing loops
- **Save Path**: "Save Settings..." dialog checks

---

## [7.3] - 2026-02-14

### Fixed
- **Settings Save**: Implemented atomic save operation (write-to-temp then move) to prevent 0-byte file corruption
- **Debug Logging**: Enabled verbose debug logging for settings and file operations (`~/vconv_debug.log`)

---

## [7.2] - 2026-02-14

### Changed
- **GUI Refactor**: Replaced settings buttons with unified "Action" menu to fix 0-byte settings file bug
- **Action Menu**: "Start Processing", "Save Settings...", "Load Settings...", "Reset Defaults"

---

## [7.1] - 2026-02-14

### Fixed
- **Settings Load**: Loaded settings not applied to GUI (trailing pipe in variable parsing)
- **Recursive Stability**: Improved isolation of recursive conversion to prevent premature termination

---

## [7.0] - 2026-02-14

### Added
- **Manual Settings Management**: Save, Load, Reset buttons in main interface
- **Stability Improvements**: Added delay between file processing to prevent race conditions

---

## [6.0] - 2026-02-14

### Added
- **Settings Persistence**: Settings saved to `~/.config/vconv.conf` and restored on launch
### Fixed
- **D&D Conversion Exit**: Fixed hang when clicking "Back" in Drag & Drop window

---

## [5.2] - 2026-02-14

### Removed
- **Drag & Drop Analysis**: Temporarily removed due to stability issues
### Fixed
- **Recursive Analysis Display**: Reverted to newline separation format

---

## [5.1] - 2026-02-14 [YANKED]

- Attempted fix for D&D Analysis caused regressions

---

## [5.0] - 2026-02-14 [YANKED]

- Attempted queuing system for D&D Analysis

---

## [4.9] - 2026-02-14

### Added
- **Audio Bitrate Column**: Analysis results include "Audio Bitrate" column
- **Async D&D**: Non-blocking Drag & Drop to prevent UI freezes
### Fixed
- **D&D Deadlock**: Fixed GUI freeze on dropping multiple files (pipe buffer saturation)
- **Path Normalization**: Python-based decoding for special characters

---

## [4.8] - 2026-02-14

### Fixed
- **Dependency Repair**: Enhanced auto-installer with `apt-get update` and `reinstall`
- **Broken Library Feedback**: Added "Error: FFprobe Broken" message

---

## [4.7] - 2026-02-14

### Added
- **Broken Library Detection**: Verifies tool runs without error, not just exists

---

## [4.6] - 2026-02-14

### Fixed
- **Single-Probe Parsing**: Robust single-probe analysis method to avoid "N/A"
- **Unbuffered D&D**: Forced immediate data flushing

---

## [4.5] - 2026-02-14

### Fixed
- **Flat Parsing**: Switched to `ffprobe -of flat` for improved reliability

---

## [4.3] - 2026-02-14

### Changed
- **Unified D&D UI**: Consolidated drop zone and results into single window

---

## [4.2] - 2026-02-14

### Added
- **Auto-Install**: Automatically detects and installs missing dependencies
- **Folder Drag & Drop**: Recursive processing of dropped folders

---

## [4.0] - 2026-02-14

### Added
- **Analysis Modes**: ffprobe integration for media file analysis
- **Main Menu Loop**: Returns to menu instead of exiting after stopping

---

## [Legacy Versions]

Earlier versions (pre-4.0) documented in git history.

---

## Version History

| Version | Type | Status |
|---------|------|--------|
| 8.0.0 | Major | Planned |
| 7.5 | Patch | Current (Bash) |
| 7.4 | Patch | Old |
| 7.3 | Patch | Old |
| 7.2 | Minor | Old |
| 7.1 | Patch | Old |
| 7.0 | Minor | Old |
| 6.0 | Minor | Old |

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com) principles.*
*For detailed commit history, see git log.*