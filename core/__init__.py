"""
vconv Core Package
Core functionality modules for video encoding, analysis, and queue management.
"""

from .encoder import HardwareDetector, EncoderManager
from .converter import Converter
from .analyzer import MediaAnalyzer
from .validator import FileValidator
from .queue import QueueManager, Job

__all__ = [
    'HardwareDetector',
    'EncoderManager',
    'Converter',
    'MediaAnalyzer',
    'FileValidator',
    'QueueManager',
    'Job',
]

__version__ = '8.2.0'