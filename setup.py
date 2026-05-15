#!/usr/bin/env python3
"""
vconv Installation Setup

Installation options:
- Install to /usr/local/bin (adds to PATH)
- Create start menu entry (Multimedia)
- Create desktop shortcut (optional)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

INSTALL_DIR = "/usr/local/bin"
DESKTOP_DIR = os.path.expanduser("~/Desktop")
APPLICATIONS_DIR = "/usr/local/share/applications"
ICONS_DIR = "/usr/local/share/icons"

APP_NAME = "vconv"
SCRIPT_NAME = "vconv.py"
DESKTOP_FILE = "vconv.desktop"


def get_install_path():
    """Get the path where vconv.py is currently located."""
    return os.path.dirname(os.path.abspath(__file__))


def install_system():
    """Install vconv system-wide."""
    print("=" * 50)
    print("vconv Installation")
    print("=" * 50)

    install_path = get_install_path()
    print(f"\nSource: {install_path}")

    # 1. Create symlink in /usr/local/bin (adds to PATH)
    print("\n[1/3] Creating symlink in /usr/local/bin...")
    try:
        os.symlink(os.path.join(install_path, SCRIPT_NAME), os.path.join(INSTALL_DIR, APP_NAME))
        print(f"   ✅ Created: {INSTALL_DIR}/{APP_NAME}")
        print("   ✅ Added to PATH - you can run 'vconv' from anywhere")
    except FileExistsError:
        print(f"   ⚠️  Already exists: {INSTALL_DIR}/{APP_NAME}")
    except PermissionError:
        print(f"   ❌ Need sudo: sudo ln -s {install_path}/{SCRIPT_NAME} {INSTALL_DIR}/{APP_NAME}")

    # 2. Install desktop entry
    print("\n[2/3] Creating start menu entry...")
    desktop_src = os.path.join(install_path, DESKTOP_FILE)
    desktop_dst = os.path.join(APPLICATIONS_DIR, DESKTOP_FILE)

    try:
        shutil.copy(desktop_src, desktop_dst)
        print(f"   ✅ Created: {APPLICATIONS_DIR}/{DESKTOP_FILE}")
        print("   ✅ Available in: Start Menu → Multimedia → vconv")
    except PermissionError:
        print(f"   ❌ Need sudo: sudo cp {desktop_src} {APPLICATIONS_DIR}/")
    except FileNotFoundError:
        print(f"   ❌ Desktop file not found: {desktop_src}")

    # 3. Optional desktop shortcut
    print("\n[3/3] Create desktop shortcut?")
    response = input("   Create desktop shortcut? [y/N]: ").strip().lower()
    if response == 'y':
        desktop_link = os.path.join(DESKTOP_DIR, "vconv.desktop")
        try:
            # Create a copy for desktop (not symlink, so it works)
            shutil.copy(desktop_src, desktop_link)
            os.chmod(desktop_link, 0o755)
            print(f"   ✅ Created: {desktop_link}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

    print("\n" + "=" * 50)
    print("Installation complete!")
    print("=" * 50)
    print("\nTo run vconv:")
    print("  vconv                    # From any folder")
    print("  vconv --gui              # Open GUI")
    print("  vconv --batch            # Convert all videos")
    print("  vconv --folder_in /path  # Specify folder")


def uninstall():
    """Remove vconv installation."""
    print("=" * 50)
    print("vconv Uninstallation")
    print("=" * 50)

    # Remove symlink
    symlink_path = os.path.join(INSTALL_DIR, APP_NAME)
    if os.path.islink(symlink_path):
        os.unlink(symlink_path)
        print(f"✅ Removed: {symlink_path}")

    # Remove desktop entry
    desktop_path = os.path.join(APPLICATIONS_DIR, DESKTOP_FILE)
    if os.path.exists(desktop_path):
        try:
            os.remove(desktop_path)
            print(f"✅ Removed: {desktop_path}")
        except PermissionError:
            print(f"❌ Need sudo to remove: {desktop_path}")

    # Remove desktop shortcut
    desktop_link = os.path.join(DESKTOP_DIR, "vconv.desktop")
    if os.path.exists(desktop_link):
        os.remove(desktop_link)
        print(f"✅ Removed: {desktop_link}")

    print("\n✅ Uninstallation complete!")


def quick_install():
    """Quick installation with defaults (no prompts)."""
    install_path = get_install_path()

    # Symlink to /usr/local/bin
    try:
        if not os.path.exists(os.path.join(INSTALL_DIR, APP_NAME)):
            os.symlink(os.path.join(install_path, SCRIPT_NAME), os.path.join(INSTALL_DIR, APP_NAME))
            print(f"✅ Added to PATH: {INSTALL_DIR}/{APP_NAME}")
    except PermissionError:
        pass

    # Desktop entry
    desktop_src = os.path.join(install_path, DESKTOP_FILE)
    desktop_dst = os.path.join(APPLICATIONS_DIR, DESKTOP_FILE)
    try:
        if not os.path.exists(desktop_dst):
            shutil.copy(desktop_src, desktop_dst)
            print(f"✅ Start menu entry: {desktop_dst}")
    except PermissionError:
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "uninstall":
            uninstall()
        elif sys.argv[1] == "install":
            install_system()
        elif sys.argv[1] == "quick":
            quick_install()
        else:
            print("Usage: python3 setup.py [install|uninstall|quick]")
    else:
        install_system()