#!/usr/bin/env python3
"""
Defaults hardening tests (unreleased): restore/keep copy + RF 27 defaults,
block accidental wheel changes, fix auto-recommend race, keep Help text
in sync with preset JSON.

Regression for the 2026-10-08 acceptance report:
- x265 conversions failed with HandBrakeCLI exit 3 (default -x subme=9,
  rejected by x265 whose max is 7)
- audio encoder flipped to AAC / encoder silently changed from AV1
  (mouse wheel over unfocused combos changes them)
- "recommended" encoder never auto-selected (addItem signal clobbered
  config value 'auto' before the recommendation logic read it)
- preset WhatsThis claimed stale RF numbers (tv_show RF 24 vs 27)

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_defaults_hardening.py
"""
import gc
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QComboBox, QSlider
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from utils.config import Config
from utils.i18n import I18n
import ui.main_window as mw

ROOT = Path(__file__).resolve().parent.parent
PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


class _StubWorker(mw.QThread):
    """No-network stand-in for the three startup workers (smoke-test pattern)."""
    status_ready = mw.pyqtSignal(object)
    update_found = mw.pyqtSignal(object)
    auto_updated = mw.pyqtSignal(object)
    done = mw.pyqtSignal()
    result = mw.pyqtSignal(object, bool, str)
    progress = mw.pyqtSignal(float, str)

    def __init__(self, *a, **k):
        super().__init__()

    def start(self, *a, **k):
        return None


def make_window(cfg=None):
    mw.UpdateCheckWorker = _StubWorker
    mw.ToolUpdaterWorker = _StubWorker
    mw.ToolInstallWorker = _StubWorker
    tmp = tempfile.TemporaryDirectory(prefix="vconv_defaults_")
    if cfg is None:
        cfg = Config(str(Path(tmp.name) / "vconv.conf"))
        cfg.load()
    win = mw.MainWindow(cfg, I18n(lang="en"))
    win._test_tmp = tmp
    return win


def send_wheel(widget, delta=120):
    e = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, delta),
                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, e)


def test_x265_default_command_uses_valid_subme():
    from core.converter import Converter, ConversionSettings
    win = make_window()
    c = Converter(win.encoder_manager)
    s = ConversionSettings(encoder='x265', quality=27, audio_encoder='copy',
                           output_format='mp4')
    cmd = c._build_command("/in.mkv", "/out.mp4", s)
    x_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == '-x']
    check("x265 command carries an -x string", bool(x_args))
    check("default -x has no subme=9 (x265 max is 7)",
          all('subme=9' not in x for x in x_args))
    check("default -x uses subme=7", all('subme=7' in x for x in x_args))
    win.close()
    del win
    gc.collect()


def test_x265_presets_have_valid_subme():
    data = json.loads((ROOT / 'presets' / 'default_presets.json').read_text())
    for name, p in data.get('presets', {}).items():
        subme = (p.get('advanced') or {}).get('subme')
        if subme is None or p.get('encoder') != 'x265':
            continue
        check(f"preset {name}: subme={subme} <= 7", subme <= 7)


def test_wheel_does_not_change_settings_widgets():
    win = make_window()
    win.show()
    cases = [
        (win.preset_combo, win.preset_combo.currentText(), -120),
        (win.encoder_combo, win.encoder_combo.currentText(), -120),
        (win.audio_enc_combo, win.audio_enc_combo.currentText(), -120),
        (win.quality_slider, win.quality_slider.value(), 120),
    ]
    for w, before, delta in cases:
        send_wheel(w, delta)
        after = w.currentText() if isinstance(w, QComboBox) else w.value()
        check(f"wheel ignored on {type(w).__name__} ({before!r} -> {after!r})",
              after == before)
    win.close()
    del win
    gc.collect()


def test_auto_recommended_encoder_selected_at_startup():
    win = make_window()  # fresh temp config -> defaults: encoder 'auto'
    rec = win.encoder_manager.get_recommended_encoder()
    expected_display = win._encoder_display(rec)
    check(f"config 'auto' resolves to recommended ({rec})",
          win.encoder == rec)
    check(f"combo shows recommended item ({expected_display!r})",
          bool(expected_display) and win.encoder_combo.currentText() == expected_display)
    win.close()
    del win
    gc.collect()


def test_audio_default_loaded_from_config():
    # Fresh config -> copy
    win = make_window()
    check("fresh config starts at audio copy",
          win.audio_enc_combo.currentText() == 'copy' and win.audio_encoder == 'copy')
    win.close()
    del win
    # Saved config -> honored
    with tempfile.TemporaryDirectory(prefix="vconv_defaults_") as d:
        cfg = Config(str(Path(d) / "vconv.conf"))
        cfg.load()
        cfg.set('defaults', 'audio_encoder', 'aac')
        cfg.save()
        cfg2 = Config(str(Path(d) / "vconv.conf"))
        cfg2.load()
        win = make_window(cfg2)
        check("saved audio default aac is restored at startup",
              win.audio_enc_combo.currentText() == 'aac' and win.audio_encoder == 'aac')
        win.close()
        del win
    gc.collect()


def test_preset_whatsthis_rf_matches_json():
    data = json.loads((ROOT / 'presets' / 'default_presets.json').read_text())
    win = make_window()
    whats = win.preset_combo.whatsThis()
    for name in ('fast', 'balanced', 'high_quality', 'archive', 'tv_show'):
        q = data['presets'][name]['quality']
        m = re.search(rf"<b>{name}</b> — .*?RF (\d+)", whats)
        check(f"WhatsThis for {name} states RF {q} (found {m.group(1) if m else None})",
              m is not None and int(m.group(1)) == q)
    win.close()
    del win
    gc.collect()


def test_presets_preserve_source_audio():
    data = json.loads((ROOT / 'presets' / 'default_presets.json').read_text())
    for name, p in data.get('presets', {}).items():
        check(f"preset {name}: audio_encoder is copy",
              p.get('audio_encoder') == 'copy')


def test_default_videos_dir():
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        (home / ".config").mkdir()
        (home / ".config" / "user-dirs.dirs").write_text(
            'XDG_VIDEOS_DIR="$HOME/Vidz"\n', encoding="utf-8")
        check("XDG user-dirs.dirs honored ($HOME expanded)",
              mw.default_videos_dir(home) == home / "Vidz")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        check("missing user-dirs.dirs falls back to ~/Videos",
              mw.default_videos_dir(home) == home / "Videos")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        (home / ".config").mkdir()
        (home / ".config" / "user-dirs.dirs").write_text(
            "# comment only\n", encoding="utf-8")
        check("missing XDG_VIDEOS_DIR key falls back to ~/Videos",
              mw.default_videos_dir(home) == home / "Videos")


def main():
    app = QApplication.instance() or QApplication([])
    test_x265_default_command_uses_valid_subme()
    test_x265_presets_have_valid_subme()
    test_wheel_does_not_change_settings_widgets()
    test_auto_recommended_encoder_selected_at_startup()
    test_audio_default_loaded_from_config()
    test_preset_whatsthis_rf_matches_json()
    test_presets_preserve_source_audio()
    test_default_videos_dir()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
