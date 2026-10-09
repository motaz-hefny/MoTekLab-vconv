#!/usr/bin/env python3
"""
Test suite for v9.9.0 hardening and security enhancements.
Tests atomic queue saving, permissions, batch validator,
ConversionWorker job settings isolation, and deb package validation.

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_v99_hardening.py
"""
import os
import sys
import tempfile
import stat
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.queue import QueueManager, Job, JobState
from core.validator import FileValidator
from core.converter import ConversionSettings
from utils.config import Config
from utils import self_update as su
import ui.main_window as mw

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


def test_queue_atomic_and_permissions():
    with tempfile.TemporaryDirectory(prefix="vconv_qtest_") as td:
        qm = QueueManager(config_dir=td)
        job = Job(id="job_1", input_path="/path/in.mp4", output_path="/path/out.mp4", settings={"quality": 22})
        qm.add_job(job)
        qfile = Path(td) / "queue.json"
        check("queue.json exists", qfile.exists())
        st = os.stat(qfile)
        mode = stat.S_IMODE(st.st_mode)
        check("queue.json has 0600 permissions", mode == 0o600)
        
        # Test reload
        qm2 = QueueManager(config_dir=td)
        check("queue reloaded job", len(qm2.jobs) == 1)
        check("queue job id matches", qm2.jobs[0].id == "job_1")
        check("queue job settings preserved", qm2.jobs[0].settings.get("quality") == 22)


def test_config_atomic_and_permissions():
    with tempfile.TemporaryDirectory(prefix="vconv_cfgtest_") as td:
        cpath = os.path.join(td, "vconv.conf")
        cfg = Config(cpath)
        cfg.set("defaults", "quality", 19)
        cfg.save()
        check("vconv.conf exists", os.path.exists(cpath))
        st = os.stat(cpath)
        mode = stat.S_IMODE(st.st_mode)
        check("vconv.conf has 0600 permissions", mode == 0o600)
        
        cfg2 = Config(cpath)
        check("reloaded config matches", cfg2.get("defaults", "quality") == 19)


def test_validate_batch_format():
    val = FileValidator()
    with tempfile.TemporaryDirectory(prefix="vconv_valtest_") as td:
        fake_video = os.path.join(td, "movie.mp4")
        with open(fake_video, "wb") as f:
            f.write(b"0" * 1024)
        out_dir = os.path.join(td, "out")
        os.makedirs(out_dir, exist_ok=True)
        
        results_mp4 = val.validate_batch([(fake_video, None)], output_dir=out_dir, format="mp4")
        check("validate_batch mp4 output ends with .mp4", results_mp4[0].output_path.endswith(".mp4"))
        
        results_mkv = val.validate_batch([(fake_video, None)], output_dir=out_dir, format="mkv")
        check("validate_batch mkv output ends with .mkv", results_mkv[0].output_path.endswith(".mkv"))


def test_conversion_worker_job_isolation():
    enc_mgr = mock.MagicMock()
    enc_mgr.to_handbrake_encoder.return_value = "x265"
    default_settings = ConversionSettings(encoder="x265", quality=27, output_format="mp4")
    
    worker = mw.ConversionWorker(
        files=None, output_base=None, settings=default_settings,
        encoder_manager=enc_mgr
    )
    
    # Check that job settings override default settings cleanly without mutating default
    job_settings = worker._build_job_settings({"encoder": "svt_av1", "quality": 20, "output_format": "mkv"})
    check("job settings encoder overridden", job_settings.encoder == "svt_av1")
    check("job settings quality overridden", job_settings.quality == 20)
    check("job settings output_format overridden", job_settings.output_format == "mkv")
    check("default settings intact", default_settings.encoder == "x265" and default_settings.quality == 27)


def test_install_deb_validation():
    with tempfile.TemporaryDirectory(prefix="vconv_debtest_") as td:
        fake_deb = Path(td) / "malicious.deb"
        fake_deb.write_text("dummy")
        
        # When dpkg-deb returns a package other than 'vconv'
        mock_proc = mock.MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "not-vconv\n"
        
        with mock.patch("shutil.which", side_effect=lambda cmd: f"/bin/{cmd}"):
            with mock.patch("subprocess.run", return_value=mock_proc):
                ok, msg = su.install_deb(fake_deb)
                check("deb rejecting non-vconv package", ok is False)
                check("message reports package validation failure", "Package validation failed" in msg)


def test_validator_check_efficiency():
    val = FileValidator()
    # HEVC file at RF 27 with heavy EAC3 768k audio
    hevc_info = {
        'video': 'HEVC',
        'video_bitrate': '568 kbps',
        'audio': 'EAC3',
        'audio_bitrate': '768 kbps',
    }
    warns = val.check_efficiency("/path/avatar.mkv", hevc_info, quality=27, audio_encoder='copy')
    check("efficiency warning generated for HEVC at RF 27", len(warns) >= 2)
    check("HEVC bloat warning present", any("already HEVC" in w for w in warns))
    check("Audio warning present", any("Audio track is high-bitrate" in w for w in warns))

    # Safe case: H.264 source converting to HEVC at RF 24 with AAC audio
    h264_info = {
        'video': 'H.264',
        'video_bitrate': '8 Mbps',
        'audio': 'AAC',
        'audio_bitrate': '128 kbps',
    }
    safe_warns = val.check_efficiency("/path/h264.mp4", h264_info, quality=24, audio_encoder='aac')
    check("no efficiency warnings for H.264 high-bitrate to HEVC", len(safe_warns) == 0)


def test_theme_toggle_and_efficiency_ui():
    from PyQt6.QtWidgets import QApplication
    from utils.i18n import I18n
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="vconv_uitest_") as td:
        cfg = Config(str(Path(td) / "vconv.conf"))
        win = mw.MainWindow(cfg, I18n("en"))
        check("theme_toggle_btn exists on toolbar", hasattr(win, 'theme_toggle_btn'))
        check("efficiency_hint_label exists", hasattr(win, 'efficiency_hint_label'))

        # Test toggle theme
        initial_theme = mw.active_theme()
        win._toggle_theme()
        toggled_theme = mw.active_theme()
        check("theme toggled to opposite", toggled_theme != initial_theme)
        win._toggle_theme()
        check("theme toggled back", mw.active_theme() == initial_theme)

        # Test efficiency hint label with HEVC file
        win.files.append("/test/avatar.mkv")
        win._file_info_cache["/test/avatar.mkv"] = {
            'video': 'HEVC', 'video_bitrate': '568 kbps',
            'audio': 'EAC3', 'audio_bitrate': '768 kbps'
        }
        win.quality = 27
        win._update_efficiency_hint()
        check("efficiency hint label visible for HEVC at RF 27", not win.efficiency_hint_label.isHidden())
        check("efficiency hint text mentions Efficiency", "Efficiency Notice" in win.efficiency_hint_label.text())

        win.close()


def test_optimal_presets_and_cli_help():
    import json
    preset_path = Path(__file__).parent.parent / "presets" / "default_presets.json"
    data = json.loads(preset_path.read_text())
    presets = data.get("presets", {})

    check("av1_efficient preset exists", "av1_efficient" in presets)
    check("av1_efficient uses svt_av1", presets["av1_efficient"].get("encoder") == "svt_av1")
    check("av1_efficient uses RF 27", presets["av1_efficient"].get("quality") == 27)
    check("av1_efficient uses speed 6", str(presets["av1_efficient"].get("preset")) == "6")
    check("av1_efficient preserves audio", presets["av1_efficient"].get("audio_encoder") == "copy")

    check("hevc_optimal preset exists", "hevc_optimal" in presets)
    check("hevc_optimal uses x265", presets["hevc_optimal"].get("encoder") == "x265")
    check("hevc_optimal uses RF 25", presets["hevc_optimal"].get("quality") == 25)
    adv = presets["hevc_optimal"].get("advanced", {})
    check("hevc_optimal disables sao", adv.get("no-sao") == 1)
    check("hevc_optimal uses aq-mode 3", adv.get("aq-mode") == 3)
    check("hevc_optimal preserves audio", presets["hevc_optimal"].get("audio_encoder") == "copy")

    from PyQt6.QtWidgets import QApplication
    from utils.i18n import I18n
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="vconv_presett_") as td:
        cfg = Config(str(Path(td) / "vconv.conf"))
        win = mw.MainWindow(cfg, I18n("en"))
        
        # Test applying av1_efficient
        win._apply_preset("av1_efficient")
        check("applied av1_efficient sets quality 27", win.quality == 27)
        check("applied av1_efficient sets svt_av1", win.encoder == "svt_av1")

        # Test applying hevc_optimal
        win._apply_preset("hevc_optimal")
        check("applied hevc_optimal sets quality 25", win.quality == 25)
        check("applied hevc_optimal sets x265", win.encoder == "x265")
        check("applied hevc_optimal sets preset_advanced", win.preset_advanced.get("no-sao") == 1)

        # Check CLI reference action exists in Help menu
        help_actions = [a.text() for a in win.menuBar().actions() if a.text() == "&Help"]
        check("Help menu present", len(help_actions) > 0)
        check("_show_cli_help callable", callable(getattr(win, '_show_cli_help', None)))

        win.close()


def test_cli_argument_presets():
    from vconv import parse_arguments
    import sys
    with mock.patch.object(sys, 'argv', ['vconv', '--batch', '-p', 'av1_efficient', '-i', '/tmp']):
        args = parse_arguments()
        check("CLI accepts preset av1_efficient", args.preset == "av1_efficient")
        check("CLI batch mode flag parsed", args.batch is True)

    with mock.patch.object(sys, 'argv', ['vconv', '--batch', '-p', 'hevc_optimal']):
        args2 = parse_arguments()
        check("CLI accepts preset hevc_optimal", args2.preset == "hevc_optimal")


def test_analyzer_bitrate_enrichment():
    from core.analyzer import MediaAnalyzer
    analyzer = MediaAnalyzer()
    
    probe_data = {
        "format": {
            "format_name": "matroska,webm",
            "duration": "7200.5",
            "bit_rate": "3500000"
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "24/1",
                "pix_fmt": "yuv420p10le",
                "tags": {
                    "BPS": "2800000"
                }
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "eac3",
                "channels": 6,
                "channel_layout": "5.1(side)",
                "sample_rate": "48000",
                "bit_rate": "640000",
                "tags": {
                    "language": "eng",
                    "title": "Surround 5.1"
                }
            },
            {
                "index": 2,
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "tags": {
                    "language": "eng",
                    "title": "English SDH"
                }
            }
        ]
    }
    
    info = analyzer._parse_probe_data("movie.mkv", "/path/movie.mkv", "2.5 GB", probe_data)
    check("parsed container format", info.container_format == "MATROSKA,WEBM")
    check("parsed overall bitrate", info.overall_bitrate == "3.5 Mbps")
    check("parsed video bitrate from tags BPS", info.video_bitrate == "2.8 Mbps")
    check("parsed bit depth 10", info.bit_depth == 10)
    check("parsed framerate", info.framerate == "24.00")
    check("audio stream count 1", len(info.audio_streams) == 1)
    check("audio stream bitrate", info.audio_streams[0]["bitrate"] == "640 kbps")
    check("audio stream sample rate", info.audio_streams[0]["sample_rate"] == "48 kHz")
    check("audio stream channels", "6ch" in info.audio_streams[0]["channels"])
    check("subtitle stream count 1", len(info.subtitle_streams) == 1)
    check("subtitle stream codec", info.subtitle_streams[0]["codec"] == "SUBRIP")


def test_copy_encoder_backend_and_settings():
    from core.encoder import EncoderManager
    from core.converter import Converter, ConversionSettings
    
    mgr = EncoderManager()
    avail = mgr.get_available_encoders()
    check("copy encoder in available encoders", "copy" in avail)
    check("copy encoder backend is ffmpeg", mgr.encode_backend("copy") == "ffmpeg")
    check("copy encoder supports 10bit", mgr.supports_10bit("copy") is True)
    check("copy encoder handbrake name is copy", mgr.to_handbrake_encoder("copy") == "copy")
    check("copy encoder not hardware accelerated", mgr.is_hardware_encoder("copy") is False)
    
    info = mgr.get_encoder_info("copy")
    check("copy encoder info name", "Copy (Passthrough)" in info.get("name", ""))
    
    # Test Converter._build_command for copy
    conv = Converter(mgr)
    
    # Default copy to MP4
    settings_mp4 = ConversionSettings(
        encoder="copy",
        audio_encoder="copy",
        output_format="mp4"
    )
    cmd_mp4 = conv._build_command("/tmp/input.mkv", "/tmp/output.mp4", settings_mp4)
    check("cmd_mp4 uses ffmpeg", "ffmpeg" in cmd_mp4[0])
    check("cmd_mp4 has -c:v copy", "-c:v" in cmd_mp4 and cmd_mp4[cmd_mp4.index("-c:v") + 1] == "copy")
    check("cmd_mp4 has -c:a copy", "-c:a" in cmd_mp4 and cmd_mp4[cmd_mp4.index("-c:a") + 1] == "copy")
    check("cmd_mp4 has mov_text subtitles", "-c:s" in cmd_mp4 and cmd_mp4[cmd_mp4.index("-c:s") + 1] == "mov_text")
    check("cmd_mp4 has faststart", "+faststart" in cmd_mp4)
    check("cmd_mp4 has progress pipe", "pipe:1" in cmd_mp4)
    check("cmd_mp4 has map_metadata 0", "-map_metadata" in cmd_mp4)
    
    # Copy to MKV with audio transcoding to aac 192k
    settings_mkv = ConversionSettings(
        encoder="copy",
        audio_encoder="aac",
        audio_bitrate=192,
        output_format="mkv"
    )
    cmd_mkv = conv._build_command("/tmp/input.mp4", "/tmp/output.mkv", settings_mkv)
    check("cmd_mkv has -c:v copy", "-c:v" in cmd_mkv and cmd_mkv[cmd_mkv.index("-c:v") + 1] == "copy")
    check("cmd_mkv has -c:a aac", "-c:a" in cmd_mkv and cmd_mkv[cmd_mkv.index("-c:a") + 1] == "aac")
    check("cmd_mkv has -b:a 192k", "-b:a" in cmd_mkv and cmd_mkv[cmd_mkv.index("-b:a") + 1] == "192k")
    check("cmd_mkv has -c:s copy", "-c:s" in cmd_mkv and cmd_mkv[cmd_mkv.index("-c:s") + 1] == "copy")


def test_ui_copy_and_dialogs():
    from PyQt6.QtWidgets import QApplication
    from utils.i18n import I18n
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="vconv_uitest2_") as td:
        cfg = Config(str(Path(td) / "vconv.conf"))
        win = mw.MainWindow(cfg, I18n("en"))
        
        # Test selecting copy in encoder combo
        copy_display = win._encoder_display("copy")
        check("found copy display in encoder map", bool(copy_display))
        win.encoder_combo.setCurrentText(copy_display)
        check("win.encoder is copy", win.encoder == "copy")
        check("quality_slider disabled when copy", not win.quality_slider.isEnabled())
        check("quality_label shows Lossless Copy", "Lossless Copy" in win.quality_label.text())
        check("efficiency hint shows Passthrough Active", "Passthrough Active" in win.efficiency_hint_label.text())
        
        # Switch back to x265 or recommended
        x265_display = win._encoder_display("x265")
        if x265_display:
            win.encoder_combo.setCurrentText(x265_display)
            check("win.encoder restored", win.encoder == "x265")
            check("quality_slider re-enabled", win.quality_slider.isEnabled())
        
        win.close()


def main():
    test_queue_atomic_and_permissions()
    test_config_atomic_and_permissions()
    test_validate_batch_format()
    test_conversion_worker_job_isolation()
    test_install_deb_validation()
    test_validator_check_efficiency()
    test_theme_toggle_and_efficiency_ui()
    test_optimal_presets_and_cli_help()
    test_cli_argument_presets()
    test_analyzer_bitrate_enrichment()
    test_copy_encoder_backend_and_settings()
    test_ui_copy_and_dialogs()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
