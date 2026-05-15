"""
Hardware Detection and Encoder Management

Detects available GPU hardware and manages encoder options.
Supports NVIDIA (NVENC), Intel (QSV), AMD (VCE/VCN), and CPU encoders.
"""

import subprocess
import logging
import shutil
from dataclasses import dataclass
from typing import Optional
from enum import Enum


logger = logging.getLogger(__name__)


class HardwareType(Enum):
    """Hardware acceleration types."""
    NONE = "none"
    NVIDIA = "nvidia"
    INTEL = "intel"
    AMD = "amd"


@dataclass
class HardwareInfo:
    """Hardware information container."""
    type: HardwareType
    name: str
    detected: bool
    encoders_available: list[str]


class HardwareDetector:
    """Detects available GPU hardware on the system."""

    def __init__(self):
        self._hardware = None

    def detect(self) -> HardwareInfo:
        """Detect available hardware."""
        if self._hardware:
            return self._hardware

        # Check NVIDIA
        nvidia_info = self._detect_nvidia()
        if nvidia_info:
            self._hardware = nvidia_info
            logger.info(f"Detected NVIDIA GPU: {nvidia_info.name}")
            return self._hardware

        # Check Intel Quick Sync
        intel_info = self._detect_intel()
        if intel_info:
            self._hardware = intel_info
            logger.info(f"Detected Intel GPU: {intel_info.name}")
            return self._hardware

        # Check AMD
        amd_info = self._detect_amd()
        if amd_info:
            self._hardware = amd_info
            logger.info(f"Detected AMD GPU: {amd_info.name}")
            return self._hardware

        # No hardware acceleration
        self._hardware = HardwareInfo(
            type=HardwareType.NONE,
            name="CPU Only",
            detected=False,
            encoders_available=["x264", "x265", "libsvtav1"]
        )
        logger.info("No GPU detected, using CPU encoding")
        return self._hardware

    def _detect_nvidia(self) -> Optional[HardwareInfo]:
        """Detect NVIDIA GPU using nvidia-smi."""
        if not shutil.which('nvidia-smi'):
            return None

        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip()
                return HardwareInfo(
                    type=HardwareType.NVIDIA,
                    name=gpu_name,
                    detected=True,
                    encoders_available=["nvenc_h265", "nvenc_h264", "x264", "x265"]
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"NVIDIA detection failed: {e}")

        return None

    def _detect_intel(self) -> Optional[HardwareInfo]:
        """Detect Intel GPU using vainfo."""
        if not shutil.which('vainfo'):
            return None

        try:
            result = subprocess.run(
                ['vainfo'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout + result.stderr
                if 'H264' in output and ('Intel' in output or 'iHD' in output):
                    # Try to get more specific GPU info
                    cpu_info = self._get_cpu_name()
                    return HardwareInfo(
                        type=HardwareType.INTEL,
                        name=cpu_info or "Intel GPU",
                        detected=True,
                        encoders_available=["qsv_h265", "qsv_h264", "x264", "x265"]
                    )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"Intel detection failed: {e}")

        return None

    def _detect_amd(self) -> Optional[HardwareInfo]:
        """Detect AMD GPU."""
        if not shutil.which('vainfo'):
            return None

        try:
            result = subprocess.run(
                ['vainfo'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout + result.stderr
                if 'H264' in output and ('AMD' in output or 'r600' in output):
                    gpu_name = self._get_amd_gpu_name() or "AMD GPU"
                    return HardwareInfo(
                        type=HardwareType.AMD,
                        name=gpu_name,
                        detected=True,
                        encoders_available=["amf_h265", "amf_h264", "x264", "x265"]
                    )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"AMD detection failed: {e}")

        return None

    def _get_cpu_name(self) -> Optional[str]:
        """Get CPU model name for Intel identification."""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return None

    def _get_amd_gpu_name(self) -> Optional[str]:
        """Get AMD GPU name using lspci."""
        try:
            result = subprocess.run(
                ['lspci', '-mm', '-n', '-d', '::0300'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'AMD' in line or 'Radeon' in line:
                        # Extract GPU name from the line
                        parts = line.split('"')
                        if len(parts) >= 2:
                            return parts[1].split(':')[-1].strip()
        except Exception:
            pass
        return None


class EncoderManager:
    """Manages encoder options and HandBrakeCLI encoder mapping."""

    # Encoder descriptions for tooltips
    ENCODER_INFO = {
        'nvenc_h265': {
            'name': 'NVIDIA HEVC (NVENC)',
            'description': 'Fast GPU encoding using NVIDIA CUDA',
            'best_for': 'NVIDIA GPUs - fastest encoding, good quality',
            'requires': 'NVIDIA GPU with NVENC support'
        },
        'nvenc_h264': {
            'name': 'NVIDIA H.264 (NVENC)',
            'description': 'Fast H.264 encoding using NVIDIA CUDA',
            'best_for': 'NVIDIA GPUs - fastest H.264 encoding',
            'requires': 'NVIDIA GPU with NVENC support'
        },
        'qsv_h265': {
            'name': 'Intel HEVC (Quick Sync)',
            'description': 'Hardware accelerated HEVC using Intel Quick Sync',
            'best_for': 'Intel CPUs with integrated GPU - fast, low power',
            'requires': 'Intel CPU with Quick Sync (6th gen+)'
        },
        'qsv_h264': {
            'name': 'Intel H.264 (Quick Sync)',
            'description': 'Hardware accelerated H.264 using Intel Quick Sync',
            'best_for': 'Intel CPUs with integrated GPU - fast, low power',
            'requires': 'Intel CPU with Quick Sync (6th gen+)'
        },
        'amf_h265': {
            'name': 'AMD HEVC (AMF)',
            'description': 'Hardware accelerated HEVC using AMD VCE/VCN',
            'best_for': 'AMD GPUs (RX series) - good speed/quality balance',
            'requires': 'AMD GPU with VCE/VCN support'
        },
        'amf_h264': {
            'name': 'AMD H.264 (AMF)',
            'description': 'Hardware accelerated H.264 using AMD VCE/VCN',
            'best_for': 'AMD GPUs (RX series) - fast H.264 encoding',
            'requires': 'AMD GPU with VCE/VCN support'
        },
        'x265': {
            'name': 'x265 (CPU)',
            'description': 'High quality HEVC encoding using CPU',
            'best_for': 'Quality-first encoding, no GPU required',
            'requires': 'None (CPU-only)'
        },
        'x264': {
            'name': 'x264 (CPU)',
            'description': 'Mature H.264 encoder with wide compatibility',
            'best_for': 'Maximum compatibility, proven quality',
            'requires': 'None (CPU-only)'
        },
        'libsvtav1': {
            'name': 'SVT-AV1 (CPU)',
            'description': 'Modern AV1 encoder with excellent compression',
            'best_for': 'Future-proof, smallest file sizes',
            'requires': 'None (CPU-only, slower)'
        }
    }

    # HandBrakeCLI encoder mappings
    HB_ENCODER_MAP = {
        'nvenc_h265': 'nvenc_h265',
        'nvenc_h264': 'nvenc_h264',
        'qsv_h265': 'qsv_h265',
        'qsv_h264': 'qsv_h264',
        'amf_h265': 'amf_h265',
        'amf_h264': 'amf_h264',
        'x265': 'x265',
        'x264': 'x264',
        'libsvtav1': 'libsvtav1'
    }

    def __init__(self):
        self.detector = HardwareDetector()
        self.hardware = self.detector.detect()

    def get_available_encoders(self) -> list[str]:
        """Get list of available encoders based on hardware."""
        return self.hardware.encoders_available

    def get_recommended_encoder(self) -> str:
        """Get the recommended encoder based on detected hardware."""
        if self.hardware.type == HardwareType.NVIDIA:
            return 'nvenc_h265'
        elif self.hardware.type == HardwareType.INTEL:
            return 'qsv_h265'
        elif self.hardware.type == HardwareType.AMD:
            return 'amf_h265'
        else:
            return 'x265'

    def get_encoder_info(self, encoder: str) -> dict:
        """Get detailed information about an encoder."""
        return self.ENCODER_INFO.get(encoder, {
            'name': encoder,
            'description': 'Unknown encoder',
            'best_for': 'Unknown',
            'requires': 'Unknown'
        })

    def to_handbrake_encoder(self, encoder: str) -> str:
        """Convert generic encoder name to HandBrakeCLI format."""
        return self.HB_ENCODER_MAP.get(encoder, encoder)

    def is_hardware_encoder(self, encoder: str) -> bool:
        """Check if encoder is hardware accelerated."""
        return encoder in ['nvenc_h265', 'nvenc_h264', 'qsv_h265',
                         'qsv_h264', 'amf_h265', 'amf_h264']

    def get_hardware_name(self) -> str:
        """Get the detected hardware name for display."""
        return self.hardware.name


if __name__ == "__main__":
    # Test hardware detection
    detector = HardwareDetector()
    hardware = detector.detect()
    print(f"Detected: {hardware.type.value} - {hardware.name}")
    print(f"Available encoders: {hardware.encoders_available}")

    manager = EncoderManager()
    print(f"Recommended: {manager.get_recommended_encoder()}")