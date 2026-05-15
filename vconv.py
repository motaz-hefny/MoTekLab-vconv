#!/usr/bin/env python3
"""
vconv - Video Converter CLI/GUI
A modern video conversion application powered by HandBrakeCLI

Author: MoTekLab
Version: 8.0.0
License: GPLv3
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to path
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


# Video file extensions to scan
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg'}


def parse_arguments():
    """Parse command line arguments."""
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

    # Folder options
    parser.add_argument(
        '--folder_in', '-i',
        type=str,
        default=None,
        help='Input folder containing video files (default: current directory)'
    )
    parser.add_argument(
        '--folder_out', '-O',
        type=str,
        default=None,
        help='Output folder for converted files (default: same as source)'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        default=True,
        help='Scan subdirectories (default: True)'
    )

    # Mode options
    parser.add_argument(
        '--gui', '-g',
        action='store_true',
        help='Launch GUI (default if no other mode specified)'
    )
    parser.add_argument(
        '--batch', '-b',
        action='store_true',
        help='Batch mode: scan and convert without GUI interaction'
    )
    parser.add_argument(
        '--analyze', '-a',
        action='store_true',
        help='Analyze files only, show info without converting'
    )

    # Encoding options
    parser.add_argument(
        '--encoder', '-e',
        type=str,
        default='auto',
        choices=['auto', 'nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264',
                 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1'],
        help='Video encoder (auto-detects best available)'
    )
    parser.add_argument(
        '--quality', '-q',
        type=int,
        default=27,
        metavar='0-51',
        help='RF quality value (lower=better quality, default: 27)'
    )
    parser.add_argument(
        '--preset', '-p',
        type=str,
        default=None,
        choices=['ultra_fast', 'fast', 'balanced', 'high_quality', 'archive',
                 'nvenc_fast', 'nvenc_quality', 'web_optimized', 'mobile', 'tv_show'],
        help='Use preset settings'
    )
    parser.add_argument(
        '--format', '-f',
        type=str,
        default='mp4',
        choices=['mp4', 'mkv'],
        help='Output format (default: mp4)'
    )

    # Audio options
    parser.add_argument(
        '--audio_encoder', '-ae',
        type=str,
        default='copy',
        choices=['copy', 'aac', 'ac3', 'mp3', 'flac'],
        help='Audio encoder (default: copy)'
    )
    parser.add_argument(
        '--audio_bitrate', '-ab',
        type=int,
        default=128,
        help='Audio bitrate in kbps (default: 128)'
    )

    # Technical options
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--no-check',
        action='store_true',
        help='Skip dependency check on startup'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset configuration to defaults'
    )
    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help='Show version information'
    )

    return parser.parse_args()


def show_version():
    """Display version information."""
    print("vconv - Video Converter")
    print("Version: 8.0.0")
    print("License: GPLv3")
    print("Powered by HandBrakeCLI")


def scan_folder(folder_path: str, recursive: bool = True) -> list:
    """
    Scan folder for video files.

    Args:
        folder_path: Path to scan
        recursive: Whether to scan subdirectories

    Returns:
        List of video file paths
    """
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


def analyze_files(files: list, analyzer: MediaAnalyzer):
    """Display media information for files."""
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
                print(f"   Subtitles: {len(info.subtitle_streams)} track(s)")
                for sub in info.subtitle_streams[:3]:
                    print(f"      - [{sub['language']}] {sub['title']}")
        else:
            print("   ❌ Unable to analyze file")

    print("\n" + "="*80)


def convert_files(files: list, args, logger, encoder_manager):
    """Convert files with settings from args."""
    # Determine encoder
    if args.encoder == 'auto':
        encoder = encoder_manager.get_recommended_encoder()
    else:
        encoder = args.encoder

    # Build settings
    settings = ConversionSettings(
        encoder=encoder,
        quality=args.quality,
        audio_encoder=args.audio_encoder,
        audio_bitrate=args.audio_bitrate if args.audio_encoder != 'copy' else None,
        output_format=args.format
    )

    logger.info(f"Conversion settings: encoder={encoder}, quality={args.quality}, format={args.format}")

    # Create converter
    converter = Converter(encoder_manager)

    total = len(files)
    success = 0
    failed = 0

    print("\n" + "="*80)
    print("BATCH CONVERSION STARTED")
    print(f"Files to convert: {total}")
    print(f"Output location: {args.folder_out or 'in-place'}")
    print("="*80)

    for idx, input_file in enumerate(files, 1):
        # Calculate output path
        if args.folder_out:
            # Preserve relative structure
            try:
                rel_path = input_file.relative_to(args.folder_in)
                output_dir = args.folder_out / rel_path.parent
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / (input_file.stem + f".{args.format}")
            except ValueError:
                # Different drives or can't compute relative path
                output_path = Path(args.folder_out) / (input_file.stem + f".{args.format}")
        else:
            # In-place (same as source)
            output_path = generate_output_path(str(input_file), format=args.format, conflict_mode='rename')

        print(f"\n[{idx}/{total}] Processing: {input_file.name}")
        print(f"   Output: {output_path}")

        # Run conversion
        success_flag = converter.convert(
            str(input_file),
            str(output_path),
            settings,
            progress_callback=lambda p: print(f"   Progress: {p.percent:.1f}%", end='\r')
        )

        if success_flag:
            print(f"   ✅ Completed")
            success += 1
        else:
            print(f"   ❌ Failed")
            failed += 1

    print("\n" + "="*80)
    print(f"CONVERSION COMPLETE: {success} succeeded, {failed} failed")
    print("="*80)

    return success, failed


def main():
    """Main entry point for vconv application."""
    args = parse_arguments()

    if args.version:
        show_version()
        sys.exit(0)

    # Determine input folder
    input_folder = args.folder_in if args.folder_in else os.getcwd()
    args.folder_in = input_folder

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(level=log_level)
    logger.info(f"Starting vconv v8.0.0...")
    logger.info(f"Input folder: {input_folder}")

    if args.folder_out:
        logger.info(f"Output folder: {args.folder_out}")

    # Load configuration
    config = Config()
    if args.reset:
        logger.info("Resetting configuration to defaults")
        config.reset_to_defaults()
    config.load()

    # Override config with CLI args (quality 27 default)
    config.set('defaults', 'quality', args.quality)
    config.set('defaults', 'encoder', args.encoder)
    config.set('defaults', 'format', args.format)

    # Setup internationalization
    i18n = I18n(lang=config.get('general', 'language', 'en'))

    # Check dependencies
    if not args.no_check:
        dep_checker = DependencyChecker()
        if not dep_checker.check_all():
            logger.warning("Some dependencies are missing")
            missing = dep_checker.get_missing()
            print("\n⚠️  Missing dependencies:")
            for dep in missing:
                print(f"   - {dep.name}: {dep.install_hint}")
            print("\nTo install: sudo apt-get install handbrake-cli ffmpeg")
        else:
            logger.info("All dependencies verified")

    # Hardware detection
    encoder_manager = EncoderManager()
    hw_info = encoder_manager.hardware
    print(f"\n🖥️  Detected hardware: {hw_info.name}")
    print(f"   Recommended encoder: {encoder_manager.get_recommended_encoder()}")

    # Scan for videos
    logger.info("Scanning for video files...")
    video_files = scan_folder(input_folder, args.recursive)

    if not video_files:
        print(f"\n❌ No video files found in: {input_folder}")
        sys.exit(0)

    print(f"\n📁 Found {len(video_files)} video file(s)")
    for f in video_files[:10]:
        print(f"   - {f}")
    if len(video_files) > 10:
        print(f"   ... and {len(video_files) - 10} more")

    # Determine mode of operation
    if args.analyze:
        # Analyze mode
        analyzer = MediaAnalyzer()
        analyze_files(video_files, analyzer)

    elif args.batch:
        # Batch mode (CLI conversion)
        success, failed = convert_files(video_files, args, logger, encoder_manager)
        logger.info(f"Batch complete: {success} succeeded, {failed} failed")

    else:
        # GUI mode (or default)
        try:
            from ui.main_window import MainWindow
            app = MainWindow(config=config, i18n=i18n, args=args)
            app.run()
        except ImportError as e:
            logger.warning(f"GUI not available: {e}")
            print("\n⚠️  GUI module not ready, switching to batch mode")
            args.batch = True
            success, failed = convert_files(video_files, args, logger, encoder_manager)

    logger.info("Application exited normally")


if __name__ == "__main__":
    main()