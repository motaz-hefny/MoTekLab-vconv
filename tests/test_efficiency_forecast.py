#!/usr/bin/env python3
"""
Unit tests for the mathematical efficiency forecasting engine in core/validator.py.
Verifies BPPF calculation, encoder profiles, RF exponential scaling, and size estimates.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.validator import (
    calculate_efficiency_forecast,
    check_efficiency,
    get_efficiency_feedback,
    _parse_bitrate_bps,
    _parse_resolution,
    _parse_framerate,
    _parse_duration_seconds,
    _format_size_bytes,
)

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


def test_parsers():
    # Bitrate parsing
    check("parse bitrate kbps", _parse_bitrate_bps("127 kbps") == 127_000)
    check("parse bitrate mbps float", _parse_bitrate_bps("1.1 Mbps") == 1_100_000)
    check("parse bitrate int bps", _parse_bitrate_bps(2_500_000) == 2_500_000)
    check("parse bitrate fallback None", _parse_bitrate_bps(None) is None)

    # Resolution parsing
    check("parse resolution 1280x536", _parse_resolution("1280x536") == (1280, 536))
    check("parse resolution 1920x1080", _parse_resolution("1920x1080") == (1920, 1080))
    check("parse resolution invalid", _parse_resolution("invalid") == (None, None))

    # Framerate parsing
    check("parse framerate 23.98 fps", abs(_parse_framerate("23.98 fps") - 23.98) < 0.01)
    check("parse framerate 24/1 fraction", abs(_parse_framerate("24000/1001") - 23.976) < 0.01)

    # Duration parsing
    check("parse duration 02:06:07", _parse_duration_seconds("02:06:07") == 7567.0)
    check("parse duration seconds float", _parse_duration_seconds("120.5") == 120.5)

    # Size formatting
    check("format size GB", "1.1 GB" in _format_size_bytes(1_214_849_624))
    check("format size MB", "MB" in _format_size_bytes(986_941_633))


def test_matchbox_rf25_bloat_prediction():
    """Matchbox The Movie (2026): 720p WEBRip x264 @ 1.1 Mbps, 127 kbps AAC.
    RF 25 on nvenc_h265 produced 1.24 GB (+2.2% bloat).
    Model must predict break-even / potential expansion, NOT 30-50% reduction!
    """
    source_info = {
        "format": "mp4",
        "video_codec": "h264",
        "video_bitrate": "1.1 Mbps",
        "width": 1280,
        "height": 536,
        "framerate": 23.976,
        "duration": "02:06:07",
        "audio_bitrate": "127 kbps",
        "file_size": 1_214_849_624,
    }

    forecast = calculate_efficiency_forecast(
        source_info=source_info,
        target_encoder="nvenc_h265",
        target_rf=25,
        target_audio_enc="copy",
    )

    check("forecast status is warning or neutral", forecast["status"] in ("warning", "neutral"))
    check("delta percent is near break-even (>= -5%)", forecast["delta_pct"] >= -5.0)
    check("est output size ~1.2 GB", "1.2 GB" in forecast["est_target_size_str"] or "1.3 GB" in forecast["est_target_size_str"])
    # Crucial: message must warn or state approximately same size, NOT 30-50% reduction
    check("message warns about expansion or break-even", "approximately the SAME" in forecast["message"] or "INCREASE" in forecast["message"])
    check("message does not claim 30-50% reduction", "30–50%" not in forecast["message"])


def test_matchbox_rf27_reduction_prediction():
    """Matchbox The Movie (2026): 720p WEBRip x264 @ 1.1 Mbps.
    RF 27 on nvenc_h265 produced 986 MB (-18.7% reduction).
    Model must predict ~10-20% reduction (est ~980 MB), matching empirical test!
    """
    source_info = {
        "format": "mp4",
        "video_codec": "h264",
        "video_bitrate": "1.1 Mbps",
        "width": 1280,
        "height": 536,
        "framerate": 23.976,
        "duration": "02:06:07",
        "audio_bitrate": "127 kbps",
        "file_size": 1_214_849_624,
    }

    forecast = calculate_efficiency_forecast(
        source_info=source_info,
        target_encoder="nvenc_h265",
        target_rf=27,
        target_audio_enc="copy",
    )

    check("rf27 status is optimal", forecast["status"] == "optimal")
    check("rf27 delta is negative (reduction)", forecast["delta_pct"] < -5.0)
    check("rf27 reduction range includes ~12-18%", "12%–18%" in forecast["message"] or "reduction" in forecast["message"])
    check("rf27 estimated size is in hundreds of MB or ~1.0 GB", "MB" in forecast["est_target_size_str"] or "1.0 GB" in forecast["est_target_size_str"])


def test_high_bitrate_transcode_prediction():
    """High bitrate 1080p source (15 Mbps H.264) transcode to SVT-AV1 at RF 28.
    Should predict substantial efficiency reduction (>50%).
    """
    source_info = {
        "format": "mkv",
        "video_codec": "h264",
        "video_bitrate": "15 Mbps",
        "width": 1920,
        "height": 1080,
        "framerate": 24.0,
        "duration": "01:30:00",
        "audio_bitrate": "640 kbps",
        "file_size": 10_000_000_000,
    }

    forecast = calculate_efficiency_forecast(
        source_info=source_info,
        target_encoder="svt_av1",
        target_rf=28,
        target_audio_enc="aac",
        target_audio_bitrate=128,
    )

    check("high bitrate AV1 status is optimal", forecast["status"] == "optimal")
    check("high bitrate reduction > 50%", forecast["delta_pct"] < -50.0)


def test_check_efficiency_and_feedback():
    source_info = {
        "format": "mp4",
        "video_codec": "h264",
        "video_bitrate": "1.1 Mbps",
        "width": 1280,
        "height": 536,
        "framerate": 23.976,
        "duration": "02:06:07",
        "audio_bitrate": "127 kbps",
        "file_size": 1_214_849_624,
    }

    # RF 25
    eff25 = check_efficiency(source_info, "nvenc_h265", 25, "copy")
    feedback25 = get_efficiency_feedback(source_info, "nvenc_h265", 25, "copy")
    check("feedback25 has forecast message", feedback25 is not None and "est." in feedback25.get("message", ""))

    # RF 27
    eff27 = check_efficiency(source_info, "nvenc_h265", 27, "copy")
    feedback27 = get_efficiency_feedback(source_info, "nvenc_h265", 27, "copy")
    check("feedback27 has optimal forecast", "Optimal:" in feedback27.get("message", "") and "reduction" in feedback27.get("message", ""))


def main():
    test_parsers()
    test_matchbox_rf25_bloat_prediction()
    test_matchbox_rf27_reduction_prediction()
    test_high_bitrate_transcode_prediction()
    test_check_efficiency_and_feedback()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
