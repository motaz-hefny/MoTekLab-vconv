"""
Video Converter Module

Wrapper for HandBrakeCLI to handle video encoding operations.
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
    """Conversion settings container."""
    encoder: str = "x265"
    quality: int = 23  # RF value (0-51)
    audio_encoder: str = "copy"
    audio_bitrate: Optional[int] = None
    resolution: Optional[str] = None  # "1920x1080", "1280x720", etc.
    denoise: str = "off"
    deinterlace: str = "off"
    rotation: int = 0
    subtitle_track: Optional[int] = None
    burn_subtitle: bool = False
    output_format: str = "mp4"


@dataclass
class ConversionProgress:
    """Progress information."""
    percent: float = 0.0
    current_frame: int = 0
    fps: float = 0.0
    eta_seconds: int = 0
    current_task: str = ""


class Converter:
    """Handles video conversion using HandBrakeCLI."""

    def __init__(self, encoder_manager):
        self.encoder_manager = encoder_manager
        self._current_process: Optional[subprocess.Popen] = None
        self._cancel_flag = False
        self._progress_callback: Optional[Callable] = None

    def convert(
        self,
        input_path: str,
        output_path: str,
        settings: ConversionSettings,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Convert a video file.

        Args:
            input_path: Path to input video
            output_path: Path to output video
            settings: Conversion settings
            progress_callback: Callback function for progress updates

        Returns:
            True if conversion succeeded, False otherwise
        """
        self._cancel_flag = False
        self._progress_callback = progress_callback

        # Validate input file
        if not os.path.exists(input_path):
            logger.error(f"Input file not found: {input_path}")
            return False

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Build HandBrakeCLI command
        cmd = self._build_command(input_path, output_path, settings)
        logger.info(f"Starting conversion: {input_path} -> {output_path}")
        logger.debug(f"Command: {' '.join(cmd)}")

        try:
            # Start process with piping
            self._current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # Monitor progress
            self._monitor_progress()

            # Wait for completion
            self._current_process.wait()
            exit_code = self._current_process.returncode

            if self._cancel_flag:
                logger.info("Conversion cancelled by user")
                return False

            if exit_code != 0:
                logger.error(f"HandBrakeCLI exited with code: {exit_code}")
                return False

            logger.info(f"Conversion completed: {output_path}")
            return True

        except FileNotFoundError:
            logger.error("HandBrakeCLI not found in system")
            return False
        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            return False
        finally:
            self._current_process = None

    def cancel(self):
        """Cancel current conversion."""
        self._cancel_flag = True
        if self._current_process:
            try:
                self._current_process.terminate()
                logger.info("Conversion terminated")
            except Exception as e:
                logger.warning(f"Failed to terminate process: {e}")

    def _build_command(self, input_path: str, output_path: str, settings: ConversionSettings) -> list:
        """Build HandBrakeCLI command from settings."""
        cmd = [
            'HandBrakeCLI',
            '-i', input_path,
            '-o', output_path,
            '--encoder', self.encoder_manager.to_handbrake_encoder(settings.encoder),
            '--quality', str(settings.quality),
        ]

        # Audio settings
        if settings.audio_encoder == 'copy':
            cmd.extend(['--aencoder', 'copy'])
        else:
            cmd.extend(['--aencoder', settings.audio_encoder])
            if settings.audio_bitrate:
                cmd.extend(['--ab', str(settings.audio_bitrate)])

        # Resolution
        if settings.resolution:
            if 'x' in settings.resolution:
                width, height = settings.resolution.split('x')
                cmd.extend(['--width', width, '--height', height])

        # Video filters
        if settings.denoise != 'off':
            if settings.denoise == 'light':
                cmd.extend(['--denoise', 'weak'])
            elif settings.denoise == 'medium':
                cmd.extend(['--denoise', 'medium'])
            elif settings.denoise == 'strong':
                cmd.extend(['--denoise', 'strong'])

        if settings.deinterlace == 'on':
            cmd.extend(['--deinterlace'])
        elif settings.deinterlace == 'auto':
            cmd.extend(['--deinterlace', 'auto'])

        if settings.rotation != 0:
            cmd.extend(['--rotate', str(settings.rotation)])

        # Subtitles
        if settings.subtitle_track is not None:
            if settings.burn_subtitle:
                cmd.extend(['--subtitle', f'{settings.subtitle_track}', '--burn-subtitle', f'{settings.subtitle_track}'])
            else:
                cmd.extend(['--subtitle', f'{settings.subtitle_track}'])

        # Format
        if settings.output_format == 'mkv':
            cmd.extend(['--format', 'mkv'])
        else:
            cmd.extend(['--format', 'mp4'])

        # Extra options for better quality (tuned settings)
        if settings.encoder in ['x264', 'x265']:
            cmd.extend([
                '--x264-preset', 'medium',
                '--h264-level', '4.1'
            ])

        return cmd

    def _monitor_progress(self):
        """Monitor conversion progress from stderr output."""
        if not self._current_process:
            return

        # Progress pattern: "Encoding: task 1 of 1, 50.00 %"
        progress_pattern = re.compile(r'Encoding:\s+task\s+\d+\s+of\s+\d+,\s+([\d.]+)\s+%')

        while self._current_process.poll() is None:
            try:
                # Read stderr line (HandBrake outputs progress here)
                line = self._current_process.stderr.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                # Parse progress
                match = progress_pattern.search(line)
                if match:
                    percent = float(match.group(1))
                    if self._progress_callback:
                        progress = ConversionProgress(
                            percent=percent,
                            current_task="Encoding"
                        )
                        self._progress_callback(progress)

            except Exception as e:
                logger.debug(f"Progress parsing error: {e}")
                break


def create_default_settings() -> ConversionSettings:
    """Create default conversion settings."""
    return ConversionSettings(
        encoder="x265",
        quality=23,
        audio_encoder="copy",
        output_format="mp4"
    )


# Test
if __name__ == "__main__":
    from encoder import EncoderManager

    em = EncoderManager()
    converter = Converter(em)

    print("Converter initialized")
    print(f"Default encoder: {em.get_recommended_encoder()}")