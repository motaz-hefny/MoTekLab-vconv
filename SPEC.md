# vconv - Video Converter GUI Specification

> ⚠️ **ARCHIVAL NOTICE:** This specification document reflects the v8.0 planning phase and references PySimpleGUI/CustomTkinter. The actual implementation migrated to **PyQt6** in v9.0.0 and is now at **v9.2.0**. See `docs/upgrade_audit.md` for the current code audit and `CHANGELOG.md` for version history.

## Project Overview

| Aspect | Details |
|--------|---------|
| **Project Name** | vconv (Video Converter) |
| **Type** | Standalone Desktop Application |
| **Core Technology** | Python 3 + PySimpleGUI / CustomTkinter + HandBrakeCLI |
| **Version** | 8.0 (Major Rewrite) |
| **License** | GPLv3 |
| **Platform** | Linux (primary), macOS/Windows (future) |

## Mission Statement

vconv is a user-friendly, feature-rich video conversion application that leverages HandBrakeCLI as its core engine, providing a modern GUI with hardware acceleration detection, batch processing, and professional-grade encoding options.

---

## 1. UI/UX Specification

### 1.1 Window Structure

#### Main Window
- **Size**: 900x650px (default), resizable (min: 800x600)
- **Title**: "vconv - Video Converter" + version
- **Layout**: Tab-based interface

#### Dialogs
| Dialog | Purpose | Type |
|--------|---------|------|
| Settings | Global preferences | Modal |
| Queue Manager | View/manage pending jobs | Modal |
| Batch Pre-check | Validate files before processing | Modal |
| Dependency Installer | Install missing tools | Modal |
| About | Version and credits | Modal |

### 1.2 Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  [Icon] vconv - Video Converter                    [─][□][×]│
├─────────────────────────────────────────────────────────────┤
│  [File] [Settings] [Help]                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────┬────────────────────────────────────┐   │
│  │                │                                    │   │
│  │   ┌─────────┐  │    ┌──────────────────────────┐    │   │
│  │   │ Convert │  │    │                          │    │   │
│  │   ├─────────┤  │    │    Drop Zone / File      │    │   │
│  │   │ Analyze │  │    │    List                  │    │   │
│  │   │ Presets │  │    │                          │    │   │
│  │   │ Queue   │  │    └──────────────────────────┘    │   │
│  │   └─────────┘  │                                    │   │
│  │                │    ┌──────────────────────────┐    │   │
│  │   Encoders:    │    │   Progress / Job Info    │    │   │
│  │   ─────────    │    └──────────────────────────┘    │   │
│  │   [✓] NVENC   │                                    │   │
│  │   [ ] x264    │    ┌──────────────────────────┐    │   │
│  │   [ ] x265    │    │   [Convert Now]  [Clear] │    │   │
│  │                │    └──────────────────────────┘    │   │
│  └────────────────┴────────────────────────────────────┘   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Ready | GPU: NVIDIA RTX 3060 detected | Files: 0          │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Visual Design

#### Color Palette
| Role | Color | Hex |
|------|-------|-----|
| Primary Background | Dark Slate | #1E1E2E |
| Secondary Background | Charcoal | #2D2D3D |
| Accent | Cyan Blue | #00B4D8 |
| Success | Green | #2ECC71 |
| Warning | Orange | #F39C12 |
| Error | Red | #E74C3C |
| Text Primary | White | #FFFFFF |
| Text Secondary | Gray | #A0A0B0 |
| Border | Dark Gray | #404050 |

#### Typography
- **Font Family**: "Segoe UI" (Windows), "Ubuntu" (Linux), "SF Pro" (macOS)
- **Headings**: 14px bold
- **Body Text**: 12px regular
- **Monospace** (logs): "Consolas" or "Monospace", 11px

#### Spacing System
- Base unit: 8px
- Margins: 16px (2 units)
- Padding: 8px (1 unit)
- Component gaps: 12px

### 1.4 Theme Support

| Theme | Description |
|-------|-------------|
| Dark (Default) | Dark slate with cyan accents |
| Light | Light gray with blue accents |
| System | Follow OS theme preference |

---

## 2. Functional Specification

### 2.1 Core Features

#### 2.1.1 File Input
- **Drag & Drop**: Single file, multiple files, folders
- **File Browser**: Native file dialog with filters (.mkv, .mp4, .avi, .mov, .webm, .wmv, .flv)
- **Recursive Add**: Option to scan subdirectories
- **Supported Formats**: MKV, MP4, AVI, MOV, WebM, WMV, FLV, M4V, MPG, MPEG

#### 2.1.2 Video Encoders

| Encoder | Type | Description | Best For |
|---------|------|-------------|----------|
| **nvenc_h265** | GPU (NVIDIA) | NVIDIA HEVC/H.265 encoder | Fast encoding, CUDA hardware |
| **nvenc_h264** | GPU (NVIDIA) | NVIDIA H.264 encoder | Fast encoding, compatibility |
| **qsv_h265** | GPU (Intel) | Quick Sync Video HEVC | Intel CPUs with iGPU |
| **qsv_h264** | GPU (Intel) | Quick Sync Video H.264 | Intel CPUs with iGPU |
| **amf_h265** | GPU (AMD) | AMD VCE/VCN HEVC | AMD GPUs (RX series) |
| **amf_h264** | GPU (AMD) | AMD VCE/VCN H.264 | AMD GPUs (RX series) |
| **x265** | CPU | x265 HEVC/H.265 | Quality-first, no GPU |
| **x264** | CPU | x264 H.264 | Maximum compatibility |
| **libsvtav1** | CPU | AV1/SVT-AV1 | Future-proof, small files |

**Encoder Selection Logic**:
1. Auto-detect available hardware on startup
2. Mark detected hardware with badge
3. Show "Recommended" badge for best option
4. Fallback to CPU encoder if no GPU detected

#### 2.1.3 Quality Settings

| Parameter | Range | Description |
|-----------|-------|-------------|
| RF (Rate Factor) | 0-51 | Lower = better quality, higher = smaller size |
| Preset | ultrafast..veryslow | Encoding speed vs compression |
| Profile | baseline, main, high | Compatibility level |
| Level | auto, 4.0, 4.1, etc. | Bitstream constraint |

**Recommended Presets**:
- Fast: RF 23-25 (good quality, fast)
- Medium: RF 20-22 (better quality)
- High: RF 18-20 (best quality, slower)

#### 2.1.4 Audio Settings

| Option | Values |
|--------|--------|
| Encoder | Copy, AAC, AC3, E-AC3, MP3, FLAC |
| Bitrate | 64, 96, 128, 160, 192, 224, 256, 320 kbps |
| Channels | Copy (original), Stereo, 5.1, 7.1 |
| Mixdown | Mono, Stereo, Dolby Surround, Dolby Pro Logic II |

#### 2.1.5 Output Settings

| Setting | Options | Default |
|---------|---------|---------|
| Format | MP4, MKV, WebM | MP4 |
| Output Location | Same as source, Custom | Same as source |
| Filename Conflict | Ask, Overwrite, Auto-rename | Ask |
| Container | MP4, MKV | MP4 |

**Filename Conflict Resolution**:
- **Ask**: Show dialog per file (default for single file)
- **Overwrite**: Silent overwrite with warning in log
- **Auto-rename**: Append `_1`, `_2`, etc. (default for batch)

#### 2.1.6 Filters

| Filter | Description | Parameters |
|--------|-------------|-------------|
| Denoise | Reduce video noise | Off, Light, Medium, Strong |
| Deinterlace | Remove interlacing | Off, On, Auto |
| Detelecine | Remove telecine | Off, On, Auto |
| Crop/Scale | Resize video | Custom dimensions |
| Rotation | Rotate video | 0°, 90°, 180°, 270° |

#### 2.1.7 Subtitle Handling

| Feature | Description |
|---------|-------------|
| Track Selection | Choose from available subtitle tracks |
| Burn-in | Burn subtitles into video |
| External SRT | Load external subtitle file |
| Language Filter | Filter by language code |

### 2.2 User Workflows

#### Workflow 1: Simple Convert
1. Drop file(s) into drop zone
2. Select encoder (or leave auto-detected)
3. Adjust quality slider
4. Click "Convert"
5. Monitor progress
6. Receive notification on completion

#### Workflow 2: Batch Processing
1. Add folder or multiple files
2. Click "Check All" - validates files BEFORE processing
3. Review conflicts (exist, output dir, etc.)
4. Resolve all conflicts (rename/overwrite options)
5. Confirm "Start Batch"
6. Watch queue progress
7. Individual job control available

#### Workflow 3: Analyze Only
1. Switch to "Analyze" tab
2. Drop files
3. View detailed media info
4. Optional: Send to convert

### 2.3 Data Architecture

#### Configuration Files

```
~/.config/vconv/
├── vconv.conf         # Main config (INI format)
├── presets.json      # Custom presets
├── themes/           # Theme files
│   ├── dark.json
│   └── light.json
├── logs/
│   └── vconv.log     # Application log
└── queue/
    └── queue.json    # Current queue state (for resume)
```

#### Config Schema (vconv.conf)
```ini
[general]
language = en
theme = dark
check_updates = true
log_level = info

[defaults]
encoder = auto
quality = 23
format = mp4
output_dir = source
conflict_resolution = ask

[ui]
window_size = 900x650
show_toolbar = true
```

### 2.4 Module Architecture

```
vconv/
├── vconv.py              # Main entry point
├── core/
│   ├── __init__.py
│   ├── encoder.py        # Encoder detection & management
│   ├── converter.py      # HandBrakeCLI wrapper
│   ├── analyzer.py       # Media analysis (ffprobe)
│   ├── validator.py      # File validation
│   └── queue.py          # Job queue management
├── ui/
│   ├── __init__.py
│   ├── main_window.py    # Main window
│   ├── dialogs.py        # All dialogs
│   ├── widgets.py        # Custom widgets
│   └── themes.py         # Theme system
├── utils/
│   ├── __init__.py
│   ├── config.py         # Config management
│   ├── logging.py        # Logging setup
│   ├── i18n.py           # Internationalization
│   └── tools.py          # Dependency checker/installer
├── presets/
│   └── default_presets.json
└── locales/
    ├── en.json
    ├── ar.json
    └── ar_eg.json
```

---

## 3. Feature Specifications

### 3.1 Hardware Detection

#### GPU Detection Logic
```python
def detect_hardware():
    nvidia_smi = run("n vainfo")
    if "NVIDIA" in nvidia_smi:
        return {"nvidia": True, "intel": False, "amd": False}
    # Check Intel Quick Sync
    if "VAProfileH264" in vainfo:
        return {"nvidia": False, "intel": True, "amd": False}
    # Check AMD VCE/VCN
    if "VAProfileH264" in vainfo and "AMD" in vainfo:
        return {"nvidia": False, "intel": False, "amd": True}
    return {"nvidia": False, "intel": False, "amd": False}
```

### 3.2 Dependency Management

#### Required Dependencies
| Tool | Purpose | Auto-install |
|------|---------|--------------|
| handbrakecli | Video encoding | Yes |
| ffmpeg/ffprobe | Analysis | Yes |
| python3 | Runtime | No (system) |
| python3-gi | GTK3 bindings | Yes |
| pyinstaller | Packaging | For release |

#### Installation Options
1. **Internal Install**: Download + compile/install in sandboxed location
2. **Manual Install**: Provide download link, user does it themselves
3. **System Package**: Use apt/dnf/pacman/zypper

### 3.3 Batch Pre-Validation

#### Pre-check Algorithm
```
1. Get list of all input files
2. For each file:
   a. Check if readable
   b. Check if valid video (ffprobe)
   c. Calculate output path
   d. Check if output exists
   e. Check disk space available
3. Collect all conflicts/warnings
4. Show dialog with summary:
   - Total files: X
   - Valid: Y
   - Conflicts: Z
   - Warnings: W
5. User resolves each conflict
6. Only then: Enable "Start Batch" button
```

### 3.4 Parallel Processing

| Setting | Description |
|---------|-------------|
| Off (Default) | Process files sequentially |
| 2 jobs | Process 2 files simultaneously |
| 3 jobs | Process 3 files simultaneously |
| Auto | Based on CPU cores - 2 |

**Warning UI**:
> "Parallel processing will increase overall throughput for multiple files but may slow down individual file encoding and increase CPU/GPU usage."

### 3.5 Internationalization

#### Supported Languages
| Code | Language | Direction |
|------|----------|-----------|
| en | English | LTR |
| ar | Arabic (Classical) | RTL |
| ar_eg | Egyptian Arabic | RTL |

#### RTL Support
- Mirror layout for Arabic
- Proper text alignment
- Icon placement adjustment

### 3.6 Job Queue Management

#### Queue Features
- View all pending/running/completed jobs
- Cancel individual job
- Cancel all jobs
- Reorder jobs (drag & drop)
- Save queue to file
- Resume queue after restart

#### Job States
| State | Description |
|-------|-------------|
| pending | Waiting to start |
| running | Currently encoding |
| completed | Finished successfully |
| failed | Encoding failed |
| cancelled | User cancelled |

### 3.7 Logging

#### Log Levels
| Level | When |
|-------|------|
| DEBUG | Verbose, all operations |
| INFO | Normal operations |
| WARNING | Non-critical issues |
| ERROR | Operation failed |
| CRITICAL | Fatal errors |

#### Log Format
```
[2026-02-14 15:30:45] [INFO] vconv: Application started
[2026-02-14 15:30:46] [INFO] hardware: Detected NVIDIA GPU
[2026-02-14 15:30:47] [INFO] encoder: Auto-selected nvenc_h265
[2026-02-14 15:30:48] [INFO] queue: Added 5 files to queue
[2026-02-14 15:31:00] [INFO] convert: Starting encode - movie.mkv
[2026-02-14 15:35:20] [INFO] convert: Completed movie.mkv (3:20)
```

---

## 4. Acceptance Criteria

### 4.1 Application Launch
- [ ] Application starts without errors
- [ ] GPU detection runs and shows result in status bar
- [ ] Missing dependencies trigger install dialog
- [ ] Previous settings are loaded

### 4.2 File Operations
- [ ] Drag & drop works for single/multiple files
- [ ] Drag & drop works for folders
- [ ] File browser opens and allows selection
- [ ] Invalid files show clear error message
- [ ] Duplicate output names prompt resolution dialog

### 4.3 Encoding
- [ ] All encoders produce valid output
- [ ] Progress bar updates in real-time
- [ ] Cancel stops current job properly
- [ ] Completed jobs show success message

### 4.4 Batch Processing
- [ ] Pre-validation catches all issues before start
- [ ] Batch processes all files in order
- [ ] Individual job cancel works
- [ ] All jobs cancel works

### 4.5 Settings
- [ ] All settings persist across restarts
- [ ] Presets can be saved and loaded
- [ ] Theme switching works
- [ ] Language switching works immediately

### 4.6 UI/UX
- [ ] All buttons have tooltips
- [ ] Keyboard shortcuts work
- [ ] Window resize works properly
- [ ] RTL layout correct for Arabic

---

## 5. Implementation Phases

### Phase 1: Foundation (v8.0.0)
- Project structure setup
- Config management
- Logging system
- Dependency checker
- Basic window framework

### Phase 2: Core Features (v8.1.0)
- Encoder detection
- File drop zone
- Basic conversion
- Progress tracking

### Phase 3: Batch & Queue (v8.2.0)
- Queue management UI
- Pre-validation
- Job control

### Phase 4: Polish (v8.3.0)
- Localization (EN, AR, AR-EG)
- Theme support
- Presets system
- Subtitle handling

### Phase 5: Release (v8.4.0)
- Documentation
- Testing
- Packaging

---

*Document Version: 1.0*
*Last Updated: 2026-02-14*