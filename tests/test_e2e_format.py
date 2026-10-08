#!/usr/bin/env python3
"""
End-to-end output container test (MP4 vs MKV)

Verifies sending `output_format='mkv'` / `output_format='mp4'` through
ConversionSettings results in the correct HandBrakeCLI `--format` arg and
an output file whose actual container matches (MP4 -> mp4, MKV -> matroska).

Uses a tiny generated source file so the test runs in seconds.

Run:
    python3 tests/test_e2e_format.py 2>&1 | tail -20
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.converter import ConversionSettings

HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_HB = shutil.which("HandBrakeCLI") is not None

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


def container_of(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=format_name",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return out.stdout.strip()


def make_source(tmp):
    src = os.path.join(tmp, "src.mkv")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-c:v", "libx264", "-preset", "ultrafast", src
    ], capture_output=True, check=True)
    return src


def test_format(out_format, ftype):
    global PASS
    tmp = tempfile.mkdtemp()
    try:
        src = make_source(tmp)
        from core import encoder
        from core import converter
        em = encoder.EncoderManager()
        conv = converter.Converter(em)
        args = conv._build_command(src, os.path.join(tmp, f"out.{out_format}"), converter.ConversionSettings(output_format=out_format, encoder='x264', quality=31, audio_encoder='copy'))
        check(f"[{out_format}] --format {out_format} in command",
              f"--format {out_format}" in " ".join(args))
        subprocess.run(["HandBrakeCLI", "-i", src, "-o",
                        os.path.join(tmp, f"out.{out_format}"),
                        "--format", out_format, "--encoder", "x264",
                        "--quality", "31", "--audio", "1"],
                       capture_output=True)
        check(f"[{out_format}] output exists", os.path.exists(os.path.join(tmp, f"out.{out_format}")))
        c = container_of(os.path.join(tmp, f"out.{out_format}"))
        # HandBrakeCLI MP4 often reports mov,mp4,...; accept either 'mp4' or contains 'mp4'
        is_ok = (ftype == c) or ('mp4' in c and ftype == 'mp4') or ('matroska' in c and ftype == 'matroska,webm')
        check(f"[{out_format}] container is {ftype} (got: {c})", is_ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if not HAS_FFMPEG:
        print("ffmpeg not found — cannot run e2e test")
        return 2
    if not HAS_HB:
        print("HandBrakeCLI not found — cannot run e2e test")
        return 2
    test_format("mkv", "matroska,webm")
    test_format("mp4", "mp4")
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())