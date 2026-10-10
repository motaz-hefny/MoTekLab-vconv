"""
File Validator Module

Validates files before conversion: checks existence, validity, output conflicts.
"""

import os
import re
import math
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path

from core.constants import VIDEO_EXTENSIONS
from utils.logging import get_logger

logger = get_logger("validator")

ENCODER_EFFICIENCY_PROFILES = {
    # encoder_key: (base_rf, base_bppf, rf_step_divisor)
    'svt_av1': (27, 0.045, 6.0),
    'av1': (27, 0.045, 6.0),
    'av1_10bit': (27, 0.045, 6.0),
    'x265': (25, 0.056, 6.0),
    'hevc': (25, 0.056, 6.0),
    'x265_10bit': (25, 0.054, 6.0),
    'nvenc_h265': (25, 0.072, 6.0),
    'qsv_h265': (25, 0.072, 6.0),
    'vce_h265': (25, 0.074, 6.0),
    'x264': (22, 0.088, 6.0),
    'h264': (22, 0.088, 6.0),
    'x264_10bit': (22, 0.086, 6.0),
    'nvenc_h264': (22, 0.108, 6.0),
    'qsv_h264': (22, 0.108, 6.0),
}

def _parse_bitrate_bps(br_str: str) -> Optional[int]:
    if not br_str:
        return None
    s = str(br_str).lower().strip()
    m = re.search(r'([\d.]+)\s*(mbps|kbps|m|k|bps)?', s)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2) or ''
    if 'm' in unit:
        return int(val * 1_000_000)
    elif 'k' in unit:
        return int(val * 1_000)
    elif val > 10000:
        return int(val)
    elif val < 100:
        return int(val * 1_000_000)
    return int(val * 1_000)

def _parse_resolution(res_str: str) -> Tuple[Optional[int], Optional[int]]:
    if not res_str:
        return None, None
    m = re.search(r'(\d+)\s*[xX*×]\s*(\d+)', str(res_str))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def _parse_framerate(fps_str: str) -> float:
    if not fps_str:
        return 23.976
    s = str(fps_str).strip()
    if '/' in s:
        try:
            num, den = s.split('/', 1)
            return float(num) / float(den)
        except Exception:
            return 23.976
    try:
        val = float(s)
        return val if val > 0 else 23.976
    except Exception:
        return 23.976

def _parse_duration_seconds(dur_str: str) -> Optional[float]:
    if not dur_str:
        return None
    s = str(dur_str).strip()
    parts = s.split(':')
    try:
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(s)
    except Exception:
        return None

def _format_size_bytes(bytes_val: Optional[float]) -> str:
    if not bytes_val or bytes_val <= 0:
        return ""
    if bytes_val >= 1024 * 1024 * 1024:
        return f"{bytes_val / (1024**3):.1f} GB"
    elif bytes_val >= 1024 * 1024:
        return f"{bytes_val / (1024**2):.0f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.0f} KB"
    return f"{int(bytes_val)} B"



class ValidationStatus:
    """Validation status constants."""
    VALID = "valid"
    FILE_NOT_FOUND = "file_not_found"
    NOT_VIDEO = "not_video"
    NO_READ_PERMISSION = "no_read_permission"
    OUTPUT_EXISTS = "output_exists"
    OUTPUT_DIR_NOT_WRITABLE = "output_dir_not_writable"
    DISK_SPACE_LOW = "disk_space_low"


@dataclass
class ValidationResult:
    """Result of file validation."""
    status: str
    message: str
    input_path: str = ""
    output_path: str = ""


class FileValidator:
    """Validates files and output locations before conversion."""

    SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS.copy()

    def __init__(self):
        self.validation_results: list[ValidationResult] = []

    def validate_file(self, input_path: str, output_path: str = None) -> ValidationResult:
        """
        Validate a single input file.

        Args:
            input_path: Path to input file
            output_path: Path to output file (optional, for conflict check)

        Returns:
            ValidationResult
        """
        result = ValidationResult(
            status=ValidationStatus.VALID,
            message="File is valid",
            input_path=input_path
        )

        # Check if file exists
        if not os.path.exists(input_path):
            result.status = ValidationStatus.FILE_NOT_FOUND
            result.message = f"File not found: {input_path}"
            return result

        # Check if it's a file (not directory)
        if not os.path.isfile(input_path):
            result.status = ValidationStatus.NOT_VIDEO
            result.message = "Not a file"
            return result

        # Check read permission
        if not os.access(input_path, os.R_OK):
            result.status = ValidationStatus.NO_READ_PERMISSION
            result.message = f"No read permission: {input_path}"
            return result

        # Check if it's a video file
        ext = Path(input_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            result.status = ValidationStatus.NOT_VIDEO
            result.message = f"Unsupported file type: {ext}"
            return result

        # If output path provided, check it
        if output_path:
            result.output_path = output_path

            # Check if output exists (but only if we plan to ask user)
            if os.path.exists(output_path):
                result.status = ValidationStatus.OUTPUT_EXISTS
                result.message = f"Output file exists: {output_path}"
                return result

            # Check if output directory is writable
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except PermissionError:
                    result.status = ValidationStatus.OUTPUT_DIR_NOT_WRITABLE
                    result.message = f"Cannot create output directory: {output_dir}"
                    return result

            if output_dir and os.path.exists(output_dir):
                if not os.access(output_dir, os.W_OK):
                    result.status = ValidationStatus.OUTPUT_DIR_NOT_WRITABLE
                    result.message = f"Output directory not writable: {output_dir}"
                    return result

            # Check disk space (rough estimate - require at least input size * 2)
            try:
                input_size = os.path.getsize(input_path)
                output_dir = output_dir or os.path.dirname(input_path) or '.'
                stat = os.statvfs(output_dir)
                free_space = stat.f_bavail * stat.f_frsize

                if free_space < input_size * 2:
                    result.status = ValidationStatus.DISK_SPACE_LOW
                    result.message = "Insufficient disk space for conversion"
                    return result
            except Exception as e:
                logger.warning(f"Could not check disk space: {e}")

        return result

    def validate_batch(self, files: list[tuple], output_dir: str = None, format: str = "mp4") -> list[ValidationResult]:
        """
        Validate multiple files for batch processing.

        Args:
            files: List of (input_path, output_path) tuples
            output_dir: Default output directory (optional)
            format: Output format ('mp4', 'mkv', default: 'mp4')

        Returns:
            List of ValidationResult
        """
        results = []

        for input_path, output_path in files:
            if output_path is None and output_dir:
                # Generate default output path
                filename = Path(input_path).stem + f".{format}"
                output_path = os.path.join(output_dir, filename)

            result = self.validate_file(input_path, output_path)
            results.append(result)

        return results

    def check_conflicts(self, results: list[ValidationResult]) -> dict:
        """
        Check for all conflicts in validation results.

        Args:
            results: List of validation results

        Returns:
            Dictionary with conflict summary
        """
        conflicts = {
            'total': len(results),
            'valid': 0,
            'output_exists': [],
            'other_errors': []
        }

        for result in results:
            if result.status == ValidationStatus.VALID:
                conflicts['valid'] += 1
            elif result.status == ValidationStatus.OUTPUT_EXISTS:
                conflicts['output_exists'].append(result)
            else:
                conflicts['other_errors'].append(result)

        return conflicts

    def calculate_efficiency_forecast(self, file_path: str = "", media_info: dict = None, quality: int = 25,
                                      audio_encoder: str = "copy", encoder: str = "",
                                      source_info: dict = None, target_encoder: str = None,
                                      target_rf: int = None, target_audio_enc: str = None,
                                      target_audio_bitrate: int = None) -> dict:
        """
        Mathematically calculate projected output bitrate, size delta, and efficiency feedback.
        Accounts for source BPPF, target encoder profile, RF curve, and audio settings.
        """
        if source_info is not None and not media_info:
            media_info = source_info
        if target_encoder is not None and not encoder:
            encoder = target_encoder
        if target_rf is not None:
            quality = target_rf
        if target_audio_enc is not None:
            audio_encoder = target_audio_enc

        if encoder == 'copy':
            return {
                'status': 'passthrough',
                'delta_pct': 0.0,
                'warnings': [],
                'message': 'Passthrough Active: Video stream copied directly without re-encoding (instantaneous & 100% lossless).'
            }

        if not media_info:
            return {
                'status': 'info',
                'delta_pct': 0.0,
                'warnings': [],
                'message': f'Settings configured for RF {quality}. Analysis pending.'
            }

        # Encoder profile matching
        enc_key = (encoder or "x265").lower()
        if 'av1' in enc_key:
            profile = ENCODER_EFFICIENCY_PROFILES['svt_av1']
        elif 'nvenc' in enc_key and ('265' in enc_key or 'hevc' in enc_key):
            profile = ENCODER_EFFICIENCY_PROFILES['nvenc_h265']
        elif ('qsv' in enc_key or 'vce' in enc_key) and ('265' in enc_key or 'hevc' in enc_key):
            profile = ENCODER_EFFICIENCY_PROFILES['qsv_h265']
        elif 'nvenc' in enc_key:
            profile = ENCODER_EFFICIENCY_PROFILES['nvenc_h264']
        elif '265' in enc_key or 'hevc' in enc_key:
            profile = ENCODER_EFFICIENCY_PROFILES['x265']
        elif '264' in enc_key or 'avc' in enc_key:
            profile = ENCODER_EFFICIENCY_PROFILES['x264']
        else:
            profile = ENCODER_EFFICIENCY_PROFILES['x265']

        base_rf, base_bppf, divisor = profile

        # Extract resolution and framerate
        w = media_info.get('width')
        h = media_info.get('height')
        if not (w and h):
            w, h = _parse_resolution(media_info.get('resolution', ''))
        if not (w and h):
            w, h = 1280, 720

        fps = _parse_framerate(media_info.get('framerate', ''))
        pixel_rate = w * h * fps

        # Extract source bitrates
        src_v_bps = _parse_bitrate_bps(media_info.get('video_bitrate', ''))
        src_a_bps = _parse_bitrate_bps(media_info.get('audio_bitrate', '')) or 128_000
        if not src_v_bps:
            overall = _parse_bitrate_bps(media_info.get('overall_bitrate', ''))
            if overall and overall > src_a_bps:
                src_v_bps = overall - src_a_bps
            elif os.path.exists(file_path):
                sz = os.path.getsize(file_path)
                dur_s = _parse_duration_seconds(media_info.get('duration', ''))
                if dur_s and dur_s > 0:
                    src_v_bps = max(200_000, int((sz * 8) / dur_s) - src_a_bps)

        if not src_v_bps:
            # Fallback estimation for typical web source
            src_v_bps = int(pixel_rate * 0.080)

        src_bppf = src_v_bps / pixel_rate if pixel_rate > 0 else 0.080

        # Mathematical target video bitrate using exponential RF scaling
        rf_exponent = (quality - base_rf) / divisor
        r_raw = pixel_rate * base_bppf * math.pow(2.0, -rf_exponent)

        if r_raw >= src_v_bps:
            tgt_v_bps = min(r_raw, src_v_bps * 1.30)
        else:
            ratio = r_raw / src_v_bps
            tgt_v_bps = r_raw * (0.85 + 0.15 * ratio)

        # Target audio bitrate
        if audio_encoder == 'copy':
            tgt_a_bps = src_a_bps
        else:
            tgt_a_bps = 128_000

        src_total = src_v_bps + src_a_bps
        tgt_total = tgt_v_bps + tgt_a_bps
        delta = (tgt_total - src_total) / src_total if src_total > 0 else 0.0

        # File size estimation
        src_sz = None
        if os.path.exists(file_path):
            try:
                src_sz = os.path.getsize(file_path)
            except OSError:
                pass
        if not src_sz and media_info.get('file_size'):
            try:
                src_sz = int(media_info['file_size'])
            except Exception:
                pass
        if not src_sz and media_info.get('filesize'):
            m_sz = re.search(r'([\d.]+)\s*(gb|mb|kb)?', str(media_info['filesize']).lower())
            if m_sz:
                v = float(m_sz.group(1))
                u = m_sz.group(2) or 'mb'
                mult = 1024**3 if 'g' in u else (1024**2 if 'm' in u else 1024)
                src_sz = int(v * mult)

        est_sz = src_sz * (1.0 + delta) if src_sz else None
        src_sz_str = _format_size_bytes(src_sz) if src_sz else ""
        est_sz_str = f"~{_format_size_bytes(est_sz)}" if est_sz else ""

        # Labels
        v_codec = str(media_info.get('video', media_info.get('video_codec', ''))).upper()
        v_label = "H.264" if any(c in v_codec for c in ('H264', 'H.264', 'AVC')) else (v_codec or "Source")
        enc_label = encoder.upper() if encoder else "HEVC"
        res_str = f" ({w}x{h})" if (w and h) else ""
        src_mbps = src_v_bps / 1_000_000

        warnings = []

        # Categorize output
        is_already_hevc = any(c in v_codec for c in ('HEVC', 'H.265', 'AV1', 'VP9'))
        codec_name = "HEVC" if ("HEVC" in v_codec or "H.265" in v_codec) else ("AV1" if "AV1" in v_codec else ("VP9" if "VP9" in v_codec else "compressed"))
        already_desc = f"already {codec_name} and highly compressed" if is_already_hevc else "already highly compressed"

        if delta >= 0.05:
            status = 'warning'
            min_pct = max(2, int(round((delta - 0.03) * 100)))
            max_pct = int(round((delta + 0.04) * 100))
            rec_rf = quality + max(2, int(round(math.log2(1 + delta) * divisor)) + 1)
            est_comp = f" (est. {est_sz_str} vs source {src_sz_str})" if (est_sz_str and src_sz_str) else ""
            msg = (
                f"Source video is {already_desc} ({src_mbps:.1f} Mbps, BPPF {src_bppf:.3f}). "
                f"Re-encoding to {enc_label} at RF {quality} is projected to INCREASE file size by ~{min_pct}%–{max_pct}%{est_comp}. "
                f"Recommended: Use RF {rec_rf}+ to achieve compression, or choose Lossless Copy (passthrough)."
            )
            warnings.append(msg)
        elif -0.05 <= delta < 0.05:
            status = 'neutral'
            est_comp = f" (±5%, est. {est_sz_str})" if est_sz_str else " (±5%)"
            msg = (
                f"Break-Even Notice: Converting {v_label}{res_str} @ {src_mbps:.1f} Mbps to {enc_label} (RF {quality}) "
                f"is projected to produce approximately the SAME file size{est_comp} because the source is already low-bitrate. "
                f"Recommended: Use RF {quality + 2}–{quality + 4} if you want a 15–30% size reduction."
            )
        else:
            status = 'optimal'
            pct_mag = abs(delta)
            min_pct = max(5, int(round((pct_mag - 0.03) * 100)))
            max_pct = int(round((pct_mag + 0.03) * 100))
            est_comp = f" (est. {est_sz_str} vs source {src_sz_str})" if (est_sz_str and src_sz_str) else ""

            # Visual fidelity & quality classification based on encoder and RF
            enc_lower = (encoder or '').lower()
            is_h264_target = any(k in enc_lower for k in ('264', 'avc'))

            if is_h264_target:
                # H.264 RF scale
                if quality <= 19:
                    category = "Optimal"
                    fidelity_desc = "with near-lossless visual quality."
                elif quality <= 24:
                    category = "Optimal"
                    fidelity_desc = "with excellent visual fidelity."
                elif quality <= 27:
                    category = "Optimal"
                    fidelity_desc = "with good visual quality (balanced size and fidelity)."
                elif quality <= 32:
                    category = "High Compression"
                    fidelity_desc = "with noticeable compression trade-offs (minor softening in fine textures and motion)."
                elif quality <= 38:
                    category = "Aggressive Compression"
                    fidelity_desc = f"with visible quality degradation and compression artifacts (RF {quality} prioritizes low file size over fidelity)."
                else:
                    category = "Extreme Compression (Low Quality)"
                    fidelity_desc = f"with severe visual degradation (heavy macroblocking and loss of detail) (RF {quality} sacrifices visual quality for file size)."
            else:
                # HEVC / AV1 RF scale
                if quality <= 22:
                    category = "Optimal"
                    fidelity_desc = "with near-lossless visual quality."
                elif quality <= 27:
                    category = "Optimal"
                    fidelity_desc = "with excellent visual fidelity."
                elif quality <= 31:
                    category = "Optimal"
                    fidelity_desc = "with good visual quality (balanced size and fidelity)."
                elif quality <= 36:
                    category = "High Compression"
                    fidelity_desc = "with noticeable compression trade-offs (minor softening in fine textures and motion)."
                elif quality <= 43:
                    category = "Aggressive Compression"
                    fidelity_desc = f"with visible quality degradation and compression artifacts (RF {quality} prioritizes low file size over fidelity)."
                else:
                    category = "Extreme Compression (Low Quality)"
                    fidelity_desc = f"with severe visual degradation (heavy macroblocking and loss of detail) (RF {quality} sacrifices visual quality for file size)."

            msg = (
                f"{category}: Converting {v_label}{res_str} @ {src_mbps:.1f} Mbps to {enc_label} (RF {quality}) "
                f"is projected to achieve ~{min_pct}%–{max_pct}% file size reduction{est_comp} {fidelity_desc}"
            )

        # Check audio bloat
        a_codec = str(media_info.get('audio', media_info.get('audio_codec', ''))).upper()
        a_br = str(media_info.get('audio_bitrate', '')).lower()
        if audio_encoder == 'copy':
            m = re.search(r'(\d+)', a_br)
            br_val = int(m.group(1)) if m else 0
            is_heavy_audio = br_val >= 448 or any(k in a_codec for k in ('DTS', 'TRUEHD', 'EAC3'))
            if is_heavy_audio:
                audio_warn = (
                    f"Audio track is high-bitrate ({a_codec} {a_br}). "
                    f"Using 'copy' leaves audio uncompressed. "
                    f"Converting to AAC or Opus (128-160 kbps) will save hundreds of MB."
                )
                warnings.append(audio_warn)

        return {
            'status': status,
            'delta_pct': delta * 100.0,
            'warnings': warnings,
            'message': msg,
            'est_size_str': est_sz_str,
            'est_target_size_str': est_sz_str,
            'src_size_str': src_sz_str,
        }

    def check_efficiency(self, file_path: str = "", media_info: dict = None, quality: int = 25, audio_encoder: str = "copy", encoder: str = "") -> list[str]:
        """
        Check if current settings might lead to file bloat (output larger than input).
        Returns a list of warning/recommendation strings.
        """
        if isinstance(file_path, dict):
            media_info = file_path
            file_path = ""
        warnings = []
        if not media_info:
            return warnings

        v_codec = str(media_info.get('video', media_info.get('video_codec', ''))).upper()
        is_already_hevc = any(c in v_codec for c in ('HEVC', 'H.265', 'AV1', 'VP9'))
        v_bitrate_str = str(media_info.get('video_bitrate', '')).lower()

        # Run mathematical forecast
        forecast = self.calculate_efficiency_forecast(file_path, media_info, quality, audio_encoder, encoder=encoder)
        if forecast.get('warnings'):
            warnings.extend(forecast['warnings'])

        # Fallback/safeguard for already-HEVC files when forecast didn't already flag size expansion
        if is_already_hevc and quality <= 28 and not any("already" in w and "INCREASE" in w for w in warnings):
            codec_name = "HEVC" if ("HEVC" in v_codec or "H.265" in v_codec) else ("AV1" if "AV1" in v_codec else ("VP9" if "VP9" in v_codec else "compressed"))
            br_info = f" ({v_bitrate_str})" if v_bitrate_str else ""
            warnings.append(
                f"Source video is already {codec_name}{br_info}. "
                f"Re-encoding at RF {quality} will likely INCREASE file size. "
                f"Recommended: Use RF 30+ or preserve the original video."
            )

        # De-duplicate warnings while preserving order
        seen = set()
        deduped = []
        for w in warnings:
            if w not in seen:
                seen.add(w)
                deduped.append(w)
        return deduped

    def get_efficiency_feedback(self, file_path: str = "", media_info: dict = None, quality: int = 25,
                                audio_encoder: str = "copy", encoder: str = "") -> dict:
        """
        Get complete efficiency feedback and optimization forecasts for all media formats (MP4 and MKV).
        Returns a dict with 'status' ('warning', 'optimal', 'passthrough', 'info'), 'warnings', and 'message'.
        """
        if isinstance(file_path, dict):
            media_info = file_path
            file_path = ""
        if encoder == 'copy':
            return {
                'status': 'passthrough',
                'warnings': [],
                'message': 'Passthrough Active: Video stream copied directly without re-encoding (instantaneous & 100% lossless).'
            }

        forecast = self.calculate_efficiency_forecast(file_path, media_info, quality, audio_encoder, encoder=encoder)
        warnings = self.check_efficiency(file_path, media_info, quality, audio_encoder, encoder=encoder)
        forecast['warnings'] = warnings
        if warnings and forecast['status'] != 'warning':
            # E.g. audio warning on otherwise optimal video
            forecast['status'] = 'warning'
            forecast['message'] = warnings[0]
        elif warnings and forecast['status'] == 'warning':
            forecast['message'] = warnings[0]

        return forecast


# Utility functions
def generate_output_path(
    input_path: str,
    output_dir: str = None,
    format: str = "mp4",
    conflict_mode: str = "rename"
) -> str:
    """
    Generate output path with conflict handling.

    Args:
        input_path: Input file path
        output_dir: Output directory (default: same as input)
        format: Output format (mp4, mkv)
        conflict_mode: "rename" or "overwrite"

    Returns:
        Output file path
    """
    input_dir = os.path.dirname(input_path)
    input_stem = Path(input_path).stem

    if not output_dir:
        output_dir = input_dir

    output_ext = f".{format}"
    output_path = os.path.join(output_dir, input_stem + output_ext)

    # If the output would be the same file as the input (same dir, same extension),
    # always rename to avoid HandBrakeCLI reading from and writing to the same path.
    same_as_input = (os.path.normpath(output_path) == os.path.normpath(input_path))

    if same_as_input or (conflict_mode == "rename" and os.path.exists(output_path)):
        counter = 1
        while True:
            candidate = os.path.join(output_dir, f"{input_stem}_{counter}{output_ext}")
            # Skip if it would still collide with the input
            if os.path.normpath(candidate) == os.path.normpath(input_path):
                counter += 1
                continue
            if conflict_mode == "rename" and os.path.exists(candidate):
                counter += 1
                continue
            output_path = candidate
            break

    return output_path


_default_validator = FileValidator()


def calculate_efficiency_forecast(file_path: str = "", media_info: dict = None, quality: int = 25,
                                  audio_encoder: str = "copy", encoder: str = "",
                                  source_info: dict = None, target_encoder: str = None,
                                  target_rf: int = None, target_audio_enc: str = None,
                                  target_audio_bitrate: int = None) -> dict:
    return _default_validator.calculate_efficiency_forecast(
        file_path=file_path, media_info=media_info, quality=quality,
        audio_encoder=audio_encoder, encoder=encoder,
        source_info=source_info, target_encoder=target_encoder,
        target_rf=target_rf, target_audio_enc=target_audio_enc,
        target_audio_bitrate=target_audio_bitrate
    )


def check_efficiency(file_path: str = "", media_info: dict = None, quality: int = 25,
                     audio_encoder: str = "copy", encoder: str = "",
                     source_info: dict = None, target_encoder: str = None,
                     target_rf: int = None, target_audio_enc: str = None) -> list[str]:
    if source_info and not media_info:
        media_info = source_info
    if target_encoder and not encoder:
        encoder = target_encoder
    if target_rf is not None:
        quality = target_rf
    if target_audio_enc and not audio_encoder:
        audio_encoder = target_audio_enc
    return _default_validator.check_efficiency(file_path, media_info or {}, quality, audio_encoder, encoder=encoder)


def get_efficiency_feedback(file_path: str = "", media_info: dict = None, quality: int = 25,
                            audio_encoder: str = "copy", encoder: str = "",
                            source_info: dict = None, target_encoder: str = None,
                            target_rf: int = None, target_audio_enc: str = None) -> dict:
    if source_info and not media_info:
        media_info = source_info
    if target_encoder and not encoder:
        encoder = target_encoder
    if target_rf is not None:
        quality = target_rf
    if target_audio_enc and not audio_encoder:
        audio_encoder = target_audio_enc
    return _default_validator.get_efficiency_feedback(file_path, media_info or {}, quality, audio_encoder, encoder=encoder)


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    validator = FileValidator()

    # Test with non-existent file
    result = validator.validate_file("/nonexistent/file.mp4")
    print(f"Test: {result.status} - {result.message}")