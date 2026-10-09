"""
Unit and integration tests for:
1. Audio track naming according to title, language, or fallback to movie name.
2. Subtitle track naming and language preservation in MKV/MP4 output.
3. Validate dialog parity for MP4 sources (always shows rich Validation & Optimization Report).
4. Efficiency notice parity for MP4 sources.
5. Media analysis parity with linked external subtitles and clean container display.
"""

import os
import sys
import tempfile
import subprocess
import json
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.converter import Converter, ConversionSettings, ISO639_LANG_NAMES
from core.encoder import EncoderManager
from core.validator import FileValidator
from core.analyzer import MediaAnalyzer, MediaInfo
from ui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication

_app = None
def get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv[:1])
    return _app

def check(desc, cond):
    if cond:
        print(f"[PASS] {desc}")
    else:
        print(f"[FAIL] {desc}")
        sys.exit(1)


def test_audio_and_subtitle_track_naming():
    conv = Converter(EncoderManager())
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "Inception (2010).mp4")
        srt_ar = os.path.join(td, "Inception.ara.srt")
        srt_en = os.path.join(td, "Inception.eng.srt")
        with open(srt_ar, 'w') as f: f.write("1\n00:00:01,000 --> 00:00:02,000\nمرحبا\n")
        with open(srt_en, 'w') as f: f.write("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        # Create source video with:
        # Audio 1: language 'eng', title 'Director Commentary'
        # Audio 2: language 'fre', no title
        # Audio 3: language 'und', no title
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=2:size=320x240:rate=1',
            '-f', 'lavfi', '-i', 'sine=duration=2',
            '-f', 'lavfi', '-i', 'sine=duration=2',
            '-f', 'lavfi', '-i', 'sine=duration=2',
            '-map', '0:v', '-map', '1:a', '-map', '2:a', '-map', '3:a',
            '-c:v', 'mpeg4', '-c:a', 'aac',
            '-metadata:s:a:0', 'language=eng',
            '-metadata:s:a:0', 'title=Director Commentary',
            '-metadata:s:a:0', 'handler_name=Director Commentary',
            '-metadata:s:a:1', 'language=fre',
            '-metadata:s:a:2', 'language=und',
            src
        ], check=True, capture_output=True)

        settings = ConversionSettings(
            output_format='mkv',
            external_srt_files=[(srt_ar, 'ara'), (srt_en, 'eng')]
        )

        # 1. Test audio track name resolution
        names = conv._resolve_audio_track_names(src, settings)
        check("Audio 1 with known title named 'Director Commentary'", names[0] == "Director Commentary")
        check("Audio 2 with known language named 'French'", names[1] == "French")
        check("Audio 3 with unknown language named after movie 'Inception (2010)'", names[2] == "Inception (2010)")

        # 2. Test subtitle arguments
        sub_args = conv._build_subtitle_args(settings, input_path=src)
        check("--srt-lang contains ara,eng", "--srt-lang" in sub_args and "ara,eng" in sub_args)
        check("--subname contains Arabic,English", "--subname" in sub_args and "Arabic,English" in sub_args)

        # 3. Test build command includes --aname
        cmd = conv._build_command(src, os.path.join(td, "out.mkv"), settings)
        check("--aname in command", "--aname" in cmd)
        aname_val = cmd[cmd.index("--aname") + 1]
        check("--aname value matches resolved names", aname_val == "Director Commentary,French,Inception (2010)")


def test_ffmpeg_copy_metadata_preservation():
    conv = Converter(EncoderManager())
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "Gladiator (2000).mp4")
        out = os.path.join(td, "Gladiator.mkv")
        srt_ar = os.path.join(td, "Gladiator.ara.srt")
        srt_en = os.path.join(td, "Gladiator.eng.srt")
        with open(srt_ar, 'w') as f: f.write("1\n00:00:01,000 --> 00:00:02,000\nمرحبا\n")
        with open(srt_en, 'w') as f: f.write("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', 'testsrc=duration=2:size=320x240:rate=1',
            '-f', 'lavfi', '-i', 'sine=duration=2',
            '-c:v', 'mpeg4', '-c:a', 'aac',
            '-metadata', 'title=Gladiator (2000)',
            src
        ], check=True, capture_output=True)

        # Encode with HandBrakeCLI using our exact flags
        cmd = [
            'HandBrakeCLI',
            '-i', src,
            '-o', out,
            '--format', 'mkv',
            '--encoder', 'x264',
            '--srt-file', f"{srt_ar},{srt_en}",
            '--srt-codeset', 'UTF-8,UTF-8',
            '--srt-lang', 'ara,eng',
            '--subname', 'Arabic,English'
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # Run _copy_metadata
        conv._copy_metadata(src, out, 'mkv', 'ffmpeg', None, 'ffprobe')

        # Probe output
        p = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', out], capture_output=True, text=True)
        data = json.loads(p.stdout)

        # Global container title must be Gladiator (2000)
        check("Global container title preserved", data.get('format', {}).get('tags', {}).get('title') == "Gladiator (2000)")

        # Subtitle streams MUST be Arabic and English, and NOT Gladiator (2000)!
        sub_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'subtitle']
        check("Output has 2 subtitle streams", len(sub_streams) == 2)
        check("Subtitle 1 language is ara", sub_streams[0].get('tags', {}).get('language') == 'ara')
        check("Subtitle 1 title is Arabic", sub_streams[0].get('tags', {}).get('title') == 'Arabic')
        check("Subtitle 2 language is eng", sub_streams[1].get('tags', {}).get('language') == 'eng')
        check("Subtitle 2 title is English", sub_streams[1].get('tags', {}).get('title') == 'English')


def test_validator_and_efficiency_notice_mp4():
    val = FileValidator()
    # Typical MP4 source: H.264 video at 4 Mbps, AAC stereo audio
    mp4_info = {
        'video': 'H.264',
        'resolution': '1920x1080',
        'video_bitrate': '4.2 Mbps',
        'audio': 'AAC',
        'audio_bitrate': '128 kbps',
    }

    # Bloat warnings list is empty (safe)
    warns = val.check_efficiency("/path/movie.mp4", mp4_info, quality=24, audio_encoder='copy')
    check("No bloat warnings for standard H.264 MP4", len(warns) == 0)

    # get_efficiency_feedback returns optimal status and clear projection
    fb = val.get_efficiency_feedback("/path/movie.mp4", mp4_info, quality=24, audio_encoder='copy', encoder='x265')
    check("Efficiency feedback status is optimal", fb['status'] == 'optimal')
    check("Efficiency feedback provides projection", "projected to achieve ~" in fb['message'] and "reduction" in fb['message'])


def test_ui_validate_and_analyze_mp4_parity():
    get_app()
    from ui.theme import apply_theme
    from utils.config import Config
    from utils.i18n import I18n
    apply_theme(get_app(), 'light')
    win = MainWindow(Config(), I18n(lang="en"))
    win.show()

    with tempfile.TemporaryDirectory() as td:
        mp4_file = os.path.join(td, "test_movie.mp4")
        srt_file = os.path.join(td, "test_movie.ara.srt")
        with open(mp4_file, 'wb') as f: f.write(b'\x00' * 1024)
        with open(srt_file, 'w') as f: f.write("1\n00:00:01,000 --> 00:00:02,000\nمرحبا\n")

        win.files = [mp4_file]
        win.file_subtitles[mp4_file] = [(srt_file, 'ara')]
        win._file_info_cache[mp4_file] = {
            'video': 'H.264',
            'resolution': '1920x1080',
            'video_bitrate': '4 Mbps',
            'audio': 'AAC 2ch',
            'audio_bitrate': '128 kbps',
            'duration': '01:45:00',
            'container_format': 'MOV,MP4,M4A,3GP,3G2,MJ2',
            'subtitle_streams': []
        }

        # 1. Test efficiency hint updates and stays visible with guidance for MP4
        win._update_efficiency_hint()
        check("Efficiency hint is visible for MP4", not win.efficiency_hint_label.isHidden())
        check("Efficiency hint contains guidance", "Efficiency Notice" in win.efficiency_hint_label.text())

        # 2. Test _on_file_analyzed triggers efficiency hint update
        win._on_file_analyzed(mp4_file, win._file_info_cache[mp4_file])
        check("Efficiency hint remains visible after _on_file_analyzed", not win.efficiency_hint_label.isHidden())

        # 3. Test MediaInfo container_display
        mi = MediaInfo(
            filename="test.mp4",
            filepath="/tmp/test.mp4",
            filesize="1.2 GB",
            container_format="MOV,MP4,M4A,3GP,3G2,MJ2",
            video_profile="High"
        )
        check("MediaInfo container_display is clean", mi.container_display == "MP4 (MPEG-4 Part 14)")
        check("MediaInfo video_profile captured", mi.video_profile == "High")

        # 4. Test subtitle language guessing
        check("Language guess 'ar' -> 'ara'", MainWindow._parse_subtitle_lang_code('ar') == 'ara')
        check("Language guess 'arabic' -> 'ara'", MainWindow._parse_subtitle_lang_code('arabic') == 'ara')
        check("Language guess 'en' -> 'eng'", MainWindow._parse_subtitle_lang_code('en') == 'eng')
        check("Language guess 'english' -> 'eng'", MainWindow._parse_subtitle_lang_code('english') == 'eng')

        # 5. Test queue job subtitle persistence
        win._add_file_to_queue(0)
        job = win.queue_manager.jobs[-1]
        check("Queue job preserves external_srt_files", job.settings.get('external_srt_files') == [(srt_file, 'ara')])

    win.close()


def test_audio_track_dialog_custom_title():
    get_app()
    from ui.main_window import AudioTrackDialog
    streams = [
        {'index': 1, 'language': 'eng', 'codec': 'AAC', 'title': ''},
        {'index': 2, 'language': 'ara', 'codec': 'AC3', 'title': 'Original'}
    ]
    dlg = AudioTrackDialog(streams, global_encoder='copy', global_bitrate=128, overrides={})
    title_edit = dlg.table.cellWidget(0, 5)
    title_edit.setText("Director Commentary")
    dlg._on_ok()
    ov = dlg.get_overrides()
    check("AudioTrackDialog captures custom title", ov[1].get('title') == "Director Commentary")


if __name__ == "__main__":
    print("=== Running Media Parity and Track Naming Tests ===")
    test_audio_and_subtitle_track_naming()
    test_ffmpeg_copy_metadata_preservation()
    test_validator_and_efficiency_notice_mp4()
    test_ui_validate_and_analyze_mp4_parity()
    test_audio_track_dialog_custom_title()
    print("\nALL PARITY AND TRACK NAMING TESTS PASSED!")
