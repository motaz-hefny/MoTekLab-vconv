"""
File Validator Module

Validates files before conversion: checks existence, validity, output conflicts.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from core.constants import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


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

    def validate_batch(self, files: list[tuple], output_dir: str = None) -> list[ValidationResult]:
        """
        Validate multiple files for batch processing.

        Args:
            files: List of (input_path, output_path) tuples
            output_dir: Default output directory (optional)

        Returns:
            List of ValidationResult
        """
        results = []

        for input_path, output_path in files:
            if output_path is None and output_dir:
                # Generate default output path
                filename = Path(input_path).stem + ".mp4"
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

    # Handle conflicts
    if conflict_mode == "rename" and os.path.exists(output_path):
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(output_dir, f"{input_stem}_{counter}{output_ext}")
            counter += 1

    return output_path


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    validator = FileValidator()

    # Test with non-existent file
    result = validator.validate_file("/nonexistent/file.mp4")
    print(f"Test: {result.status} - {result.message}")