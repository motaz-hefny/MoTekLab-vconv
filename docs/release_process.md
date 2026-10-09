# Release Process

> Always produce 3 artifacts: `.deb`, `.AppImage`, and source (auto).
> **All builds go into `dist/`** in the project root directory.

## Steps

### 1. Update Version
Update version in:
- `utils/version.py` — **single source of truth** (`__version__` and `VERSION`)
  (everything else — `vconv.py`, `ui/main_window.py` title/status bar, About dialog — imports from here; no other hardcoded version edits needed)
- `docs/user_guide.md` (version line at top + footer)
- `docs/user_guide.ar.md` (version line at top + footer)
- `vconv.desktop` (`Comment=` line)
- `CHANGELOG.md` (add new version entry)
- `README.md` (Version line)

### 2. Commit & Tag
```bash
git add -A
git commit -m "vX.Y.Z: summary of changes"
git tag vX.Y.Z
git push origin main --tags
```

### 3. Build .deb Package
```bash
mkdir -p dist
BUILD="/tmp/vconv-build/vconv_X.Y.Z_all"
rm -rf "$BUILD"

# Create build structure
mkdir -p "$BUILD/DEBIAN"
for d in core ui utils docs presets locales themes; do
  mkdir -p "$BUILD/opt/vconv/$d"
done
mkdir -p "$BUILD/usr/local/bin"
mkdir -p "$BUILD/usr/local/share/applications"
mkdir -p "$BUILD/usr/local/share/doc/vconv"
# Icon for XDG icon theme (needed for `Icon=vconv` in desktop file)
mkdir -p "$BUILD/usr/local/share/icons/hicolor/256x256/apps"

# Copy files
cp vconv.py "$BUILD/opt/vconv/"
cp core/*.py "$BUILD/opt/vconv/core/"
cp ui/*.py "$BUILD/opt/vconv/ui/"
cp utils/*.py "$BUILD/opt/vconv/utils/"
cp docs/*.md "$BUILD/opt/vconv/docs/"
cp presets/*.json "$BUILD/opt/vconv/presets/"
cp locales/*.json "$BUILD/opt/vconv/locales/"
cp public/vconv-icon-256.png "$BUILD/opt/vconv/"
cp public/vconv-icon-256.png "$BUILD/usr/local/share/icons/hicolor/256x256/apps/vconv.png"
cp public/vconv-about-banner.png "$BUILD/opt/vconv/"
cp public/vconv-logo-512.png "$BUILD/opt/vconv/"
cp CHANGELOG.md README.md LICENSE "$BUILD/usr/local/share/doc/vconv/"

# Create wrapper
cat > "$BUILD/usr/local/bin/vconv" << 'EOF'
#!/bin/sh
exec python3 /opt/vconv/vconv.py "$@"
EOF
chmod +x "$BUILD/usr/local/bin/vconv"

# Create DEBIAN/control (update version)
cat > "$BUILD/DEBIAN/control" << CONTROL
Package: vconv
Version: X.Y.Z
Section: multimedia
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-pyqt6, handbrake-cli, ffmpeg
Maintainer: MoTekLab <motaz@moteklab.com>
Description: vconv - Video Converter powered by HandBrakeCLI & PyQt6
CONTROL

# Build — output goes to dist/
dpkg-deb --build "$BUILD" "dist/vconv_X.Y.Z_all.deb"
```

### 4. Build AppImage
```bash
mkdir -p dist
pip install pyinstaller

# Build standalone executable
pyinstaller --onefile --name vconv \
  --distpath /tmp/vconv-appimage \
  --workpath /tmp/vconv-build/pyibuild \
  --specpath /tmp/vconv-build \
  --add-data "core:core" --add-data "ui:ui" --add-data "utils:utils" \
  --add-data "docs:docs" --add-data "presets:presets" --add-data "locales:locales" \
  --hidden-import PyQt6 --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets \
  --hidden-import markdown \
  vconv.py

# Create AppDir
mkdir -p /tmp/vconv-build/vconv.AppDir
cp /tmp/vconv-appimage/vconv /tmp/vconv-build/vconv.AppDir/AppRun
chmod +x /tmp/vconv-build/vconv.AppDir/AppRun

cp public/vconv-icon-256.png /tmp/vconv-build/vconv.AppDir/
cat > /tmp/vconv-build/vconv.AppDir/vconv.desktop << 'DESKTOP'
[Desktop Entry]
Name=MoTekLab Video Encoder
Comment=A modern video converter powered by HandBrakeCLI & PyQt6
Exec=AppRun
Icon=vconv-icon-256
Terminal=false
Type=Application
Categories=AudioVideo;Video;
DESKTOP

# Build AppImage — output goes to dist/
appimagetool --appimage-extract-and-run \
  /tmp/vconv-build/vconv.AppDir \
  "dist/vconv-X.Y.Z-x86_64.AppImage"
```

### 5. Create GitHub Release
```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z — Title" \
  --notes "Release notes here..."

# Or via API:
python3 << 'PYEOF'
import urllib.request, json
# ... (see existing release script)
PYEOF
```

### 6. Upload Artifacts
```bash
# Upload .deb (from dist/)
gh release upload vX.Y.Z dist/vconv_X.Y.Z_all.deb

# Upload AppImage (from dist/)
gh release upload vX.Y.Z dist/vconv-X.Y.Z-x86_64.AppImage
```

After uploads, verify at: https://github.com/motaz-hefny/MoTekLab-vconv/releases

### 7. Public Release Communication (Forum & Blog)

**Strict Order: Forum First, Blog Second.**

#### 7.1. Detailed Forum Post (First)
- **Destination**: MoTekLab Community Forum (`forum.moteklab.com`), proper category (e.g. *Releases / Video Converter*).
- **Format & Content**:
  - Full title: `MoTekLab Video Encoder vX.Y.Z Released — [Key Highlights]`
  - Detailed release notes broken down by category (Core Engine, UI/UX, Performance, Fixes).
  - **Comprehensive historical version segmentation**: Clearly delineate which features/bug fixes landed in which version, minor version, or patch update (e.g., `v9.8.0`, `v9.7.5`, `v9.7.2`, etc.).
  - Technical context, caveats, configuration notes, and direct download links (GitHub release assets & apt commands).
  - Open thread for community feedback and issue reports.

#### 7.2. High-Level Blog Post (Second)
- **Destination**: MoTekLab Blog (`moteklab.com` repository: `content/blog/vconv-X-Y-launch.mdx`).
- **Format & Content**:
  - Concise **2 to 3 paragraphs** only.
  - Highlights the most exciting user-facing improvements and performance gains.
  - Concludes with a prominent call-to-action button or link pointing directly to the **detailed Forum announcement** for full technical changelogs, discussion, and download links.

---

## Practical build notes (2026-10-08, v9.7.1/v9.7.2)

- **Pillow not assumed**: the deb build only needs `dpkg-deb`; the AppImage needs a bundled PyQt6 build (`pyinstaller --onefile`; always use **absolute** `--add-data "/abs/path/core:core"` — relative paths resolve against `--specpath` and fail with "Unable to find …").
- **appimagetool is not installed on this machine.** Two working local paths:
  - `~/.cache/tauri/linuxdeploy-x86_64.AppImage` (+ `linuxdeploy-plugin-appimage.AppImage` beside it) → `ARCH=x86_64 LDAI_OUTPUT="dist/vconv-X.Y.Z-x86_64.AppImage" <linuxdeploy> --appdir <AppDir> --output appimage`
  - or download the official `appimagetool-x86_64.AppImage` from the AppImage/AppImageKit releases and run it with `--appimage-extract-and-run`. (The electron-builder cache at `~/.cache/electron-builder/appimage-12.0.1/` contains only runtime binaries, NOT the CLI.)
- **Publish order gotcha**: the app caches the check result in `~/.config/vconv/update_cache.json` for **24 h**. If a check ran before the new tag was pushed, detection of the new version is delayed until the cache expires — delete that file before verifying "update available".
- **GH API pushes**: plain `git push` fails on this box's HTTPS remote; use the transient helper:
  `git -c credential.helper='!f() { echo "username=oauth2"; echo "password=$(gh auth token)"; }; f' push origin …`
- **Multi-version start menu**: after installing a new deb, the user-scope launcher may still point at an old dev checkout. Regenerate with the installed-aware path: `cp utils/xdg_integration.py /opt/vconv/utils/ && python3 -c "import sys; sys.path.insert(0,'/home/motaz/WebProjects/Video_Convert'); from pathlib import Path; from utils.xdg_integration import ensure_xdg_integration; ensure_xdg_integration(Path('/opt/vconv'))"`.
- Version bump lives in `utils/version.py`; release branches are built in **worktrees** (`git worktree add /tmp/vconv-XYZ HEAD`), so the dev checkout keeps the old version number for update testing. After the user accepts the update test, fast-forward `main` to the release tag commit.

---

## Artifact Summary

All builds go into the **`dist/`** folder in the project root.

| Format | File (in dist/) | Type |
|--------|-----------------|------|
| 📦 Debian | `vconv_X.Y.Z_all.deb` | System package (depends on PyQt6) |
| 🖥️ AppImage | `vconv-X.Y.Z-x86_64.AppImage` | Standalone (bundles PyQt6) |
| 📄 Source | `Source code (tar.gz)` | Auto-generated by GitHub |
