#!/usr/bin/env python3
"""
MediaAnalyzer attached-picture (cover art) stream tests (2026-10-08)

Regression for the AV1 black-screen bug chain: files with an embedded
cover (e.g. MKV stream `mjpeg ... attached_pic=1 filename=cover.jpg`)
made `_parse_probe_data` overwrite the real video stream's fields —
last video stream wins — so `bit_depth` resolved to 8 and 10-bit
sources were silently encoded as 8-bit.

Run:
    python3 tests/test_analyzer_attached_pic.py
"""
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.analyzer import MediaAnalyzer
from core.converter import ConversionSettings, Converter
from core.encoder import EncoderManager

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


def _streams(with_cover: bool, only_cover: bool = False):
    av1 = {
        "index": 0, "codec_type": "video", "codec_name": "av1", "profile": "Main",
        "width": 1920, "height": 1080, "pix_fmt": "yuv420p10le",
        "r_frame_rate": "24000/1001",
        "disposition": {"default": 1, "attached_pic": 0},
    }
    audio = {
        "index": 1, "codec_type": "audio", "codec_name": "eac3", "channels": 6,
        "channel_layout": "5.1", "disposition": {"default": 1},
        "tags": {"language": "eng", "title": "English"},
    }
    sub = {
        "index": 2, "codec_type": "subtitle", "codec_name": "ass",
        "disposition": {"default": 0}, "tags": {"language": "eng"},
    }
    cover = {
        "index": 3, "codec_type": "video", "codec_name": "mjpeg",
        "width": 2000, "height": 3000, "pix_fmt": "yuvj422p",
        "r_frame_rate": "90000/1",
        "disposition": {"default": 0, "attached_pic": 1},
        "tags": {"filename": "cover.jpg", "mimetype": "image/jpeg"},
    }
    if only_cover:
        return [audio, cover]
    streams = [av1, audio, sub] + ([cover] if with_cover else [])
    return streams


def _fixture(with_cover: bool, only_cover: bool = False):
    return {
        "streams": _streams(with_cover, only_cover),
        "format": {"duration": "1431.500000", "bit_rate": "971071"},
    }


def _analyze(data: dict):
    fd, path = tempfile.mkstemp(suffix=".mkv")
    os.close(fd)
    try:
        probe = SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        with mock.patch("core.analyzer.subprocess.run", return_value=probe):
            return MediaAnalyzer().analyze(path), path
    finally:
        os.unlink(path)


def test_cover_art_ignored():
    info, _ = _analyze(_fixture(with_cover=True))
    check("analyze() returns info", info is not None)
    check("video codec is AV1 (not MJPEG)", info.video_codec == "AV1")
    check("resolution is the AV1 stream", (info.width, info.height) == (1920, 1080))
    check("pix_fmt is yuv420p10le", info.pix_fmt == "yuv420p10le")
    check("bit_depth is 10 (not 8)", info.bit_depth == 10)
    check("framerate from AV1 stream", info.framerate == "23.98")


def test_no_cover_regression():
    info, _ = _analyze(_fixture(with_cover=False))
    check("no-cover file still analyzed", info is not None)
    check("no-cover video codec", info.video_codec == "AV1")
    check("no-cover bit_depth", info.bit_depth == 10)
    check("no-cover audio stream kept", len(info.audio_streams) == 1)
    check("no-cover audio codec", info.audio_streams[0]["codec"] == "EAC3")


def test_only_cover_stream():
    info, _ = _analyze(_fixture(with_cover=True, only_cover=True))
    check("cover-only file analyzed", info is not None)
    check("cover-only: no fake video codec", info.video_codec in (None, ""))
    check("cover-only: no fake bit_depth", info.bit_depth is None)


def test_effective_bit_depth_end_to_end():
    """Converter must pick svt_av1_10bit for a 10-bit source with cover art."""
    fd, path = tempfile.mkstemp(suffix=".mkv")
    os.close(fd)
    try:
        probe = SimpleNamespace(returncode=0, stdout=json.dumps(_fixture(True)), stderr="")
        with mock.patch("core.analyzer.subprocess.run", return_value=probe):
            conv = Converter(EncoderManager())
            depth = conv._effective_bit_depth(path, ConversionSettings())
            check("effective bit depth is 10", depth == 10)
            cmd = conv._build_command(
                path, "/tmp/out.mkv",
                ConversionSettings(encoder="svt_av1", quality=27, output_format="mkv"),
            )
            check("command uses svt_av1_10bit",
                  "svt_av1_10bit" in cmd[cmd.index("--encoder") + 1])
    finally:
        os.unlink(path)


def main():
    test_cover_art_ignored()
    test_no_cover_regression()
    test_only_cover_stream()
    test_effective_bit_depth_end_to_end()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
