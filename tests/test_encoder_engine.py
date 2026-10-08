#!/usr/bin/env python3
"""
Encoder Capability Engine Tests (v9.7.0)

Covers the runtime-probed encoder engine in core/encoder.py:
- --help parsing of HandBrakeCLI encoder lists
- family -> HandBrake id mapping (8/10-bit)
- NVEncC backend routing
- availability / recommendation / badges
- legacy id normalization

Run:
    python3 tests/test_encoder_engine.py
"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.encoder as enc

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


FAKE_HB_HELP = """\
Usage: HandBrakeCLI [options] -i <input> -o <output>
...
  --encoder <string>  Select video encoder:
      svt_av1
      svt_av1_10bit
      x264
      x264_10bit
      nvenc_h264
      x265
      x265_10bit
      x265_12bit
      nvenc_h265
      nvenc_h265_10bit
      mpeg4
      mpeg2
  --quality <float>
"""


class FakeResult:
    def __init__(self, text):
        self.stdout = text
        self.stderr = ""


def test_probe_parser():
    orig_which = enc.shutil.which
    orig_run = enc.subprocess.run
    enc._hb_encoders_cache = None
    enc.shutil.which = lambda name, *a, **k: "/usr/bin/HandBrakeCLI" if name == "HandBrakeCLI" else None
    enc.subprocess.run = lambda *a, **k: FakeResult(FAKE_HB_HELP)
    try:
        got = enc.probe_handbrake_encoders(refresh=True)
    finally:
        enc.shutil.which = orig_which
        enc.subprocess.run = orig_run
        enc._hb_encoders_cache = None

    check("probe parses svt_av1", "svt_av1" in got)
    check("probe parses svt_av1_10bit", "svt_av1_10bit" in got)
    check("probe parses nvenc_h265_10bit", "nvenc_h265_10bit" in got)
    check("probe parses x265_12bit", "x265_12bit" in got)
    check("probe does NOT grab --quality line", "--quality" not in got)


def test_handbrake_mapping():
    check("x265 8bit -> x265", enc.HB_FAMILY_IDS["x265"][0] == "x265")
    check("x265 10bit -> x265_10bit", enc.HB_FAMILY_IDS["x265"][1] == "x265_10bit")
    check("svt_av1 10bit -> svt_av1_10bit", enc.HB_FAMILY_IDS["svt_av1"][1] == "svt_av1_10bit")
    check("nvenc_h265 10bit -> nvenc_h265_10bit", enc.HB_FAMILY_IDS["nvenc_h265"][1] == "nvenc_h265_10bit")
    check("x264 10bit -> x264_10bit", enc.HB_FAMILY_IDS["x264"][1] == "x264_10bit")
    check("libsvtav1 alias -> svt_av1", enc.ENCODER_ALIASES["libsvtav1"] == "svt_av1")


def fake_manager(encoders_available, hw_type=None):
    """Build an EncoderManager with deterministic hardware."""
    hw = types.SimpleNamespace(
        type=hw_type or enc.HardwareType.NVIDIA,
        name="FakeGPU",
        encoders_available=list(encoders_available),
        nvenc_tool=None,
    )
    m = enc.EncoderManager.__new__(enc.EncoderManager)
    m.hardware = hw
    return m


def test_availability_and_badges():
    # Turing-like GPU: no NVENC AV1, NVEncC not installed
    m = fake_manager(["nvenc_h265", "nvenc_h264", "x265", "x264", "svt_av1"])
    avail = m.get_available_encoders()
    check("CPU families present", "x265" in avail and "x264" in avail and "svt_av1" in avail)
    check("nvenc_h265 available", "nvenc_h265" in avail)
    check("nvenc_av1 correctly absent on Turing-like GPU", "nvenc_av1" not in avail)
    check("nvencc_hevc absent when NVEncC not installed", "nvencc_hevc" not in avail)

    best = m.get_recommended_encoder()
    check("recommended = nvenc_h265 (GPU HEVC first)", best == "nvenc_h265")
    check("best badge text", m.get_badge("nvenc_h265") == "★ Best for your GPU")
    check("non-best encoder gets no badge", m.get_badge("x265") == "")


def test_recommendation_preferences():
    # Ada/Blackwell with NVENC AV1 available -> GPU AV1 wins
    m = fake_manager(["nvenc_av1", "nvenc_h265", "x265"])
    check("GPU AV1 preferred over GPU HEVC", m.get_recommended_encoder() == "nvenc_av1")
    check("GPU AV1 badge", m.get_badge("nvenc_av1") == "★ Best for your GPU")

    # NVEncC HEVC available, no HandBrake nvenc -> NVEncC preferred
    m = fake_manager(["nvencc_hevc", "x265", "svt_av1"])
    check("NVEncC preferred over CPU x265", m.get_recommended_encoder() == "nvencc_hevc")

    # CPU-only machine -> x265 recommended with plain '★ Best'
    m = fake_manager(["x265", "x264", "svt_av1"], hw_type=enc.HardwareType.NONE)
    check("CPU-only recommends x265", m.get_recommended_encoder() == "x265")
    check("CPU best badge is '★ Best'", m.get_badge("x265") == "★ Best")


def test_10bit_mapping_and_backends():
    m = fake_manager(["x265", "nvenc_h265", "nvencc_hevc"])

    check("to_hb x265 10bit", m.to_handbrake_encoder("x265", 10) == "x265_10bit")
    check("to_hb x265 8bit", m.to_handbrake_encoder("x265", 8) == "x265")
    check("to_hb svt_av1 10bit", m.to_handbrake_encoder("svt_av1", 10) == "svt_av1_10bit")
    check("to_hb nvenc_h265 10bit", m.to_handbrake_encoder("nvenc_h265", 10) == "nvenc_h265_10bit")
    check("to_hb x264 10bit -> x264_10bit", m.to_handbrake_encoder("x264", 10) == "x264_10bit")
    check("to_hb x264 8bit stays x264", m.to_handbrake_encoder("x264", 8) == "x264")
    check("libsvtav1 normalizes then maps to svt_av1", m.to_handbrake_encoder("libsvtav1") == "svt_av1")

    check("supports_10bit nvencc_hevc", m.supports_10bit("nvencc_hevc") is True)
    check("supports_10bit nvencc_h264", m.supports_10bit("nvencc_h264") is False)

    check("encode_backend nvencc_hevc -> nvenc",
          m.encode_backend("nvencc_hevc") == "nvenc")
    check("encode_backend x265 -> handbrake",
          m.encode_backend("x265") == "handbrake")
    check("is_hardware nvenc_h265", m.is_hardware_encoder("nvenc_h265") is True)
    check("is_hardware x265", m.is_hardware_encoder("x265") is False)


def main():
    test_probe_parser()
    test_handbrake_mapping()
    test_availability_and_badges()
    test_recommendation_preferences()
    test_10bit_mapping_and_backends()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())