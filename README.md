# MoTekLab Video Encoder

<p align="center">
  <strong>A modern video conversion tool powered by HandBrakeCLI & PyQt6</strong>
  <br>
  <a href="https://moteklab.com">moteklab.com</a>
</p>

<p align="center">
  <a href="https://github.com/motaz-hefny/MoTekLab-vconv/releases/latest">
    <img src="https://img.shields.io/github/v/release/motaz-hefny/MoTekLab-vconv?include_prereleases&style=flat" alt="Version">
  </a>
  <a href="https://github.com/motaz-hefny/MoTekLab-vconv/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/motaz-hefny/MoTekLab-vconv?style=flat" alt="License">
  </a>
</p>

---

## About

**MoTekLab Video Encoder** (formerly vconv) is a video converter GUI and CLI powered by HandBrakeCLI, built with PyQt6. Scan folders, convert video files in-place or to a new location, with hardware acceleration, subtitle handling, and a full conversion queue.

Version: **9.2.2** (PyQt6 rewrite)

### Key Features

- **PyQt6 GUI**: Modern, responsive interface with proper threading (no UI freezes)
- **Hardware Acceleration**: Auto-detects NVIDIA NVENC, Intel QSV, AMD AMF
- **Batch Processing**: Convert entire TV shows or movie collections
- **Conversion Queue**: Add files to queue, process sequentially
- **Real-time Progress**: Per-file and overall progress bars
- **Folder Structure Preservation**: Source directory tree mirrored in output by default
- **Subtitle Handling**: Embedded subtitle passthrough, external SRT/ASS/SSA import with per-file language tagging, burn-in support
- **Audio Tracks**: Passthrough or re-encode (AAC, AC3, MP3, FLAC) with configurable bitrate
- **CLI Interface**: Full command-line support for scripting and headless operation
- **Custom Quality Settings**: Your tuned HandBrakeCLI x265 parameters applied by default
- **Presets**: Fast, Balanced, High Quality, Archive, NVENC-optimized, TV Show
- **File Validation & Analysis**: Check files before converting, view media metadata
- **Comprehensive Help System**: Searchable help browser (F1), tooltips, What's This? context help (Shift+F1)

---

## Installation

### 1. Install Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install handbrake-cli ffmpeg python3-pyqt6

# Fedora
sudo dnf install handbrake-cli ffmpeg python3-qt6

# Arch
sudo pacman -S handbrake ffmpeg python-pyqt6
```

```bash
# Python dependencies
pip install PyQt6 markdown
```

### 2. Clone and Install (Development)

```bash
git clone https://github.com/motaz-hefny/MoTekLab-vconv.git
cd MoTekLab-vconv
pip install -r requirements.txt
# Or: sudo python3 setup.py install
```

### Quick Start (No Install)

```bash
pip install -r requirements.txt
python3 vconv.py --gui           # Launch GUI
python3 vconv.py --batch         # Batch convert current folder
python3 vconv.py --help          # All command line options
```

---

## Documentation

Full documentation is in the `docs/` folder:
- **`docs/user_guide.md`** — Comprehensive user guide with CLI reference, setup, troubleshooting, FAQ
- **`docs/future_plan.md`** — Roadmap of planned features from community requests

Press **F1** in the GUI for the searchable help browser.

---

## Usage

### GUI Mode

```bash
python3 vconv.py                 # Launch with GUI (default)
python3 vconv.py --gui           # Same as above
```

### Batch Mode (Headless)

```bash
# Convert all videos in current folder (in-place)
python3 vconv.py --batch

# Specify input/output folders
python3 vconv.py --folder_in /path/to/videos --folder_out /output --batch

# With custom settings
python3 vconv.py -i /videos -O /output -q 23 -e nvenc_h265 -f mp4 --batch
```

### Analyze Mode

```bash
python3 vconv.py --folder_in /path/to/videos --analyze
```

### All CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--folder_in` | `-i` | Input folder | current directory |
| `--folder_out` | `-O` | Output folder | same as source |
| `--recursive` | `-r` | Scan subdirectories | true |
| `--gui` | `-g` | Launch GUI | auto |
| `--batch` | `-b` | Batch convert (non-interactive) | off |
| `--analyze` | `-a` | Analyze only (ffprobe) | off |
| `--encoder` | `-e` | Video encoder | auto |
| `--quality` | `-q` | RF quality (0-51) | 27 |
| `--preset` | `-p` | Use preset | none |
| `--format` | `-f` | Output format (mp4/mkv) | mp4 |
| `--audio_encoder` | `-ae` | Audio encoder | copy |
| `--audio_bitrate` | `-ab` | Audio bitrate (kbps) | 128 |
| `--debug` | `-d` | Debug logging | off |
| `--no-check` | | Skip dependency check | off |
| `--reset` | | Reset config | off |
| `--version` | `-v` | Show version | — |

---

## Encoders

| Encoder | Type | Speed | Best For |
|---------|------|-------|----------|
| **nvenc_h265** | NVIDIA GPU | ⚡ Very Fast | Fast HEVC encoding |
| **nvenc_h264** | NVIDIA GPU | ⚡ Very Fast | Fast H.264, compatibility |
| **qsv_h265** | Intel GPU | ⚡ Fast | Low power HEVC |
| **qsv_h264** | Intel GPU | ⚡ Fast | Low power H.264 |
| **amf_h265** | AMD GPU | ⚡ Fast | AMD hardware encoding |
| **amf_h264** | AMD GPU | ⚡ Fast | AMD H.264 encoding |
| **x265** | CPU | 🐢 Slow | Best quality, compression |
| **x264** | CPU | 🐢 Medium | Maximum compatibility |
| **libsvtav1** | CPU | 🐢 Very Slow | Future-proof AV1 |

---

## Presets

| Preset | RF Quality | Speed | Description |
|--------|-----------|-------|-------------|
| fast | 27 | Fast | Quick encoding, balanced size |
| balanced | 25 | Medium | Everyday use (default) |
| high_quality | 22 | Slow | Better quality for important files |
| archive | 20 | Slow | Best quality for long-term storage |
| nvenc_fast | 27 | Very Fast | Quick NVIDIA GPU encoding |
| nvenc_balanced | 25 | Fast | Balanced NVIDIA quality/speed |
| nvenc_quality | 22 | Medium | High quality NVIDIA encoding |
| tv_show | 24 | Medium | Optimized for television episodes |

---

## Project Structure

```
vconv/
├── vconv.py              # Main entry point
├── core/                 # Backend modules
│   ├── constants.py      # Shared constants (video extensions, etc.)
│   ├── converter.py      # HandBrakeCLI wrapper, subtitle args
│   ├── encoder.py        # Hardware detection (NVENC/QSV/AMF)
│   ├── analyzer.py       # ffprobe media analysis
│   ├── validator.py      # File validation
│   └── queue.py          # Job queue management
├── ui/                   # GUI modules
│   ├── main_window.py    # PyQt6 main window
│   └── help_browser.py   # Searchable help browser
├── utils/                # Utilities
│   ├── version.py        # Central version string
│   ├── config.py         # JSON config management
│   ├── i18n.py           # Internationalization
│   ├── logging.py        # Logging setup
│   ├── updater.py        # GitHub release update checker
│   └── tools.py          # Dependency checker
├── legacy/               # Legacy Bash scripts (archived)
├── docs/                 # Documentation
│   ├── user_guide.md     # Comprehensive user guide (EN)
│   ├── user_guide.ar.md  # User guide (AR)
│   ├── future_plan.md    # Feature roadmap
│   ├── release_process.md # Build pipeline guide
│   └── upgrade_audit.md  # Code audit & recommendations
├── presets/              # Preset files
├── locales/              # Translation files (en, ar, ar_eg)
├── public/               # Image assets (icon, banner, splash)
├── CHANGELOG.md          # Version history
└── README.md             # This file
```

---

## Requirements

- **OS**: Linux (Ubuntu/Debian, Fedora, Arch)
- **Python**: 3.8+
- **HandBrakeCLI**: Required for conversion (`apt install handbrake-cli`)
- **ffprobe**: Recommended for analysis (`apt install ffmpeg`)
- **PyQt6**: GUI framework (`pip install PyQt6`)

---

## Troubleshooting

```bash
# Check logs
cat ~/.config/vconv/logs/vconv.log

# Run with debug
python3 vconv.py --debug --batch

# Reset configuration
python3 vconv.py --reset

# Help in GUI
Press F1 for help browser
Press Shift+F1 then click any control for context help
```

---

## License

[GPLv3](LICENSE) — Created by MoTekLab

---

<p align="center">
  <a href="https://moteklab.com">moteklab.com</a> &middot; Made with ❤️
</p>