#!/usr/bin/env python3
"""
Conversion Command Flags Tests (v9.7.0)

Verifies core/converter.py emits the right flags for:
- crop control (none / auto / custom)
- 10-bit encoder selection + source bit-depth probing
- SVT-AV1 --encoder-preset
- rigaya NVEncC backend routing

Run:
    python3 tests/test_conversion_flags.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def build(**settings_kw):
    m = EncoderManager()
    s = ConversionSettings(audio_encoder="copy", **settings_kw)
    c = Converter(m)
    return c._build_command("/tmp/vconv_in.mkv", "/tmp/vconv_out.mp4", s)


def test_crop_flags():
    cmd = build(encoder="x265")
    check("default crop_mode -> --crop-mode none", "--crop-mode" in cmd and "none" in cmd)
    check("default has no --crop", "--crop" not in cmd)

    cmd = build(encoder="x265", crop_mode="auto")
    i = cmd.index("--crop-mode")
    check("auto crop_mode -> --crop-mode auto", cmd[i + 1] == "auto")

    cmd = build(encoder="x265", crop_mode="custom", crop_custom="2:2:4:4")
    check("custom crop mode flag", "--crop-mode" in cmd and "custom" in cmd)
    check("custom crop geometry flag", "--crop" in cmd)
    check("custom crop geometry values", cmd[cmd.index("--crop") + 1] == "2:2:4:4")


def test_preset_flag():
    cmd = build(encoder="svt_av1", encoder_preset=6)
    check("--encoder-preset emitted", "--encoder-preset" in cmd)
    check("preset value", cmd[cmd.index("--encoder-preset") + 1] == "6")

    cmd = build(encoder="svt_av1", encoder_preset=None)
    check("no --encoder-preset when unset", "--encoder-preset" not in cmd)


def test_10bit_flag():
    # Explicit 10-bit target -> *_10bit HandBrake encoder id
    cmd = build(encoder="x265", bit_depth=10, preserve_bit_depth=True)
    check("x265 10-bit -> x265_10bit encoder",
          "--encoder" in cmd and "x265_10bit" in cmd[cmd.index("--encoder") + 1])
    cmd = build(encoder="svt_av1", bit_depth=10, preserve_bit_depth=True)
    check("svt_av1 10-bit -> svt_av1_10bit encoder",
          "svt_av1_10bit" in cmd[cmd.index("--encoder") + 1])

    # preserve off -> 8-bit id
    cmd = build(encoder="x265", bit_depth=10, preserve_bit_depth=False)
    check("preserve off forces 8-bit x265",
          cmd[cmd.index("--encoder") + 1] == "x265")


def test_probe_bit_depth_real_clip():
    """Generate a real 10-bit clip and confirm the probe picks depth 10."""
    if not shutil.which("ffmpeg"):
        print("[SKIP] ffmpeg not available — real probe test skipped")
        return
    m = EncoderManager()
    c = Converter(m)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "depth10.mp4"
        r = subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "testsrc=size=320x240:rate=10:duration=1",
            "-pix_fmt", "yuv420p10le", "-c:v", "libx264", str(src),
        ], capture_output=True, text=True, timeout=120)
        check("test clip created", r.returncode == 0 and src.exists())

        s = ConversionSettings(audio_encoder="copy")
        depth = c._effective_bit_depth(str(src), ConversionSettings(audio_encoder="copy"))
        check("preserve on probes real source -> 10", depth == 10)

        depth = c._effective_bit_depth(
            str(src),
            ConversionSettings(audio_encoder="copy", preserve_bit_depth=False, bit_depth=8))
        check("preserve off uses settings bit_depth 8", depth == 8)

        cmd = c._build_command(str(src), str(Path(td) / "out.mp4"),
                               ConversionSettings(encoder="x265", audio_encoder="copy"))
        check("real 10-bit source selects x265_10bit",
              "x265_10bit" in cmd[cmd.index("--encoder") + 1])


def test_nvenc_routing():
    cmd = build(encoder="nvencc_hevc", quality=21, bit_depth=10)
    check("nvcc command starts with NVEncC tool", cmd[0].endswith("NVEncC") or cmd[0] == "NVEncC")
    check("nvcc codec hevc", "--codec" in cmd and cmd[cmd.index("--codec") + 1] == "hevc")
    check("nvcc cq", "--cq" in cmd and cmd[cmd.index("--cq") + 1] == "21")
    check("nvcc 10-bit output", "--output-depth" in cmd)
    check("nvcc preset", "--preset" in cmd)

    cmd = build(encoder="nvencc_h264", quality=22)
    check("nvcc h264 never 10-bit", "--output-depth" not in cmd)
    check("nvcc h264 codec", cmd[cmd.index("--codec") + 1] == "h264")


def main():
    test_crop_flags()
    test_preset_flag()
    test_10bit_flag()
    test_nvenc_routing()
    test_probe_bit_depth_real_clip()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())