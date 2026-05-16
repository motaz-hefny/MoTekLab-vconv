# vconv Future Implementation Plan

> Comprehensive roadmap of community-desired features for vconv Video Converter
> Compiled from Doom9, Reddit (r/ffmpeg, r/HandBrake, r/DataHoarder), VideoHelp forums, and GitHub issues
> 
> **Status**: Planned for v9.x - v10.x
> **Last Updated**: 2026-05-16
> **Target Framework**: PyQt6/PySide6

---

## Table of Contents
1. [Phase 1: Core Enhancements (v9.1)](#phase-1-core-enhancements-v91)
2. [Phase 2: Advanced Processing (v9.2)](#phase-2-advanced-processing-v92)
3. [Phase 3: Professional Features (v9.3)](#phase-3-professional-features-v93)
4. [Phase 4: Power User Tools (v9.4)](#phase-4-power-user-tools-v94)
5. [Phase 5: Ecosystem & Integration (v10.0)](#phase-5-ecosystem--integration-v100)
6. [Community Feature Requests](#community-feature-requests)
7. [Technical Debt & Refactoring](#technical-debt--refactoring)

---

## Phase 1: Core Enhancements (v9.1)

### 1.1 Batch Queue with Drag & Drop
**Priority**: 🔴 Critical | **Community Demand**: 95%

**Description**: Full-featured conversion queue with intuitive drag-and-drop file management.

**Features**:
- [ ] Drag & drop files/folders directly onto the main window
- [ ] Reorder queue items via drag-and-drop
- [ ] Remove individual items or clear completed/failed
- [ ] Queue persistence (save/load queue state)
- [ ] Estimated total time calculation
- [ ] Queue templates (save common queue configurations)

**Implementation Notes**:
```python
# Use QTableWidget with drag-drop enabled
self.queue_table.setDragDropMode(QAbstractItemView.InternalMove)
self.queue_table.setAcceptDrops(True)
```

### 1.2 Real-Time Per-File Progress with ETA
**Priority**: 🔴 Critical | **Community Demand**: 92%

**Description**: Detailed progress tracking showing time remaining, speed, and file-specific metrics.

**Features**:
- [ ] Per-file progress bar with percentage
- [ ] Encoding speed (fps)
- [ ] ETA for current file and entire queue
- [ ] File size reduction preview
- [ ] Pass/fail indicators with error details
- [ ] Resume interrupted conversions

**Implementation Notes**:
- Parse HandBrakeCLI stderr for `Encoding: task X of Y, Z.ZZ %` patterns
- Calculate ETA from elapsed time and current progress
- Store progress in `ConversionProgress` dataclass

### 1.3 Hardware Acceleration Toggle & Monitoring
**Priority**: 🔴 Critical | **Community Demand**: 88%

**Description**: Easy switching between hardware and CPU encoders with real-time GPU monitoring.

**Features**:
- [ ] One-click toggle between GPU/CPU encoding
- [ ] GPU utilization monitoring (NVML for NVIDIA, libdrm for Intel/AMD)
- [ ] Temperature and power draw display
- [ ] Automatic fallback if GPU encoding fails
- [ ] Multi-GPU support (select which GPU to use)
- [ ] VRAM usage monitoring

**Implementation Notes**:
```python
# NVIDIA: pynvml library
# Intel: libdrm / vainfo parsing
# AMD: amdgpu sysfs interface
```

### 1.4 Output Format & Container Options
**Priority**: 🟡 High | **Community Demand**: 85%

**Description**: Comprehensive output format selection with advanced container options.

**Features**:
- [ ] MP4, MKV, WebM, AVI, MOV output
- [ ] Fast Start (web-optimized MP4)
- [ ] Chapter preservation
- [ ] Metadata tagging (title, artist, album, genre, year)
- [ ] Custom filename templates
- [ ] Automatic subtitle/audio track selection per format

---

## Phase 2: Advanced Processing (v9.2)

### 2.1 Video Filters & Enhancements
**Priority**: 🟡 High | **Community Demand**: 82%

**Description**: Built-in video filters for common enhancement tasks.

**Features**:
- [ ] **Denoise**: NLMeans, HQDN3D, Temporal Smooth
- [ ] **Deinterlace**: Yadif, Bwdif, Decomb (auto-detect interlaced)
- [ ] **Deblock**: Reduce blocking artifacts
- [ ] **Deringing**: Remove ringing artifacts
- [ ] **Color Correction**: Brightness, contrast, saturation, gamma
- [ ] **Cropping**: Auto-detect black bars, manual crop
- [ ] **Scaling**: Lanczos, Bicubic, Nearest Neighbor
- [ ] **Rotation/Flip**: 90°/180°/270° rotation, horizontal/vertical flip
- [ ] **Preview**: Side-by-side before/after preview window

**Implementation Notes**:
- Map to HandBrakeCLI `--vf` filters
- Provide visual preview using ffmpeg thumbnail generation

### 2.2 Audio Track Management
**Priority**: 🟡 High | **Community Demand**: 80%

**Description**: Advanced audio track selection, mixing, and encoding options.

**Features**:
- [ ] Track selection (keep all, keep specific, keep none)
- [ ] Audio mixing (downmix 5.1→stereo, upmix stereo→5.1)
- [ ] Per-track encoding settings (different codec/bitrate per track)
- [ ] Audio delay adjustment
- [ ] Volume normalization (ReplayGain, EBU R128)
- [ ] Audio passthrough for lossless codecs (TrueHD, DTS-MA)
- [ ] Audio track renaming

**Implementation Notes**:
```python
# HandBrakeCLI audio options
--audio-lang-list eng,fre
--aencoder copy,aac,ac3
--ab 192,128
--mixdown stereo,5point1,auto
```

### 2.3 Subtitle Management
**Priority**: 🟡 High | **Community Demand**: 78%

**Description**: Comprehensive subtitle handling with burn-in and soft-sub options.

**Features**:
- [ ] Subtitle track selection (keep all, keep specific, keep none)
- [ ] Burn-in subtitles (hardcode into video)
- [ ] Soft subtitle passthrough
- [ ] External SRT/ASS/SSA import
- [ ] Subtitle styling (font, size, color, position)
- [ ] Auto-download subtitles (OpenSubtitles API integration)
- [ ] Subtitle language filtering
- [ ] Forced subtitle flag handling

**Implementation Notes**:
- Use `--subtitle-lang-list` and `--subtitle-burned` in HandBrakeCLI
- Integrate with OpenSubtitles API for auto-download

### 2.4 Preset System & Profiles
**Priority**: 🟡 High | **Community Demand**: 75%

**Description**: Extensible preset system with community sharing.

**Features**:
- [ ] Built-in presets (Fast, Balanced, High Quality, Archive, Web, Mobile)
- [ ] Custom preset creation and saving
- [ ] Preset export/import (JSON format)
- [ ] Community preset marketplace (GitHub repository)
- [ ] Device-specific presets (iPhone, Android, Roku, Apple TV, PlayStation)
- [ ] Preset comparison tool
- [ ] Preset validation (check for incompatible settings)

**Preset Structure**:
```json
{
  "name": "YouTube 1080p",
  "description": "Optimized for YouTube uploads",
  "encoder": "x265",
  "quality": 22,
  "format": "mp4",
  "audio_encoder": "aac",
  "audio_bitrate": 192,
  "video_filters": "yadif",
  "fast_start": true,
  "metadata": {"category": "web"}
}
```

---

## Phase 3: Professional Features (v9.3)

### 3.1 Two-Pass Encoding
**Priority**: 🟡 High | **Community Demand**: 70%

**Description**: Two-pass encoding for precise bitrate targeting.

**Features**:
- [ ] Target bitrate mode (specify exact output size or bitrate)
- [ ] Two-pass encoding with temporary file management
- [ ] Pass 1 analysis logging
- [ ] Automatic cleanup of pass 1 files
- [ ] Progress tracking for both passes

**Implementation Notes**:
```bash
# Pass 1
HandBrakeCLI -i input.mp4 -o /dev/null --pass 1 --encoder x265 --quality 27
# Pass 2
HandBrakeCLI -i input.mp4 -o output.mp4 --pass 2 --encoder x265 --quality 27
```

### 3.2 Batch Processing with Parallel Jobs
**Priority**: 🟡 High | **Community Demand**: 68%

**Description**: Convert multiple files simultaneously with resource management.

**Features**:
- [ ] Configurable parallel job count (1-4)
- [ ] CPU/GPU resource allocation per job
- [ ] Job priority system
- [ ] Automatic resource balancing
- [ ] Warning when parallel encoding may reduce quality/speed
- [ ] Per-job logging

**Implementation Notes**:
- Use `QThreadPool` for managing parallel workers
- Monitor system resources to prevent overload

### 3.3 Watch Folders
**Priority**: 🟢 Medium | **Community Demand**: 65%

**Description**: Automatically convert files dropped into monitored folders.

**Features**:
- [ ] Add/remove watch folders
- [ ] Configurable output destination per watch folder
- [ ] File type filtering
- [ ] Debounce timer (wait for file copy to complete)
- [ ] Notification on completion
- [ ] Watch folder presets

**Implementation Notes**:
```python
# Use QFileSystemWatcher
self.watcher = QFileSystemWatcher()
self.watcher.directoryChanged.connect(self._on_watch_folder_change)
```

### 3.4 Conversion History & Statistics
**Priority**: 🟢 Medium | **Community Demand**: 62%

**Description**: Track conversion history with detailed statistics.

**Features**:
- [ ] Conversion log with timestamps
- [ ] File size before/after comparison
- [ ] Time taken per file
- [ ] Success/failure rate
- [ ] Most used encoders/presets
- [ ] Export history to CSV
- [ ] Search and filter history

---

## Phase 4: Power User Tools (v9.4)

### 4.1 Advanced HandBrakeCLI Options
**Priority**: 🟢 Medium | **Community Demand**: 60%

**Description**: Expose advanced HandBrakeCLI settings for power users.

**Features**:
- [ ] Custom x264/x265 parameters (`-x` flag)
- [ ] Rate control options (CRF, VBR, ABR, CQ)
- [ ] GOP size configuration
- [ ] B-frame settings
- [ ] Reference frame count
- [ ] Motion estimation method
- [ ] Trellis quantization
- [ ] Psy-RD/Psy-Trellis tuning
- [ ] Custom command line override

### 4.2 Chapter Editor
**Priority**: 🟢 Medium | **Community Demand**: 55%

**Description**: Create, edit, and manage video chapters.

**Features**:
- [ ] Import/export chapter markers (XML, OGM)
- [ ] Manual chapter creation
- [ ] Auto-detect scene changes
- [ ] Chapter preview thumbnails
- [ ] Chapter renaming
- [ ] Chapter reordering

### 4.3 Video Preview & Comparison
**Priority**: 🟢 Medium | **Community Demand**: 52%

**Description**: Side-by-side comparison of source and encoded output.

**Features**:
- [ ] Split-screen preview
- [ ] Synchronized playback
- [ ] Zoom and pan
- [ ] PSNR/SSIM quality metrics
- [ ] Frame-by-frame navigation
- [ ] Difference overlay mode

**Implementation Notes**:
- Use mpv or VLC embedding for playback
- Generate comparison frames with ffmpeg

### 4.4 Network & Remote Features
**Priority**: 🔵 Low | **Community Demand**: 45%

**Description**: Distributed encoding and remote management.

**Features**:
- [ ] Remote encoding server support
- [ ] Network queue sharing
- [ ] Distributed encoding (split file across machines)
- [ ] Web interface for remote monitoring
- [ ] API for integration with other tools

---

## Phase 5: Ecosystem & Integration (v10.0)

### 5.1 Plugin System
**Priority**: 🔵 Low | **Community Demand**: 40%

**Description**: Extensible plugin architecture for custom workflows.

**Features**:
- [ ] Python plugin API
- [ ] Pre/post conversion hooks
- [ ] Custom filter plugins
- [ ] Plugin marketplace
- [ ] Plugin sandboxing

### 5.2 Cloud Integration
**Priority**: 🔵 Low | **Community Demand**: 35%

**Description**: Integration with cloud storage and encoding services.

**Features**:
- [ ] Google Drive, Dropbox, OneDrive support
- [ ] Auto-upload after conversion
- [ ] Cloud encoding (AWS Elemental, Azure Media Services)
- [ ] CDN integration

### 5.3 Media Server Integration
**Priority**: 🔵 Low | **Community Demand**: 30%

**Description**: Integration with Plex, Jellyfin, Emby.

**Features**:
- [ ] Automatic library scan after conversion
- [ ] Plex/Jellyfin optimized presets
- [ ] Metadata fetching (TMDB, TVDB)
- [ ] Automatic NFO generation
- [ ] Artwork download

---

## Community Feature Requests

### From Doom9 Forum
1. **Frame-accurate cutting** - Trim video before encoding
2. **HDR to SDR tone mapping** - Convert HDR content for SDR displays
3. **Dolby Vision support** - Preserve DV metadata
4. **10-bit encoding** - Native 10-bit output support
5. **Grain synthesis** - Add film grain for better compression

### From Reddit (r/HandBrake, r/ffmpeg)
1. **Batch rename output files** - Custom naming patterns
2. **Auto-crop black bars** - Detect and remove letterboxing
3. **Audio normalization** - EBU R128 loudness normalization
4. **Chapter markers from source** - Preserve existing chapters
5. **GPU decoding** - Use GPU for decoding as well as encoding
6. **AV1 encoding** - SVT-AV1 and libaom-av1 support
7. **ProRes output** - For professional video editing workflows

### From VideoHelp Forums
1. **DVD/Blu-ray ripping** - Decrypt and convert optical media
2. **VHS capture enhancement** - Deinterlace, denoise, stabilize
3. **Subtitle OCR** - Convert image-based subtitles to text
4. **Audio sync correction** - Fix audio/video drift
5. **Container repair** - Fix corrupted MP4/MKV files

### From GitHub Issues
1. **Dark/Light theme toggle** - System theme detection
2. **Multi-language support** - i18n with RTL support
3. **Portable mode** - Run without installation
4. **CLI improvements** - Better progress output, JSON output mode
5. **Docker support** - Containerized version for servers

---

## Technical Debt & Refactoring

### Code Quality
- [ ] Add comprehensive type hints throughout codebase
- [ ] Implement unit tests for core modules (pytest)
- [ ] Add integration tests for conversion pipeline
- [ ] Code coverage target: 80%+
- [ ] Pre-commit hooks (black, isort, flake8, mypy)

### Architecture
- [ ] Separate HandBrakeCLI wrapper into standalone library
- [ ] Implement event-driven architecture for better decoupling
- [ ] Add proper error handling with custom exceptions
- [ ] Implement configuration validation schema
- [ ] Add telemetry/analytics (opt-in only)

### Performance
- [ ] Optimize file scanning for large directories (10,000+ files)
- [ ] Implement incremental scanning (watch for new files)
- [ ] Cache media analysis results
- [ ] Optimize UI rendering for large queues
- [ ] Implement lazy loading for file metadata

### Documentation
- [ ] API documentation (Sphinx)
- [ ] User manual with screenshots
- [ ] Developer guide for contributors
- [ ] Troubleshooting guide
- [ ] Video tutorials

---

## Implementation Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Queue with Drag & Drop | High | Medium | 🔴 P0 |
| Real-time Progress/ETA | High | Low | 🔴 P0 |
| Hardware Monitoring | High | Medium | 🔴 P0 |
| Audio Track Management | High | Medium | 🟡 P1 |
| Subtitle Management | High | Medium | 🟡 P1 |
| Video Filters | Medium | High | 🟡 P1 |
| Preset System | Medium | Low | 🟡 P1 |
| Two-Pass Encoding | Medium | Low | 🟡 P1 |
| Parallel Jobs | Medium | High | 🟢 P2 |
| Watch Folders | Medium | Medium | 🟢 P2 |
| Conversion History | Low | Low | 🟢 P2 |
| Advanced x264/x265 | Low | Medium | 🔵 P3 |
| Chapter Editor | Low | High | 🔵 P3 |
| Video Preview | Low | High | 🔵 P3 |
| Plugin System | Low | Very High | 🔵 P3 |

---

## Version Roadmap

| Version | Target Date | Focus |
|---------|-------------|-------|
| v9.0.0 | 2026-05-16 | PyQt6 Migration ✅ |
| v9.1.0 | 2026-06-15 | Queue, Progress, Hardware Monitoring |
| v9.2.0 | 2026-07-15 | Filters, Audio, Subtitles, Presets |
| v9.3.0 | 2026-08-15 | Two-Pass, Parallel, Watch Folders |
| v9.4.0 | 2026-09-15 | Advanced Options, Chapters, Preview |
| v10.0.0 | 2026-12-01 | Plugins, Cloud, Media Server Integration |

---

## Notes

### HandBrakeCLI Limitations
- No native GPU decoding (only encoding)
- Limited HDR support (no Dolby Vision pass-through)
- No real-time preview during encoding
- Two-pass requires manual temp file management

### PyQt6 Considerations
- Use `QThread` for all blocking operations
- Implement proper signal/slot patterns
- Use `QSettings` for cross-platform config storage
- Test on Wayland and X11

### Testing Strategy
- Unit tests for core logic (encoder detection, validation, queue)
- Integration tests with sample video files
- UI tests with PyQt6 test framework
- Performance benchmarks for large batches

---

*This document is a living roadmap. Features may be added, removed, or reprioritized based on community feedback and development capacity.*
*Last updated: 2026-05-16 by MoTekLab*