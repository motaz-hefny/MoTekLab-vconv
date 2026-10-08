"""
Tool Auto-Updater — keeps encoding tools at their official latest.

Managed tools (v9.7.0):
- **ffmpeg / ffprobe**: BtbN/FFmpeg-Builds static Linux builds (no root needed)
- **NVEncC** (rigaya NVEnc): official ``nvencc_*_amd64.deb`` extracted to the
  user tools dir (no root needed)
- **HandBrakeCLI**: no official prebuilt Linux tarball exists (only
  Win/mac/flatpak/source), so this tries the Flatpak CLI first and otherwise
  reports what the latest release is for the user to install.

All tools are installed under ``~/.local/share/vconv/tools``; binaries are
symlinked into ``tools/bin`` which is prepended to ``PATH`` so existing
``shutil.which`` / subprocess call sites pick up the latest builds.
"""
import os
import re
import json
import logging
import shutil
import tarfile
import subprocess
import threading
import urllib.request
import urllib.error
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from utils.updater import parse_version
from utils.version import __version__

logger = logging.getLogger("vconv." + __name__)

TOOLS_ROOT = Path.home() / ".local" / "share" / "vconv" / "tools"
BIN_DIR = TOOLS_ROOT / "bin"
GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
USER_AGENT = f"MoTekLab-vconv/{__version__}"

FFMPEG_REPO = "BtbN/FFmpeg-Builds"
NVENC_REPO = "rigaya/NVEnc"
HB_REPO = "HandBrake/HandBrake"

FFMPEG_ASSET_RE = re.compile(r"ffmpeg-n([\d.]+)-latest-linux64-gpl(?:-[\d.]+)?.tar.xz$")
NVENC_ASSET_RE = re.compile(r"nvencc_([\d.]+)_amd64\.deb$")
# Real NVEncC banner: "NVEnc (x64) 9.38 (r4176) by rigaya, ..."
_NVENC_VER_RE = re.compile(r"NVEnc\s*\(x(?:64|86)\)\s*([^\s]+)")

# Guard against two threads installing the SAME tool concurrently (e.g. the
# startup auto-update racing a manual "Update" click in the Tools dialog).
INSTALL_ACTIVE: set[str] = set()
INSTALL_LOCK = threading.Lock()


def _reserve_install(tool_id: str) -> bool:
    with INSTALL_LOCK:
        if tool_id in INSTALL_ACTIVE:
            return False
        INSTALL_ACTIVE.add(tool_id)
        return True


def _release_install(tool_id: str) -> None:
    with INSTALL_LOCK:
        INSTALL_ACTIVE.discard(tool_id)


@dataclass
class ToolStatus:
    """Status snapshot of one managed tool."""
    tool_id: str
    display: str
    installed_version: str = ""
    latest_version: str = ""
    update_available: bool = False
    installed_path: str = ""
    note: str = ""
    error: str = ""


def ensure_bin_dir_on_path() -> None:
    """Symlink/bin dir must be first on PATH so the latest tools are used."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    path = os.environ.get("PATH", "")
    if str(BIN_DIR) in path.split(os.pathsep):
        return
    os.environ["PATH"] = f"{BIN_DIR}{os.pathsep}{path}"


def _run(cmd: list, timeout: int = 20) -> str:
    """Run a command and return combined stdout/stderr ('' on failure)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        logger.debug(f"tool cmd failed {cmd}: {e}")
        return ""


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


# ---------------------------------------------------------------------------
# Version detection per tool
# ---------------------------------------------------------------------------

def _ffmpeg_version() -> str:
    out = _run([shutil.which("ffmpeg") or "ffmpeg", "-version"], timeout=15)
    m = re.search(r"version\s+([^\s]+)", out)
    return m.group(1) if m else ""


def _nvenc_version() -> str:
    exe = _which("NVEncC") or _which("NVEncC64") or _which("nvencc") or _which("nvencc64")
    if not exe:
        return ""
    out = _run([exe, "--version"], timeout=15)
    m = _NVENC_VER_RE.search(out)
    return m.group(1) if m else ""


def _hb_version() -> str:
    out = _run([_which("HandBrakeCLI") or "HandBrakeCLI", "--version"], timeout=15)
    m = re.search(r"HandBrake(?:CLI)?\s+([\d.]+)", out)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# GitHub release helpers
# ---------------------------------------------------------------------------

def _github_latest(repo: str) -> dict:
    """Fetch the latest GitHub release for a repo -> {'tag': str, 'assets': [(name,url)]}."""
    url = GITHUB_API.format(repo=repo)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": USER_AGENT,
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    assets = [(a.get("name", ""), a.get("browser_download_url", ""))
              for a in data.get("assets", [])]
    return {"tag": data.get("tag_name", ""), "assets": assets}


def _find_asset(assets: list, pattern: re.Pattern) -> Optional[tuple]:
    for name, url in assets:
        if pattern.search(name):
            return (name, url)
    return None


def _download(url: str, dest: Path,
              progress: Optional[Callable[[float, str], None]] = None,
              error_cb: Optional[Callable[[str], None]] = None) -> bool:
    """Download a file with optional progress callback (throttled to 1% steps)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            got = 0
            last_pct = -1
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if progress and total:
                        pct = int(got * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            progress(float(pct), "")
        return True
    except Exception as e:
        msg = f"Download failed: {e}"
        logger.error(f"Download failed {url}: {e}")
        if error_cb:
            error_cb(msg)
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def _parse_version_str(ver: str):
    if not ver:
        return ()
    return parse_version(ver)


def _clean_version(ver: str) -> str:
    """Normalize a version string for display/comparison (strips leading 'n'/'v')."""
    v = (ver or "").strip()
    for pfx in ("n", "v"):
        if v.startswith(pfx):
            v = v[1:]
            break
    return v


# ---------------------------------------------------------------------------
# Tool updater
# ---------------------------------------------------------------------------

class ToolUpdater:
    """Detects, downloads and installs the latest encoding tools."""

    TOOL_IDS = ("ffmpeg", "nvencc", "handbrake")

    def __init__(self):
        ensure_bin_dir_on_path()
        self._release_cache: dict = {}

    # -- status -----------------------------------------------------------

    def status(self, tool_id: str) -> ToolStatus:
        if tool_id == "ffmpeg":
            return self.status_ffmpeg()
        if tool_id == "nvencc":
            return self.status_nvencc()
        return self.status_handbrake()

    def status_all(self) -> list[ToolStatus]:
        return [self.status(t) for t in self.TOOL_IDS]

    def _grab(self, repo: str) -> dict:
        if repo not in self._release_cache:
            try:
                self._release_cache[repo] = _github_latest(repo)
            except Exception as e:
                logger.warning(f"GitHub release fetch failed for {repo}: {e}")
                self._release_cache[repo] = {"tag": "", "assets": []}
        return self._release_cache[repo]

    def status_ffmpeg(self) -> ToolStatus:
        st = ToolStatus(tool_id="ffmpeg", display="ffmpeg / ffprobe")
        st.installed_version = _ffmpeg_version()
        rel = self._grab(FFMPEG_REPO)
        asset = _find_asset(rel.get("assets", []), FFMPEG_ASSET_RE)
        if asset:
            st.latest_version = _clean_version(asset[0].split("-")[1] if "-" in asset[0] else asset[0])
        else:
            st.latest_version = _clean_version(rel.get("tag", ""))
        st.installed_path = _which("ffmpeg") or ""
        if st.installed_version and st.latest_version:
            st.update_available = _parse_version_str(_clean_version(st.installed_version)) < \
                                  _parse_version_str(st.latest_version)
        elif not st.installed_version:
            st.update_available = True
        if not st.installed_version:
            st.note = "Not installed — will be auto-downloaded"
        return st

    def status_nvencc(self) -> ToolStatus:
        st = ToolStatus(tool_id="nvencc", display="NVEncC (rigaya)")
        st.installed_version = _nvenc_version()
        rel = self._grab(NVENC_REPO)
        st.latest_version = _clean_version(rel.get("tag", ""))
        st.installed_path = (_which("NVEncC") or _which("NVEncC64") or
                             _which("nvencc") or _which("nvencc64") or "")
        if st.installed_version and st.latest_version:
            st.update_available = _parse_version_str(st.installed_version) < \
                                  _parse_version_str(st.latest_version)
        else:
            st.update_available = bool(st.latest_version)
        if not st.installed_version:
            st.note = "Not installed — will be auto-downloaded (adds GPU encoders)"
        return st

    def status_handbrake(self) -> ToolStatus:
        st = ToolStatus(tool_id="handbrake", display="HandBrakeCLI")
        st.installed_version = _hb_version()
        rel = self._grab(HB_REPO)
        st.latest_version = _clean_version(rel.get("tag", ""))
        st.installed_path = _which("HandBrakeCLI") or ""
        if st.installed_version and st.latest_version:
            st.update_available = _parse_version_str(st.installed_version) < \
                                  _parse_version_str(st.latest_version)
        else:
            st.update_available = bool(st.latest_version)
        if not st.installed_version:
            st.note = "Install via system package manager (no official Linux binary)"
        return st

    # -- install -----------------------------------------------------------

    def update(self, tool_id: str,
               progress: Optional[Callable[[float, str], None]] = None,
               error_cb: Optional[Callable[[str], None]] = None) -> bool:
        """Install/update a tool. Returns True on success."""
        if not _reserve_install(tool_id):
            msg = "Another update for this tool is already running (startup auto-update?)"
            logger.warning(f"update({tool_id}) refused — already active")
            if error_cb:
                error_cb(msg)
            return False
        try:
            if tool_id == "ffmpeg":
                return self._install_ffmpeg(progress, error_cb)
            if tool_id == "nvencc":
                return self._install_nvencc(progress, error_cb)
            if tool_id == "handbrake":
                return self._install_handbrake(progress, error_cb)
        except Exception as e:
            logger.exception(f"Tool update failed for {tool_id}")
            if error_cb:
                error_cb(str(e))
            return False
        finally:
            _release_install(tool_id)
        return False

    def _install_ffmpeg(self, progress=None, error_cb=None) -> bool:
        rel = self._grab(FFMPEG_REPO)
        asset = _find_asset(rel.get("assets", []), FFMPEG_ASSET_RE)
        if not asset:
            msg = "No ffmpeg build found on GitHub releases"
            if progress:
                progress(0, msg)
            if error_cb:
                error_cb(msg)
            return False
        name, url = asset
        ver = _clean_version(name.split("-")[1] if "-" in name else name)
        if progress:
            progress(5, f"Downloading ffmpeg {ver}…")
        with tempfile.TemporaryDirectory(prefix="vconv_ffmpeg_") as td:
            tarball = Path(td) / name
            if not _download(url, tarball, progress, error_cb):
                return False
            if progress:
                progress(55, "Extracting…")
            dest = TOOLS_ROOT / f"ffmpeg-{ver}"
            dest.mkdir(parents=True, exist_ok=True)
            ok = _extract_strip(tarball, dest, strip=1)
            if not ok:
                if error_cb:
                    error_cb(f"Failed to extract {name}")
                return False
            for exe in ("ffmpeg", "ffprobe"):
                src = dest / exe
                if src.exists():
                    _symlink(src, BIN_DIR / exe)
                else:
                    # walk subdirs (bin/ under extracted root)
                    found = next(iter(list(dest.rglob(exe))), None)
                    if found:
                        _symlink(found, BIN_DIR / exe)
            _cleanup_versions("ffmpeg-", keep=ver)
        if progress:
            progress(100, f"ffmpeg {ver} installed")
        return True

    def _install_nvencc(self, progress=None, error_cb=None) -> bool:
        rel = self._grab(NVENC_REPO)
        asset = _find_asset(rel.get("assets", []), NVENC_ASSET_RE)
        if not asset:
            msg = "No NVEncC .deb found on GitHub releases"
            if progress:
                progress(0, msg)
            if error_cb:
                error_cb(msg)
            return False
        name, url = asset
        ver = _clean_version(rel.get("tag", ""))
        if progress:
            progress(5, f"Downloading NVEncC {ver}…")
        with tempfile.TemporaryDirectory(prefix="vconv_nvenc_") as td:
            deb = Path(td) / name
            if not _download(url, deb, progress, error_cb):
                return False
            if progress:
                progress(55, "Extracting…")
            dest = TOOLS_ROOT / f"nvencc-{ver}"
            dest.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(["dpkg-deb", "-x", str(deb), str(dest)],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                msg = f"dpkg-deb extraction failed: {r.stderr[:120]}"
                if progress:
                    progress(0, "dpkg-deb extraction failed")
                if error_cb:
                    error_cb(msg)
                return False
            binary = _find_nvenc_binary(dest)
            if not binary:
                msg = "NVEncC binary not found in package"
                if progress:
                    progress(0, msg)
                if error_cb:
                    error_cb(msg)
                return False
            _symlink(binary, BIN_DIR / "NVEncC")
            _cleanup_versions("nvencc-", keep=ver)
        if progress:
            progress(100, f"NVEncC {ver} installed")
        return True

    def _install_handbrake(self, progress=None, error_cb=None) -> bool:  # noqa: C901
        """No official Linux prebuilt — try Flatpak CLI, else report latest."""
        flatpak = _which("flatpak")
        if flatpak:
            if progress:
                progress(20, "Installing fr.handbrake.HandBrakeCLI via Flatpak…")
            r = subprocess.run(
                [flatpak, "install", "-y", "flathub", "fr.handbrake.HandBrakeCLI"],
                capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                if progress:
                    progress(100, "HandBrakeCLI installed via Flatpak")
                return True
            err = (r.stderr or r.stdout or "unknown flatpak error").strip()
            msg = ("Flatpak install failed: " + err[:200] + ". "
                   "This typically needs system-wide permission and a runtime "
                   "download. If it keeps failing, run in a terminal:\n"
                   "flatpak install flathub fr.handbrake.HandBrakeCLI")
            if progress:
                progress(0, f"Flatpak install failed: {err[:200]}")
            if error_cb:
                error_cb(msg)
            return False
        msg = ("Flatpak not available. Install HandBrakeCLI via your package "
               "manager (e.g. 'sudo apt install handbrake-cli'); latest release "
               "is " + self.status_handbrake().latest_version + ".")
        if progress:
            progress(0, msg)
        if error_cb:
            error_cb(msg)
        return False


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------

def _find_nvenc_binary(dest: Path) -> Optional[Path]:
    """Locate the NVEncC executable inside an extracted deb, case-insensitively.

    rigaya's recent debs ship the binary as lowercase ``usr/bin/nvencc`` while
    older ones used ``usr/bin/NVEncC`` — only a case-insensitive scan is safe.
    """
    for p in dest.rglob("*"):
        if p.is_file() and p.name.lower() in ("nvencc", "nvencc64"):
            return p
    return None


def _extract_strip(tarball: Path, dest: Path, strip: int = 1) -> bool:
    """Extract a tar.xz stripping the top-level directory."""
    try:
        with tarfile.open(tarball, "r:xz") as tar:
            # Strip the single top-level dir: extract to temp, then move contents
            tmp = dest.parent / f".{dest.name}_tmp"
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True, exist_ok=True)
            tar.extractall(tmp, filter="data")
            items = list(tmp.iterdir())
            top = items[0] if (len(items) == 1 and items[0].is_dir()) else None
            src = top if top else tmp
            for child in src.iterdir():
                target = dest / child.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target, ignore_errors=True)
                    else:
                        target.unlink(missing_ok=True)
                shutil.move(str(child), str(target))
            shutil.rmtree(tmp, ignore_errors=True)
        return True
    except Exception as e:
        logger.error(f"Extract failed {tarball}: {e}")
        return False


def _symlink(src: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.unlink(missing_ok=True)
    except Exception:
        pass
    os.symlink(str(src), str(link))
    logger.info(f"Linked {link} -> {src}")


def _cleanup_versions(prefix: str, keep: str) -> None:
    """Remove old tool version dirs except the one just installed."""
    for p in TOOLS_ROOT.glob(f"{prefix}*"):
        if p.name != f"{prefix}{keep}":
            try:
                shutil.rmtree(p, ignore_errors=True)
            except Exception:
                pass