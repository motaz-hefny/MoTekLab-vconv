"""
Hardware Detection and Encoder Management

Detects available GPU hardware and manages encoder options.
Supports NVIDIA (NVENC), Intel (QSV), AMD (VCE/VCN), and CPU encoders,
plus rigaya NVEncC as an optional backend when installed (auto-downloadable).

Capability detection is **runtime-probed** against the installed
HandBrakeCLI encoder list, so the app always offers exactly what the
local HandBrake build + GPU actually support (never a hardcoded guess).

Design notes (v9.7.0):
- Encoder ids are *families* (e.g. ``nvenc_h265``, ``svt_av1``). The 10-bit
  variant is selected via ``to_handbrake_encoder(enc, bit_depth=10)``.
- ``libsvtav1`` (invalid HandBrake id, caused "Invalid video encoder")
  is replaced by ``svt_av1``; the old id is still accepted and aliased.
- GPU AV1 (``nvenc_av1``) is only offered when the HandBrake build has it
  AND the GPU is Ada/Blackwell (RTX 40/50 series).
"""

import re
import subprocess
import logging
import shutil
from dataclasses import dataclass, field
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
    # Path to NVEncC binary when installed (separate backend), else None.
    nvenc_tool: Optional[str] = None


def _nvidia_supports_av1(gpu_name: str) -> bool:
    """True when an NVIDIA GPU supports NVENC AV1 (Ada/Blackwell: RTX 40/50+)."""
    if not gpu_name:
        return False
    # GeForce RTX 4060/4070/4080/4090/5060/... -> 4060..50xx
    m = re.search(r'RTX\s*(\d{4})', gpu_name)
    if m:
        return int(m.group(1)) >= 4000
    # Ampere cards are named RTX A6000 / A5000 (no bare 4-digit match) -> no AV1.
    return False


def _find_nvenc_tool() -> Optional[str]:
    """Locate rigaya NVEncC binary (auto-downloadable via tool updater)."""
    return shutil.which('NVEncC') or shutil.which('NVEncC64')


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
            encoders_available=[e for e in CPU_FAMILIES],
            nvenc_tool=_find_nvenc_tool(),
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
                    encoders_available=self._nvidia_families(gpu_name),
                    nvenc_tool=_find_nvenc_tool(),
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"NVIDIA detection failed: {e}")

        return None

    @staticmethod
    def _nvidia_families(gpu_name: str) -> list[str]:
        """NVIDIA encoder families supported by GPU + installed HandBrake."""
        hb = probe_handbrake_encoders()
        families = [f for f in CPU_FAMILIES]
        # GPU families the HandBrake build actually ships
        for fam, hb_id in (
            ('nvenc_h265', 'nvenc_h265'),
            ('nvenc_h264', 'nvenc_h264'),
        ):
            if hb_id in hb:
                families.insert(0, fam)
        if 'nvenc_av1' in hb and _nvidia_supports_av1(gpu_name):
            families.insert(0, 'nvenc_av1')
        # NVEncC native backend (optional, installed by tool updater)
        nv = _find_nvenc_tool()
        if nv:
            families.append('nvencc_h264')
            families.append('nvencc_hevc')
            if _nvidia_supports_av1(gpu_name):
                families.append('nvencc_av1')
        # de-dup, preserve order
        seen = set()
        out = []
        for f in families:
            if f not in seen:
                seen.add(f)
                out.append(f)
        return out

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
                    hb = probe_handbrake_encoders()
                    families = list(CPU_FAMILIES)
                    for fam, hb_id in (('qsv_h265', 'qsv_h265'), ('qsv_h264', 'qsv_h264')):
                        if hb_id in hb:
                            families.insert(0, fam)
                    nv = _find_nvenc_tool()
                    if nv:
                        families.append('nvencc_hevc')
                        families.append('nvencc_h264')
                    return HardwareInfo(
                        type=HardwareType.INTEL,
                        name=cpu_info or "Intel GPU",
                        detected=True,
                        encoders_available=families,
                        nvenc_tool=nv,
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
                    hb = probe_handbrake_encoders()
                    families = list(CPU_FAMILIES)
                    for fam, hb_id in (('amf_h265', 'amf_h265'), ('amf_h264', 'amf_h264')):
                        if hb_id in hb:
                            families.insert(0, fam)
                    nv = _find_nvenc_tool()
                    if nv:
                        families.append('nvencc_hevc')
                        families.append('nvencc_h264')
                    return HardwareInfo(
                        type=HardwareType.AMD,
                        name=gpu_name,
                        detected=True,
                        encoders_available=families,
                        nvenc_tool=nv,
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


# ---------------------------------------------------------------------------
# Encoder catalog (families)
# ---------------------------------------------------------------------------

# CPU families always available (HandBrake ships x264/x265/svt_av1).
CPU_FAMILIES = ['x265', 'x264', 'svt_av1']

# family -> (8-bit HandBrake encoder id, 10-bit HandBrake encoder id or None)
HB_FAMILY_IDS: dict[str, tuple[str, Optional[str]]] = {
    'nvenc_av1':   ('nvenc_av1', 'nvenc_av1'),
    'nvenc_h265':  ('nvenc_h265', 'nvenc_h265_10bit'),
    'nvenc_h264':  ('nvenc_h264', None),
    'qsv_h265':    ('qsv_h265', 'qsv_h265_10bit'),
    'qsv_h264':    ('qsv_h264', None),
    'amf_h265':    ('amf_h265', 'amf_h265_10bit'),
    'amf_h264':    ('amf_h264', None),
    'x265':        ('x265', 'x265_10bit'),
    'x264':        ('x264', 'x264_10bit'),
    'svt_av1':     ('svt_av1', 'svt_av1_10bit'),
}

# NVEncC (rigaya) native backend families -> (NVEncC --codec value, 10-bit ok)
NVENC_FAMILY_IDS: dict[str, tuple[str, bool]] = {
    'nvencc_av1':  ('av1', True),
    'nvencc_hevc': ('hevc', True),
    'nvencc_h264': ('h264', False),
}

# Backward-compat aliases for old/invalid ids found in config or presets.
ENCODER_ALIASES = {
    'libsvtav1': 'svt_av1',
    'svtav1': 'svt_av1',
    'hevc': 'x265',
    'h264': 'x264',
}

# GPU (hardware) families
HW_FAMILIES = {'nvenc_av1', 'nvenc_h265', 'nvenc_h264',
               'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264',
               'nvencc_av1', 'nvencc_hevc', 'nvencc_h264'}

_hb_encoders_cache: Optional[set[str]] = None


def probe_handbrake_encoders(refresh: bool = False) -> set[str]:
    """Parse the installed HandBrakeCLI's supported encoder ids (cached).

    Runs ``HandBrakeCLI --help`` once and extracts the ids listed under
    "Select video encoder:". Returns an empty set when HandBrakeCLI is
    missing (CPU families are still offered; conversion will error later).
    """
    global _hb_encoders_cache
    if _hb_encoders_cache is not None and not refresh:
        return _hb_encoders_cache

    encoders: set[str] = set()
    exe = shutil.which('HandBrakeCLI')
    if not exe:
        _hb_encoders_cache = encoders
        return encoders

    try:
        result = subprocess.run(
            [exe, '--help'],
            capture_output=True, text=True, timeout=20
        )
        text = (result.stdout or '') + (result.stderr or '')
    except Exception as e:
        logger.debug(f"HandBrake encoder probe failed: {e}")
        _hb_encoders_cache = encoders
        return encoders

    in_list = False
    for line in text.splitlines():
        if 'Select video encoder:' in line:
            in_list = True
            continue
        if in_list:
            stripped = line.strip()
            # End of the indented id list: next option flag or blank block.
            if stripped.startswith('-') or (stripped and '<' in stripped and ' ' in stripped):
                if encoders:
                    break
                continue
            if not stripped:
                if encoders:
                    break
                continue
            encoders.add(stripped)

    logger.info(f"HandBrake encoders: {sorted(encoders)}")
    _hb_encoders_cache = encoders
    return encoders


class EncoderManager:
    """Manages encoder options and HandBrakeCLI/NVEncC encoder mapping."""

    # Encoder descriptions for tooltips / badges
    ENCODER_INFO = {
        'nvenc_av1': {
            'name': 'NVIDIA AV1 (NVENC)',
            'description': 'Fastest GPU AV1 encoding (RTX 40/50 series)',
            'best_for': 'NVIDIA Ada/Blackwell GPUs - best speed + compression',
            'requires': 'NVIDIA RTX 40/50 series + HandBrake with nvenc_av1'
        },
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
        'nvencc_av1': {
            'name': 'NVEncC AV1 (NVIDIA)',
            'description': 'rigaya NVEncC native AV1 encode (auto-downloadable)',
            'best_for': 'NVIDIA Ada/Blackwell GPUs - fastest AV1 available',
            'requires': 'NVEncC installed + NVIDIA RTX 40/50 series'
        },
        'nvencc_hevc': {
            'name': 'NVEncC HEVC (NVIDIA)',
            'description': 'rigaya NVEncC native HEVC encode (auto-downloadable)',
            'best_for': 'NVIDIA GPUs - fastest HEVC, excellent for streaming',
            'requires': 'NVEncC installed + NVIDIA GPU with NVENC'
        },
        'nvencc_h264': {
            'name': 'NVEncC H.264 (NVIDIA)',
            'description': 'rigaya NVEncC native H.264 encode (auto-downloadable)',
            'best_for': 'NVIDIA GPUs - fastest H.264, wide compatibility',
            'requires': 'NVEncC installed + NVIDIA GPU with NVENC'
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
        'svt_av1': {
            'name': 'SVT-AV1 (CPU)',
            'description': 'Modern AV1 encoder with excellent compression',
            'best_for': 'Smallest files, future-proof, 10-bit capable',
            'requires': 'None (CPU-only, slower)'
        },
    }

    # Legacy HandBrakeCLI encoder mapping (kept for backward compatibility;
    # new code uses to_handbrake_encoder(encoder, bit_depth)).
    HB_ENCODER_MAP = {
        'nvenc_h265': 'nvenc_h265',
        'nvenc_h264': 'nvenc_h264',
        'qsv_h265': 'qsv_h265',
        'qsv_h264': 'qsv_h264',
        'amf_h265': 'amf_h265',
        'amf_h264': 'amf_h264',
        'x265': 'x265',
        'x264': 'x264',
        'svt_av1': 'svt_av1',
        # legacy invalid id aliased to the correct HandBrake id
        'libsvtav1': 'svt_av1',
    }

    def __init__(self):
        self.detector = HardwareDetector()
        self.hardware = self.detector.detect()

    # -- availability ------------------------------------------------------

    @staticmethod
    def normalize(encoder: str) -> str:
        """Map legacy/invalid encoder ids to canonical family ids."""
        enc = (encoder or '').strip()
        return ENCODER_ALIASES.get(enc, enc)

    def get_available_encoders(self) -> list[str]:
        """Get list of available encoder *families* for this machine."""
        seen = set()
        out = []
        for enc in self.hardware.encoders_available:
            enc = self.normalize(enc)
            if enc not in seen:
                seen.add(enc)
                out.append(enc)
        # CPU families are always present even if detection returned early
        for enc in CPU_FAMILIES:
            if enc not in seen:
                seen.add(enc)
                out.append(enc)
        return out

    def is_available(self, encoder: str) -> bool:
        return self.normalize(encoder) in self.get_available_encoders()

    # -- recommendation / badges -------------------------------------------

    def get_recommended_encoder(self) -> str:
        """Best encoder for this hardware (recommend, never force).

        Preference: GPU AV1 > GPU HEVC > NVEncC > CPU x265.
        """
        avail = self.get_available_encoders()
        if self.hardware.type == HardwareType.NVIDIA:
            for pref in ('nvenc_av1', 'nvenc_h265', 'nvencc_av1',
                         'nvencc_hevc', 'nvenc_h264', 'nvencc_h264'):
                if pref in avail:
                    return pref
        elif self.hardware.type == HardwareType.INTEL:
            for pref in ('qsv_h265', 'qsv_h264', 'nvencc_hevc', 'nvencc_h264'):
                if pref in avail:
                    return pref
        elif self.hardware.type == HardwareType.AMD:
            for pref in ('amf_h265', 'amf_h264', 'nvencc_hevc', 'nvencc_h264'):
                if pref in avail:
                    return pref
        for pref in ('x265', 'svt_av1'):
            if pref in avail:
                return pref
        return 'x265'

    def get_badge(self, encoder: str) -> str:
        """Short badge text for a dropdown entry (e.g. 'Best for your GPU')."""
        enc = self.normalize(encoder)
        if enc == self.get_recommended_encoder():
            if self.is_hardware_encoder(enc):
                return '★ Best for your GPU'
            return '★ Best'
        return ''

    def get_available_badge(self, encoder: str) -> str:
        """Availability marker (for encoders not usable on this machine)."""
        return '' if self.is_available(encoder) else ' (unavailable)'

    # -- info / mapping -----------------------------------------------------

    def get_encoder_info(self, encoder: str) -> dict:
        """Get detailed information about an encoder."""
        enc = self.normalize(encoder)
        return self.ENCODER_INFO.get(enc, {
            'name': enc,
            'description': 'Unknown encoder',
            'best_for': 'Unknown',
            'requires': 'Unknown'
        })

    def supports_10bit(self, encoder: str) -> bool:
        """True when the family has a 10-bit HandBrake variant (or NVEncC 10-bit)."""
        enc = self.normalize(encoder)
        if enc in NVENC_FAMILY_IDS:
            return NVENC_FAMILY_IDS[enc][1]
        pair = HB_FAMILY_IDS.get(enc)
        return bool(pair and pair[1])

    def to_handbrake_encoder(self, encoder: str, bit_depth: int = 8) -> str:
        """Convert encoder family id to a concrete HandBrakeCLI encoder id.

        ``bit_depth=10`` selects the ``*_10bit`` variant when one exists,
        preserving the source's color depth instead of down-converting to 8-bit.
        """
        enc = self.normalize(encoder)
        if enc in NVENC_FAMILY_IDS:
            # NVEncC backend — not a HandBrake id; converter handles it.
            return enc
        pair = HB_FAMILY_IDS.get(enc)
        if pair:
            hb8, hb10 = pair
            if bit_depth and bit_depth >= 10 and hb10:
                return hb10
            return hb8
        # Unknown: preserve old behaviour (pass through), alias fixed.
        return self.HB_ENCODER_MAP.get(enc, enc)

    def encode_backend(self, encoder: str) -> str:
        """'nvenc' when the encoder uses rigaya NVEncC, else 'handbrake'."""
        return 'nvenc' if self.normalize(encoder) in NVENC_FAMILY_IDS else 'handbrake'

    def is_hardware_encoder(self, encoder: str) -> bool:
        """Check if encoder is hardware accelerated."""
        return self.normalize(encoder) in HW_FAMILIES

    def get_hardware_name(self) -> str:
        """Get the detected hardware name for display."""
        return self.hardware.name

    def get_nvenc_tool(self) -> Optional[str]:
        """Path to NVEncC when installed (None otherwise)."""
        return self.hardware.nvenc_tool or _find_nvenc_tool()


if __name__ == "__main__":
    # Test hardware detection
    detector = HardwareDetector()
    hardware = detector.detect()
    print(f"Detected: {hardware.type.value} - {hardware.name}")
    print(f"Available encoders: {hardware.encoders_available}")

    manager = EncoderManager()
    best = manager.get_recommended_encoder()
    print(f"Recommended: {best}  badge={manager.get_badge(best)!r}")
    for enc in manager.get_available_encoders():
        print(f"  {enc}: hb={manager.to_handbrake_encoder(enc, 10)} "
              f"10bit={manager.supports_10bit(enc)} "
              f"hw={manager.is_hardware_encoder(enc)} "
              f"badge={manager.get_badge(enc)!r}")
