"""
Dependency Checker and Installer Module

Detects missing dependencies and offers installation options.
"""

import subprocess
import shutil
import logging
import urllib.request
import tempfile
import os
import platform
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class InstallMethod(Enum):
    """Installation method types."""
    SYSTEM_PACKAGE = "system"
    INTERNAL_DOWNLOAD = "download"
    MANUAL_LINK = "manual"


@dataclass
class Dependency:
    """Dependency information."""
    name: str
    command: str
    package_name: str
    install_hint: str
    required: bool = True
    download_url: str = ""
    download_filename: str = ""


class DependencyChecker:
    """
    Checks for and helps install required dependencies.
    """

    # Define required dependencies
    DEPENDENCIES = {
        'handbrake': Dependency(
            name='HandBrakeCLI',
            command='HandBrakeCLI',
            package_name='handbrake-cli',
            install_hint='Video encoding engine',
            download_url='https://handbrake.fr/downloads.php',
            download_filename='HandBrakeCLI'
        ),
        'ffprobe': Dependency(
            name='FFprobe',
            command='ffprobe',
            package_name='ffmpeg',
            install_hint='Media analysis tool',
            download_url='https://ffmpeg.org/download.html',
            download_filename='ffmpeg'
        ),
        'python': Dependency(
            name='Python',
            command='python3',
            package_name='python3',
            install_hint='Application runtime',
            required=True
        )
    }

    def __init__(self):
        self.missing_deps: List[str] = []
        self.check_all()

    def check_all(self) -> bool:
        """Check all dependencies."""
        self.missing_deps = []

        for key, dep in self.DEPENDENCIES.items():
            if not self._check_command(dep.command):
                self.missing_deps.append(key)
                logger.warning(f"Missing dependency: {dep.name}")

        return len(self.missing_deps) == 0

    def _check_command(self, command: str) -> bool:
        """Check if a command is available."""
        return shutil.which(command) is not None

    def get_missing(self) -> List[Dependency]:
        """Get list of missing dependencies."""
        return [
            self.DEPENDENCIES[key]
            for key in self.missing_deps
            if key in self.DEPENDENCIES
        ]

    def is_missing(self, dep_key: str) -> bool:
        """Check if specific dependency is missing."""
        return dep_key in self.missing_deps

    def get_install_options(self, dep: Dependency) -> List[Tuple[str, str, str]]:
        """
        Get installation options for a dependency.

        Returns:
            List of (method, description, command) tuples
        """
        options = []

        # System package manager
        pkg_manager = self._detect_package_manager()
        if pkg_manager:
            install_cmd = self._get_system_install_command(pkg_manager, dep.package_name)
            options.append((
                InstallMethod.SYSTEM_PACKAGE.value,
                f"Install via {pkg_manager}",
                install_cmd
            ))

        # Download option
        if dep.download_url:
            options.append((
                InstallMethod.MANUAL_LINK.value,
                "Download manually",
                dep.download_url
            ))

        # Internal download (for some tools)
        if dep.download_filename:
            options.append((
                InstallMethod.INTERNAL_DOWNLOAD.value,
                "Download & install automatically",
                f"download:{dep.download_filename}"
            ))

        return options

    def _detect_package_manager(self) -> Optional[str]:
        """Detect available package manager."""
        managers = ['apt-get', 'dnf', 'pacman', 'zypper', 'brew']
        for mgr in managers:
            if shutil.which(mgr):
                return mgr
        return None

    def _get_system_install_command(self, pkg_mgr: str, package: str) -> str:
        """Get system package install command."""
        commands = {
            'apt-get': f'sudo apt-get update && sudo apt-get install -y {package}',
            'dnf': f'sudo dnf install -y {package}',
            'pacman': f'sudo pacman -S --noconfirm {package}',
            'zypper': f'sudo zypper install -y {package}',
            'brew': f'brew install {package}'
        }
        return commands.get(pkg_mgr, f'Unknown package manager: {pkg_mgr}')

    def install_via_system(self, package: str) -> bool:
        """Install package using system package manager."""
        pkg_mgr = self._detect_package_manager()
        if not pkg_mgr:
            logger.error("No package manager detected")
            return False

        cmd = self._get_system_install_command(pkg_mgr, package)

        try:
            logger.info(f"Installing: {package}")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if result.returncode == 0:
                logger.info(f"Successfully installed: {package}")
                return True
            else:
                logger.error(f"Installation failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Installation timed out")
            return False
        except Exception as e:
            logger.error(f"Installation error: {e}")
            return False

    def verify_installation(self, command: str) -> bool:
        """Verify a command is now available."""
        return self._check_command(command)

    def get_system_info(self) -> dict:
        """Get system information for debugging."""
        info = {
            'os': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'package_manager': self._detect_package_manager()
        }

        # Check GPU (basic)
        if shutil.which('nvidia-smi'):
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    info['nvidia_gpu'] = result.stdout.strip()
            except Exception:
                pass

        return info


# Installer dialog helper
class InstallerDialogHelper:
    """Helps create installer dialog content."""

    @staticmethod
    def create_install_dialog_content(missing_deps: List[Dependency]) -> dict:
        """Create content for install dialog."""
        lines = ["The following dependencies are missing:\n"]

        for dep in missing_deps:
            lines.append(f"• {dep.name}")
            lines.append(f"  Purpose: {dep.install_hint}")
            lines.append(f"  Package: {dep.package_name}")
            lines.append("")

        lines.append("Would you like to install them?")

        return {
            'title': 'Missing Dependencies',
            'message': "\n".join(lines),
            'deps': missing_deps
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    checker = DependencyChecker()
    print(f"All deps available: {checker.check_all()}")

    if checker.missing_deps:
        print(f"Missing: {checker.missing_deps}")
        for dep in checker.get_missing():
            print(f"\nInstall options for {dep.name}:")
            options = checker.get_install_options(dep)
            for method, desc, cmd in options:
                print(f"  [{method}] {desc}: {cmd}")

    print(f"\nSystem info: {checker.get_system_info()}")