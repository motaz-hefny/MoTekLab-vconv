# vconv - Video Converter GUI

<p align="center">
  <strong>A modern, feature-rich video conversion application powered by HandBrakeCLI</strong>
</p>

<p align="center">
  <a href="https://github.com/vconv-project/vconv/releases/latest">
    <img src="https://img.shields.io/github/v/release/vconv-project/vconv?include_prereleases&style=flat" alt="Version">
  </a>
  <a href="https://github.com/vconv-project/vconv/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/vconv-project/vconv?style=flat" alt="License">
  </a>
  <a href="https://github.com/vconv-project/vconv/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/vconv-project/vconv/build.yml?style=flat" alt="Build">
  </a>
</p>

---

## About

**vconv** is a standalone desktop application for video conversion on Linux. Built with Python 3, it provides a polished interface for [HandBrakeCLI](https://handbrake.fr/) with hardware acceleration detection, batch processing, and professional encoding options.

### Key Features

- **CLI-First Design**: Run from any folder to scan and convert video files in place
- **Smart Scanning**: Automatically finds video files in current directory and subdirectories
- **Hardware Acceleration**: Auto-detects NVIDIA, Intel, and AMD GPUs
- **Batch Processing**: Convert entire TV shows or movie collections with one command
- **In-Place Encoding**: Output files saved in the same location as source

### Powered By

| Tool | Role |
|------|------|
| [HandBrakeCLI](https://handbrake.fr/) | Video encoding engine |
| [FFprobe](https://ffmpeg.org/ffprobe.html) | Media analysis |
| Python 3 | Application runtime |

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/vconv-project/vconv.git
cd vconv

# Install dependencies
pip install -r requirements.txt

# Make executable
chmod +x vconv.py
```

### Usage

```bash
# Run from any folder containing video files
./vconv.py

# Scan subfolders and show GUI
./vconv.py --gui

# Run in batch mode (scan current folder, convert all)
./vconv.py --batch

# Analyze files without converting
./vconv.py --analyze

# Specify output quality
./vconv.py --quality 23

# Use specific encoder
./vconv.py --encoder nvenc_h265
```

---

## Usage Examples

### Convert TV Show Folder

```bash
# Navigate to your TV show folder
cd "/path/to/TV Show Season 1"

# Run vconv - it will scan all subfolders
vconv
```

### Batch Convert Multiple Shows

```bash
# From parent folder containing multiple shows
cd "/path/to/movies"

# Convert all videos in all subfolders
vconv --batch --quality 22
```

### Use Specific Preset

```bash
# Use "Archive" preset for best quality
vconv --preset archive

# Use "Fast" preset for quick conversion
vconv --preset fast --encoder nvenc_h265
```

---

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--gui` | Launch GUI (default when display available) | Enabled |
| `--batch` | Batch mode: scan and convert without interaction | Disabled |
| `--analyze` | Analyze files only, don't convert | Disabled |
| `--quality, -q` | RF quality value (0-51, lower = better) | 23 |
| `--encoder, -e` | Video encoder (auto, nvenc_h265, x265, etc.) | auto |
| `--preset, -p` | Use preset (fast, balanced, high_quality, archive) | None |
| `--output, -o` | Output format (mp4, mkv) | mp4 |
| `--recursive, -r` | Scan subdirectories | True |
| `--debug` | Enable debug logging | Disabled |
| `--help, -h` | Show help message | - |

---

## Requirements

### System Requirements

- **OS**: Linux (Ubuntu/Debian, Fedora, Arch, openSUSE)
- **Python**: 3.8 or higher
- **Display**: 800x600 minimum (for GUI mode)

### Required Dependencies

| Package | Description | Auto-install |
|---------|-------------|---------------|
| `handbrake-cli` | Video encoding | Yes |
| `ffmpeg` / `ffprobe` | Media analysis | Yes |
| `python3` | Runtime | No (system) |

### Hardware Acceleration (Optional)

| GPU | Encoder | Driver |
|-----|---------|--------|
| NVIDIA | NVENC | nvidia-driver |
| Intel | QSV | intel-media-driver |
| AMD | VCE/VCN | Mesa drivers |

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
| **x265** | CPU | Quality-first HEVC |
| **x264** | CPU | Maximum compatibility |
| **libsvtav1** | CPU | Modern AV1 codec |

---

## Configuration

Settings are stored in `~/.config/vconv/vconv.conf`

```json
{
  "general": {
    "language": "en",
    "theme": "dark"
  },
  "defaults": {
    "encoder": "auto",
    "quality": 23,
    "format": "mp4"
  }
}
```

---

## Releases

We provide releases in multiple formats:

| Format | Description | Target |
|--------|-------------|--------|
| **.deb** | Debian/Ubuntu package | Debian-based distros |
| **AppImage** | Portable format | Any Linux distro |
| **Source** | GitHub releases | Building from source |

### Installing .deb

```bash
sudo dpkg -i vconv_8.0.0_amd64.deb
```

### Running AppImage

```bash
chmod +x vconv_8.0.0.AppImage
./vconv_8.0.0.AppImage
```

---

## Troubleshooting

### Check Logs

```bash
cat ~/.config/vconv/logs/vconv.log
```

### Common Issues

| Issue | Solution |
|-------|----------|
| HandBrakeCLI not found | `sudo apt install handbrake-cli` |
| GPU not detected | Install GPU drivers |
| Permission denied | Check output directory permissions |

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs.

---

## License

This project is licensed under the [GPLv3 License](LICENSE).

---

<p align="center">
  Made with ❤️ for the open source community
</p>