"""
XDG integration — auto-installs desktop file and icons for start menu/taskbar.

On every launch, ensures:
  - ~/.local/share/applications/vconv.desktop
  - ~/.local/share/icons/hicolor/{256,128,64,48,32}x{...}/apps/vconv.png
  - Icon cache updated
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

XDG_DATA_HOME = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
APPLICATIONS_DIR = XDG_DATA_HOME / 'applications'
ICON_BASE = XDG_DATA_HOME / 'icons' / 'hicolor'


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


def _install_desktop_file(project_root: Path) -> Path | None:
    src = project_root / 'vconv.desktop'
    if not src.exists():
        logger.warning("Desktop file not found at %s", src)
        return None
    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    dest = APPLICATIONS_DIR / 'vconv.desktop'
    content = src.read_text()
    python = sys.executable
    script = project_root / 'vconv.py'
    content = content.replace(
        'Exec=python3 /opt/vconv/vconv.py',
        f'Exec={python} {script}'
    )
    content = content.replace(
        'Icon=/opt/vconv/vconv-icon-256.png',
        'Icon=vconv'
    )
    dest.write_text(content)
    return dest


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
    # create empty mime cache if tool not available (avoids spurious errors)
    if not mime_file.exists():
        try:
            mime_file.write_text('[MIME Cache]\n')
        except OSError:
            pass


def ensure_xdg_integration(project_root: Path) -> bool:
    source_icon = project_root / 'public' / 'vconv-icon-256.png'
    if not source_icon.exists():
        logger.warning("Source icon not found at %s", source_icon)
        return False

    _install_desktop_file(project_root)
    _scale_icon(source_icon)
    _update_icon_cache()
    _update_desktop_database()

    logger.info(
        "XDG integration complete — desktop file in %s, icons in %s",
        APPLICATIONS_DIR, ICON_BASE
    )
    return True
