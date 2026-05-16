# Changelog

All notable changes to the vconv project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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