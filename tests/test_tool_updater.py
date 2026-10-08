#!/usr/bin/env python3
"""
Tool Updater Tests (v9.7.0)

Covers:
- GitHub release API parsing (mocked, no network)
- Asset-name regex matching for the real release asset names
- Version detection + update_available logic per tool
- ensure_bin_dir_on_path() PATH handling
- _extract_strip() with a real tar.xz
- ToolsDialog UI status rendering (offscreen)

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_tool_updater.py
"""
import os
import sys
import tarfile
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from utils import tool_updater as tu
from utils.tool_updater import ToolUpdater, ToolStatus

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# offline logic
# ---------------------------------------------------------------------------

def test_asset_regexes():
    check("ffmpeg n8.1 asset matches",
          bool(tu.FFMPEG_ASSET_RE.search("ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz")))
    check("ffmpeg master build does NOT match",
          not tu.FFMPEG_ASSET_RE.search("ffmpeg-master-latest-linux64-gpl.tar.xz"))
    check("ffmpeg shared build does NOT match",
          not tu.FFMPEG_ASSET_RE.search("ffmpeg-n8.1-latest-linux64-gpl-shared-8.1.tar.xz"))
    check("nvencc amd64 deb matches",
          bool(tu.NVENC_ASSET_RE.search("nvencc_9.38_amd64.deb")))
    check("nvencc other arch does NOT match",
          not tu.NVENC_ASSET_RE.search("nvencc_9.38_win64.zip"))


def test_mocked_statuses():
    # Simulate the three GitHub release shapes seen in the wild
    fake = {
        tu.FFMPEG_REPO: {
            "tag": "latest",
            "assets": [("ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz", "https://x/n8.1.tar.xz")],
        },
        tu.NVENC_REPO: {
            "tag": "9.38",
            "assets": [("nvencc_9.38_amd64.deb", "https://x/nvencc_9.38_amd64.deb")],
        },
        tu.HB_REPO: {
            "tag": "1.11.2",
            "assets": [],
        },
    }
    orig = tu.ToolUpdater._grab
    tu.ToolUpdater._grab = lambda self, repo: fake.get(repo, {"tag": "", "assets": []})
    try:
        u = ToolUpdater()
        st = u.status_ffmpeg()
        check("ffmpeg latest parsed from asset (8.1)", st.latest_version == "8.1")
        check("ffmpeg outdated flagged (6.1.1 < 8.1)", st.update_available is True)

        st = u.status_nvencc()
        check("nvencc latest from tag (9.38)", st.latest_version == "9.38")
        check("nvencc not installed -> update available", st.update_available is True)

        st = u.status_handbrake()
        check("handbrake latest from tag (1.11.2)", st.latest_version == "1.11.2")
        check("handbrake outdated flagged (1.7.2 < 1.11.2)", st.update_available is True)
    finally:
        tu.ToolUpdater._grab = orig


def test_version_clean():
    check("_clean_version strips n prefix", tu._clean_version("n8.1") == "8.1")
    check("_clean_version strips v prefix", tu._clean_version("v1.11.2") == "1.11.2")
    check("_clean_version leaves 6.1.1-3ubuntu5", tu._clean_version("6.1.1-3ubuntu5") == "6.1.1-3ubuntu5")
    from utils.updater import parse_version
    check("parse_version handles distro suffix", parse_version("6.1.1-3ubuntu5") == (6, 1, 1))


def test_bin_dir_on_path():
    tu.ensure_bin_dir_on_path()
    check("BIN_DIR in PATH", str(tu.BIN_DIR) in os.environ.get("PATH", ""))
    before = os.environ["PATH"]
    tu.ensure_bin_dir_on_path()
    check("ensure_bin_dir_on_path idempotent (no dup entry)",
          os.environ["PATH"] == before)


def test_extract_strip():
    with tempfile.TemporaryDirectory() as td:
        src_dir = Path(td) / "ffmpeg-8.1" / "release"
        src_dir.mkdir(parents=True)
        (src_dir / "ffmpeg").write_text("binary")
        (src_dir / "ffprobe").write_text("binary")
        tarball = Path(td) / "ffmpeg-n8.1.tar.xz"
        with tarfile.open(tarball, "w:xz") as tar:
            tar.add(Path(td) / "ffmpeg-8.1", arcname="ffmpeg-8.1")
        dest = Path(td) / "out"
        dest.mkdir()
        ok = tu._extract_strip(tarball, dest)
        check("_extract_strip returns True", ok)
        check("_extract_strip strips top dir", (dest / "release" / "ffmpeg").exists())


def test_dialog_rendering():
    app = QApplication.instance() or QApplication([])
    from utils.config import Config
    from ui.main_window import ToolsDialog
    cfg = Config(Path(tempfile.mkdtemp()) / "cfg.json")
    dlg = ToolsDialog(cfg)
    st = ToolStatus(tool_id="ffmpeg", display="ffmpeg / ffprobe",
                    installed_version="6.1.1", latest_version="8.1",
                    update_available=True)
    dlg._apply_status(st)
    row = dlg.rows["ffmpeg"]
    check("dialog shows installed version", "6.1.1" in row["label"].text())
    check("dialog shows latest version", "8.1" in row["label"].text())
    check("dialog enables Update button when outdated", row["button"].isEnabled())

    st.update_available = False
    dlg._apply_status(st)
    check("dialog disables Update button when current", not row["button"].isEnabled())

    dlg.auto_check.setChecked(False)
    check("auto-update toggle persists to config", cfg.get('general', 'auto_update_tools') is False)


def main():
    test_asset_regexes()
    test_version_clean()
    test_mocked_statuses()
    test_bin_dir_on_path()
    test_extract_strip()
    test_dialog_rendering()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())