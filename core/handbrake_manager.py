"""HandBrakeCLI detection, installation, and update management."""

import os
import re
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)

FLATPAK_APP_ID = "fr.handbrake.ghb"
FLATPAK_CLI_HELPER = "fr.handbrake.HandBrakeCLI"


class HandBrakeManager:
    """Detect, install, and update HandBrakeCLI."""

    def __init__(self):
        self._cmd: list[str] | None = None
        self._version_str: str | None = None
        self._version_tuple: tuple[int, int, int] | None = None

    # ------------------------------------------------------------------ #
    #  Detection
    # ------------------------------------------------------------------ #

    def find_cli(self) -> list[str] | None:
        """Return the command list, or None.  Only checks system PATH (apt-installed binary)."""
        path_bin = shutil.which("HandBrakeCLI")
        if path_bin:
            return [path_bin]
        return None

    def detect(self) -> bool:
        """Populate internal state.  Returns True if HandBrakeCLI is usable."""
        cmd = self.find_cli()
        if cmd is None:
            self._cmd = None
            self._version_str = None
            self._version_tuple = None
            return False

        self._cmd = cmd
        self._detect_version()
        return True

    def get_command(self) -> list[str]:
        """Return the command list (length >= 1).  Raises RuntimeError if not detected."""
        if self._cmd is None:
            raise RuntimeError("HandBrakeCLI not found")
        return self._cmd

    # ------------------------------------------------------------------ #
    #  Version
    # ------------------------------------------------------------------ #

    def _detect_version(self):
        """Parse version from `HandBrakeCLI --version`."""
        try:
            cmd = self._cmd + ["--version"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            output = (r.stdout or "") + (r.stderr or "")
            m = re.search(r"HandBrake\s+(\d+)\.(\d+)\.(\d+)", output)
            if m:
                self._version_tuple = (int(m[1]), int(m[2]), int(m[3]))
                self._version_str = f"{m[1]}.{m[2]}.{m[3]}"
                logger.info("Detected HandBrakeCLI %s", self._version_str)
        except Exception as exc:
            logger.debug("Version detection failed: %s", exc)

    @property
    def version_str(self) -> str | None:
        return self._version_str

    @property
    def version_tuple(self) -> tuple[int, int, int] | None:
        return self._version_tuple

    def supports_preserve_metadata(self) -> bool:
        """--preserve-metadata was added in HandBrake 1.8.0.  1.7.2 (system apt) doesn't have it."""
        return self._version_tuple is not None and self._version_tuple >= (1, 8, 0)

    def metadata_flag(self) -> str | None:
        """Return the CLI flag or None.  For <1.8.0 we always return None — rely on ffmpeg fallback."""
        return None

    # ------------------------------------------------------------------ #
    #  Package manager helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apt_available() -> bool:
        return shutil.which("apt") is not None

    @staticmethod
    def _pkexec_available() -> bool:
        return shutil.which("pkexec") is not None

    @staticmethod
    def _run_privileged(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
        """Run a command with pkexec (graphical sudo prompt). Returns (returncode, stdout, stderr)."""
        full_cmd = ["pkexec"] + cmd
        try:
            r = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Timed out"
        except Exception as exc:
            return -1, "", str(exc)

    @staticmethod
    def _get_apt_version(package: str = "handbrake-cli") -> str | None:
        """Return the version string available in the apt repo, or None."""
        try:
            r = subprocess.run(
                ["apt-cache", "policy", package],
                capture_output=True, text=True, timeout=15,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("Candidate:"):
                    return line.split(None, 1)[1]
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------ #
    #  Generic apt package helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def install_apt_package(package: str, display_name: str = "") -> tuple[bool, str]:
        """Install a package via apt using pkexec.  Returns (success, message)."""
        name = display_name or package
        if not HandBrakeManager._apt_available():
            return False, f"apt is not available.  Please install {name} manually."
        if not HandBrakeManager._pkexec_available():
            return False, (
                f"pkexec is required to install {name}.\n"
                "Install it with:  sudo apt install policykit-1\n\n"
                f"Then run:  sudo apt install -y {package}"
            )
        logger.info("Installing %s via apt …", package)
        rc, out, err = HandBrakeManager._run_privileged(
            ["apt", "install", "-y", package], timeout=300,
        )
        if rc == 0:
            return True, f"{name} installed successfully."
        return False, err or f"apt exit code {rc}"

    @staticmethod
    def update_apt_package(package: str, display_name: str = "") -> tuple[bool, str]:
        """Upgrade a package via apt using pkexec.  Returns (success, message)."""
        name = display_name or package
        if not HandBrakeManager._apt_available():
            return False, "apt is not available."
        if not HandBrakeManager._pkexec_available():
            return False, f"Run:  sudo apt install --only-upgrade -y {package}"
        logger.info("Updating %s via apt …", package)
        rc, out, err = HandBrakeManager._run_privileged(
            ["apt", "install", "--only-upgrade", "-y", package], timeout=300,
        )
        if rc == 0:
            return True, f"{name} updated."
        return False, err or f"apt exit code {rc}"

    @staticmethod
    def check_apt_package_update(package: str, current_version: tuple | None = None
                                  ) -> tuple[bool, str | None]:
        """Check if a newer version is available in apt.  Returns (available, candidate_str)."""
        if current_version is None:
            return False, None
        try:
            r = subprocess.run(
                ["apt-cache", "policy", package],
                capture_output=True, text=True, timeout=15,
            )
            candidate = None
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.startswith("Candidate:"):
                    candidate = line.split(None, 1)[1]
                    break
            if not candidate:
                return False, None
            m = re.search(r"(\d+)\.(\d+)\.(\d+)", candidate)
            if m:
                c = (int(m[1]), int(m[2]), int(m[3]))
                if c > current_version:
                    return True, candidate
            return False, None
        except Exception:
            return False, None

    @staticmethod
    def command_available(command: str) -> bool:
        """Return True if the command exists in PATH."""
        return shutil.which(command) is not None

    # ------------------------------------------------------------------ #
    #  Install
    # ------------------------------------------------------------------ #

    def install(self) -> tuple[bool, str]:
        """
        Install HandBrakeCLI via apt (using pkexec for privilege elevation).
        Returns (success, message).
        """
        if not self._apt_available():
            return (False,
                    "apt is not available on this system.\n"
                    "Please install handbrake-cli manually.")

        if not self._pkexec_available():
            msg = (
                "pkexec is required to install HandBrakeCLI.\n"
                "Install it with:\n"
                "  sudo apt install policykit-1\n\n"
                "Then run this command:\n"
                "  sudo apt install -y handbrake-cli"
            )
            return False, msg

        logger.info("Installing handbrake-cli via apt …")
        rc, out, err = self._run_privileged(
            ["apt", "install", "-y", "handbrake-cli"],
            timeout=300,
        )
        if rc == 0:
            self.detect()
            return True, "HandBrakeCLI installed successfully."
        else:
            return False, err or f"apt exit code {rc}"

    # ------------------------------------------------------------------ #
    #  Update
    # ------------------------------------------------------------------ #

    def update(self) -> tuple[bool, str]:
        """
        Update HandBrakeCLI via apt.
        Returns (success, message).
        """
        if not self._apt_available():
            return False, "apt is not available."

        if not self._pkexec_available():
            return False, (
                "pkexec is required to update.\n"
                "Run: sudo apt install --only-upgrade -y handbrake-cli"
            )

        logger.info("Updating handbrake-cli via apt …")
        rc, out, err = self._run_privileged(
            ["apt", "install", "--only-upgrade", "-y", "handbrake-cli"],
            timeout=300,
        )
        if rc == 0:
            self.detect()
            if self._version_str:
                return True, f"HandBrakeCLI updated to {self._version_str}."
            return True, "HandBrakeCLI updated."
        else:
            return False, err or f"apt exit code {rc}"

    def check_for_update(self) -> tuple[bool, str | None]:
        """
        Check whether a newer version is available in the apt repo.
        Returns (update_available, latest_version_str_or_None).
        """
        if not self._apt_available() or self._version_str is None:
            return False, None

        candidate = self._get_apt_version()
        if not candidate:
            return False, None

        # Parse candidate version
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", candidate)
        if not m:
            return False, None

        candidate_tuple = (int(m[1]), int(m[2]), int(m[3]))
        if candidate_tuple > self._version_tuple:
            return True, candidate
        return False, None

    # ------------------------------------------------------------------ #
    #  Flatpak helpers (kept as fallback for systems without apt)
    # ------------------------------------------------------------------ #

    @staticmethod
    def flatpak_available() -> bool:
        return shutil.which("flatpak") is not None
