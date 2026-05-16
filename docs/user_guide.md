# MoTekLab Video Encoder — User Guide

> Version 9.2.2 | PyQt6 + HandBrakeCLI
> Language: English

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Adding Files](#adding-files)
3. [Encoder Settings](#encoder-settings)
4. [Quality & Presets](#quality--presets)
5. [Output Options](#output-options)
6. [Audio Tracks](#audio-tracks)
7. [Subtitles](#subtitles)
8. [Conversion Queue](#conversion-queue)
9. [Progress & Monitoring](#progress--monitoring)
10. [Validation & Analysis](#validation--analysis)
11. [Settings Management](#settings-management)
12. [Command Line Interface](#command-line-interface)
13. [Keyboard Shortcuts](#keyboard-shortcuts)
14. [Troubleshooting](#troubleshooting)
15. [FAQ](#faq)

---

## Getting Started

### Quick Start

**The 30-second workflow:**

1. Launch vconv: `python3 vconv.py` or double-click the app
2. Click **➕ Files** or **➕ Folder** to add video files
3. Choose your **Encoder** and **Quality** settings (defaults are good for most users)
4. Click **🚀 CONVERT** and watch your files encode

**Step by step example — Converting a movie:**

```
1. Open vconv (GUI launches automatically)
2. Click "➕ Folder" → select "/Videos/Movies/"
3. App finds all .mkv and .mp4 files (up to 500)
4. Select "x265" encoder, RF 23 quality for high quality
5. Choose "MKV" format for subtitle/audio track support
6. Set subtitle mode to "copy", languages "eng"
7. Click "🚀 CONVERT"
8. Progress bars show encoding status for each file
9. When done, new files appear alongside originals with .mp4 extension
```

### First-Time Setup

vconv auto-detects your hardware and recommends the best encoder:

| Detected Hardware | Recommended Encoder | Why |
|---|---|---|
| NVIDIA GPU (any) | NVENC H.265 | Fastest encoding, good quality, low CPU usage |
| Intel GPU (6th gen+) | QSV H.265 | Low power, good for laptops |
| AMD GPU (RX series+) | AMF H.265 | Good balance of speed and quality |
| No GPU detected | x265 (CPU) | Highest quality, best compression, slower |

**What happens on first launch:**
1. Dependency check runs — verifies HandBrakeCLI and ffprobe exist
2. Hardware detection scans for NVIDIA/Intel/AMD GPUs
3. Configuration file is created at `~/.config/vconv/vconv.conf`
4. Default settings are applied (RF 27, x265, MP4, copy audio)

**If dependencies are missing:**
```
⚠️  Missing dependencies:
  - HandBrakeCLI: sudo apt-get install handbrake-cli
  - ffprobe: sudo apt-get install ffmpeg
```

### Prerequisites

**Required:**
- **HandBrakeCLI** — the actual encoding engine. Install:
  ```bash
  sudo apt-get install handbrake-cli      # Debian/Ubuntu
  sudo dnf install handbrake-cli           # Fedora
  sudo pacman -S handbrake                 # Arch
  brew install handbrake                   # macOS (Homebrew)
  ```

- **Python 3.8+** with **PyQt6**:
  ```bash
  pip install PyQt6
  ```

**Recommended:**
- **ffprobe** (comes with ffmpeg) — for file analysis:
  ```bash
  sudo apt-get install ffmpeg
  ```

**Optional:**
- **nvidia-smi** — for NVIDIA GPU detection
- **vainfo** — for Intel/AMD GPU detection
- **markdown** (Python package) — for the help browser to render properly:
  ```bash
  pip install markdown
  ```

---

## Adding Files

### Add Individual Files (➕ Files)

Opens a file browser to select one or more video files.

**Supported formats:**
```
MKV, MP4, AVI, MOV, WebM, WMV, FLV, M4V, TS, M2TS, MTS, VOB
```

**What if I select non-video files?**
The file browser filters by video extensions, so only valid types are shown. If you force-select a non-video file, validation will warn you before conversion.

**Example — Adding specific episodes:**
```
1. Click "➕ Files"
2. Navigate to /Videos/TV Show/Season 1/
3. Ctrl+click to select: ep1.mkv, ep3.mkv, ep5.mkv
4. Click "Open"
5. Only those 3 episodes appear in the file list
```

### Add Folder (➕ Folder)

Scan an entire folder recursively for all video files.

**How it works:**
- Searches all subdirectories automatically
- Finds all files with supported extensions (case-insensitive: .MKV, .Mkv, .mkv all work)
- Limited to 500 files per scan to prevent memory issues
- The folder you select becomes the **source root**

**Example — Adding a TV show season:**
```
Source folder: /Videos/TV Shows/Breaking Bad/Season 1/
Files found:  episode_01.mkv, episode_02.mkv, ..., episode_07.mkv
Source root set to: /Videos/TV Shows/Breaking Bad/Season 1/
```

**What if the folder has mixed content?**
Only video files are added. Text files, images, and other non-video files are ignored. Subtitle files in the folder are NOT auto-added — use the subtitle section in the left panel to add those.

### Folder Structure Preservation

**Default behavior (Same as source):**
Files are encoded in their original location. The new file sits right next to the original:
```
Before:  /Videos/Movie.mkv
After:   /Videos/Movie.mp4   (original Movie.mkv untouched)
```

**Custom folder with structure preservation:**
When using "Custom folder" with "Flat output" UNCHECKED:
```
Source:     /Videos/TV Show/Season 1/episode_01.mkv
Source root: /Videos/TV Show/        (the folder you added)
Output:     /Output/TV Show/Season 1/episode_01.mp4
```

**Custom folder with flat output:**
When "Flat output" is CHECKED:
```
Source:     /Videos/TV Show/Season 1/episode_01.mkv
Source root: /Videos/TV Show/
Output:     /Output/episode_01.mp4     (all files in one folder)
```

**What if files are from different drives?**
Example: `/mnt/disk1/video.mkv` and `/mnt/disk2/video.mkv`
The source root will be the common parent. If there's no common parent, files are placed at the root of the output folder.

**What if output path already exists?**
vconv does NOT overwrite files. If `output.mp4` exists, it creates `output_1.mp4`, `output_2.mp4`, etc.

### Managing the File List

| Button | What it does | When to use |
|--------|-------------|-------------|
| **➕ Files** | Add individual video files | When you need specific files |
| **➕ Folder** | Add entire folder recursively | For TV seasons, movie collections |
| **❌ Clear** | Remove ALL files from list | When starting fresh |
| **❌ Remove** | Remove SELECTED rows only | When you made a wrong selection |
| **📋 Add to Queue** | Move selected files to queue | When you want to batch later |

**Tip:** Select rows in the file table first, then click Remove or Add to Queue. If nothing is selected and you click "Add to Queue", ALL files are added.

---

## Encoder Settings

### Available Encoders

| Encoder | Type | Speed | File Size | Quality | Best For |
|---------|------|-------|-----------|---------|----------|
| **NVENC H.265** | NVIDIA GPU | ⚡ Very Fast (200+ fps) | Medium | Good | Gaming recordings, daily videos |
| **NVENC H.264** | NVIDIA GPU | ⚡ Very Fast (250+ fps) | Large | Fair | Streaming, compatibility |
| **QSV H.265** | Intel GPU | ⚡ Fast (150+ fps) | Medium | Good | Battery-saving encodes |
| **QSV H.264** | Intel GPU | ⚡ Fast (180+ fps) | Large | Fair | Quick H.264 encodes |
| **AMF H.265** | AMD GPU | ⚡ Fast (120+ fps) | Medium | Good | AMD GPU encodes |
| **AMF H.264** | AMD GPU | ⚡ Fast (150+ fps) | Large | Fair | AMD compatibility |
| **x265 (CPU)** | CPU | 🐢 Slow (20-50 fps) | Small | Excellent | Archival, best compression |
| **x264 (CPU)** | CPU | 🐢 Medium (50-100 fps) | Medium | Great | Universal compatibility |
| **SVT-AV1** | CPU | 🐢 Very Slow (5-15 fps) | Very Small | Best | Future-proof, smallest files |

**Speed estimates are for 1080p video on a modern 8-core CPU with NVIDIA RTX 2060 SUPER.**

### Hardware Acceleration

**How detection works:**
- NVIDIA: runs `nvidia-smi --query-gpu=name` 
- Intel: runs `vainfo` and checks for Intel in output
- AMD: runs `vainfo` and checks for AMD in output

**GPU vs CPU: Which should I choose?**

| Scenario | Recommended | Why |
|----------|-------------|-----|
| I want it done fast | NVENC/QSV/AMF | 3-5x faster than CPU |
| I want smallest file | x265 | Best compression, 30-50% smaller |
| I want best quality | x265 (RF 18-20) | More efficient encoding |
| I'm on a laptop battery | QSV | Uses less power |
| I'm converting a large library | NVENC | Fast enough, reasonable size |
| I'm archiving forever | x265 (RF 20) | Best size/quality tradeoff |

**What if my GPU encoder is not listed?**
- NVIDIA: you need an NVIDIA GPU with NVENC support (GTX 10-series or newer)
- Intel: requires integrated GPU with Quick Sync (6th gen Core or newer)
- AMD: requires AMD GPU with VCE/VCN (RX 400 series or newer)
- If your GPU supports it but it's not showing, check that HandBrakeCLI has GPU support compiled in

### Custom x264/x265 Parameters

Your personal tuned settings are applied by default to all x264/x265 encodes:

```
cabac=1:ref=5:analyse=0x133:me=umh:subme=9:chroma-me=1:
deadzone-inter=21:deadzone-intra=11:b-adapt=2:rc-lookahead=60:
vbv-maxrate=10000:vbv-bufsize=10000:qpmax=69:bframes=5:direct=auto
```

**What these parameters mean:**

| Parameter | Value | Effect |
|-----------|-------|--------|
| ref (reference frames) | 5 | Better compression, slightly slower |
| me (motion estimation) | umh | More accurate motion search, better quality |
| subme (subpixel refinement) | 9 | Very high quality motion estimation |
| bframes | 5 | Better compression with B-frames |
| rc-lookahead | 60 | Improves rate control and quality consistency |
| b-adapt | 2 | Intelligent B-frame placement |

**Why these settings?** They provide an excellent balance of quality and speed. Higher values would improve compression marginally but dramatically slow down encoding.

---

## Quality & Presets

### Quality (RF) Scale

RF (Rate Factor) is the primary quality control. **Lower = better quality, larger files.**

| RF | Visual Quality | File Size | Use Case |
|----|---------------|-----------|----------|
| **0** | Lossless | Huge | Professional mastering |
| **16-17** | Transparent | Very Large | You can't tell from original |
| **18-20** | Excellent | Large | Archival, best quality |
| **21-23** | Great | Good | High quality personal rips |
| **24-27** | Good | Medium | DEFAULT — best balance |
| **28-30** | Fair | Small | Mobile devices, tablets |
| **31-35** | Poor | Very Small | Streaming previews |
| **36-51** | Bad | Tiny | Not recommended |

**Visual quality comparison at different RF values (1080p source):**
```
RF 20: ~8 MB/min → Excellent, no visible artifacts
RF 23: ~5 MB/min → Very good, minor detail loss on zoom
RF 27: ~3 MB/min → Good, some detail loss, default
RF 30: ~2 MB/min → Fair, visible compression artifacts
RF 35: ~1 MB/min → Poor, blocky in dark scenes
```

**Rule of thumb:**
- RF 20 = "I'll keep this forever"
- RF 24 = "Good enough for most people"
- RF 27 = "Default — balanced quality"
- RF 30 = "I need to save space"

### Presets

| Preset | RF | Description | Best For |
|--------|-----|-------------|----------|
| **fast** | 27 | Quick encoding, balanced size | Drafts, testing |
| **balanced** | 25 | Slightly better than default | Everyday encoding (recommended) |
| **high_quality** | 22 | Significant quality improvement | Important videos, movies |
| **archive** | 20 | Best quality for storage | Long-term archiving |
| **nvenc_fast** | 27 | Fast NVIDIA GPU | Quick GPU encodes |
| **nvenc_balanced** | 25 | Balanced NVIDIA | Daily GPU use |
| **nvenc_quality** | 22 | High quality NVIDIA | GPU archival |
| **tv_show** | 24 | Optimized for TV | Television episodes |

**Can I create my own presets?**
Not yet — presets are loaded from `presets/default_presets.json`. You can edit this file directly to add custom presets. Custom preset creation in the GUI is planned for a future release.

### Advanced Quality Tips

**For x265 encodes:**
- RF 22 on x265 ≈ RF 18 on x264 (same visual quality, smaller file)
- Hardware encoders need lower RF for same quality (RF 22 NVENC ≈ RF 27 x265)
- 10-bit x265 is more efficient than 8-bit but not all devices support it

**File size estimation:**
```
Estimated size = bitrate × duration
Example: 3 MB/min × 120 min movie = 360 MB at RF 27
Actual sizes vary based on content complexity (action movies are larger)
```

---

## Output Options

### Same as Source (Default)

Files are encoded in their ORIGINAL location. The original is NEVER overwritten.

**Naming convention:**
```
Source:  /Videos/Movie.mkv
Output:  /Videos/Movie.mp4       (first time)
         /Videos/Movie_1.mp4     (if Movie.mp4 already exists)
         /Videos/Movie_2.mp4     (and so on)
```

**What if the output drive is full?**
HandBrakeCLI will fail with an error, and vconv will mark that file as failed. Free up space before retrying.

### Custom Folder

All output goes to a single destination folder.

**With structure preservation (default):**
```
Source:     /home/user/Videos/TV/Show/S01/ep1.mkv
Source root: /home/user/Videos/TV/Show/
Output:     /mnt/output/S01/ep1.mp4
```

**Without structure preservation (flat):**
Check "Flat output (dump all files in one folder)"
```
Source:     /home/user/Videos/TV/Show/S01/ep1.mkv
Source root: /home/user/Videos/TV/Show/
Output:     /mnt/output/ep1.mp4
```

**Real-world example — Converting a series for Plex:**
```
Source structure:
  /Videos/Plex/TV Shows/Breaking Bad/Season 1/S01E01.mkv
  /Videos/Plex/TV Shows/Breaking Bad/Season 1/S01E02.mkv
  /Videos/Plex/TV Shows/Breaking Bad/Season 2/S02E01.mkv

Add folder: /Videos/Plex/TV Shows/       # Source root
Output:     /mnt/plex/                   # Custom folder
Preserve structure: ON

Result:
  /mnt/plex/Breaking Bad/Season 1/S01E01.mp4
  /mnt/plex/Breaking Bad/Season 1/S01E02.mp4
  /mnt/plex/Breaking Bad/Season 2/S02E01.mp4
```

### Output Formats

| Feature | MP4 | MKV |
|---------|-----|-----|
| **Compatibility** | Excellent (all devices) | Good (most players) |
| **Streaming** | Yes (Fast Start option) | Yes |
| **Multiple audio tracks** | Limited (1-2 tracks) | Yes (unlimited) |
| **Multiple subtitle tracks** | Limited (soft subs not well supported) | Yes (unlimited) |
| **Chapters** | Yes | Yes |
| **Metadata** | Yes | Yes |
| **10-bit video** | Yes | Yes |
| **Lossless audio (FLAC)** | No | Yes |

**When to use MP4:**
- Uploading to YouTube, social media
- Playing on iPhone, PlayStation, Xbox
- Sharing with non-technical users
- Streaming over network

**When to use MKV:**
- Archiving with multiple audio tracks (commentary, different languages)
- Multiple subtitle languages
- FLAC lossless audio
- Anime with styled subtitles (ASS/SSA)
- Personal media server (Plex, Jellyfin)

---

## Audio Tracks

### Audio Encoder Options

| Encoder | Type | Bitrate Range | Quality | Best For |
|---------|------|--------------|---------|----------|
| **Copy** | Passthrough | N/A | Identical to source | Keeping original audio |
| **AAC** | Lossy | 64-512 kbps | Good | MP4 compatibility (default) |
| **AC3** | Lossy | 64-640 kbps | Good | Surround sound, home theater |
| **MP3** | Lossy | 32-320 kbps | Fair | Legacy devices, podcasts |
| **FLAC** | Lossless | N/A | Perfect | Archival, music videos |

**"Copy" mode explained:**
When you select "Copy", the audio is NOT re-encoded. It's taken from the source and placed into the output container without modification. This is:
- ✅ Fastest (no processing needed)
- ✅ No quality loss
- ❌ Usually results in larger files (no compression applied)
- ⚠️ Some audio formats may not be compatible with MP4 (use MKV instead)

**When do I need to re-encode audio?**
- When the original audio is a format your device doesn't support (e.g., TrueHD on an iPhone)
- When you want smaller files (MP3 at 128 kbps is much smaller than lossless FLAC)
- When you need downmixing (5.1 → stereo)

### Bitrate Guide

| Bitrate | Quality | File Size/Hour | Best For |
|---------|---------|---------------|----------|
| **64 kbps** | Poor | ~28 MB | Speech, podcasts, audiobooks |
| **96 kbps** | Fair | ~42 MB | Background music |
| **128 kbps** | Good | ~56 MB | Default — general use |
| **192 kbps** | Great | ~84 MB | Music, quality movies |
| **256 kbps** | Excellent | ~112 MB | High fidelity audio |
| **320 kbps** | Best | ~140 MB | Maximum quality MP3/AAC |

**Pro tip:** For most users, 128 kbps AAC sounds identical to the original. Unless you have high-end audio equipment, higher bitrates are wasted space.

### What Happens to Surround Sound?

When using "Copy" passthrough, surround sound is preserved exactly as-is.

When re-encoding, the audio is typically downmixed to stereo unless your encoder supports multichannel (AC3 supports up to 5.1).

---

## Subtitles

### Embedded Subtitles Mode

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Copy** | Keep source subtitles matching the **Language Filter** | You want specific language subs |
| **All** | Keep ALL embedded subtitle tracks | Every subtitle is preserved |
| **None** | Remove ALL subtitles from output | Clean video, no subs |

**Important:** HandBrakeCLI does NOT include subtitles by default. You must explicitly select "Copy" or "All" to keep them.

### Language Filter

Enter comma-separated ISO 639-2 codes:

| Code | Language | Code | Language | Code | Language |
|------|----------|------|----------|------|----------|
| eng | English | ara | Arabic | fre | French |
| spa | Spanish | ger | German | ita | Italian |
| jpn | Japanese | kor | Korean | chi | Chinese |
| rus | Russian | por | Portuguese | hin | Hindi |
| tur | Turkish | dut | Dutch | swe | Swedish |
| nor | Norwegian | dan | Danish | fin | Finnish |
| pol | Polish | cze | Czech | gre | Greek |
| heb | Hebrew | tha | Thai | vie | Vietnamese |

**Default:** `eng,ara` — keeps English and Arabic subtitles.

**Example scenarios:**
```
Keep only English:        eng
Keep English + Arabic:    eng,ara
Keep all European:        eng,fre,spa,ger,ita,por
Keep all languages:       leave blank or use "All" mode
```

### Burn Subtitles

"Burn" means subtitles are permanently drawn into the video image. They CANNOT be turned off.

**Burn these subtitle types:**
- Forced subtitles (foreign language parts in movies)
- When subtitle support is required on devices that don't support soft subtitles
- When converting to GIF or using in video editors

**Limitations:**
- Only ONE subtitle track can be burned at a time
- Burned subtitles increase file size slightly
- Cannot be hidden or disabled after encoding

### External Subtitles

**Supported formats:** SRT (SubRip), ASS (Advanced SubStation Alpha), SSA (SubStation Alpha), SUB (MicroDVD), VTT (WebVTT)

**Adding external subtitles:**
1. Click **➕ Add** below "External Subtitles"
2. Select one or more subtitle files (Shift+click for multiple)
3. A dialog asks: **"Select language for these subtitles"**
4. Choose the correct language code (e.g., "eng" for English, "ara" for Arabic)
5. The file appears in the list as `filename.srt [eng]`

**Per-file language example:**
```
Add "English.srt" → choose "eng" → list shows: English.srt [eng]
Add "Arabic.srt"  → choose "ara" → list shows: Arabic.srt [ara]
Add "French.srt"  → choose "fre" → list shows: French.srt [fre]
```

**Options:**
- **Burn external:** Hardcode external subs into the video
- **Set as default:** Make external subs the default playback track

**Character encoding for non-Latin scripts:**
Arabic, Chinese, Japanese, Korean, and all other non-Latin scripts are handled automatically using UTF-8 encoding. The `--srt-codeset UTF-8` flag is passed to HandBrakeCLI for every external SRT file.

**Example — Adding Arabic subtitles to a movie:**
```
1. Add the movie: "The Movie.mkv"
2. In Subtitles section:
   - Mode: "copy" (keep embedded English subs)
   - Languages: "eng,ara"
3. Add external subtitle:
   - Click "➕ Add"
   - Select "Arabic_SRT.srt"
   - Choose language: "ara"
   - List shows: Arabic_SRT.srt [ara]
4. Optional: Check "Burn external" if you want subs hardcoded
5. Convert → output has both embedded English and external Arabic subtitles
```

### Subtitle Track Ordering

When both embedded and external subtitles are present, the track order in the output is:
1. Embedded subtitles (from the source file)
2. External SRT files (in the order you added them)
3. External ASS/SSA files (in the order you added them)

---

## Conversion Queue

### Adding to Queue

**Three ways to add files to the queue:**

| Method | How | Result |
|--------|-----|--------|
| Select rows + click Add to Queue | Select files in table, click button | Only selected files added |
| Click Add to Queue (no selection) | Just click the button | ALL files added |
| File → Add to Queue (future) | Menu option | All files added |

**Workflow:**
```
1. Add files via "➕ Files" or "➕ Folder"
2. Review files in the Files table
3. (Optional) Select specific files
4. Click "📋 Add to Queue"
5. Switch to Queue table to review queued jobs
6. Click "▶ Start Queue" when ready
```

### Queue Operations

| Button | What It Does | When To Use |
|--------|-------------|-------------|
| **▶ Start Queue** | Process all pending jobs in sequence | Ready to encode |
| **❌ Remove Selected** | Delete selected rows from queue | Remove unwanted jobs |
| **🗑 Clear All** | Delete ALL jobs from queue | Restart fresh |

**What happens when I click Start Queue?**
1. All pending jobs are loaded into the file list
2. Conversion begins with the first file
3. Progress bars update in real-time
4. Each completed job is marked "completed" or "failed"
5. Queue state is saved after each job

### Queue Table Columns

| Column | Shows | Example |
|--------|-------|---------|
| **File** | Source filename | `episode_01.mkv` |
| **Output** | Destination filename | `episode_01.mp4` |
| **Progress** | Current encoding % | `72%` |
| **Status** | Job state | `pending`, `running`, `completed`, `failed`, `cancelled` |

### Queue States - What Each Means

| Icon/Badge | Meaning | What To Do |
|------------|---------|------------|
| **pending** | Waiting to be processed | Nothing — will run when queue starts |
| **running** | Currently encoding | Wait for it to finish |
| **completed** | Successfully encoded | Nothing — enjoy your file |
| **failed** | Encoding error occurred | Check error message, retry |
| **cancelled** | Manually stopped | Start again if needed |

### Queue Persistence

The queue is saved to `~/.config/vconv/queue.json` and loaded on next launch. This means:
- ✅ You can close vconv and come back later — queue is preserved
- ✅ If vconv crashes, the queue is recovered
- ❌ If you delete the file, the queue is lost

---

## Progress & Monitoring

### Progress Indicators

vconv has TWO progress bars:

```
[━━━━━━━━━━━━━━━━━━━━] Overall: 3/10 files    ← How many files done
[━━━━━━━━━━━━━━━━━━━━] Current file: 72%       ← Current encoding %
```

**What the status messages mean:**

| Status | Meaning |
|--------|---------|
| **Ready** | Idle — waiting for you to add files or click Convert |
| **Starting conversion...** | Preparing encoder settings |
| **Processing (3/10): filename.mp4** | File 3 of 10 is being encoded |
| **✅ Complete: 10 ok, 0 failed** | All files done successfully |
| **⏹ Stopped: 3 done, 5 skipped, 2 failed** | You cancelled mid-batch |
| **❌ Error: HandBrakeCLI not found** | Missing dependency |

### What If I Close vconv During Encoding?

1. The current encoding is **terminated** (the file will be incomplete/corrupt)
2. Any completed files are safe
3. The queue is saved (pending jobs remain)
4. On next launch, pending jobs are still in the queue

### Encoding Speed Factors

| Factor | Effect on Speed |
|--------|----------------|
| **Encoder** | x265 is 3-5x slower than NVENC |
| **Quality (RF)** | Lower RF = slower (RF 20 is ~2x slower than RF 30) |
| **Resolution** | 4K is 4x slower than 1080p |
| **CPU cores** | More cores = faster (x265 scales well to 16+ cores) |
| **GPU** | More CUDA cores = faster NVENC |

---

## Validation & Analysis

### Validate Files (✅ Validate)

Checks every file in your list for potential issues BEFORE conversion:

| Check | What It Detects | If It Fails |
|-------|----------------|-------------|
| File exists | Missing file | "File not found" error |
| Read permission | Can't read file | "No read permission" |
| Supported format | Wrong file type | "Unsupported file type" |
| Output path | Can't write | "Output directory not writable" |
| Disk space | Not enough space | "Insufficient disk space" |

**When to validate:**
- Always before a big batch conversion
- When adding files from network drives
- If you suspect files might be corrupted

### Analyze Files (📊 Analyze)

Runs ffprobe on each file and shows:

```
📄 The.Movie.2024.mkv
   🎬 H.265 1920x1080 | 8.5 GB | ⏱️ 02:15:30
   📝 Subtitles (3): [eng] English, [ara] Arabic, [fre] French
```

**What you can learn from analysis:**
- Video codec type and resolution
- File size and duration
- Audio codec
- Number of subtitle tracks and their languages
- Bitrate information

**Limitations:**
- Limited to 50 files per analysis to prevent slowdowns
- Requires ffprobe to be installed
- Analysis adds ~1-2 seconds per file

---

## Settings Management

### Saving Defaults

1. Configure all your preferred settings (encoder, quality, format, audio, subtitles, output)
2. Go to **File → Settings → Save Current as Default**
3. These settings will be loaded every time you start vconv

**What gets saved:**
- Encoder selection
- Quality (RF) value
- Output format (MP4/MKV)
- Audio encoder and bitrate
- Output directory preference

### Reset to Defaults

**File → Settings → Reset to Defaults**

Resets EVERYTHING to factory settings:
- Quality → RF 27
- Encoder → auto
- Format → MP4
- Audio → copy
- Window size and position are reset
- Last folder memory is cleared

### Default Folder

| Action | What It Does |
|--------|-------------|
| **Set Default Folder** | The file browser opens here by default |
| **Clear Default Folder** | File browser opens in your home directory |

### Configuration File

Location: `~/.config/vconv/vconv.conf`

```json
{
  "general": {
    "language": "en",
    "theme": "dark",
    "check_updates": true,
    "log_level": "info"
  },
  "defaults": {
    "encoder": "auto",
    "quality": 27,
    "format": "mp4",
    "audio_encoder": "copy",
    "audio_bitrate": 128,
    "last_folder": "/Videos"
  },
  "ui": {
    "window_width": 1250,
    "window_height": 800,
    "window_x": 100,
    "window_y": 100
  }
}
```

**Can I edit this file manually?**
Yes, but be careful with JSON syntax. vconv will reset to defaults if the file is corrupted.

### Logs

Location: `~/.config/vconv/logs/vconv.log`

The log file records:
- Every conversion command
- All errors and warnings
- Hardware detection results
- Configuration changes

---

## Command Line Interface

vconv can be used entirely from the terminal — no GUI required. This is useful for:
- **Servers** without a display
- **Scripts** and automation (cron jobs, CI/CD)
- **Remote sessions** (SSH)
- **Batch processing** large libraries

### Basic Usage

```bash
# Convert all videos in current directory (in-place)
vconv --batch

# Convert with custom settings
vconv --batch --encoder x265 --quality 23 --format mkv

# Specify input and output folders
vconv --folder_in /path/to/videos --folder_out /mnt/storage/converted --batch

# Analyze videos without converting
vconv --folder_in /path/to/videos --analyze

# Launch GUI
vconv --gui

# Show version
vconv --version

# Show all options
vconv --help
```

### All Command Line Options

| Option | Short | Description | Default | Example |
|--------|-------|-------------|---------|---------|
| `--folder_in` | `-i` | Input folder to scan | current directory | `-i /Videos` |
| `--folder_out` | `-O` | Output folder | same as source | `-O /output` |
| `--recursive` | `-r` | Scan subdirectories | true | `--no-recursive` |
| `--gui` | `-g` | Launch GUI | auto-detect | `--gui` |
| `--batch` | `-b` | Batch convert non-interactively | off | `--batch` |
| `--analyze` | `-a` | Analyze with ffprobe (no convert) | off | `--analyze` |
| `--encoder` | `-e` | Video encoder | auto | `-e nvenc_h265` |
| `--quality` | `-q` | RF quality (0-51) | 27 | `-q 23` |
| `--preset` | `-p` | Configuration preset name | none | `-p high_quality` |
| `--format` | `-f` | Output container | mp4 | `-f mkv` |
| `--audio_encoder` | `-ae` | Audio encoder | copy | `-ae aac` |
| `--audio_bitrate` | `-ab` | Audio bitrate in kbps | 128 | `-ab 192` |
| `--debug` | `-d` | Verbose logging | off | `--debug` |
| `--no-check` | | Skip dependency check | off | `--no-check` |
| `--reset` | | Reset configuration | off | `--reset` |
| `--version` | `-v` | Show version and exit | — | `--version` |

### Valid Values Reference

**`--encoder` / `-e`:**
```
auto            → Auto-detect best encoder
nvenc_h265      → NVIDIA HEVC (recommended for NVIDIA)
nvenc_h264      → NVIDIA H.264
qsv_h265        → Intel Quick Sync HEVC
qsv_h264        → Intel Quick Sync H.264
amf_h265        → AMD HEVC
amf_h264        → AMD H.264
x265            → CPU HEVC (best quality)
x264            → CPU H.264 (best compatibility)
libsvtav1       → CPU AV1 (smallest files)
```

**`--preset` / `-p`:**
```
fast            → RF 27, quick encode
balanced        → RF 25, everyday use
high_quality    → RF 22, better quality
archive         → RF 20, best quality
nvenc_fast      → RF 27, NVIDIA quick
nvenc_balanced  → RF 25, NVIDIA daily
nvenc_quality   → RF 22, NVIDIA quality
tv_show         → RF 24, television
web_optimized   → RF 25, web streaming
mobile          → RF 28, mobile devices
```

**`--format` / `-f`:** `mp4`, `mkv`

**`--audio_encoder` / `-ae`:**
```
copy    → Passthrough (no re-encode)
aac     → Advanced Audio Codec
ac3     → Dolby Digital
mp3     → MPEG Audio Layer 3
flac    → Free Lossless Audio Codec
```

### Complete CLI Examples

**1. Basic TV show conversion:**
```bash
cd "/mnt/tv/Breaking Bad/Season 1"
vconv --batch
# Scans:  ./*.mkv ./*.mp4 (recursive)
# Output: in-place .mp4 files
```

**2. Movie collection with high quality:**
```bash
vconv \
  --folder_in /mnt/movies \
  --folder_out /mnt/archive \
  --quality 20 \
  --encoder x265 \
  --format mkv \
  --audio_encoder copy \
  --batch
# Converts all movies in /mnt/movies to /mnt/archive
# Preserves folder structure
# x265 RF 20 - near-lossless quality
```

**3. Quick mobile-optimized encode:**
```bash
vconv -i /videos -O /phone -q 30 -e nvenc_h265 -f mp4 -ae aac -ab 96 --batch
# Fast NVENC encode at lower quality
# AAC audio at 96 kbps (good for phones)
# MP4 format for compatibility
```

**4. Analyze a folder of unknown videos:**
```bash
vconv --folder_in /downloads --analyze
# Shows codec, resolution, duration, subtitles for each file
# No conversion happens
```

**5. Convert with debug logging:**
```bash
vconv --folder_in /videos --batch --debug 2> convert.log
# All debugging info saved to convert.log
```

**6. Use a specific preset:**
```bash
vconv -i /videos -O /output -p high_quality --batch
# Applies RF 22 with balanced settings
```

**7. Full short-form command:**
```bash
vconv -i /src -O /dst -q 23 -e x265 -f mkv -ae copy --batch
```

**8. Convert files without GPU check:**
```bash
vconv --folder_in /videos --batch --no-check
# Skips hardware detection (saves ~2 seconds)
```

### Batch Mode Behavior

When running in `--batch` mode:

1. **Scanning phase:** All video files in the input folder are found recursively
2. **Analysis phase:** Hardware is detected, encoder recommended
3. **Conversion phase:** Each file is encoded one at a time
4. **Progress output:** Per-file progress printed to terminal
5. **Error handling:** If a file fails, batch continues with next file
6. **Completion:** Summary printed (X succeeded, Y failed)

**Sample batch output:**
```
📁 Found 10 video file(s)

🖥️  Detected: NVIDIA GeForce RTX 2060 SUPER
   Recommended: nvenc_h265

BATCH CONVERSION STARTED - 10 files
Encoder: nvenc_h265 | Quality: 27 | Format: mp4

[1/10] episode_01.mkv
   Progress: 45.2%
   ✅ Completed
[2/10] episode_02.mkv
   Progress: 12.8%
   ✅ Completed
...
COMPLETE: 10 succeeded, 0 failed
```

### Analyze Mode Output

```
ANALYSIS RESULTS
════════════════════════════════════════════════════

📄 The.Movie.2024.mkv
────────────────────────────────────────
   Duration:  02:15:30
   Size:      8.5 GB
   Video:     HEVC 1920x1080 @ 23.976 fps
   Bitrate:   8500 kbps
   Audio:     AAC 6ch (5.1)
   Subtitles (3):
      - [eng] English
      - [ara] Arabic
      - [fre] French
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F1** | Open Help Browser |
| **Shift + F1** | Enter What's This? mode (click any control) |
| **Ctrl + O** | Add video files |
| **Ctrl + Shift + O** | Add video folder |
| **Ctrl + Q** | Quit application |
| **Escape** | Cancel current operation |

**What's This? mode explained:**
Press `Shift+F1`, then click on any button, slider, or control in the window. A popup will explain what that control does.

---

## Troubleshooting

### Common Issues & Solutions

#### "HandBrakeCLI not found"
```
✅ Solution: Install HandBrakeCLI
sudo apt-get install handbrake-cli   # Debian/Ubuntu
sudo dnf install handbrake-cli        # Fedora
sudo pacman -S handbrake              # Arch
```

#### "ffprobe not available"
Analysis won't work without ffprobe. Conversion still works.
```
✅ Solution: Install ffmpeg (includes ffprobe)
sudo apt-get install ffmpeg
```

#### No video files found
```
Possible causes:
  ❌ Folder is empty
  ❌ Files have unsupported extensions (.ts, .vob not included by default)
  ❌ Permission denied
  
✅ Check:
  - File extensions match: .mkv .mp4 .avi .mov .webm .wmv .flv .m4v
  - Run: ls -la /path/to/folder
  - Check folder permissions
```

#### Subtitles not showing in output
```
Possible causes:
  ❌ Subtitle mode set to "none"
  ❌ Language filter doesn't match source subtitle languages
  ❌ External SRT file uses wrong character encoding (fixed in v9.1.0+)
  
✅ Fix:
  1. Set subtitle mode to "copy" or "all"
  2. Language filter: "eng" for English, "ara" for Arabic
  3. For external files: add them via the subtitle section
```

#### Encoder not showing in dropdown
```
Possible causes:
  ❌ Your GPU may not support that encoder type
  ❌ Required driver not installed
  
✅ NVIDIA: Check with: nvidia-smi
✅ Intel:   Check with: vainfo
✅ AMD:     Check with: vainfo | grep AMD

If nothing shows: your system doesn't have GPU encoding support
```

#### Output file is huge
```
Possible causes:
  ❌ RF value is too low (e.g., RF 18 creates very large files)
  ❌ Using hardware encoder at very low RF
  ❌ Audio passthrough of lossless format (TrueHD, DTS-MA)
  
✅ Fix:
  - Use RF 24-27 for normal use
  - For hardware encoders: RF 27 is recommended
  - Consider AAC 128 kbps audio instead of passthrough
```

#### Conversion is very slow
```
Possible causes:
  ❌ Using x265 at very low RF (RF 18 is 2-3x slower than RF 27)
  ❌ Encoding 4K video
  ❌ Running on a low-power CPU
  
✅ Speed up:
  - Use a hardware encoder (NVENC/QSV/AMF)
  - Increase RF value (27-30)
  - Reduce resolution (if possible)
  - Close other CPU-heavy applications
```

#### GUI crashes or fails to open
```
Possible causes:
  ❌ PyQt6 not installed correctly
  ❌ Display server issue (Wayland vs X11)
  
✅ Fix:
  pip install PyQt6
  export QT_QPA_PLATFORM=xcb   # Force X11 mode
  python3 vconv.py --batch     # Use CLI instead of GUI
```

#### Arabic subtitles show garbled characters
```
⚠️ This was a known issue in v9.0.0.
✅ Fixed in v9.1.0: UTF-8 encoding is now automatic.
If you still see issues, verify the SRT file is saved as UTF-8:
  file -i subtitle.srt
  # Should show: charset=utf-8
```

### Logs & Debug

```bash
# View the log file
cat ~/.config/vconv/logs/vconv.log

# Follow the log in real-time during conversion
tail -f ~/.config/vconv/logs/vconv.log

# Run with verbose debug output
python3 vconv.py --debug --batch

# Save debug output to file
python3 vconv.py --debug --batch 2>&1 | tee debug.log

# Check HandBrakeCLI version (for compatibility issues)
HandBrakeCLI --version

# Test HandBrakeCLI directly
HandBrakeCLI -i input.mkv -o output.mp4 --encoder x265 --quality 27
```

### Known Limitations

| Limitation | Details | Workaround |
|------------|---------|------------|
| **No parallel encoding** | Files are encoded one at a time | Open multiple instances of vconv |
| **No GPU decode** | HandBrakeCLI uses CPU for decoding | None (HandBrake limitation) |
| **MP4 subtitle limits** | MP4 doesn't support soft subtitles well | Use MKV for multiple subs |
| **500 file limit** | Folder scan limited to 500 files | Split into multiple folders |
| **No preview** | Can't preview output during encoding | Check after completion |
| **No HDR passthrough** | HDR metadata may be lost | Use x265 with appropriate settings |

### Performance Tips

**General:**
- Hardware encoders are 3-5x faster than CPU encoding
- RF 27 provides the best quality/size balance for most users
- Flat output avoids nested directory creation overhead
- Adding more than 500 files at once may slow down the UI

**File size optimization:**
- For smallest files: x265 RF 28-30
- For best quality: x265 RF 20-22
- Hardware encoders produce ~20% larger files than CPU at same RF

**Speed optimization:**
- Use NVENC for 4K content (dramatically faster than CPU)
- Don't use analysis on large batches unless needed
- Run on an SSD (disk I/O is often the bottleneck)

---

## FAQ

**Q: Does vconv overwrite my original files?**
A: No. Original files are never touched. Output files always have a different extension (.mp4/.mkv). If a file with the same name exists, a number suffix is added (`file_1.mp4`, `file_2.mp4`).

**Q: Can I convert to a different folder?**
A: Yes. Select "Custom folder" and choose your destination. Source folder structure is preserved by default. Check "Flat output" to dump all files in one folder.

**Q: Is hardware acceleration supported?**
A: Yes. NVIDIA NVENC, Intel QSV, and AMD AMF are all supported and auto-detected. The best encoder for your hardware is shown with a ✅ badge.

**Q: How do I keep subtitles in the output?**
A: Set subtitle mode to "Copy" or "All". Enter your language codes in the Language Filter (e.g., `eng` for English). External SRT/ASS files can be added separately in the Subtitles section.

**Q: Why is the output file so large?**
A: Lower RF values = larger files. Try RF 27-30 for smaller files. Hardware encoders also tend to produce larger files than CPU at the same RF. Audio passthrough of lossless formats (TrueHD, DTS-HD) can also add significant size.

**Q: What's the difference between "Copy" and "AAC" audio?**
A: "Copy" passes the audio through unchanged (fast, no quality loss, but larger). AAC re-encodes the audio (slower, slight quality loss, but can be much smaller).

**Q: Can I queue multiple jobs?**
A: Yes. Select files in the Files table, click "Add to Queue", then click "Start Queue". The queue persists between sessions.

**Q: Does vconv support AV1 encoding?**
A: Yes, via the `libsvtav1` encoder. It's CPU-only and very slow, but produces the smallest files at excellent quality.

**Q: How do I update vconv?**
A: Pull the latest version from GitHub:
```bash
cd MoTekLab-vconv
git pull
python3 vconv.py --version   # Verify new version
```

**Q: Can I run vconv on a server without a display?**
A: Yes. Use `--batch` mode or `--analyze` mode. No display required.

**Q: What should I do if a conversion fails?**
A: Check the log at `~/.config/vconv/logs/vconv.log`. Common causes: disk full, incompatible source file, HandBrakeCLI crash. Fix the issue and re-add the failed file to the queue.

**Q: How do I reset everything to defaults?**
A: Run `vconv --reset` or go to File → Settings → Reset to Defaults.

---

*Last updated: 2026-05-16 | MoTekLab Video Encoder v9.2.2 | Created by MoTekLab*
*Full documentation and updates at [moteklab.com](https://moteklab.com)*