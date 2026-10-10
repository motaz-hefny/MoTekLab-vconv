#!/usr/bin/env python3
"""
Test suite for v10.0.5 enhancements:
1. Dynamic visual fidelity and quality trade-off notices across RF ranges (RF 27, 40, 51, etc.).
2. Elimination of misleading 'excellent visual fidelity' on aggressive and extreme RF settings.
3. Metadata parity and symmetry across MKV and MP4 containers.
4. Deduplication of 4CC and freeform atoms in MP4 ilst builder.
5. MKV Tag 30/50 dual-level tagging completeness.
"""

import os
import sys
import tempfile
import struct
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validator import FileValidator, calculate_efficiency_forecast, get_efficiency_feedback
from core.converter import Converter, ConversionSettings

passed = 0
failed = 0

def check(desc: str, condition: bool):
    global passed, failed
    if condition:
        print(f"  ✓ {desc}")
        passed += 1
    else:
        print(f"  ✗ FAIL: {desc}")
        failed += 1

def test_efficiency_visual_fidelity_grading():
    print("\n--- Testing Visual Fidelity Grading (HEVC & AV1) ---")
    val = FileValidator()
    media_info = {
        'video': 'H.264',
        'video_codec': 'h264',
        'width': 1280,
        'height': 536,
        'video_bitrate': '1100 kbps',
        'audio': 'AAC',
        'audio_bitrate': '128 kbps',
        'filesize': '1.1 GB',
    }

    high_bitrate_info = {
        'video': 'H.264',
        'video_codec': 'h264',
        'width': 1920,
        'height': 1080,
        'video_bitrate': '8000 kbps',
        'audio': 'AAC',
        'audio_bitrate': '128 kbps',
        'filesize': '4.5 GB',
    }

    # 1. RF 22 (Near-Lossless on high-bitrate source)
    fb_22 = val.get_efficiency_feedback("/path/high_br.mp4", high_bitrate_info, quality=22, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 22 categorizes as Optimal", "Optimal:" in fb_22['message'])
    check("RF 22 notes near-lossless visual quality", "near-lossless visual quality" in fb_22['message'])

    # 2. RF 25 (Excellent Fidelity on high-bitrate source)
    fb_25 = val.get_efficiency_feedback("/path/high_br.mp4", high_bitrate_info, quality=25, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 25 categorizes as Optimal", "Optimal:" in fb_25['message'])
    check("RF 25 notes excellent visual fidelity", "excellent visual fidelity" in fb_25['message'])

    # 2b. RF 25 on low-bitrate (1.1 Mbps) warns about size increase (as user reported in v10.0.3)
    fb_25_low = val.get_efficiency_feedback("/path/movie.mp4", media_info, quality=25, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 25 on 1.1 Mbps warns about file size increase", "INCREASE file size" in fb_25_low['message'] and fb_25_low['status'] == 'warning')

    # 3. RF 27 (Excellent Fidelity)
    fb_27 = val.get_efficiency_feedback("/path/movie.mp4", media_info, quality=27, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 27 categorizes as Optimal", "Optimal:" in fb_27['message'])
    check("RF 27 notes excellent visual fidelity", "excellent visual fidelity" in fb_27['message'])

    # 4. RF 30 (Good Visual Quality / Balanced)
    fb_30 = val.get_efficiency_feedback("/path/movie.mp4", media_info, quality=30, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 30 categorizes as Optimal", "Optimal:" in fb_30['message'])
    check("RF 30 notes good visual quality (balanced size and fidelity)", "good visual quality (balanced size and fidelity)" in fb_30['message'])

    # 5. RF 34 (High Compression)
    fb_34 = val.get_efficiency_feedback("/path/movie.mp4", media_info, quality=34, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 34 categorizes as High Compression", "High Compression:" in fb_34['message'])
    check("RF 34 notes noticeable compression trade-offs", "noticeable compression trade-offs" in fb_34['message'])
    check("RF 34 does NOT claim excellent visual fidelity", "excellent visual fidelity" not in fb_34['message'])

    # 6. RF 40 (Aggressive Compression - user reported case!)
    fb_40 = val.get_efficiency_feedback("/path/movie.mp4", media_info, quality=40, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 40 categorizes as Aggressive Compression", "Aggressive Compression:" in fb_40['message'])
    check("RF 40 notes visible quality degradation and compression artifacts", "visible quality degradation and compression artifacts" in fb_40['message'])
    check("RF 40 accurately states prioritizing low file size over fidelity", "prioritizes low file size over fidelity" in fb_40['message'])
    check("RF 40 does NOT claim excellent visual fidelity", "excellent visual fidelity" not in fb_40['message'])
    check("RF 40 preserves size reduction forecast percentage", "projected to achieve ~" in fb_40['message'] and "reduction" in fb_40['message'])

    # 7. RF 51 (Extreme Compression - user reported case!)
    fb_51 = val.get_efficiency_feedback("/path/movie.mp4", media_info, quality=51, audio_encoder='copy', encoder='nvenc_h265')
    check("RF 51 categorizes as Extreme Compression (Low Quality)", "Extreme Compression (Low Quality):" in fb_51['message'])
    check("RF 51 notes severe visual degradation (heavy macroblocking and loss of detail)", "severe visual degradation (heavy macroblocking and loss of detail)" in fb_51['message'])
    check("RF 51 notes sacrificing visual quality for file size", "sacrifices visual quality for file size" in fb_51['message'])
    check("RF 51 does NOT claim excellent visual fidelity", "excellent visual fidelity" not in fb_51['message'])
    check("RF 51 preserves size reduction forecast percentage", "projected to achieve ~" in fb_51['message'] and "reduction" in fb_51['message'])

def test_efficiency_h264_grading():
    print("\n--- Testing Visual Fidelity Grading (H.264 Target) ---")
    val = FileValidator()
    media_info = {
        'video': 'MPEG-2',
        'width': 1920,
        'height': 1080,
        'video_bitrate': '15000 kbps',
        'audio': 'AC3',
        'audio_bitrate': '384 kbps',
    }

    # H.264 RF 22 -> Optimal / excellent visual fidelity
    fb_h264_22 = val.get_efficiency_feedback("/path/dvd.mpg", media_info, quality=22, audio_encoder='copy', encoder='x264')
    check("H.264 RF 22 notes excellent visual fidelity", "excellent visual fidelity" in fb_h264_22['message'])

    # H.264 RF 30 -> High Compression
    fb_h264_30 = val.get_efficiency_feedback("/path/dvd.mpg", media_info, quality=30, audio_encoder='copy', encoder='x264')
    check("H.264 RF 30 categorizes as High Compression", "High Compression:" in fb_h264_30['message'])

    # H.264 RF 35 -> Aggressive Compression
    fb_h264_35 = val.get_efficiency_feedback("/path/dvd.mpg", media_info, quality=35, audio_encoder='copy', encoder='x264')
    check("H.264 RF 35 categorizes as Aggressive Compression", "Aggressive Compression:" in fb_h264_35['message'])
    check("H.264 RF 35 does NOT claim excellent visual fidelity", "excellent visual fidelity" not in fb_h264_35['message'])

    # H.264 RF 45 -> Extreme Compression
    fb_h264_45 = val.get_efficiency_feedback("/path/dvd.mpg", media_info, quality=45, audio_encoder='copy', encoder='x264')
    check("H.264 RF 45 categorizes as Extreme Compression", "Extreme Compression (Low Quality):" in fb_h264_45['message'])

def test_mp4_ilst_builder_deduplication():
    print("\n--- Testing MP4 ilst Builder Deduplication ---")
    import inspect
    src = inspect.getsource(Converter._copy_metadata)
    check("_build_ilst_from_tags contains seen_4cc deduplication", "seen_4cc = set()" in src)
    check("_build_ilst_from_tags contains seen_freeform deduplication", "seen_freeform = set()" in src)
    check("_apply_mp4_metadata helper is defined", "def _apply_mp4_metadata(" in src)
    check("try_ffmpeg_copy calls _apply_mp4_metadata for MP4", "_apply_mp4_metadata(dest_path, tags, cover_data)" in src)
    check("try_explicit_metadata calls _apply_mp4_metadata for MP4", "_apply_mp4_metadata(dest_path, tags)" in src)

def test_mkv_tagging_completeness():
    print("\n--- Testing MKV Tag 30/50 Dual-Level Tagging Completeness ---")
    import inspect
    src = inspect.getsource(Converter._copy_metadata)
    check("Tag 30 includes ARTIST, LEAD_PERFORMER, PERFORMER", "_add_simple(tag_30, 'ARTIST', v, added_30)" in src)
    check("Tag 30 includes DATE_RELEASED and DATE_RECORDED", "_add_simple(tag_30, 'DATE_RELEASED', v, added_30)" in src)
    check("Tag 30 includes ENCODED_BY", "_add_simple(tag_30, 'ENCODED_BY', v, added_30)" in src)
    check("Tag 30 includes director, actor, genre, description, synopsis, composer", "lk in ('director', 'actor', 'genre', 'description', 'synopsis', 'composer', 'writer', 'written_by', 'screenwriter')" in src)

def main():
    test_efficiency_visual_fidelity_grading()
    test_efficiency_h264_grading()
    test_mp4_ilst_builder_deduplication()
    test_mkv_tagging_completeness()

    print(f"\n==========================================")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"==========================================")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
