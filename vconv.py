#!/usr/bin/env python3
"""
vconv - Video Converter GUI v9.0.0
A modern video conversion application powered by HandBrakeCLI
Built with PyQt6

Author: MoTekLab
Version: 9.0.0
License: GPLv3
"""

import sys
import os
import argparse
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.logging import setup_logging
from utils.config import Config
from utils.i18n import I18n
from utils.tools import DependencyChecker
from core.encoder import EncoderManager
from core.converter import Converter, ConversionSettings
from core.validator import FileValidator, generate_output_path
from core.analyzer import MediaAnalyzer
from core.queue import QueueManager


VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts', '.vob'}


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='vconv',
        description='vconv - Video Converter powered by HandBrakeCLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vconv                          Start GUI (scans current folder)
  vconv --gui                    Launch GUI interface
  vconv --batch                  Convert all videos in current folder
  vconv --folder_in /path/to/videos   Process specific folder
  vconv --folder_in /path --folder_out /output  Convert to different location
  vconv --quality 20 --encoder nvenc_h265  Use specific settings
  vconv --analyze                Analyze videos without converting
        """
    )

    parser.add_argument('--folder_in', '-i', type=str, default=None, help='Input folder (default: current directory)')
    parser.add_argument('--folder_out', '-O', type=str, default=None, help='Output folder (default: same as source)')
    parser.add_argument('--recursive', '-r', action='store_true', default=True, help='Scan subdirectories')
    parser.add_argument('--gui', '-g', action='store_true', help='Launch GUI')
    parser.add_argument('--batch', '-b', action='store_true', help='Batch mode')
    parser.add_argument('--analyze', '-a', action='store_true', help='Analyze only')
    parser.add_argument('--encoder', '-e', type=str, default='auto',
                       choices=['auto', 'nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1'])
    parser.add_argument('--quality', '-q', type=int, default=27, metavar='0-51', help='RF quality (default: 27)')
    parser.add_argument('--preset', '-p', type=str, default=None,
                       choices=['fast', 'balanced', 'high_quality', 'archive', 'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'web_optimized', 'mobile', 'tv_show'])
    parser.add_argument('--format', '-f', type=str, default='mp4', choices=['mp4', 'mkv'])
    parser.add_argument('--audio_encoder', '-ae', type=str, default='copy', choices=['copy', 'aac', 'ac3', 'mp3', 'flac'])
    parser.add_argument('--audio_bitrate', '-ab', type=int, default=128, help='Audio bitrate kbps')
    parser.add_argument('--debug', '-d', action='store_true', help='Debug logging')
    parser.add_argument('--no-check', action='store_true', help='Skip dependency check')
    parser.add_argument('--reset', action='store_true', help='Reset config')
    parser.add_argument('--version', '-v', action='store_true', help='Show version')

    return parser.parse_args()


def show_version():
    print("vconv - Video Converter")
    print("Version: 9.2.0")
    print("License: GPLv3")
    print("Powered by HandBrakeCLI")


def scan_folder(folder_path: str, recursive: bool = True) -> list:
    videos = []
    base_path = Path(folder_path)
    if recursive:
        for ext in VIDEO_EXTENSIONS:
            videos.extend(base_path.rglob(f"*{ext}"))
            videos.extend(base_path.rglob(f"*{ext.upper()}"))
    else:
        for ext in VIDEO_EXTENSIONS:
            videos.extend(base_path.glob(f"*{ext}"))
            videos.extend(base_path.glob(f"*{ext.upper()}"))
    return sorted(set(videos))


def analyze_files_cli(files: list, analyzer: MediaAnalyzer):
    print("\n" + "="*80)
    print("ANALYSIS RESULTS")
    print("="*80)
    for filepath in files:
        print(f"\n📄 {filepath.name}")
        print("-" * 40)
        info = analyzer.analyze(str(filepath))
        if info:
            print(f"   Duration:  {info.duration or 'N/A'}")
            print(f"   Size:      {info.filesize}")
            print(f"   Video:     {info.video_codec} {info.width}x{info.height} @ {info.framerate or 'N/A'} fps")
            print(f"   Bitrate:   {info.video_bitrate or 'N/A'}")
            print(f"   Audio:     {info.audio_codec} {info.audio_channels or 'N/A'}")
            if info.subtitle_streams:
                print(f"   Subtitles ({len(info.subtitle_streams)}):")
                for sub in info.subtitle_streams[:5]:
                    print(f"      - [{sub['language']}] {sub['title']}")
        else:
            print("   ❌ Unable to analyze")
    print("\n" + "="*80)


def convert_files_cli(files: list, args, logger, encoder_manager):
    encoder = encoder_manager.get_recommended_encoder() if args.encoder == 'auto' else args.encoder
    settings = ConversionSettings(
        encoder=encoder, quality=args.quality,
        audio_encoder=args.audio_encoder,
        audio_bitrate=args.audio_bitrate if args.audio_encoder != 'copy' else None,
        output_format=args.format
    )
    converter = Converter(encoder_manager)
    total = len(files)
    success = 0
    failed = 0

    print("\n" + "="*80)
    print(f"BATCH CONVERSION STARTED - {total} files")
    print(f"Encoder: {encoder} | Quality: {args.quality} | Format: {args.format}")
    print(f"Output: {args.folder_out or 'in-place'}")
    print("="*80)

    for idx, input_file in enumerate(files, 1):
        if args.folder_out:
            try:
                rel_path = input_file.relative_to(args.folder_in)
                output_dir = Path(args.folder_out) / rel_path.parent
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / (input_file.stem + f".{args.format}")
            except ValueError:
                output_path = Path(args.folder_out) / (input_file.stem + f".{args.format}")
        else:
            output_path = Path(generate_output_path(str(input_file), format=args.format, conflict_mode='rename'))

        print(f"\n[{idx}/{total}] {input_file.name}")
        print(f"   -> {output_path}")

        result = converter.convert(str(input_file), str(output_path), settings,
                                  progress_callback=lambda p: print(f"   Progress: {p.percent:.1f}%", end='\r'))
        if result:
            print(f"   ✅ Completed")
            success += 1
        else:
            print(f"   ❌ Failed")
            failed += 1

    print("\n" + "="*80)
    print(f"COMPLETE: {success} succeeded, {failed} failed")
    print("="*80)
    return success, failed


def main():
    args = parse_arguments()
    if args.version:
        show_version()
        sys.exit(0)

    input_folder = args.folder_in if args.folder_in else os.getcwd()
    args.folder_in = input_folder

    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(level=log_level)
    logger.info(f"Starting vconv v9.2.0...")
    logger.info(f"Input folder: {input_folder}")

    config = Config()
    if args.reset:
        config.reset_to_defaults()
    config.load()

    config.set('defaults', 'quality', args.quality)
    config.set('defaults', 'encoder', args.encoder)
    config.set('defaults', 'format', args.format)

    i18n = I18n(lang=config.get('general', 'language', 'en'))

    if not args.no_check:
        dep_checker = DependencyChecker()
        if not dep_checker.check_all():
            missing = dep_checker.get_missing()
            print("\n⚠️  Missing dependencies:")
            for dep in missing:
                print(f"   - {dep.name}: {dep.install_hint}")
            print("\nTo install: sudo apt-get install handbrake-cli ffmpeg")
        else:
            logger.info("All dependencies verified")

    encoder_manager = EncoderManager()
    hw_info = encoder_manager.hardware
    print(f"\n🖥️  Detected: {hw_info.name}")
    print(f"   Recommended: {encoder_manager.get_recommended_encoder()}")

    if args.analyze or args.batch:
        video_files = scan_folder(input_folder, args.recursive)
        if not video_files:
            print(f"\n❌ No video files found in: {input_folder}")
            sys.exit(0)
        print(f"\n📁 Found {len(video_files)} video file(s)")

    if args.analyze:
        analyzer = MediaAnalyzer()
        analyze_files_cli(video_files, analyzer)
    elif args.batch:
        convert_files_cli(video_files, args, logger, encoder_manager)
    else:
        # Launch PyQt6 GUI
        try:
            from ui.main_window import MainWindow
            from PyQt6.QtWidgets import QApplication
            app = QApplication(sys.argv)
            app.setApplicationName("vconv")
            app.setApplicationVersion("9.0.0")
            window = MainWindow(config=config, i18n=i18n, args=args, encoder_manager=encoder_manager)
            window.show()
            sys.exit(app.exec())
        except Exception as e:
            logger.error(f"GUI failed: {e}")
            print(f"\n⚠️  GUI error: {e}")
            print("Falling back to batch mode...")
            video_files = scan_folder(input_folder, args.recursive)
            if video_files:
                convert_files_cli(video_files, args, logger, encoder_manager)


if __name__ == "__main__":
    main()