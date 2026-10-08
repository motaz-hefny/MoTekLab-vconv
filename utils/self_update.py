"""
In-place self-update (v9.7.2).

When the app detects a newer release, it can download the matching artifact and
install it in place, then relaunch:

  - .deb install (files under /opt/vconv)  -> `pkexec dpkg -i <deb>` (polkit)
  - AppImage build                          -> replace the AppImage file (no root)
  - dev checkout only                       -> no auto-install; open release page

All network calls go to the app's own GitHub releases. Downloads stream to a
temp file with progress callbacks.
"""

import os
import json
import logging
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/motaz-hefny/MoTekLab-vconv/releases/latest"

INSTALL_ROOT = Path('/opt/vconv')
INSTALL_WRAPPER = Path('/usr/local/bin/vconv')
USER_AGENT = "vconv-self-updater"


def _ua() -> str:
    from utils.version import __version__
    return f"vconv-self-updater/{__version__}"


def detect_install_mode() -> str:
    """'appimage' | 'deb' | 'dev' — how the current instance is deployed."""
    if os.environ.get('APPIMAGE'):
        return 'appimage'
    if (INSTALL_ROOT / 'vconv.py').exists() or INSTALL_WRAPPER.exists():
        return 'deb'
    return 'dev'


def fetch_release_assets() -> dict:
    """
    Fetch the latest release's asset map: {'tag': 'v9.7.2',
    'assets': {'file.deb': 'https://...', ...}}.
    Returns {'tag': '', 'assets': {}} on any failure.
    """
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': _ua()}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        assets = {
            a.get('name', ''): a.get('browser_download_url', '')
            for a in data.get('assets', [])
            if a.get('name') and a.get('browser_download_url')
        }
        return {'tag': data.get('tag_name', ''), 'assets': assets}
    except (urllib.error.HTTPError, urllib.error.URLError,
            json.JSONDecodeError, OSError, KeyError) as e:
        logger.warning("fetch_release_assets failed: %s", e)
        return {'tag': '', 'assets': {}}


def select_asset_for_mode(assets: dict, mode: str) -> Optional[str]:
    """Pick the right artifact URL for the install mode (first match)."""
    if mode == 'deb':
        for name in assets:
            if name.endswith('_all.deb'):
                return assets[name]
        return None
    if mode == 'appimage':
        for name in assets:
            if name.endswith('.AppImage'):
                return assets[name]
        return None
    return None


def download_asset(url: str, dest: Path,
                   progress_cb: Optional[Callable[[int, int], None]] = None) -> Path:
    """
    Stream `url` to `dest` (atomic via `.part` temp). progress_cb(done, total).
    """
    req = urllib.request.Request(url, headers={'User-Agent': _ua()})
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    if part.exists():
        part.unlink()
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get('Content-Length') or 0)
        done = 0
        with open(part, 'wb') as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)
    part.replace(dest)
    return dest


def install_deb(deb_path: Path) -> tuple[bool, str]:
    """Install a .deb with pkexec/dpkg. Returns (ok, message)."""
    pkexec = shutil.which('pkexec')
    if not pkexec:
        return (False, "pkexec is not available — install manually: download the "
                       ".deb and run `sudo dpkg -i`.")
    proc = subprocess.run(
        [pkexec, 'dpkg', '-i', str(deb_path)],
        capture_output=True, text=True
    )
    if proc.returncode == 0:
        return (True, f"Installed package {deb_path.name}")
    detail = (proc.stderr or proc.stdout or '').strip()[-400:]
    return (False, f"Installer failed (exit {proc.returncode}): {detail or 'password refused or cancelled'}")


def _replace_appimage(new_appimage: Path) -> bool:
    """Atomically replace the currently-running AppImage file."""
    current = os.environ.get('APPIMAGE')
    if not current:
        return False
    current = Path(current)
    backup = current.with_name(current.name + '.old')
    if backup.exists():
        backup.unlink()
    try:
        os.rename(current, backup)
        os.replace(new_appimage, current)
        st = os.stat(current)
        os.chmod(current, st.st_mode | 0o111)
        return True
    except OSError as e:
        logger.warning("AppImage replace failed: %s", e)
        return False


def install_update(assets: dict, mode: str,
                   progress_cb: Optional[Callable[[int, int], None]] = None,
                   status_cb: Optional[Callable[[str], None]] = None,
                   ) -> dict:
    """
    Download + install the update for `mode`. progress_cb(done,total) during the
    download; status_cb(message) for phase announcements. Returns a result dict:
        {'success': bool, 'message': str, 'relaunch': bool, 'mode': mode}
    """
    url = select_asset_for_mode(assets, mode)
    if not url:
        return {'success': False, 'mode': mode, 'relaunch': False,
                'message': 'No installable asset for this installation type.'}

    dest = Path(tempfile.gettempdir()) / url.rsplit('/', 1)[-1]
    try:
        if status_cb:
            status_cb("Downloading update…")
        download_asset(url, dest, progress_cb)

        if mode == 'deb':
            if status_cb:
                status_cb("Installing… (enter your password)")
            ok, msg = install_deb(dest)
            if not ok:
                return {'success': False, 'mode': mode, 'relaunch': False, 'message': msg}
            try:
                dest.unlink()
            except OSError:
                pass
            return {'success': True, 'mode': mode, 'relaunch': True,
                    'message': f"Update installed in place.{' ' + msg if msg else ''}"}

        if mode == 'appimage':
            if status_cb:
                status_cb("Replacing AppImage…")
            if not _replace_appimage(dest):
                return {'success': False, 'mode': mode, 'relaunch': False,
                        'message': 'Could not replace the AppImage file.'}
            return {'success': True, 'mode': mode, 'relaunch': True,
                    'message': 'AppImage replaced. Relaunching…'}

    except Exception as e:
        logger.warning("self-update failed: %s", e, exc_info=True)
        return {'success': False, 'mode': mode, 'relaunch': False,
                'message': f"{type(e).__name__}: {e}"}

    return {'success': False, 'mode': mode, 'relaunch': False,
            'message': 'Unhandled installation mode.'}


def relaunch_app(mode: str):
    """Spawn the freshly-installed app and let the current process exit."""
    try:
        if mode == 'deb' and INSTALL_WRAPPER.exists():
            subprocess.Popen(['/usr/local/bin/vconv', '--gui'])
        elif mode == 'appimage':
            current = os.environ.get('APPIMAGE')
            if current:
                subprocess.Popen([current, '--gui'])
        elif mode == 'dev':
            subprocess.Popen([shutil.which('python3') or 'python3',
                              str(INSTALL_ROOT / 'vconv.py'), '--gui'])
    except OSError as e:
        logger.warning("Relaunch failed: %s", e)
    logger.info("Relaunched app (mode=%s); old process exiting.", mode)