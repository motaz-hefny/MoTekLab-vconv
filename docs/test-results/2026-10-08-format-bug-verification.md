# Test Results — 2026-10-08

## Environment
- Qt platform: offscreen (QT_QPA_PLATFORM=offscreen)
- Python: 3.12
- HandBrakeCLI: present
- ffmpeg/ffprobe: present

## Format radio regression (tests/test_format_radio.py)
- All checks passed (14/14)
  - Initial state correct (mp4 selected)
  - Radio clicks update `MainWindow.format` (mkv/mp4)
  - MKV radio toggled handler fixes the desync
  - 10x flip-flop: no desync
  - `generate_output_path` uses correct extension per format

## E2E container verification (tests/test_e2e_format.py)
- All checks passed (6/6)
  - `--format mkv` passed to HandBrakeCLI; output container = matroska,webm
  - `--format mp4` passed to HandBrakeCLI; output container = mp4 family (mov,mp4,...)

## Real conversion verification (S01E20)
- Source: `/mnt/File_Server/Sources/00 - Media Files/02 TV Shows/Coven Academy (2026)/Season 01/Coven Academy - S01E20 - Bloodlines 2026.mkv` (untouched: size/mtime unchanged)
- Dest: `/home/motaz/Videos/Coven Academy (2026)/Coven Academy (2026)/Season 01/`
  - `Coven Academy - S01E20 - Bloodlines 2026.mkv` — container: matroska (✓)
  - `Coven Academy - S01E20 - Bloodlines 2026_fmttest.mp4` — container: mov,mp4,... (✓)

## Conclusion
MKV radio now correctly sets format and outputs .mkv with correct container. Fix is minimal (1 line in `ui/main_window.py`).
