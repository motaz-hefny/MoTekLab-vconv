# vconv - Video Converter

<p align="center">
  <strong>A modern video conversion tool powered by HandBrakeCLI</strong>
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

**vconv** is a CLI-first video converter that scans folders and converts video files in place or to a new location. It's designed to work from any folder containing video files.

### Key Features

- **CLI-First Design**: Run from any folder to scan and convert video files
- **Smart Scanning**: Automatically finds video files in current directory and subdirectories
- **Hardware Acceleration**: Auto-detects NVIDIA, Intel, and AMD GPUs
- **Batch Processing**: Convert entire TV shows or movie collections
- **In-Place Encoding**: Output files saved in the same location as source (default)
- **Custom Quality Settings**: Your tuned HandBrakeCLI settings for best quality/size ratio

---

## Installation

### 1. Install Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install handbrake-cli ffmpeg python3-pysimplegui

# Fedora
sudo dnf install handbrake-cli ffmpeg python3-pysimplegui
```

### 2. Clone and Install

```bash
# Clone the repository
git clone https://github.com/motaz-hefny/MoTekLab-vconv.git
cd MoTekLab-vconv

# Run installation (creates PATH entry and start menu)
sudo python3 setup.py install
```

### Installation Options

The setup script will:
- ✅ Create symlink in `/usr/local/bin` (adds to PATH - run `vconv` from anywhere)
- ✅ Add to Start Menu under **Multimedia**
- ✅ Ask to create Desktop shortcut (optional)

### Manual Installation

```bash
# Add to PATH (requires sudo)
sudo ln -s $(pwd)/vconv.py /usr/local/bin/vconv

# Add to start menu
sudo cp vconv.desktop /usr/local/share/applications/
```

### Verify Installation

```bash
# Test
vconv --version

# Open GUI
vconv --gui

---

## Usage

### Basic Usage

```bash
# Run from current folder (scans current directory and subfolders)
./vconv.py

# Launch GUI
./vconv.py --gui
```

### Folder Options

```bash
# Specify input folder
./vconv.py --folder_in /path/to/videos

# Convert to different output folder (preserves folder structure)
./vconv.py --folder_in /mnt/movies --folder_out /mnt/converted

# Convert in place (default - same folder as source)
./vconv.py --folder_in /home/user/videos
```

### Mode Options

```bash
# Batch mode (non-interactive, converts all found files)
./vconv.py --batch

# Analyze files (show info without converting)
./vconv.py --analyze

# Launch GUI
./vconv.py --gui
```

### Encoding Options

```bash
# Quality (RF value: 0-51, lower=better quality, default: 27)
./vconv.py --quality 27
./vconv.py -q 23

# Encoder selection
./vconv.py --encoder nvenc_h265    # NVIDIA GPU
./vconv.py --encoder x265           # CPU
./vconv.py --encoder auto           # Auto-detect (default)

# Output format
./vconv.py --format mp4    # Default
./vconv.py --format mkv

# Use preset
./vconv.py --preset balanced   # Your favorite settings
./vconv.py --preset fast
./vconv.py --preset archive
```

### Examples

```bash
# Convert TV show folder in place
cd "/path/to/TV Show Season 1"
./vconv.py --batch

# Convert movies to new location with high quality
./vconv.py --folder_in /mnt/movies --folder_out /mnt/converted --quality 23 --batch

# Analyze a folder without converting
./vconv.py --folder_in /home/user/videos --analyze

# Use GPU encoding (if NVIDIA available)
./vconv.py --encoder nvenc_h265 --batch

# Quick convert with lower quality (smaller files)
./vconv.py --quality 30 --batch
```

---

## Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--folder_in` | `-i` | Input folder to scan | current directory |
| `--folder_out` | `-O` | Output folder (preserves structure) | same as source |
| `--recursive` | `-r` | Scan subdirectories | true |
| `--gui` | `-g` | Launch GUI | auto |
| `--batch` | `-b` | Batch mode (no interaction) | disabled |
| `--analyze` | `-a` | Analyze files only | disabled |
| `--encoder` | `-e` | Video encoder | auto |
| `--quality` | `-q` | RF quality (0-51) | 27 |
| `--preset` | `-p` | Use preset | none |
| `--format` | `-f` | Output format (mp4/mkv) | mp4 |
| `--audio_encoder` | `-ae` | Audio encoder | copy |
| `--audio_bitrate` | `-ab` | Audio bitrate (kbps) | 128 |
| `--debug` | `-d` | Enable debug logging | disabled |
| `--help` | `-h` | Show help | - |

---

## Encoders

| Encoder | Type | Best For |
|---------|------|----------|
| **nvenc_h265** | NVIDIA GPU | Fast HEVC encoding |
| **nvenc_h264** | NVIDIA GPU | Fast H.264 encoding |
| **qsv_h265** | Intel iGPU | Quick Sync Video |
| **qsv_h264** | Intel iGPU | Quick Sync Video |
| **amf_h265** | AMD GPU | AMD hardware encoding |
| **amf_h264** | AMD GPU | AMD hardware encoding |
| **x265** | CPU | Quality-first HEVC (default) |
| **x264** | CPU | Maximum compatibility |
| **libsvtav1** | CPU | Modern AV1 codec |

---

## Presets

| Preset | Quality | Description |
|--------|---------|-------------|
| **fast** | RF 27 | Quick encoding, good balance |
| **balanced** | RF 27 | Your personal favorite settings |
| **high_quality** | RF 23 | Better quality |
| **archive** | RF 20 | Best quality for storage |
| **tv_show** | RF 27 | Optimized for TV shows |
| **nvenc_fast** | RF 27 | Fast NVIDIA GPU |
| **nvenc_balanced** | RF 25 | Balanced NVIDIA |
| **nvenc_quality** | RF 22 | High quality NVIDIA |
| **web_optimized** | RF 25 | Web/streaming |
| **mobile** | RF 28 | Smaller files for mobile |

---

## Your Quality Settings

The default settings include your tuned HandBrakeCLI parameters:

```
cabac=1:ref=5:analyse=0x133:me=umh:subme=9:chroma-me=1:deadzone-inter=21:deadzone-intra=11:b-adapt=2:rc-lookahead=60:vbv-maxrate=10000:vbv-bufsize=10000:qpmax=69:bframes=5:direct=auto
```

These are applied by default when using x265/x264 encoders.

---

## Requirements

### System Requirements

- **OS**: Linux (Ubuntu/Debian, Fedora, Arch)
- **Python**: 3.8+

### Required Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install handbrake-cli ffmpeg

# Fedora
sudo dnf install handbrake-cli ffmpeg

# Arch
sudo pacman -S handbrake ffmpeg
```

---

## Troubleshooting

```bash
# Check logs
cat ~/.config/vconv/logs/vconv.log

# Run with debug
./vconv.py --debug --batch
```

---

## License

[GPLv3](LICENSE) - Created by MoTekLab

---

<p align="center">
  Made with ❤️
</p>