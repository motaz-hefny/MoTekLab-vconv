"""
Video Converter Module - HandBrakeCLI wrapper with real progress tracking
"""
import subprocess
import os
import logging
import threading
import time
import re
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ConversionSettings:
    encoder: str = "x265"
    quality: int = 27
    audio_encoder: str = "copy"
    audio_bitrate: Optional[int] = None
    resolution: Optional[str] = None
    denoise: str = "off"
    deinterlace: str = "off"
    rotation: int = 0
    subtitle_mode: str = "copy"
    subtitle_burn: bool = False
    subtitle_lang_list: str = ""
    external_srt_files: list = None
    external_srt_burn: bool = False
    external_srt_default: bool = True
    output_format: str = "mp4"
    advanced: Optional[dict] = None

    def __post_init__(self):
        if self.external_srt_files is None:
            self.external_srt_files = []

@dataclass
class ConversionProgress:
    percent: float = 0.0
    fps: float = 0.0
    eta_seconds: int = 0
    current_frame: int = 0
    total_frames: int = 0

class Converter:
    def __init__(self, encoder_manager):
        self.encoder_manager = encoder_manager
        self._current_process: Optional[subprocess.Popen] = None
        self._cancel_flag = False

    def convert(self, input_path: str, output_path: str, settings: ConversionSettings,
                progress_callback: Optional[Callable] = None) -> bool:
        self._cancel_flag = False
        if not os.path.exists(input_path):
            logger.error(f"Input not found: {input_path}")
            return False

        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        cmd = self._build_command(input_path, output_path, settings)
        logger.info(f"Converting: {input_path} -> {output_path}")
        logger.debug(f"Command: {' '.join(cmd)}")

        try:
            self._current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1
            )
            self._monitor_progress(progress_callback)
            self._current_process.wait()
            exit_code = self._current_process.returncode

            if self._cancel_flag:
                logger.info("Conversion cancelled")
                return False
            if exit_code != 0:
                logger.error(f"HandBrakeCLI exit code: {exit_code}")
                return False
            logger.info(f"Completed: {output_path}")
            return True
        except FileNotFoundError:
            logger.error("HandBrakeCLI not found")
            return False
        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            return False
        finally:
            self._current_process = None

    def cancel(self):
        self._cancel_flag = True
        if self._current_process:
            try:
                self._current_process.terminate()
            except:
                pass

    def _build_command(self, input_path: str, output_path: str, settings: ConversionSettings) -> list:
        cmd = ['HandBrakeCLI', '-i', input_path, '-o', output_path,
               '--encoder', self.encoder_manager.to_handbrake_encoder(settings.encoder),
               '--quality', str(settings.quality)]

        if settings.audio_encoder == 'copy':
            cmd.extend(['--aencoder', 'copy'])
        else:
            cmd.extend(['--aencoder', settings.audio_encoder])
            if settings.audio_bitrate:
                cmd.extend(['--ab', str(settings.audio_bitrate)])

        if settings.resolution and 'x' in settings.resolution:
            w, h = settings.resolution.split('x')
            cmd.extend(['--width', w, '--height', h])

        if settings.denoise != 'off':
            denoise_map = {'light': 'weak', 'medium': 'medium', 'strong': 'strong'}
            cmd.extend(['--denoise', denoise_map.get(settings.denoise, 'off')])
        if settings.deinterlace == 'on':
            cmd.append('--deinterlace')
        elif settings.deinterlace == 'auto':
            cmd.extend(['--deinterlace', 'auto'])
        if settings.rotation != 0:
            cmd.extend(['--rotate', str(settings.rotation)])

        if settings.output_format == 'mkv':
            cmd.extend(['--format', 'mkv'])
        else:
            cmd.extend(['--format', 'mp4'])

        cmd.extend(self._build_subtitle_args(settings))

        # Add advanced x264/x265 settings
        if settings.encoder in ['x264', 'x265']:
            if settings.advanced:
                x_opts = ':'.join(f"{k}={v}" for k, v in settings.advanced.items())
                cmd.extend(['-x', x_opts])
            else:
                cmd.extend(['-x', 'cabac=1:ref=5:analyse=0x133:me=umh:subme=9:chroma-me=1:deadzone-inter=21:deadzone-intra=11:b-adapt=2:rc-lookahead=60:vbv-maxrate=10000:vbv-bufsize=10000:qpmax=69:bframes=5:direct=auto'])

        return cmd

    def _build_subtitle_args(self, settings: ConversionSettings) -> list:
        args = []

        if settings.subtitle_mode == 'none':
            args.append('--subtitle')
            args.append('none')
            return args

        if settings.subtitle_mode in ['copy', 'all']:
            if settings.subtitle_lang_list:
                args.extend(['--subtitle-lang-list', settings.subtitle_lang_list])
                if settings.subtitle_mode == 'all':
                    args.append('--all-subtitles')
            else:
                args.append('--all-subtitles')

            if settings.subtitle_burn:
                args.append('--subtitle-burned')

        srt_files = []
        srt_langs = []
        srt_defaults = []
        srt_burns = []
        ssa_files = []
        ssa_langs = []
        ssa_defaults = []
        ssa_burns = []

        for i, sub_entry in enumerate(settings.external_srt_files):
            if isinstance(sub_entry, tuple):
                srt_file, lang = sub_entry
            else:
                srt_file = sub_entry
                lang = 'eng'
            if not os.path.exists(srt_file):
                logger.warning(f"External subtitle not found: {srt_file}")
                continue
            ext = os.path.splitext(srt_file)[1].lower()
            idx = i + 1
            if ext == '.srt':
                srt_files.append(srt_file)
                srt_langs.append(lang)
                if settings.external_srt_default:
                    srt_defaults.append(str(idx))
                if settings.external_srt_burn:
                    srt_burns.append(str(idx))
            elif ext in ['.ass', '.ssa']:
                ssa_files.append(srt_file)
                ssa_langs.append(lang)
                if settings.external_srt_default:
                    ssa_defaults.append(str(idx))
                if settings.external_srt_burn:
                    ssa_burns.append(str(idx))

        if srt_files:
            args.extend(['--srt-file', ','.join(srt_files)])
            args.extend(['--srt-codeset', ','.join(['UTF-8'] * len(srt_files))])
            args.extend(['--srt-lang', ','.join(srt_langs)])
            if srt_defaults:
                args.extend(['--srt-default', ','.join(srt_defaults)])
            if srt_burns:
                args.extend(['--srt-burn', ','.join(srt_burns)])

        if ssa_files:
            args.extend(['--ssa-file', ','.join(ssa_files)])
            args.extend(['--ssa-lang', ','.join(ssa_langs)])
            if ssa_defaults:
                args.extend(['--ssa-default', ','.join(ssa_defaults)])
            if ssa_burns:
                args.extend(['--ssa-burn', ','.join(ssa_burns)])

        return args

    def _monitor_progress(self, callback):
        if not self._current_process:
            return
        # Patterns for HandBrake progress output
        pct_pattern = re.compile(r'Encoding:\s+task\s+\d+\s+of\s+\d+,\s+([\d.]+)\s+%')
        fps_pattern = re.compile(r'([\d.]+)\s+fps')
        eta_pattern = re.compile(r'ETA\s+([\d:]+)')

        while self._current_process.poll() is None:
            try:
                line = self._current_process.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                match = pct_pattern.search(line)
                if match:
                    pct = float(match.group(1))
                    fps = 0.0
                    fps_m = fps_pattern.search(line)
                    if fps_m:
                        fps = float(fps_m.group(1))
                    if callback:
                        callback(ConversionProgress(percent=pct, fps=fps))
            except:
                break

def create_default_settings() -> ConversionSettings:
    return ConversionSettings(encoder="x265", quality=27, audio_encoder="copy", output_format="mp4")