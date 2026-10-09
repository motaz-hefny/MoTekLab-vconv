"""
Media Analyzer Module

Analyzes video files using ffprobe to extract metadata.
"""

import subprocess
import json
import logging
import shutil
import re
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class MediaInfo:
    """Container for media file information."""
    filename: str
    filepath: str
    filesize: str
    duration: Optional[str] = None
    container_format: Optional[str] = None
    overall_bitrate: Optional[str] = None
    video_codec: Optional[str] = None
    video_bitrate: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    framerate: Optional[str] = None
    pix_fmt: Optional[str] = None
    bit_depth: Optional[int] = None
    audio_codec: Optional[str] = None
    audio_bitrate: Optional[str] = None
    audio_channels: Optional[str] = None
    audio_samplerate: Optional[str] = None
    audio_streams: list = None
    subtitle_streams: list = None

    def __post_init__(self):
        if self.audio_streams is None:
            self.audio_streams = []
        if self.subtitle_streams is None:
            self.subtitle_streams = []


class MediaAnalyzer:
    """Analyzes media files using ffprobe."""

    def __init__(self):
        self.ffprobe_path = shutil.which('ffprobe')
        if not self.ffprobe_path:
            logger.warning("ffprobe not found in system")

    def analyze(self, filepath: str) -> Optional[MediaInfo]:
        """
        Analyze a media file and return its information.

        Args:
            filepath: Path to the media file

        Returns:
            MediaInfo object or None if analysis fails
        """
        if not self.ffprobe_path:
            logger.error("ffprobe not available")
            return None

        if not self._file_exists(filepath):
            logger.error(f"File not found: {filepath}")
            return None

        try:
            # Get file size
            import os
            filesize = self._format_size(os.path.getsize(filepath))

            # Get filename
            filename = os.path.basename(filepath)

            # Run ffprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                filepath
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"ffprobe failed: {result.stderr}")
                return None

            data = json.loads(result.stdout)
            return self._parse_probe_data(filename, filepath, filesize, data)

        except subprocess.TimeoutExpired:
            logger.error(f"ffprobe timed out for: {filepath}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe output: {e}")
            return None
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            return None

    def _file_exists(self, filepath: str) -> bool:
        """Check if file exists."""
        import os
        return os.path.isfile(filepath)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size to human readable."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def _parse_probe_data(self, filename: str, filepath: str, filesize: str, data: dict) -> MediaInfo:
        """Parse ffprobe JSON output to MediaInfo."""
        info = MediaInfo(
            filename=filename,
            filepath=filepath,
            filesize=filesize
        )

        # Format info (container format, duration, overall bitrate)
        fmt_bitrate_fallback = None
        if 'format' in data:
            fmt = data['format']
            if 'format_name' in fmt:
                info.container_format = fmt['format_name'].upper()
            if 'duration' in fmt:
                info.duration = self._format_duration(float(fmt['duration']))
            if 'bit_rate' in fmt:
                info.overall_bitrate = self._format_bitrate(int(fmt['bit_rate']))
                fmt_bitrate_fallback = int(fmt['bit_rate'])

        # Stream info
        audio_streams = []
        subtitle_streams = []

        for stream in data.get('streams', []):
            codec_type = stream.get('codec_type', '')

            if codec_type == 'video':
                # Cover art arrives as a pseudo-video stream (e.g. MKV
                # cover.jpg with attached_pic=1). Skipping it prevents the
                # image's codec/pix_fmt/bit depth from overwriting the real
                # video track (regression: 10-bit sources encoded as 8-bit).
                if info.video_codec:
                    continue  # main video already parsed; skip angles/covers
                disp = stream.get('disposition') or {}
                if disp.get('attached_pic') or disp.get('timed_thumbnails'):
                    continue

                info.video_codec = stream.get('codec_name', '').upper()
                info.width = stream.get('width')
                info.height = stream.get('height')

                # Video bitrate from stream properties or container tags (e.g. MKV BPS)
                v_bitrate = None
                if stream.get('bit_rate'):
                    try:
                        v_bitrate = self._format_bitrate(int(stream['bit_rate']))
                    except (ValueError, TypeError):
                        pass
                if not v_bitrate:
                    tags = stream.get('tags', {}) or {}
                    bps = tags.get('BPS') or tags.get('BPS-eng') or next(
                        (v for k, v in tags.items() if k.upper().startswith('BPS')), None
                    )
                    if bps:
                        try:
                            v_bitrate = self._format_bitrate(int(bps))
                        except (ValueError, TypeError):
                            pass
                if v_bitrate:
                    info.video_bitrate = v_bitrate
                elif fmt_bitrate_fallback:
                    info.video_bitrate = f"≈{self._format_bitrate(fmt_bitrate_fallback)} (total)"

                # Pixel format / color bit depth (yuv420p10le -> 10-bit)
                info.pix_fmt = stream.get('pix_fmt')
                info.bit_depth = self._parse_bit_depth(info.pix_fmt)

                # Frame rate
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    try:
                        num, den = fps_str.split('/')
                        fps = float(num) / float(den)
                        info.framerate = f"{fps:.2f}"
                    except (ValueError, ZeroDivisionError):
                        pass

            elif codec_type == 'audio':
                a_codec = stream.get('codec_name', '').upper()
                a_bitrate = None
                if 'bit_rate' in stream:
                    a_bitrate = self._format_bitrate(int(stream['bit_rate']))
                else:
                    tags = stream.get('tags', {}) or {}
                    bps = tags.get('BPS') or tags.get('BPS-eng') or next(
                        (v for k, v in tags.items() if k.upper().startswith('BPS')), None
                    )
                    if bps:
                        a_bitrate = self._format_bitrate(int(bps))
                    elif fmt_bitrate_fallback:
                        a_bitrate = f"≈{self._format_bitrate(fmt_bitrate_fallback)} (total)"
                channels = stream.get('channels')
                a_channels = None
                if channels:
                    ch_layout = stream.get('channel_layout', 'unknown')
                    a_channels = f"{channels}ch ({ch_layout})"
                sample_rate = stream.get('sample_rate')
                a_sample_rate = None
                if sample_rate:
                    try:
                        sr_val = int(sample_rate)
                        sr_khz = sr_val / 1000.0
                        a_sample_rate = f"{sr_khz:.1f} kHz" if sr_val % 1000 != 0 else f"{int(sr_khz)} kHz"
                    except (ValueError, TypeError):
                        a_sample_rate = f"{sample_rate} Hz"
                a_lang = stream.get('tags', {}).get('language', 'unknown') if stream.get('tags') else 'unknown'
                a_title = stream.get('tags', {}).get('title', '') if stream.get('tags') else ''
                audio_streams.append({
                    'index': stream.get('index'),
                    'codec': a_codec,
                    'bitrate': a_bitrate,
                    'channels': a_channels,
                    'sample_rate': a_sample_rate,
                    'language': a_lang,
                    'title': a_title
                })
                # Keep first audio as legacy fields
                if info.audio_codec is None:
                    info.audio_codec = a_codec
                    info.audio_bitrate = a_bitrate
                    info.audio_channels = a_channels
                    info.audio_samplerate = a_sample_rate

            elif codec_type == 'subtitle':
                s_codec = stream.get('codec_name', '').upper()
                lang = stream.get('tags', {}).get('language', 'unknown') if stream.get('tags') else 'unknown'
                title = stream.get('tags', {}).get('title', f'Stream {len(subtitle_streams) + 1}') if stream.get('tags') else f'Stream {len(subtitle_streams) + 1}'
                subtitle_streams.append({
                    'index': stream.get('index'),
                    'codec': s_codec,
                    'language': lang,
                    'title': title
                })

        info.audio_streams = audio_streams
        info.subtitle_streams = subtitle_streams
        return info

    def _format_duration(self, seconds: float) -> str:
        """Format duration to HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _format_bitrate(self, bitrate: int) -> str:
        """Format bitrate to kbps or mbps."""
        kbps = bitrate // 1000
        if kbps >= 1000:
            return f"{kbps / 1000:.1f} Mbps"
        return f"{kbps} kbps"

    def _parse_bit_depth(self, pix_fmt: Optional[str]) -> Optional[int]:
        """Derive color bit depth from ffprobe pix_fmt (e.g. yuv420p10le -> 10)."""
        if not pix_fmt:
            return None
        m = re.search(r'(\d{1,2})le', pix_fmt) or re.search(r'p(\d{1,2})', pix_fmt)
        if m:
            depth = int(m.group(1))
            if 1 <= depth <= 16:
                return depth
        return 8 if 'yuvj' in pix_fmt or pix_fmt.startswith('yuv') else None


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    analyzer = MediaAnalyzer()

    # Would need an actual file to test
    print("MediaAnalyzer ready")
    print(f"ffprobe available: {analyzer.ffprobe_path is not None}")