#!/usr/bin/env python3
"""
MoTekLab Video Encoder — A modern video conversion application
powered by HandBrakeCLI and PyQt6.

Author: MoTekLab
License: GPLv3
"""

import sys
import os
import argparse
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.version import __version__, APP_NAME, APP_DISPLAY_NAME
from utils.logging import setup_logging
from utils.config import Config
from utils.i18n import I18n
from utils.tools import DependencyChecker
from core.encoder import EncoderManager
from core.converter import Converter, ConversionSettings
from core.handbrake_manager import HandBrakeManager
from core.validator import FileValidator, generate_output_path
from core.analyzer import MediaAnalyzer
from core.queue import QueueManager
from core.constants import VIDEO_EXTENSIONS


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='vconv',
        description=f"""{APP_DISPLAY_NAME} v{__version__}
High-Performance Video Conversion GUI & Headless CLI
Powered by HandBrakeCLI, FFmpeg & NVEncC""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Execution Modes:
  GUI Desktop Mode:
    vconv                                Launch GUI interface (or vconv --gui)
    vconv --folder_in /path/to/videos    Launch GUI preloaded with folder

  Headless CLI Batch Mode:
    vconv --batch                        Batch convert videos in current directory
    vconv --batch -i /input -O /output   Convert input folder to output destination
    vconv --batch -i /input -p av1_efficient   Convert using modern SVT-AV1 10-bit preset
    vconv --batch -i /input -p hevc_optimal    Convert using fine-tuned x265 10-bit preset
    vconv --batch -i /input -e nvenc_h265 -q 25 Fast NVIDIA GPU batch conversion
    vconv --analyze -i /input            Analyze media streams without converting

Available Presets:
  av1_efficient  - Modern SVT-AV1 10-bit (25-35% smaller than HEVC, RF 27) [RECOMMENDED]
  hevc_optimal   - x265 10-bit Film-Tuned (no-sao, dark AQ mode 3, RF 25) [RECOMMENDED]
  nvenc_optimal  - NVIDIA GPU high-efficiency balanced (RF 25)
  balanced       - x265 balanced everyday use (RF 27)
  fast           - x265 quick encoding (RF 27)
  high_quality   - x265 high fidelity (RF 23)
  archive        - x265 long-term preservation (RF 20)
  nvenc_fast/balanced/quality - NVIDIA GPU presets (RF 27/25/22)
  tv_show        - TV episodes optimization (RF 27)
  web_optimized  - H.264 streaming web compatibility (RF 25)
  mobile         - H.264 small file size for mobile devices (RF 28)
"""
    )

    parser.add_argument('--folder_in', '-i', type=str, default=None, help='Input folder (default: current directory)')
    parser.add_argument('--folder_out', '-O', type=str, default=None, help='Output folder (default: same as source)')
    parser.add_argument('--recursive', '-r', action='store_true', default=True, help=argparse.SUPPRESS)  # backward compat
    parser.add_argument('--no-recursive', action='store_true', default=False, help='Disable subdirectory scanning')
    parser.add_argument('--gui', '-g', action='store_true', help='Launch GUI')
    parser.add_argument('--batch', '-b', action='store_true', help='Batch mode')
    parser.add_argument('--analyze', '-a', action='store_true', help='Analyze only')
    parser.add_argument('--encoder', '-e', type=str, default=None,
                       choices=['auto', 'copy', 'x265', 'x264', 'svt_av1',
                                'nvenc_h265', 'nvenc_h264', 'nvenc_av1',
                                'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264',
                                'nvencc_hevc', 'nvencc_h264', 'nvencc_av1'],
                       help='Video encoder (default: from config or auto; "copy" for lossless passthrough)')
    parser.add_argument('--quality', '-q', type=int, default=None, metavar='0-51', help='RF quality (default: from config or 27)')
    parser.add_argument('--preset', '-p', type=str, default=None,
                       choices=['av1_efficient', 'hevc_optimal', 'nvenc_optimal',
                                'fast', 'balanced', 'high_quality', 'archive',
                                'nvenc_fast', 'nvenc_balanced', 'nvenc_quality',
                                'web_optimized', 'mobile', 'tv_show'])
    parser.add_argument('--format', '-f', type=str, default=None, choices=['mp4', 'mkv'], help='Output format (default: from config or mp4)')
    parser.add_argument('--audio_encoder', '-ae', type=str, default=None, choices=['copy', 'aac', 'ac3', 'mp3', 'flac'], help='Audio encoder (default: from config or copy)')
    parser.add_argument('--audio_bitrate', '-ab', type=int, default=None, help='Audio bitrate kbps (default: from config or 128)')
    parser.add_argument('--debug', '-d', action='store_true', help='Debug logging')
    parser.add_argument('--no-check', action='store_true', help='Skip dependency check')
    parser.add_argument('--reset', action='store_true', help='Reset config')
    parser.add_argument('--version', '-v', action='store_true', help='Show version')

    return parser.parse_args()


def show_version():
    print(f"{APP_DISPLAY_NAME}")
    print(f"Version: {__version__}")
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
            print(f"   Duration:         {info.duration or 'N/A'}")
            print(f"   Size:             {info.filesize}")
            if info.container_format:
                print(f"   Container:        {info.container_format}")
            if info.overall_bitrate:
                print(f"   Overall Bitrate:  {info.overall_bitrate}")
            print(f"   Video:            {info.video_codec} {info.width}x{info.height} @ {info.framerate or 'N/A'} fps ({info.bit_depth or 8}-bit, {info.pix_fmt or 'N/A'})")
            print(f"   Video Bitrate:    {info.video_bitrate or 'N/A'}")
            if info.audio_streams:
                print(f"   Audio Tracks ({len(info.audio_streams)}):")
                for idx, a in enumerate(info.audio_streams, 1):
                    parts = [f"#{idx}: {a.get('codec') or 'Unknown'}"]
                    if a.get('channels'):
                        parts.append(a['channels'])
                    if a.get('bitrate'):
                        parts.append(a['bitrate'])
                    if a.get('sample_rate'):
                        parts.append(a['sample_rate'])
                    if a.get('language') and a['language'] != 'unknown':
                        parts.append(f"[{a['language']}]")
                    if a.get('title'):
                        parts.append(f'"{a["title"]}"')
                    print(f"      - {' • '.join(parts)}")
            else:
                print(f"   Audio:            {info.audio_codec or 'N/A'} {info.audio_channels or ''}")
            if info.subtitle_streams:
                print(f"   Subtitles ({len(info.subtitle_streams)}):")
                for idx, sub in enumerate(info.subtitle_streams, 1):
                    parts = [f"#{idx}"]
                    if sub.get('codec'):
                        parts.append(sub['codec'])
                    if sub.get('language') and sub['language'] != 'unknown':
                        parts.append(f"[{sub['language']}]")
                    if sub.get('title'):
                        parts.append(f'"{sub["title"]}"')
                    print(f"      - {' • '.join(parts)}")
        else:
            print("   ❌ Unable to analyze")
    print("\n" + "="*80)


def convert_files_cli(files: list, args, logger, encoder_manager, config: Config = None):
    cfg_encoder = config.get('defaults', 'encoder', 'auto') if config else 'auto'
    cfg_quality = config.get('defaults', 'quality', 27) if config else 27
    cfg_format = config.get('defaults', 'format', 'mp4') if config else 'mp4'
    cfg_audio_enc = config.get('defaults', 'audio_encoder', 'copy') if config else 'copy'
    cfg_audio_bit = config.get('defaults', 'audio_bitrate', 128) if config else 128

    preset_data = {}
    if getattr(args, 'preset', None):
        try:
            import json
            p_path = PROJECT_ROOT / 'presets' / 'default_presets.json'
            if p_path.exists():
                all_presets = json.loads(p_path.read_text()).get('presets', {})
                preset_data = all_presets.get(args.preset, {})
        except Exception as e:
            logger.warning(f"Failed to load preset {args.preset}: {e}")

    req_encoder = args.encoder if getattr(args, 'encoder', None) is not None else (preset_data.get('encoder') or cfg_encoder)
    quality = args.quality if getattr(args, 'quality', None) is not None else (preset_data.get('quality') if 'quality' in preset_data else cfg_quality)
    fmt = args.format if getattr(args, 'format', None) is not None else (preset_data.get('format') or cfg_format)
    audio_enc = args.audio_encoder if getattr(args, 'audio_encoder', None) is not None else (preset_data.get('audio_encoder') or cfg_audio_enc)
    audio_bit = args.audio_bitrate if getattr(args, 'audio_bitrate', None) is not None else (preset_data.get('audio_bitrate') or cfg_audio_bit)

    encoder = encoder_manager.get_recommended_encoder() if req_encoder == 'auto' else req_encoder
    if req_encoder != 'auto' and not encoder_manager.is_available(encoder):
        logger.warning(f"Encoder {encoder!r} unavailable on this machine — using {encoder_manager.get_recommended_encoder()!r}")
        encoder = encoder_manager.get_recommended_encoder()

    hb_manager = HandBrakeManager()
    if encoder != 'copy' and not hb_manager.detect():
        print("❌ HandBrakeCLI not found. Install it first:")
        print("   sudo apt install handbrake-cli")
        sys.exit(1)

    settings = ConversionSettings(
        encoder=encoder, quality=quality,
        audio_encoder=audio_enc,
        audio_bitrate=audio_bit if audio_enc != 'copy' else None,
        output_format=fmt,
        advanced=preset_data.get('advanced'),
        encoder_preset=preset_data.get('preset'),
    )
    settings.metadata_preserve_flag = hb_manager.metadata_flag()
    converter = Converter(encoder_manager, hb_manager.get_command())
    total = len(files)
    success = 0
    failed = 0

    preset_info = f" | Preset: {args.preset}" if getattr(args, 'preset', None) else ""
    print("\n" + "="*80)
    print(f"BATCH CONVERSION STARTED - {total} files")
    print(f"Encoder: {encoder} | Quality: {quality} | Format: {fmt}{preset_info}")
    print(f"Output: {args.folder_out or 'in-place'}")
    print("="*80)

    for idx, input_file in enumerate(files, 1):
        if args.folder_out:
            try:
                rel_path = input_file.relative_to(args.folder_in)
                output_dir = Path(args.folder_out) / rel_path.parent
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / (input_file.stem + f".{fmt}")
            except ValueError:
                output_path = Path(args.folder_out) / (input_file.stem + f".{fmt}")
        else:
            output_path = Path(generate_output_path(str(input_file), format=fmt, conflict_mode='rename'))

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
    logger.info(f"Starting {APP_NAME} v{__version__}...")
    logger.info(f"Input folder: {input_folder}")

    config = Config()
    if args.reset:
        config.reset_to_defaults()
    config.load()

    if args.quality is not None:
        config.set('defaults', 'quality', args.quality)
    if args.encoder is not None:
        config.set('defaults', 'encoder', args.encoder)
    if args.format is not None:
        config.set('defaults', 'format', args.format)
    if args.audio_encoder is not None:
        config.set('defaults', 'audio_encoder', args.audio_encoder)
    if args.audio_bitrate is not None:
        config.set('defaults', 'audio_bitrate', args.audio_bitrate)

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

    recursive = not args.no_recursive
    if args.analyze or args.batch:
        video_files = scan_folder(input_folder, recursive)
        if not video_files:
            print(f"\n❌ No video files found in: {input_folder}")
            sys.exit(0)
        print(f"\n📁 Found {len(video_files)} video file(s)")

    if args.analyze:
        analyzer = MediaAnalyzer()
        analyze_files_cli(video_files, analyzer)
    elif args.batch:
        convert_files_cli(video_files, args, logger, encoder_manager, config)
    else:
        # Launch PyQt6 GUI
        try:
            from ui.main_window import launch as gui_launch
            gui_launch(config, i18n, args, encoder_manager)
        except Exception as e:
            logger.error(f"GUI failed: {e}")
            print(f"\n⚠️  GUI error: {e}")
            print("Falling back to batch mode...")
            video_files = scan_folder(input_folder, recursive)
            if video_files:
                convert_files_cli(video_files, args, logger, encoder_manager, config)


if __name__ == "__main__":
    main()