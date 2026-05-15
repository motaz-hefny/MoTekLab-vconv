# Changelog

All notable changes to the vconv project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **NVIDIA NVENC**: H.264 and H.265 GPU encoding
- **Intel Quick Sync (QSV)**: H.264 and H.265 encoding
- **AMD VCE/VCN**: H.264 and H.265 encoding
- **Auto GPU Detection**: Automatically detects and selects best encoder
- **Hardware Badge**: Shows detected hardware in status bar

#### Encoder Descriptions
- Added descriptive tooltips explaining each encoder's use case
- "Best for" recommendations for each encoder option

#### File Handling
- **Smart Output Location**: Default output to same location as source
- **Filename Conflict Detection**: Checks all files BEFORE batch starts
- **Conflict Resolution UI**: Dialog to rename or overwrite existing files
- **Batch Pre-validation**: Validates all files before showing start button

#### UI/UX
- **Tab-based Interface**: Convert, Analyze, Presets, Queue tabs
- **Theme Support**: Dark (default), Light, System themes
- **Multi-language Support**:
  - English (en)
  - Classical Arabic (ar) - RTL
  - Egyptian Arabic (ar_eg) - RTL
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