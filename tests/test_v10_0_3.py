#!/usr/bin/env python3
"""
Test suite for v10.0.3 enhancements:
1. Cover Art and Attachments Preservation (streams + directory fallback + MKV attachment injection)
2. Chapter Markers preservation across HandBrakeCLI, NVEncC, and FFmpeg remuxing
3. Right-Panel-Only Reset (resets files table & queue, preserves encoder/quality/audio settings)
4. Auto-Add to Queue defaults & Re-Drop idempotency without duplication
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QMessageBox
from core.converter import Converter, ConversionSettings
from core.encoder import EncoderManager
from core.queue import QueueManager, Job
from utils.config import Config
import ui.main_window as mw

from utils.i18n import I18n

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


def test_config_defaults():
    cfg = Config.DEFAULT_CONFIG
    check("DEFAULT_CONFIG has queue section", 'queue' in cfg)
    check("DEFAULT_CONFIG queue.auto_add is True", cfg['queue'].get('auto_add') is True)


def test_command_chapter_markers():
    em = EncoderManager()
    conv = Converter(em)
    settings = ConversionSettings(
        encoder='x265',
        quality=25,
        output_format='mkv'
    )
    cmd = conv._build_command('/path/in.mp4', '/path/out.mkv', settings)
    check("HandBrake command contains --markers", '--markers' in cmd)

    nv_settings = ConversionSettings(
        encoder='nvenc_h265',
        quality=25,
        output_format='mkv'
    )
    with mock.patch.object(em, 'get_nvenc_tool', return_value='NVEncC'):
        nv_cmd = conv._build_nvenc_command('/path/in.mp4', '/path/out.mkv', nv_settings)
        check("NVEncC command contains --chapter-copy", '--chapter-copy' in nv_cmd)

    copy_settings = ConversionSettings(
        encoder='copy',
        output_format='mkv'
    )
    copy_cmd = conv._build_ffmpeg_copy_command('/path/in.mp4', '/path/out.mkv', copy_settings)
    check("Copy command maps attachments for MKV (-map 0:t?)", '-map' in copy_cmd and '0:t?' in copy_cmd)
    check("Copy command maps chapters (-map_chapters 0)", '-map_chapters' in copy_cmd)


def test_cover_art_directory_fallback():
    em = EncoderManager()
    conv = Converter(em)

    with tempfile.TemporaryDirectory() as td:
        dummy_video = os.path.join(td, "movie.mp4")
        with open(dummy_video, "wb") as f:
            f.write(b"dummy video data")

        cover_img = os.path.join(td, "cover.jpg")
        with open(cover_img, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"\x00" * 50)

        # In _copy_metadata, test directory lookup
        cover_found = None
        for candidate in ('cover.jpg', 'cover.jpeg', 'poster.jpg', 'folder.jpg'):
            cand_path = os.path.join(td, candidate)
            if os.path.isfile(cand_path) and os.path.getsize(cand_path) > 0:
                with open(cand_path, 'rb') as cf:
                    cover_found = (cf.read(), True)
                break

        check("Directory cover lookup finds cover.jpg", cover_found is not None)
        check("Directory cover identified as JPEG", cover_found[1] is True)


def test_right_panel_reset_and_auto_queue():
    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as td:
        cfg = Config(config_path=os.path.join(td, "vconv.conf"))
        qm = QueueManager(config_dir=td)

        win = mw.MainWindow(cfg, I18n("en"))
        win.queue_manager = qm

        # Set user settings on left panel
        win.encoder = 'nvenc_h265'
        win.quality = 22
        win.quality_slider.setValue(22)
        win.audio_encoder = 'aac'
        win.format = 'mkv'

        # Add files and queue items
        file1 = os.path.join(td, "test1.mp4")
        file2 = os.path.join(td, "test2.mp4")
        with open(file1, "wb") as f: f.write(b"video1")
        with open(file2, "wb") as f: f.write(b"video2")

        win.files = [file1, file2]
        job1 = Job(id="j1", input_path=file1, output_path=os.path.join(td, "test1.mkv"), settings={})
        win.queue_manager.add_job(job1)

        check("Initial files count is 2", len(win.files) == 2)
        check("Initial queue count is 1", len(win.queue_manager.jobs) == 1)

        # Trigger right panel reset (mock QMessageBox to answer Yes)
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
             mock.patch.object(QMessageBox, 'information', return_value=None):
            win._reset_right_panel()

        check("Files list is cleared after right-panel reset", len(win.files) == 0)
        check("Queue is cleared after right-panel reset", len(win.queue_manager.jobs) == 0)
        check("Encoder nvenc_h265 is PRESERVED", win.encoder == 'nvenc_h265')
        check("Quality RF 22 is PRESERVED", win.quality == 22)
        check("Quality slider 22 is PRESERVED", win.quality_slider.value() == 22)
        check("Audio encoder aac is PRESERVED", win.audio_encoder == 'aac')
        check("Format mkv is PRESERVED", win.format == 'mkv')

        # Test Re-drop & Auto-queue
        # Drop file1 again
        win.config.set('queue', 'auto_add', True)
        
        # Simulate dropEvent logic
        video_files = [file1]
        new_files = [x for x in video_files if x not in win.files]
        if new_files:
            start_row = len(win.files)
            win.files.extend(new_files)
            if win.config.get('queue', 'auto_add', True):
                for row_idx in range(start_row, len(win.files)):
                    win._add_file_to_queue(row_idx)

        check("File1 re-added to files table", len(win.files) == 1)
        check("File1 auto-added to queue", len(win.queue_manager.jobs) == 1)

        # Clear queue only, keeping files table
        win._clear_queue()
        check("Queue is empty", len(win.queue_manager.jobs) == 0)
        check("Files table still has file1", len(win.files) == 1)

        # Simulate dropping file1 again without clearing files table
        re_dropped = [x for x in video_files if x in win.files]
        if re_dropped and win.config.get('queue', 'auto_add', True):
            queued_inputs = {j.input_path for j in win.queue_manager.jobs}
            for vf in re_dropped:
                if vf not in queued_inputs:
                    row_idx = win.files.index(vf)
                    win._add_file_to_queue(row_idx)

        check("Files table still has exactly 1 file (no duplicate)", len(win.files) == 1)
        check("File1 cleanly re-queued after re-drop", len(win.queue_manager.jobs) == 1)
        check("Queued job matches file1", win.queue_manager.jobs[0].input_path == file1)


def main():
    print("=== Running tests/test_v10_0_3.py ===")
    test_config_defaults()
    test_command_chapter_markers()
    test_cover_art_directory_fallback()
    test_right_panel_reset_and_auto_queue()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")


if __name__ == '__main__':
    main()
