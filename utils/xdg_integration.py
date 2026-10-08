"""
XDG integration — auto-installs desktop file and icons for start menu/taskbar.

On every launch, ensures:
  - ~/.local/share/applications/vconv.desktop
  - ~/.local/share/icons/hicolor/{256,128,64,48,32}x{...}/apps/vconv.png
  - Icon cache updated

Installed-aware (v9.7.2): when the .deb is installed (files under /opt/vconv),
the start-menu entry ALWAYS points at the installed app — not at whatever
instance happened to run last (dev checkout or AppImage). This keeps exactly
one version in the start menu.
"""

import os
import re
import sys
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

XDG_DATA_HOME = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
APPLICATIONS_DIR = XDG_DATA_HOME / 'applications'
ICON_BASE = XDG_DATA_HOME / 'icons' / 'hicolor'

INSTALL_ROOT = Path('/opt/vconv')
INSTALL_WRAPPER = Path('/usr/local/bin/vconv')
SYSTEM_ICON = Path('/usr/local/share/icons/hicolor/256x256/apps/vconv.png')


def installed_root() -> Path | None:
    """Return /opt/vconv when the .deb installation exists, else None."""
    if (INSTALL_ROOT / 'vconv.py').exists():
        return INSTALL_ROOT
    return None


def _scale_icon(source_png: Path, sizes: list[int] = None) -> list[Path]:
    if sizes is None:
        sizes = [256, 128, 64, 48, 32]
    try:
        from PIL import Image
        img = Image.open(str(source_png))
        created = []
        for size in sizes:
            dest = ICON_BASE / f'{size}x{size}' / 'apps' / 'vconv.png'
            dest.parent.mkdir(parents=True, exist_ok=True)
            scaled = img.resize((size, size), Image.LANCZOS)
            scaled.save(str(dest), 'PNG', optimize=True)
            created.append(dest)
        return created
    except ImportError:
        pass

    try:
        from PyQt6.QtGui import QPixmap
        created = []
        pixmap = QPixmap(str(source_png))
        if not pixmap.isNull():
            for size in sizes:
                dest = ICON_BASE / f'{size}x{size}' / 'apps' / 'vconv.png'
                dest.parent.mkdir(parents=True, exist_ok=True)
                scaled = pixmap.scaled(size, size)
                scaled.save(str(dest))
                created.append(dest)
        return created
    except ImportError:
        pass

    logger.warning("No image library available, copying source icon directly")
    dest = ICON_BASE / '256x256' / 'apps' / 'vconv.png'
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_png), str(dest))
    return [dest]


def _installed_version() -> str:
    """Read the version of the /opt/vconv installation (fallback: empty)."""
    root = installed_root()
    if not root:
        return ""
    try:
        text = (root / 'utils' / 'version.py').read_text()
    except OSError:
        return ""
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else ""


def _install_desktop_file(project_root: Path) -> Path | None:
    installed = installed_root()

    # Prefer the INSTALLED app's desktop template when a deb is present, so the
    # menu reflects the installed version's name/comment, never the dev copy's.
    template_root = installed if installed else project_root
    src = template_root / 'vconv.desktop'
    if not src.exists():
        # Deb installs may omit the template — fall back to the source tree that
        # shipped this module.
        src = Path(__file__).resolve().parent.parent / 'vconv.desktop'
    if not src.exists():
        logger.warning("Desktop file not found at %s", src)
        return None

    if installed:
        exec_line = 'Exec=python3 /opt/vconv/vconv.py --gui'
    else:
        exec_line = f'Exec={sys.executable} {project_root / "vconv.py"} --gui'

    content = src.read_text()
    content = re.sub(r'(?m)^Exec=.*$', exec_line, content)
    # Icon may reference an absolute deb path in the template; always theme-ize it.
    content = re.sub(r'(?m)^Icon=.*$', 'Icon=vconv', content)
    if installed:
        ver = _installed_version()
        if ver:
            content = re.sub(r'(?m)^(Comment=)v[\d.]+', rf'\g<1>v{ver}', content)

    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    dest = APPLICATIONS_DIR / 'vconv.desktop'
    dest.write_text(content)
    logger.info("Wrote start-menu entry %s (Exec=%s)", dest, exec_line)
    return dest


def _find_source_icon(project_root: Path) -> Path | None:
    installed = installed_root()
    if installed:
        for path in (installed / 'vconv-icon-256.png',
                     installed / 'public' / 'vconv-icon-256.png',
                     SYSTEM_ICON):
            if path.exists():
                return path
    else:
        for path in (project_root / 'public' / 'vconv-icon-256.png',
                     SYSTEM_ICON):
            if path.exists():
                return path
    return None


def _update_icon_cache():
    try:
        subprocess.run(
            ['gtk-update-icon-cache', str(ICON_BASE)],
            capture_output=True, timeout=10
        )
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass


def _update_desktop_database():
    mime_file = APPLICATIONS_DIR / 'mimeinfo.cache'
    try:
        subprocess.run(
            ['update-desktop-database', str(APPLICATIONS_DIR)],
            capture_output=True, timeout=10
        )
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    if not mime_file.exists():
        try:
            mime_file.write_text('[MIME Cache]\n')
        except OSError:
            pass


def ensure_xdg_integration(project_root: Path) -> bool:
    source_icon = _find_source_icon(project_root)
    if source_icon is None:
        logger.warning("No source icon found (dev=%s, system=%s); skipping XDG",
                       project_root / 'public' / 'vconv-icon-256.png', SYSTEM_ICON)
        return False

    _install_desktop_file(project_root)
    _scale_icon(source_icon)
    _update_icon_cache()
    _update_desktop_database()

    logger.info(
        "XDG integration complete — desktop file in %s, icons in %s (installed=%s)",
        APPLICATIONS_DIR, ICON_BASE, installed_root() is not None
    )
    return True