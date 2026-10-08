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
import urllib.request
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
    orig_ff = tu._ffmpeg_version
    orig_nv = tu._nvenc_version
    orig_hb = tu._hb_version
    tu._ffmpeg_version = lambda: "6.1.1"
    tu._nvenc_version = lambda: ""
    tu._hb_version = lambda: "1.7.2"
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
        tu._ffmpeg_version = orig_ff
        tu._nvenc_version = orig_nv
        tu._hb_version = orig_hb


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


def test_nvencc_version_parse():
    # Real rigaya --version output: "NVEnc (x64) 9.38 (r4176) by rigaya..."
    check("parses x64 banner", tu._NVENC_VER_RE.search(
        "NVEnc (x64) 9.38 (r4176) by rigaya, Oct  7 2026 (gcc 9.4.0/Linux)").group(1) == "9.38")
    check("parses x86 banner", tu._NVENC_VER_RE.search(
        "NVEnc (x86) 9.38 (r4176) by rigaya").group(1) == "9.38")
    check("does not match old NVEncC-prefixed banner",
          tu._NVENC_VER_RE.search("NVEncC 9.37 (r4079)") is None)


def test_find_nvenc_binary():
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "nvencc-9.38"
        (dest / "usr" / "bin").mkdir(parents=True)
        (dest / "usr" / "bin" / "nvencc").write_text("x")
        found = tu._find_nvenc_binary(dest)
        check("finds lowercase nvencc from 9.38 deb", found is not None and found.name == "nvencc")
        (dest / "usr" / "bin" / "NVEncC").write_text("x")
        check("finds NVEncC naming too", tu._find_nvenc_binary(dest).name.lower() in ("nvencc", "nvencc64"))

    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "empty"
        dest.mkdir()
        check("no binary -> None", tu._find_nvenc_binary(dest) is None)


def test_install_concurrency_guard():
    tu._release_install("ffmpeg")
    check("first reserve succeeds", tu._reserve_install("ffmpeg") is True)
    check("second reserve same tool refused", tu._reserve_install("ffmpeg") is False)
    check("different tool can still reserve", tu._reserve_install("nvencc") is True)
    tu._release_install("nvencc")
    check("release frees the tool", tu._reserve_install("ffmpeg") is False)
    tu._release_install("ffmpeg")
    check("release then reserve succeeds", tu._reserve_install("ffmpeg") is True)
    tu._release_install("ffmpeg")

    # update() must refuse a concurrent install WITHOUT touching the network
    def boom(self, repo):
        raise AssertionError("_grab must not be reached when tool is busy")
    orig_grab = tu.ToolUpdater._grab
    tu.ToolUpdater._grab = boom
    try:
        tu._reserve_install("ffmpeg")
        errs = []
        ok = ToolUpdater().update("ffmpeg", error_cb=errs.append)
        check("update refuses while active", ok is False)
        check("concurrency error surfaced via error_cb", bool(errs) and "already running" in errs[0])
    finally:
        tu.ToolUpdater._grab = orig_grab
        tu._release_install("ffmpeg")

    # update() releases the reservation after a successful install
    orig_inst = tu.ToolUpdater._install_ffmpeg
    tu.ToolUpdater._install_ffmpeg = lambda self, progress, error_cb: True
    try:
        ok = ToolUpdater().update("ffmpeg")
        check("update success returns True", ok is True)
        check("reservation released after install", tu._reserve_install("ffmpeg") is True)
    finally:
        tu.ToolUpdater._install_ffmpeg = orig_inst
        tu._release_install("ffmpeg")


class _FakeResp:
    def __init__(self, data=b"hello world"):
        self.headers = {"Content-Length": str(len(data))}
        self._data = data
        self._off = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        chunk = self._data[self._off:self._off + n]
        self._off += len(chunk)
        return chunk


def test_download_error_cb():
    orig_open = urllib.request.urlopen

    def boom(req, timeout=None):
        raise OSError("connection reset by peer")
    urllib.request.urlopen = boom
    try:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "x.bin"
            errs = []
            ok = tu._download("https://x/y", dest, error_cb=errs.append)
            check("download failure returns False", ok is False)
            check("error_cb receives the real reason", bool(errs) and "connection reset by peer" in errs[0])
            check("partial download cleaned up", not dest.exists())
    finally:
        urllib.request.urlopen = orig_open

    def fake_ok(req=None, timeout=None):
        return _FakeResp()
    urllib.request.urlopen = fake_ok
    try:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "ok.bin"
            seen = {}
            ok = tu._download("https://x/y", dest,
                              progress=lambda pct, ph: seen.setdefault("pct", pct),
                              error_cb=lambda m: seen.setdefault("err", m))
            check("download success returns True", ok is True)
            check("file written", dest.read_bytes() == b"hello world")
            check("progress reached 100%", seen.get("pct") == 100)
            check("no error on success", "err" not in seen)
    finally:
        urllib.request.urlopen = orig_open


def test_logger_is_vconv_child():
    # tool_updater logs must reach the configured ~/.config/vconv/logs file
    check("logger is a child of the vconv logger", tu.logger.name == "vconv.utils.tool_updater")


def test_install_worker_surfaces_error():
    app = QApplication.instance() or QApplication([])
    from ui.main_window import ToolInstallWorker
    orig_update = tu.ToolUpdater.update
    orig_status = tu.ToolUpdater.status

    def fake_update(self, tool_id, progress, error_cb):
        if error_cb:
            error_cb("download failed: HTTP 404")
        return False

    def fake_status(self, tool_id):
        return ToolStatus(tool_id=tool_id, display="ffmpeg / ffprobe",
                          latest_version="8.1")
    tu.ToolUpdater.update = fake_update
    tu.ToolUpdater.status = fake_status
    try:
        captured = {}
        w = ToolInstallWorker("ffmpeg")
        w.result.connect(lambda st, ok, msg: captured.update(st=st, ok=ok, msg=msg))
        w.run()
        check("worker reports failure", captured.get("ok") is False)
        check("worker message carries real reason, not 'see log'",
              "download failed: HTTP 404" in captured.get("msg", ""))
        check("worker message does not say 'see log'", "see log" not in captured.get("msg", ""))
    finally:
        tu.ToolUpdater.update = orig_update
        tu.ToolUpdater.status = orig_status


def test_screen_sizing_helper():
    from ui.main_window import _screen_window_bounds
    big = _screen_window_bounds(2560, 1440)
    check("big screen keeps design min size", big[0] == (1100, 700))
    check("big screen keeps design default size", big[1] == (1250, 800))

    lap = _screen_window_bounds(1366, 768)
    check("1366x768 min height clamped below 700", lap[0][1] == 628)
    check("1366x768 default height fits below titlebar", lap[1][1] == 668)

    small = _screen_window_bounds(1024, 600)
    check("1024x600 default fits the screen", small[1][0] <= 1024 and small[1][1] <= 600)
    check("default never smaller than min", small[1][0] >= small[0][0] and small[1][1] >= small[0][1])


def main():
    test_asset_regexes()
    test_version_clean()
    test_mocked_statuses()
    test_bin_dir_on_path()
    test_extract_strip()
    test_dialog_rendering()
    test_nvencc_version_parse()
    test_find_nvenc_binary()
    test_install_concurrency_guard()
    test_download_error_cb()
    test_logger_is_vconv_child()
    test_install_worker_surfaces_error()
    test_screen_sizing_helper()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())