"""
vconv Main Window UI

PyQt6-based interface for video conversion.
Features: Queue management, real progress, hardware acceleration, subtitle/audio management.
"""

import os
import sys
import signal
import logging
import time
import threading
import shutil
import webbrowser
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QLabel, QPushButton, QComboBox, QSlider,
    QRadioButton, QCheckBox, QProgressBar, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QStatusBar, QToolBar, QMenu, QFrame, QSizePolicy,
    QLineEdit, QDialog, QFormLayout, QInputDialog,
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget,
    QWhatsThis
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QAction, QFont, QKeySequence, QIcon, QPixmap, QShortcut

from core.constants import VIDEO_EXTENSIONS
from core.encoder import EncoderManager
from core.converter import Converter, ConversionSettings, ConversionProgress
from core.handbrake_manager import HandBrakeManager
from core.validator import FileValidator, generate_output_path
from core.analyzer import MediaAnalyzer
from core.queue import QueueManager, Job, JobState
from ui.help_browser import HelpBrowser
from utils.config import Config
from utils.updater import check_for_updates, UpdateInfo
from utils.i18n import I18n
from utils.version import __version__, APP_NAME, APP_DISPLAY_NAME
from utils.xdg_integration import ensure_xdg_integration


def _asset_path(filename: str) -> Path:
    """Resolve path to an asset file, trying multiple locations.
    
    Handles three deployment modes:
    1. Dev mode: project_root/public/filename
    2. AppImage: PyInstaller bundle public/filename (via __file__ parent)
    3. .deb install: /opt/vconv/filename
    """
    # Mode 1 & 2: relative to project / bundle root
    p = Path(__file__).parent.parent / "public" / filename
    if p.exists():
        return p
    # Mode 3: same directory as script (.deb install)
    p = Path(__file__).parent.parent / filename
    if p.exists():
        return p
    return p  # Return best guess even if not found


class ConversionWorker(QThread):
    """Worker thread for file conversion with proper Qt threading."""
    progress = pyqtSignal(object)
    file_started = pyqtSignal(int, int, str)
    file_finished = pyqtSignal(bool, str)
    all_finished = pyqtSignal(int, int, int)
    error_occurred = pyqtSignal(str)
    command_ready = pyqtSignal(str)
    metadata_log = pyqtSignal(str)

    def __init__(self, files, output_base, settings, encoder_manager, source_root=None, preserve_structure=True, file_subtitles=None, handbrake_cmd=None):
        super().__init__()
        self.files = files
        self.output_base = output_base
        self.settings = settings
        self.encoder_manager = encoder_manager
        self.preserve_structure = preserve_structure
        self.source_root = source_root
        self.file_subtitles = file_subtitles or {}
        self._cancel = False
        self._skip = False
        self._converter = Converter(encoder_manager, handbrake_cmd)

    def _resolve_output(self, input_file):
        if self.output_base:
            if self.preserve_structure and self.source_root:
                input_path = Path(input_file).resolve()
                sr = Path(self.source_root).resolve()
                try:
                    rel_path = input_path.relative_to(sr)
                except ValueError:
                    rel_path = Path(input_path.name)
                output_dir = Path(self.output_base) / rel_path.parent
                output_dir.mkdir(parents=True, exist_ok=True)
                return str(output_dir / (input_path.stem + f'.{self.settings.output_format}'))
            else:
                os.makedirs(self.output_base, exist_ok=True)
                return os.path.join(self.output_base, Path(input_file).stem + f'.{self.settings.output_format}')
        return generate_output_path(input_file, format=self.settings.output_format, conflict_mode='rename')

    def run(self):
        total = len(self.files)
        success = 0
        failed = 0

        for idx, input_file in enumerate(self.files):
            if self._cancel:
                break

            if self._skip:
                self._skip = False
                self.file_finished.emit(False, f"Skipped: {os.path.basename(input_file)}")
                failed += 1
                continue

            self.file_started.emit(idx, total, os.path.basename(input_file))
            output_file = self._resolve_output(input_file)

            # Set per-file subtitles
            self.settings.external_srt_files = self.file_subtitles.get(input_file, [])

            # Construct command for debug logging
            debug_cmd = f"HandBrakeCLI -i \"{input_file}\" -o \"{output_file}\" --encoder {self.encoder_manager.to_handbrake_encoder(self.settings.encoder)} --quality {self.settings.quality}"
            self.command_ready.emit(debug_cmd)

            def progress_cb(prog):
                self.progress.emit(prog)

            def meta_log_cb(msg):
                self.metadata_log.emit(msg)

            try:
                result = self._converter.convert(input_file, output_file, self.settings,
                                                 progress_callback=progress_cb, log_callback=meta_log_cb)
                if result:
                    success += 1
                    self.file_finished.emit(True, output_file)
                else:
                    failed += 1
                    self.file_finished.emit(False, input_file)
            except Exception as e:
                failed += 1
                self.error_occurred.emit(str(e))
                self.file_finished.emit(False, str(e))

        self.all_finished.emit(success, failed, total - success - failed)

    def cancel(self):
        self._cancel = True
        if self._converter:
            self._converter.cancel()

    def pause(self):
        if self._converter:
            self._converter.pause()

    def resume(self):
        if self._converter:
            self._converter.resume()

    def skip_current(self):
        self._skip = True
        if self._converter:
            self._converter.cancel()


class UpdateCheckWorker(QThread):
    """Background worker for checking GitHub releases."""
    update_found = pyqtSignal(object)
    check_done = pyqtSignal()

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        info = check_for_updates(self.current_version)
        self.update_found.emit(info)
        self.check_done.emit()


class AudioTrackDialog(QDialog):
    """Per-track audio encoder/bitrate configuration dialog."""
    def __init__(self, audio_streams: list, global_encoder: str,
                 global_bitrate: int, overrides: dict[int, dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audio Track Configuration")
        self.resize(600, 350)
        self.audio_streams = audio_streams
        self.global_encoder = global_encoder
        self.global_bitrate = global_bitrate
        self.track_data: dict[int, dict] = {}

        layout = QVBoxLayout(self)

        info_label = QLabel(f"Configure each audio track individually. "
                            f"Empty encoder = use global default ({global_encoder}).")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Track", "Language", "Codec", "Encoder", "Bitrate (kbps)", ""])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reset All to Global Default")
        reset_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._populate(overrides)

    def _populate(self, overrides: dict[int, dict]):
        self.table.setRowCount(len(self.audio_streams))
        for i, st in enumerate(self.audio_streams):
            idx = st.get('index', i + 1)
            lang = st.get('language', 'unknown')
            codec = st.get('codec', '')
            title = st.get('title', '')
            display = f"{lang}"
            if title:
                display += f" — {title}"

            self.table.setItem(i, 0, QTableWidgetItem(f"#{idx}"))
            self.table.setItem(i, 1, QTableWidgetItem(display))
            self.table.setItem(i, 2, QTableWidgetItem(codec))

            ov = overrides.get(idx, {})
            current_enc = ov.get('encoder', '')
            enc_combo = QComboBox()
            enc_combo.addItems(['', 'copy', 'aac', 'ac3', 'mp3', 'flac'])
            if current_enc:
                enc_combo.setCurrentText(current_enc)
            else:
                enc_combo.setCurrentText('')
            enc_combo.setToolTip("Leave empty to use global default")
            self.table.setCellWidget(i, 3, enc_combo)

            current_bit = ov.get('bitrate', '')
            bit_combo = QComboBox()
            bit_combo.addItems(['', '64', '96', '128', '192', '256', '320'])
            bit_combo.setCurrentText(str(current_bit) if current_bit else '')
            bit_combo.setToolTip("Leave empty to use global default bitrate")
            bit_combo.setEnabled(current_enc not in ('', 'copy'))
            enc_combo.currentTextChanged.connect(
                lambda txt, cb=bit_combo: cb.setEnabled(txt not in ('', 'copy')))
            self.table.setCellWidget(i, 4, bit_combo)

            self.table.setItem(i, 5, QTableWidgetItem(""))

    def _reset_all(self):
        for i in range(self.table.rowCount()):
            w = self.table.cellWidget(i, 3)
            if w:
                w.setCurrentText('')
            bw = self.table.cellWidget(i, 4)
            if bw:
                bw.setCurrentText('')
                bw.setEnabled(False)

    def _on_ok(self):
        overrides = {}
        for i in range(self.table.rowCount()):
            idx_item = self.table.item(i, 0)
            if not idx_item:
                continue
            idx = int(idx_item.text().lstrip('#'))
            enc_w = self.table.cellWidget(i, 3)
            bit_w = self.table.cellWidget(i, 4)
            if not enc_w:
                continue
            enc = enc_w.currentText().strip()
            bit = bit_w.currentText().strip() if bit_w else ''
            if enc:
                entry = {'encoder': enc}
                if enc != 'copy' and bit:
                    entry['bitrate'] = int(bit)
                overrides[idx] = entry
        self.track_data = overrides
        self.accept()

    def get_overrides(self) -> dict[int, dict]:
        return self.track_data


class MainWindow(QMainWindow):
    """Main application window using PyQt6."""

    def __init__(self, config: Config, i18n: I18n, args=None, encoder_manager=None):
        super().__init__()
        self.config = config
        self.i18n = i18n
        self.args = args
        self.encoder_manager = encoder_manager or EncoderManager()
        self.hb_manager = HandBrakeManager()
        self.analyzer = MediaAnalyzer()
        self.validator = FileValidator()
        self.queue_manager = QueueManager()

        self.files = []
        self.source_root = None
        self.is_converting = False
        self.worker = None
        self._update_worker = None

        self.quality = self.config.get('defaults', 'quality', 27)
        self.encoder = self.config.get('defaults', 'encoder', 'auto')
        self.format = self.config.get('defaults', 'format', 'mp4')
        self.output_dir = self.config.get('defaults', 'output_dir', 'source')
        self.last_folder = self.config.get('defaults', 'last_folder', '')
        self.default_folder = self.config.get('defaults', 'default_folder', '')
        self.audio_encoder = 'copy'
        self.audio_bitrate = 128
        self.subtitle_mode = 'all'
        self.subtitle_burn = False
        self.subtitle_lang_list = 'eng,ara'
        self.file_subtitles: dict[str, list[tuple[str, str]]] = {}
        self.audio_track_overrides: dict[int, dict] = {}
        self.external_srt_burn = False
        self.external_srt_default = True
        self.metadata_preserve = True
        self._paused = False
        self._skip_current = False
        self._current_file_index = 0
        self._file_info_cache: dict[str, dict] = {}
        self._file_errors: dict[str, str] = {}
        self.log_lines: list[str] = []
        self.log_retention = self.config.get('general', 'log_retention', False)

        self.encoder_map = self._build_encoder_map()
        self._setup_ui()
        self._ensure_handbrake_cli()
        self._ensure_ffmpeg()
        self._ensure_ffprobe()
        self._load_window_geometry()
        self._refresh_queue_table()
        self._check_for_updates_startup()
        self.setAcceptDrops(True)
        self._setup_shortcuts()

    def _build_encoder_map(self):
        available = self.encoder_manager.get_available_encoders()
        recommended = self.encoder_manager.get_recommended_encoder()
        encoder_map = {}
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available:
                info = self.encoder_manager.get_encoder_info(enc)
                display = info['name']
                encoder_map[display] = enc
        return encoder_map

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._on_delete_key)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, self._on_delete_key)

    def _on_delete_key(self):
        focused = self.focusWidget()
        if focused in (self.file_table, self.file_table.viewport()):
            self._remove_selected()
        elif focused == self.ext_sub_list:
            self._remove_selected_subtitle()
        elif focused == self.queue_table:
            self._remove_selected_from_queue()

    def _set_busy_cursor(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def _clear_busy_cursor(self):
        QApplication.restoreOverrideCursor()

    def _log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_lines.append(line)
        if hasattr(self, 'log_text') and self.log_text:
            self.log_text.append(line)
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _toggle_log_retention(self, checked):
        self.log_retention = checked
        self.config.set('general', 'log_retention', checked)
        self.config.save()
        self.act_log_retention.setText(f"{'✅' if checked else '☐'} Retain Activity Logs")

    def _toggle_auto_update_hb(self, checked):
        self.config.set('general', 'auto_update_handbrake', checked)
        self.config.save()
        self.act_auto_update_hb.setText(f"{'✅' if checked else '☐'} Auto-Update HandBrakeCLI")
        self._log(f"{'Enabled' if checked else 'Disabled'} auto-update for HandBrakeCLI")

    def _toggle_pause_resume(self):
        if not self.worker or not self.is_converting:
            return
        if self._paused:
            self.worker.resume()
            self._paused = False
            self.pause_action.setText("⏸ Pause")
            self.pause_action.setToolTip("Pause the current encoding")
            self._log("Resumed encoding")
        else:
            self.worker.pause()
            self._paused = True
            self.pause_action.setText("▶ Resume")
            self.pause_action.setToolTip("Resume the paused encoding")
            self._log("Paused encoding")

    def _skip_current_file(self):
        if not self.worker or not self.is_converting:
            return
        self._skip_current = True
        self.worker.skip_current()
        self._log("Skipping current file...")

    def _load_column_widths(self, prefix: str, header) -> list[int]:
        widths = []
        for i in range(header.count()):
            w = self.config.get('ui', f'{prefix}_col_{i}')
            if w is not None:
                widths.append(int(w))
        return widths

    def _save_column_widths(self, prefix: str, header):
        for i in range(header.count()):
            self.config.set('ui', f'{prefix}_col_{i}', header.sectionSize(i))

    def _reset_column_widths(self):
        default_widths = [200, 65, 55, 55, 60, 60, 70, 55, 55]
        header = self.file_table.horizontalHeader()
        for i, w in enumerate(default_widths):
            if i < header.count():
                header.resizeSection(i, w)
        for i in range(9):
            self.config.set('ui', f'file_col_{i}', None)
        self.config.save()
        self._log("Column widths reset to defaults")

    def _show_file_table_context_menu(self, pos):
        menu = QMenu(self)
        reset_cols = menu.addAction("Reset Column Widths")
        reset_cols.triggered.connect(self._reset_column_widths)
        menu.exec(self.file_table.viewport().mapToGlobal(pos))

    def _analyze_files_batch(self, file_list: list[str]):
        """Analyze files in background and cache media info."""
        for f in file_list:
            if f in self._file_info_cache:
                continue
            try:
                info = self.analyzer.analyze(f)
                if info:
                    audio_codec = ""
                    audio_bitrate = ""
                    audio_streams_list = []
                    if info.audio_streams:
                        a = info.audio_streams[0]
                        audio_codec = a.get('codec', '')
                        if a.get('channels'):
                            audio_codec += f" {a['channels']}"
                        audio_bitrate = a.get('bitrate', '')
                        for st in info.audio_streams:
                            audio_streams_list.append({
                                'index': st.get('index'),
                                'codec': st.get('codec', ''),
                                'bitrate': st.get('bitrate', ''),
                                'channels': st.get('channels', ''),
                                'language': st.get('language', ''),
                                'title': st.get('title', ''),
                            })
                    video = info.video_codec or ''
                    video_bitrate = info.video_bitrate or ''
                    res = f"{info.width}x{info.height}" if info.width and info.height else ''
                    dur = info.duration or ''
                    self._file_info_cache[f] = {
                        'video': video,
                        'video_bitrate': video_bitrate,
                        'audio': audio_codec,
                        'audio_bitrate': audio_bitrate,
                        'audio_streams': audio_streams_list,
                        'resolution': res,
                        'duration': dur,
                    }
            except Exception:
                self._file_info_cache[f] = {'video': '', 'video_bitrate': '', 'audio': '', 'audio_bitrate': '', 'audio_streams': [], 'resolution': '', 'duration': ''}

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_DISPLAY_NAME} v{__version__}")
        icon = QIcon()
        icon_path = _asset_path("vconv-icon-256.png")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull() and (pixmap.width() > 256 or pixmap.height() > 256):
                pixmap = pixmap.scaled(256, 256)
            icon = QIcon(pixmap)
        if icon.isNull():
            icon = QIcon.fromTheme("vconv")
        if icon.isNull():
            icon = QIcon.fromTheme("video-display")
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setMinimumSize(1100, 700)
        self.resize(1250, 800)

        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = [u.toLocalFile() for u in event.mimeData().urls()
                if u.isLocalFile()]

        subtitle_exts = ('.srt', '.ass', '.ssa', '.sub', '.vtt')
        video_exts = tuple(VIDEO_EXTENSIONS)

        video_files = []
        subtitle_files = []
        dropped_folders = False

        for path in urls:
            if os.path.isdir(path):
                dropped_folders = True
                base = Path(path)
                for ext in video_exts:
                    video_files.extend(str(p) for p in base.rglob(f"*{ext}"))
                    video_files.extend(str(p) for p in base.rglob(f"*{ext.upper()}"))
                # Auto-match subtitles from this folder
                new_subs = self._auto_match_subtitles(video_files)
                for vf, subs in new_subs.items():
                    if vf not in self.file_subtitles:
                        self.file_subtitles[vf] = []
                    for sub in subs:
                        if sub not in self.file_subtitles[vf]:
                            self.file_subtitles[vf].append(sub)
            elif path.lower().endswith(subtitle_exts):
                subtitle_files.append(path)
            elif path.lower().endswith(video_exts):
                video_files.append(path)

        # Deduplicate
        seen = set()
        video_files = [x for x in video_files if not (x in seen or seen.add(x))]

        if video_files:
            self.files.extend(video_files)
            if dropped_folders:
                # Use parent of first dropped folder to preserve folder name in output
                for path in urls:
                    if os.path.isdir(path):
                        self.source_root = str(Path(path).parent)
                        break
            else:
                self.source_root = self._compute_source_root()
            self._set_busy_cursor()
            self._analyze_files_batch(video_files)
            self._clear_busy_cursor()
            self._refresh_file_table()
            self._update_status_bar()
            self._log(f"Added {len(video_files)} file(s) via drag-drop")

        if subtitle_files:
            # Link dropped subtitles to selected video file
            selected = self.file_table.selectionModel().selectedRows()
            if not selected:
                QMessageBox.information(self, "Info",
                    "Select a video file first, then drop subtitles to link them.")
            else:
                row = selected[0].row()
                if 0 <= row < len(self.files):
                    target_file = self.files[row]
                    lang, ok = QInputDialog.getItem(self, "Subtitle Language",
                        "Select language for these subtitles:",
                        ['eng', 'ara', 'fre', 'spa', 'ger', 'ita', 'jpn', 'kor', 'chi', 'hin', 'tur', 'por', 'rus', 'und'],
                        0, False)
                    if not ok:
                        lang = 'eng'
                    if target_file not in self.file_subtitles:
                        self.file_subtitles[target_file] = []
                    for f in subtitle_files:
                        entry = (f, lang)
                        if entry not in self.file_subtitles[target_file]:
                            self.file_subtitles[target_file].append(entry)
                    self._refresh_subtitle_list()

        if video_files or subtitle_files:
            event.acceptProposedAction()

    def _create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        act_files = QAction("Add &Files...", self)
        act_files.setShortcut(QKeySequence.StandardKey.Open)
        act_files.triggered.connect(lambda: self._add_files())
        act_files.setToolTip("Open file browser to select video files")
        file_menu.addAction(act_files)

        act_folder = QAction("Add &Folder...", self)
        act_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_folder.triggered.connect(lambda: self._add_folder())
        act_folder.setToolTip("Scan a folder recursively for video files")
        file_menu.addAction(act_folder)

        file_menu.addSeparator()
        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        settings_menu = menubar.addMenu("&Settings")
        quality_menu = settings_menu.addMenu("&Quality")
        for q in [18, 20, 23, 27, 30]:
            act = QAction(f"RF {q}", self)
            act.triggered.connect(lambda checked, v=q: self._set_quality(v))
            quality_menu.addAction(act)
        settings_menu.addSeparator()
        format_menu = settings_menu.addMenu("&Format")
        act_mp4 = QAction("MP4", self)
        act_mp4.triggered.connect(lambda checked: self._set_format('mp4'))
        format_menu.addAction(act_mp4)
        act_mkv = QAction("MKV", self)
        act_mkv.triggered.connect(lambda checked: self._set_format('mkv'))
        format_menu.addAction(act_mkv)
        settings_menu.addSeparator()

        act_def_folder = QAction("Set &Default Folder...", self)
        act_def_folder.triggered.connect(lambda: self._set_default_folder())
        settings_menu.addAction(act_def_folder)

        act_clear_def = QAction("C&lear Default Folder", self)
        act_clear_def.triggered.connect(lambda: self._clear_default_folder())
        settings_menu.addAction(act_clear_def)
        settings_menu.addSeparator()

        act_save = QAction("&Save Current as Default", self)
        act_save.triggered.connect(lambda: self._save_defaults())
        settings_menu.addAction(act_save)

        act_reset = QAction("&Reset to Defaults", self)
        act_reset.triggered.connect(lambda: self._reset_defaults())
        settings_menu.addAction(act_reset)

        settings_menu.addSeparator()
        lang_menu = settings_menu.addMenu("&Language")
        act_lang_en = QAction("English", self)
        act_lang_en.triggered.connect(lambda: self._set_language('en'))
        lang_menu.addAction(act_lang_en)
        act_lang_ar = QAction("العربية", self)
        act_lang_ar.triggered.connect(lambda: self._set_language('ar'))
        lang_menu.addAction(act_lang_ar)

        settings_menu.addSeparator()
        self.act_log_retention = QAction("☐ Retain Activity Logs", self)
        self.act_log_retention.setCheckable(True)
        self.act_log_retention.setChecked(self.log_retention)
        self.act_log_retention.triggered.connect(self._toggle_log_retention)
        self.act_log_retention.setToolTip("Keep log entries between sessions for troubleshooting")
        settings_menu.addAction(self.act_log_retention)

        self.act_auto_update_hb = QAction("☐ Auto-Update HandBrakeCLI", self)
        self.act_auto_update_hb.setCheckable(True)
        hb_auto_update = self.config.get('general', 'auto_update_handbrake', True)
        self.act_auto_update_hb.setChecked(hb_auto_update)
        self.act_auto_update_hb.setText(f"{'✅' if hb_auto_update else '☐'} Auto-Update HandBrakeCLI")
        self.act_auto_update_hb.triggered.connect(self._toggle_auto_update_hb)
        self.act_auto_update_hb.setToolTip("Automatically check for and install HandBrakeCLI updates on startup")
        settings_menu.addAction(self.act_auto_update_hb)

        self.act_reset_cols = QAction("Reset Column Widths", self)
        self.act_reset_cols.triggered.connect(self._reset_column_widths)
        settings_menu.addAction(self.act_reset_cols)

        settings_menu.addSeparator()
        self.act_update_check = QAction("✅ Check for Updates on Startup", self)
        update_enabled = self.config.get('general', 'check_updates', True)
        self.act_update_check.setChecked(update_enabled)
        self.act_update_check.setCheckable(True)
        self.act_update_check.setChecked(update_enabled)
        self.act_update_check.triggered.connect(self._toggle_update_check)
        settings_menu.addAction(self.act_update_check)

        help_menu = menubar.addMenu("&Help")
        act_help_browser = QAction("📖 &User Guide (Help Browser)", self)
        act_help_browser.setShortcut(QKeySequence("F1"))
        act_help_browser.triggered.connect(lambda: self._show_help_browser())
        act_help_browser.setToolTip("Open the searchable help browser (F1)")
        help_menu.addAction(act_help_browser)

        act_whats_this = QAction("❓ &What's This?", self)
        act_whats_this.setShortcut(QKeySequence("Shift+F1"))
        act_whats_this.triggered.connect(lambda: QWhatsThis.enterWhatsThisMode())
        act_whats_this.setToolTip("Click on any control to learn what it does (Shift+F1)")
        help_menu.addAction(act_whats_this)

        help_menu.addSeparator()
        help_menu.addAction("&Keyboard Shortcuts", self._show_shortcuts)

        help_menu.addSeparator()
        act_update = QAction("🔄 &Check for Updates", self)
        act_update.triggered.connect(lambda: self._check_for_updates_now())
        act_update.setToolTip(f"Check GitHub for a newer version of {APP_NAME}")
        help_menu.addAction(act_update)

        help_menu.addSeparator()
        help_menu.addAction(f"&About {APP_NAME}", self._show_about)

    def _create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        act_files = QAction("➕ Files", self)
        act_files.triggered.connect(lambda: self._add_files())
        toolbar.addAction(act_files)

        act_folder = QAction("➕ Folder", self)
        act_folder.triggered.connect(lambda: self._add_folder())
        toolbar.addAction(act_folder)

        toolbar.addSeparator()

        act_validate = QAction("✅ Validate", self)
        act_validate.setToolTip("Check all files for potential issues before converting")
        act_validate.triggered.connect(lambda: self._validate_files())
        toolbar.addAction(act_validate)

        act_analyze = QAction("📊 Analyze", self)
        act_analyze.setToolTip("Show detailed media info for all files (codec, resolution, subtitles)")
        act_analyze.triggered.connect(lambda: self._analyze_files())
        toolbar.addAction(act_analyze)

        toolbar.addSeparator()

        self.convert_action = QAction("🚀 CONVERT", self)
        self.convert_action.setToolTip("Start encoding all files in the list")
        self.convert_action.triggered.connect(lambda: self._start_conversion())
        self.convert_action.setFont(QFont("", -1, QFont.Weight.Bold))
        toolbar.addAction(self.convert_action)

        self.pause_action = QAction("⏸ Pause", self)
        self.pause_action.setToolTip("Pause the current encoding")
        self.pause_action.triggered.connect(lambda: self._toggle_pause_resume())
        self.pause_action.setEnabled(False)
        toolbar.addAction(self.pause_action)

        self.skip_action = QAction("⏭ Skip", self)
        self.skip_action.setToolTip("Skip the current file and continue with the next")
        self.skip_action.triggered.connect(lambda: self._skip_current_file())
        self.skip_action.setEnabled(False)
        toolbar.addAction(self.skip_action)

        self.cancel_action = QAction("⏹ Stop", self)
        self.cancel_action.setToolTip("Cancel the current conversion operation")
        self.cancel_action.triggered.connect(lambda: self._cancel_conversion())
        self.cancel_action.setEnabled(False)
        toolbar.addAction(self.cancel_action)

    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(True)
        main_layout.addWidget(splitter)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        left_panel.setMinimumWidth(0)
        left_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 950])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)
        layout.setContentsMargins(2, 2, 2, 2)

        encoder_group = QGroupBox("Encoder")
        enc_layout = QVBoxLayout(encoder_group)
        self.encoder_combo = QComboBox()
        self.encoder_combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.encoder_combo.currentTextChanged.connect(self._on_encoder_changed)
        for display in self.encoder_map.keys():
            self.encoder_combo.addItem(display)
        self.encoder_combo.setToolTip("Select video encoder (hardware or CPU)")
        self.encoder_combo.setWhatsThis(
            "<b>Video Encoder</b><br>"
            "Choose the encoding engine.<br><br>"
            "<b>NVENC H.265</b> — NVIDIA GPU, very fast, good quality<br>"
            "<b>QSV H.265</b> — Intel GPU, fast, low power<br>"
            "<b>AMF H.265</b> — AMD GPU, fast encoding<br>"
            "<b>x265</b> — CPU, excellent quality, slower<br>"
            "<b>x264</b> — CPU, great compatibility<br>"
            "<b>SVT-AV1</b> — CPU, best compression, very slow<br><br>"
            "Hardware encoders are 3-5x faster but may produce slightly larger files."
        )
        enc_layout.addWidget(self.encoder_combo)
        hw_text = f"🖥️ {self.encoder_manager.get_hardware_name()}"
        recommended = self.encoder_manager.get_recommended_encoder()
        if recommended:
            rec_name = self.encoder_manager.get_encoder_info(recommended).get('name', recommended)
            hw_text += f"  ✅ {rec_name} (Recommended)"
        hw_label = QLabel(hw_text)
        hw_label.setStyleSheet("color: #00B4D8; font-size: 11px;")
        hw_label.setWordWrap(True)
        enc_layout.addWidget(hw_label)
        layout.addWidget(encoder_group)

        quality_group = QGroupBox("Quality (RF)")
        qual_layout = QVBoxLayout(quality_group)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(0, 51)
        self.quality_slider.setValue(self.quality)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        self.quality_slider.setToolTip("Lower RF = better quality, larger files (0-51)")
        self.quality_slider.setWhatsThis(
            "<b>Quality (RF)</b><br>"
            "Constant Rate Factor controls quality.<br><br>"
            "<b>18-20</b> — Excellent (archive quality)<br>"
            "<b>21-23</b> — Great (high quality rips)<br>"
            "<b>24-27</b> — Good (default balanced)<br>"
            "<b>28-30</b> — Fair (mobile devices)<br>"
            "<b>31-35</b> — Poor (streaming)<br><br>"
            "Lower values = larger files, higher values = smaller files."
        )
        qual_layout.addWidget(self.quality_slider)
        self.quality_label = QLabel(f"Current: {self.quality}")
        qual_layout.addWidget(self.quality_label)
        layout.addWidget(quality_group)

        preset_group = QGroupBox("Preset")
        preset_layout = QVBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(['fast', 'balanced', 'high_quality', 'archive', 'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'web_optimized', 'mobile', 'tv_show'])
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        self.preset_combo.setToolTip("Quick-select a preset configuration")
        self.preset_combo.setWhatsThis(
            "<b>Presets</b><br>"
            "Pre-configured settings for common use cases.<br><br>"
            "<b>fast</b> — Quick encoding, RF 27<br>"
            "<b>balanced</b> — Everyday use, RF 25<br>"
            "<b>high_quality</b> — Important videos, RF 22<br>"
            "<b>archive</b> — Long-term storage, RF 20<br>"
            "<b>nvenc_fast/balanced/quality</b> — NVIDIA-optimized<br>"
            "<b>tv_show</b> — Television episodes, RF 24"
        )
        preset_layout.addWidget(self.preset_combo)
        layout.addWidget(preset_group)

        output_group = QGroupBox("Output")
        out_layout = QVBoxLayout(output_group)
        self.output_same_radio = QRadioButton("Same as source (preserve structure)")
        self.output_same_radio.setChecked(True)
        self.output_same_radio.setToolTip("Save encoded files in their original folders")
        self.output_same_radio.setWhatsThis("<b>Same as Source</b><br>Files are saved alongside the originals with a new extension. Folder structure is naturally preserved.")
        self.output_custom_radio = QRadioButton("Custom folder")
        self.output_custom_radio.setToolTip("Save all encoded files to a specific folder")
        self.output_custom_radio.setWhatsThis("<b>Custom Folder</b><br>Choose a destination folder. By default, the source folder structure is recreated under this folder. Check 'Flat output' to dump all files directly.")
        self.output_custom_radio.toggled.connect(self._on_output_mode_changed)
        out_layout.addWidget(self.output_same_radio)
        out_layout.addWidget(self.output_custom_radio)
        out_input_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setEnabled(False)
        self.output_dir_edit.setPlaceholderText("Select custom output folder...")
        out_input_layout.addWidget(self.output_dir_edit)
        browse_btn = QPushButton("📁")
        browse_btn.setMaximumWidth(35)
        browse_btn.setToolTip("Browse for custom output folder")
        browse_btn.clicked.connect(lambda: self._browse_output())
        out_input_layout.addWidget(browse_btn)
        out_layout.addLayout(out_input_layout)
        self.flat_output_check = QCheckBox("Flat output (dump all files in one folder)")
        self.flat_output_check.setEnabled(False)
        self.flat_output_check.setToolTip("When unchecked, folder structure is preserved relative to source root")
        self.flat_output_check.setWhatsThis("<b>Flat Output</b><br>When checked, all output files go directly into the custom folder root regardless of source folder structure. When unchecked, the relative folder paths from the source root are recreated under the output folder.")
        self.output_custom_radio.toggled.connect(lambda c: self.flat_output_check.setEnabled(c))
        out_layout.addWidget(self.flat_output_check)
        layout.addWidget(output_group)

        format_group = QGroupBox("Format")
        fmt_layout = QHBoxLayout(format_group)
        self.mp4_radio = QRadioButton("MP4")
        self.mp4_radio.setChecked(self.format == 'mp4')
        self.mp4_radio.setToolTip("MP4 output — best for universal compatibility and streaming")
        self.mp4_radio.setWhatsThis("<b>MP4 Format</b><br>Most compatible container format. Works on all devices, streaming platforms, and social media. Supports AAC audio. Soft subtitles limited.")
        self.mp4_radio.toggled.connect(lambda c: self._set_format('mp4') if c else None)
        self.mkv_radio = QRadioButton("MKV")
        self.mkv_radio.setChecked(self.format == 'mkv')
        self.mkv_radio.setToolTip("MKV output — best for multiple audio/subtitle tracks and chapters")
        self.mkv_radio.setWhatsThis("<b>MKV Format</b><br>Matroska container. Best for multiple audio tracks, subtitle tracks, and chapter markers. Supports virtually any codec. Less compatible with older devices.")
        fmt_layout.addWidget(self.mp4_radio)
        fmt_layout.addWidget(self.mkv_radio)
        layout.addWidget(format_group)

        audio_group = QGroupBox("Audio")
        aud_layout = QFormLayout(audio_group)
        aud_layout.setSpacing(4)
        self.audio_enc_combo = QComboBox()
        self.audio_enc_combo.addItems(['copy', 'aac', 'ac3', 'mp3', 'flac'])
        self.audio_enc_combo.setToolTip("Audio encoder — 'copy' passthrough without re-encoding")
        self.audio_enc_combo.setWhatsThis(
            "<b>Audio Encoder</b><br>"
            "<b>copy</b> — Passthrough original audio without re-encoding (fast, no quality loss)<br>"
            "<b>AAC</b> — Good quality, best MP4 compatibility<br>"
            "<b>AC3</b> — Dolby Digital, surround sound support<br>"
            "<b>MP3</b> — Legacy format, wide compatibility<br>"
            "<b>FLAC</b> — Lossless, archival quality (MKV only)"
        )
        self.audio_enc_combo.currentTextChanged.connect(self._on_audio_encoder_changed)
        aud_layout.addRow("Encoder:", self.audio_enc_combo)
        self.audio_bit_combo = QComboBox()
        self.audio_bit_combo.addItems(['64', '96', '128', '192', '256', '320'])
        self.audio_bit_combo.setCurrentText('128')
        self.audio_bit_combo.setEnabled(False)
        self.audio_bit_combo.setToolTip("Audio bitrate in kbps — higher = better quality, larger file")
        self.audio_bit_combo.setWhatsThis("<b>Audio Bitrate</b><br>64-96 kbps for speech, 128-192 kbps for general use, 256-320 kbps for high fidelity. Higher bitrate = larger file size.")
        aud_layout.addRow("Bitrate:", self.audio_bit_combo)
        track_btn_layout = QHBoxLayout()
        self.audio_tracks_btn = QPushButton("Tracks...")
        self.audio_tracks_btn.setToolTip("Configure per-track audio encoder and bitrate overrides")
        self.audio_tracks_btn.clicked.connect(self._open_audio_tracks_dialog)
        track_btn_layout.addWidget(self.audio_tracks_btn)
        self.audio_tracks_status = QLabel("")
        self.audio_tracks_status.setStyleSheet("color: #888; font-size: 10px;")
        track_btn_layout.addWidget(self.audio_tracks_status)
        aud_layout.addRow("", track_btn_layout)
        layout.addWidget(audio_group)

        sub_group = QGroupBox("Subtitles")
        sub_layout = QVBoxLayout(sub_group)
        sub_layout.setSpacing(6)

        sub_mode_layout = QHBoxLayout()
        sub_mode_layout.addWidget(QLabel("Embedded:"))
        self.sub_combo = QComboBox()
        self.sub_combo.addItems(['copy', 'all', 'none'])
        self.sub_combo.setCurrentText('all')
        self.sub_combo.setToolTip(
            "copy  → Keep only subtitles matching your language list (e.g. eng,ara)\n"
            "all   → Keep every subtitle track in the source, ignoring the language list\n"
            "none  → Strip all subtitles"
        )
        self.sub_combo.setWhatsThis(
            "<b>Embedded Subtitle Mode</b><br><br>"
            "<b>copy</b> — Pass through only subtitle tracks whose language matches"
            " the list in the <b>Languages</b> field. Tracks in other languages are dropped."
            " This is the recommended mode for normal use.<br><br>"
            "<b>all</b> — Keep every embedded subtitle track from the source,"
            " ignoring the language filter entirely."
            " Useful when you want to preserve commentary tracks or"
            " subtitles in unexpected languages.<br><br>"
            "<b>none</b> — Remove all subtitles from the output."
        )
        self.sub_combo.currentTextChanged.connect(self._on_subtitle_mode_changed)
        sub_mode_layout.addWidget(self.sub_combo)
        self.sub_burn_check = QCheckBox("Burn")
        self.sub_burn_check.setToolTip("Burn (hardcode) selected subtitles into the video image")
        self.sub_burn_check.setWhatsThis("<b>Burn Subtitles</b><br>Hardcode subtitles permanently into the video. They cannot be turned off. Useful for foreign language segments or when subtitle support is required.")
        self.sub_burn_check.toggled.connect(lambda c: setattr(self, 'subtitle_burn', c))
        sub_mode_layout.addWidget(self.sub_burn_check)
        sub_layout.addLayout(sub_mode_layout)

        sub_lang_layout = QHBoxLayout()
        sub_lang_layout.addWidget(QLabel("Languages:"))
        self.sub_lang_edit = QLineEdit("eng,ara")
        self.sub_lang_edit.setPlaceholderText("eng,ara,fr...")
        self.sub_lang_edit.setToolTip("Comma-separated ISO 639-2 language codes (eng=English, ara=Arabic)")
        self.sub_lang_edit.setWhatsThis("<b>Subtitle Language Filter</b><br>Specify which subtitle languages to keep. Use comma-separated ISO 639-2 codes.<br><br>Common codes: eng, ara, fre, spa, ger, jpn, kor, chi, rus, por, ita")
        self.sub_lang_edit.textChanged.connect(lambda t: setattr(self, 'subtitle_lang_list', t))
        sub_lang_layout.addWidget(self.sub_lang_edit)
        sub_layout.addLayout(sub_lang_layout)

        sub_layout.addWidget(QLabel("External Subtitles:"))
        self.ext_sub_list = QListWidget()
        self.ext_sub_list.setMaximumHeight(80)
        self.ext_sub_list.setToolTip("SRT, ASS, SSA files to embed")
        sub_layout.addWidget(self.ext_sub_list)

        ext_btn_layout = QHBoxLayout()
        ext_btn_layout.setSpacing(4)
        add_sub_btn = QPushButton("➕ Add")
        add_sub_btn.setToolTip("Add external subtitle files (SRT, ASS, SSA)")
        add_sub_btn.setWhatsThis("<b>Add External Subtitles</b><br>Browse and add subtitle files. Supported formats: SRT, ASS, SSA, SUB, VTT. Each file gets its own language tag.")
        add_sub_btn.clicked.connect(lambda: self._add_external_subtitles())
        ext_btn_layout.addWidget(add_sub_btn)
        remove_sub_btn = QPushButton("❌")
        remove_sub_btn.setMaximumWidth(35)
        remove_sub_btn.setToolTip("Remove selected subtitle from list")
        remove_sub_btn.clicked.connect(lambda: self._remove_selected_subtitle())
        ext_btn_layout.addWidget(remove_sub_btn)
        clear_sub_btn = QPushButton("🗑")
        clear_sub_btn.setMaximumWidth(35)
        clear_sub_btn.setToolTip("Clear all external subtitles")
        clear_sub_btn.clicked.connect(lambda: self._clear_external_subtitles())
        ext_btn_layout.addWidget(clear_sub_btn)
        ext_opts_layout = QHBoxLayout()
        self.ext_srt_burn_check = QCheckBox("Burn external")
        self.ext_srt_burn_check.setToolTip("Burn external subtitles permanently into the video")
        self.ext_srt_burn_check.toggled.connect(lambda c: setattr(self, 'external_srt_burn', c))
        ext_opts_layout.addWidget(self.ext_srt_burn_check)
        self.ext_srt_default_check = QCheckBox("Set as default")
        self.ext_srt_default_check.setChecked(True)
        self.ext_srt_default_check.setToolTip("Make external subtitles the default playback track")
        self.ext_srt_default_check.toggled.connect(lambda c: setattr(self, 'external_srt_default', c))
        ext_opts_layout.addWidget(self.ext_srt_default_check)
        ext_btn_layout.addLayout(ext_opts_layout)
        sub_layout.addLayout(ext_btn_layout)

        layout.addWidget(sub_group)

        self.metadata_check = QCheckBox("Preserve metadata from source")
        self.metadata_check.setChecked(True)
        self.metadata_check.setToolTip(
            "Extract and preserve source metadata (title, date, genre, cover art, etc.) "
            "after encoding. Disable to skip metadata handling for faster processing.")
        self.metadata_check.toggled.connect(lambda c: setattr(self, 'metadata_preserve', c))
        layout.addWidget(self.metadata_check)

        layout.addStretch()
        return panel

    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        files_group = QGroupBox(f"Files to Convert ({len(self.files)})")
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(4, 6, 4, 4)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(9)
        self.file_table.setHorizontalHeaderLabels(
            ["File", "Size", "Video", "Audio", "Video Bitrate", "Audio Bitrate", "Resolution", "Duration", "Status"])
        header = self.file_table.horizontalHeader()
        header.setSectionsMovable(True)
        saved = self._load_column_widths('file', header)
        for i in range(9):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        if saved:
            for i, w in enumerate(saved):
                if i < header.count():
                    header.resizeSection(i, w)
        else:
            default_w = [200, 65, 55, 55, 60, 60, 70, 55, 55]
            for i, w in enumerate(default_w):
                header.resizeSection(i, w)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setMinimumHeight(160)
        self.file_table.setToolTip("Added video files. Select rows and use buttons below to manage.")
        self.file_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self._show_file_table_context_menu)
        self.file_table.selectionModel().selectionChanged.connect(self._on_file_selection_changed)
        files_layout.addWidget(self.file_table)

        file_btn_layout = QHBoxLayout()
        btn_add_files = QPushButton("➕ Files")
        btn_add_files.setToolTip("Open file browser to select video files")
        btn_add_files.clicked.connect(self._add_files)
        file_btn_layout.addWidget(btn_add_files)
        btn_add_folder = QPushButton("➕ Folder")
        btn_add_folder.setToolTip("Scan a folder recursively for video files")
        btn_add_folder.clicked.connect(self._add_folder)
        file_btn_layout.addWidget(btn_add_folder)
        btn_clear = QPushButton("❌ Clear")
        btn_clear.setToolTip("Remove all files from the list")
        btn_clear.clicked.connect(self._clear_files)
        file_btn_layout.addWidget(btn_clear)
        btn_remove = QPushButton("❌ Remove")
        btn_remove.setToolTip("Remove selected files from the list")
        btn_remove.clicked.connect(self._remove_selected)
        file_btn_layout.addWidget(btn_remove)
        file_btn_layout.addStretch()
        self.add_to_queue_btn = QPushButton("📋 Add to Queue")
        self.add_to_queue_btn.clicked.connect(lambda: self._add_selected_to_queue())
        self.add_to_queue_btn.setToolTip("Add selected files to the conversion queue below")
        file_btn_layout.addWidget(self.add_to_queue_btn)
        files_layout.addLayout(file_btn_layout)

        layout.addWidget(files_group)

        queue_group = QGroupBox("Conversion Queue")
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.setContentsMargins(4, 6, 4, 4)

        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(4)
        self.queue_table.setHorizontalHeaderLabels(["File", "Output", "Progress", "Status"])
        self.queue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setMinimumHeight(120)
        self.queue_table.setToolTip("Queued jobs. Add files above, then press Start Queue.")
        queue_layout.addWidget(self.queue_table)

        queue_btn_layout = QHBoxLayout()
        self.queue_start_btn = QPushButton("▶ Start Queue")
        self.queue_start_btn.setToolTip("Start processing all pending queue jobs")
        self.queue_start_btn.clicked.connect(lambda: self._start_queue())
        queue_btn_layout.addWidget(self.queue_start_btn)
        btn_queue_remove = QPushButton("❌ Remove Selected")
        btn_queue_remove.setToolTip("Remove selected jobs from the queue")
        btn_queue_remove.clicked.connect(self._remove_selected_from_queue)
        queue_btn_layout.addWidget(btn_queue_remove)
        btn_queue_clear = QPushButton("🗑 Clear All")
        btn_queue_clear.setToolTip("Remove all jobs from the queue")
        btn_queue_clear.clicked.connect(self._clear_queue)
        queue_btn_layout.addWidget(btn_queue_clear)
        queue_btn_layout.addStretch()
        queue_layout.addLayout(queue_btn_layout)

        layout.addWidget(queue_group)

        progress_group = QGroupBox("Progress")
        prog_layout = QVBoxLayout(progress_group)
        prog_layout.setContentsMargins(4, 6, 4, 4)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #2ECC71; font-weight: bold; font-size: 13px;")
        self.status_label.setToolTip("Current operation status")
        prog_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("Overall: %v/%m files")
        self.progress_bar.setVisible(False)
        self.progress_bar.setToolTip("Overall batch conversion progress")
        prog_layout.addWidget(self.progress_bar)

        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setFormat("Current file: %p%")
        self.file_progress_bar.setVisible(False)
        self.file_progress_bar.setToolTip("Current file encoding progress")
        prog_layout.addWidget(self.file_progress_bar)

        layout.addWidget(progress_group)

        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(4, 4, 4, 4)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setPlaceholderText("Encoding activity will appear here...")
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        return panel

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _update_status_bar(self):
        hw = self.encoder_manager.get_hardware_name()
        self.status_bar.showMessage(f"{APP_NAME} v{__version__} | {hw} | Files: {len(self.files)} | Queue: {len(self.queue_manager.jobs)} | Quality: RF {self.quality}")

    def _load_window_geometry(self):
        x = self.config.get('ui', 'window_x')
        y = self.config.get('ui', 'window_y')
        w = self.config.get('ui', 'window_width', 1250)
        h = self.config.get('ui', 'window_height', 800)
        if x is not None and y is not None:
            self.setGeometry(int(x), int(y), int(w), int(h))
        else:
            self.resize(int(w), int(h))

    def closeEvent(self, event):
        self.config.set('ui', 'window_x', self.geometry().x())
        self.config.set('ui', 'window_y', self.geometry().y())
        self.config.set('ui', 'window_width', self.geometry().width())
        self.config.set('ui', 'window_height', self.geometry().height())
        self._save_column_widths('file', self.file_table.horizontalHeader())
        self._save_column_widths('queue', self.queue_table.horizontalHeader())
        self.config.save()
        if not self.log_retention:
            self.log_lines.clear()
        if self.is_converting:
            self._cancel_conversion()
            threading.Event().wait(0.5)
        event.accept()

    def _on_encoder_changed(self, text):
        self.encoder = self.encoder_map.get(text, 'x265')

    def _on_quality_changed(self, value):
        self.quality = value
        self.quality_label.setText(f"Current: {value}")

    def _on_audio_encoder_changed(self, text):
        is_copy = (text == 'copy')
        self.audio_bit_combo.setEnabled(not is_copy)
        self.audio_encoder = text

    def _open_audio_tracks_dialog(self):
        if not self.files:
            QMessageBox.information(self, "Info", "Add files first to see their audio tracks.")
            return
        first_file = self.files[0]
        info = self._file_info_cache.get(first_file, {})
        streams = info.get('audio_streams', [])
        if not streams:
            info_data = self.analyzer.analyze(first_file)
            if info_data and info_data.audio_streams:
                streams = [{
                    'index': s.get('index'),
                    'codec': s.get('codec', ''),
                    'bitrate': s.get('bitrate', ''),
                    'channels': s.get('channels', ''),
                    'language': s.get('language', ''),
                    'title': s.get('title', ''),
                } for s in info_data.audio_streams]
        if not streams:
            QMessageBox.information(self, "Info", "No audio tracks detected in the first file.")
            return
        global_bitrate = int(self.audio_bit_combo.currentText()) if self.audio_encoder != 'copy' else 128
        dlg = AudioTrackDialog(streams, self.audio_encoder, global_bitrate,
                               self.audio_track_overrides, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.audio_track_overrides = dlg.get_overrides()
            count = len(self.audio_track_overrides)
            if count:
                self.audio_tracks_status.setText(f"{count} track(s) customized")
            else:
                self.audio_tracks_status.setText("")

    def _on_output_mode_changed(self, checked):
        self.output_dir_edit.setEnabled(checked)
        self.flat_output_check.setEnabled(checked)

    def _on_subtitle_mode_changed(self, text):
        self.subtitle_mode = text
        self.sub_burn_check.setEnabled(text != 'none')

    def _set_quality(self, value):
        self.quality = value
        self.quality_slider.setValue(value)

    def _set_format(self, fmt):
        self.format = fmt
        if fmt == 'mp4':
            self.mp4_radio.setChecked(True)
        else:
            self.mkv_radio.setChecked(True)

    def _add_files(self):
        initial = self.last_folder or self.default_folder or os.path.expanduser('~')
        files, _ = QFileDialog.getOpenFileNames(self, "Select video files", initial,
            "Video Files (*.mkv *.mp4 *.avi *.mov *.webm *.wmv *.flv *.m4v *.ts *.m2ts)")
        if files:
            self.files.extend(files)
            self.source_root = self._compute_source_root()
            self.last_folder = os.path.dirname(files[0])
            self.config.set('defaults', 'last_folder', self.last_folder)
            self.config.save()
            self._set_busy_cursor()
            self._analyze_files_batch(files)
            self._clear_busy_cursor()
            self._refresh_file_table()
            self._update_status_bar()
            self._log(f"Added {len(files)} file(s)")

    def _compute_source_root(self):
        if not self.files:
            return None
        if len(self.files) == 1:
            return os.path.dirname(self.files[0])
        try:
            return os.path.commonpath([os.path.dirname(f) for f in self.files])
        except Exception:
            return os.path.dirname(self.files[0])

    def _add_folder(self):
        initial = self.last_folder or self.default_folder or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select folder with videos", initial)
        if folder:
            self.last_folder = folder
            self.source_root = str(Path(folder).parent)
            self.config.set('defaults', 'last_folder', folder)
            self.config.save()
            base_path = Path(folder)
            videos = []
            for ext in VIDEO_EXTENSIONS:
                videos.extend(base_path.rglob(f"*{ext}"))
                videos.extend(base_path.rglob(f"*{ext.upper()}"))
            videos = list(set(str(v) for v in videos))[:500]
            if videos:
                self.files.extend(videos)
                # Auto-match subtitles from this folder
                matched = self._auto_match_subtitles(videos)
                for vf, subs in matched.items():
                    if vf not in self.file_subtitles:
                        self.file_subtitles[vf] = []
                    for sub in subs:
                        if sub not in self.file_subtitles[vf]:
                            self.file_subtitles[vf].append(sub)
                self._set_busy_cursor()
                self._analyze_files_batch(videos)
                self._clear_busy_cursor()
                self._refresh_file_table()
                self._update_status_bar()
                self._log(f"Added {len(videos)} file(s) from folder")
                QMessageBox.information(self, "Files Added", f"Added {len(videos)} video files!")
            else:
                QMessageBox.information(self, "Info", "No video files found")

    def _clear_files(self):
        n = len(self.files)
        self.files.clear()
        self.file_subtitles.clear()
        self._file_info_cache.clear()
        self._file_errors.clear()
        self.source_root = None
        self._refresh_file_table()
        self._update_status_bar()
        self._log(f"Cleared {n} file(s) from list")

    def _remove_selected(self):
        selected = self.file_table.selectionModel().selectedRows()
        if selected:
            indices = sorted([r.row() for r in selected], reverse=True)
            for idx in indices:
                if 0 <= idx < len(self.files):
                    removed = self.files.pop(idx)
                    self.file_subtitles.pop(removed, None)
                    self._file_info_cache.pop(removed, None)
            self._refresh_file_table()
            self._update_status_bar()
            self._log(f"Removed {len(selected)} file(s)")

    def _refresh_file_table(self):
        self.file_table.setRowCount(len(self.files))
        for i, f in enumerate(self.files):
            self.file_table.setItem(i, 0, QTableWidgetItem(os.path.basename(f)))
            try:
                size = os.path.getsize(f)
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size < 1024:
                        self.file_table.setItem(i, 1, QTableWidgetItem(f"{size:.1f} {unit}"))
                        break
                    size /= 1024
            except:
                self.file_table.setItem(i, 1, QTableWidgetItem("N/A"))
            # Media info columns
            info = self._file_info_cache.get(f, {})
            self.file_table.setItem(i, 2, QTableWidgetItem(info.get('video', '')))
            self.file_table.setItem(i, 3, QTableWidgetItem(info.get('audio', '')))
            self.file_table.setItem(i, 4, QTableWidgetItem(info.get('video_bitrate', '')))
            self.file_table.setItem(i, 5, QTableWidgetItem(info.get('audio_bitrate', '')))
            self.file_table.setItem(i, 6, QTableWidgetItem(info.get('resolution', '')))
            self.file_table.setItem(i, 7, QTableWidgetItem(info.get('duration', '')))
            self.file_table.setItem(i, 8, QTableWidgetItem("Pending"))

    def _on_file_selection_changed(self, selected, deselected):
        self._refresh_subtitle_list()

    def _refresh_subtitle_list(self):
        self.ext_sub_list.clear()
        selected = self.file_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if 0 <= row < len(self.files):
            target = self.files[row]
            for entry in self.file_subtitles.get(target, []):
                f, lang = entry
                self.ext_sub_list.addItem(f"{os.path.basename(f)} [{lang}]")

    @staticmethod
    def _auto_match_subtitles(video_files):
        """Auto-detect subtitle files matching video files by Plex-style naming."""
        sub_exts = ('.srt', '.ass', '.ssa', '.sub', '.vtt')
        result = {}
        for vf in video_files:
            vp = Path(vf)
            parent = vp.parent
            base = vp.stem
            subs = []
            for ext in sub_exts:
                for p in parent.glob(f"{base}*{ext}"):
                    if not p.exists():
                        continue
                    if p.stem == base:
                        lang = 'und'
                    elif p.stem.startswith(base + '.'):
                        suffix = p.stem[len(base) + 1:]
                        lang = suffix if len(suffix) == 3 else 'und'
                    else:
                        continue
                    entry = (str(p), lang)
                    if entry not in subs:
                        subs.append(entry)
            if subs:
                result[vf] = subs
        return result

    def _validate_files(self):
        if not self.files:
            QMessageBox.information(self, "Info", "No files to validate")
            return
        valid = 0
        issues = []
        for f in self.files:
            out = generate_output_path(f, format=self.format, conflict_mode='rename')
            result = self.validator.validate_file(f, out)
            if result.status == 'valid':
                valid += 1
            else:
                issues.append(f"{os.path.basename(f)}: {result.message}")
        if issues:
            QMessageBox.warning(self, "Validation", f"✅ Valid: {valid}\n⚠️ Issues: {len(issues)}\n\n" + '\n'.join(issues[:20]))
        else:
            QMessageBox.information(self, "Validation", f"✅ All {valid} files ready!")

    def _analyze_files(self):
        if not self.files:
            QMessageBox.information(self, "Info", "No files to analyze")
            return
        results = []
        for f in self.files[:50]:
            try:
                info = self.analyzer.analyze(f)
                if info:
                    subs = ""
                    if info.subtitle_streams:
                        sub_names = [f"[{s['language']}] {s['title']}" for s in info.subtitle_streams[:5]]
                        subs = f"\n   📝 Subtitles ({len(info.subtitle_streams)}): {', '.join(sub_names)}"
                    audio_info = ""
                    if info.audio_streams:
                        aud_lines = []
                        for a in info.audio_streams[:4]:
                            parts = [f"{a['codec']}"]
                            if a['channels']:
                                parts.append(a['channels'])
                            if a['language']:
                                parts.append(f"[{a['language']}]")
                            if a['title']:
                                parts.append(f"\"{a['title']}\"")
                            if a['bitrate']:
                                parts.append(a['bitrate'])
                            aud_lines.append(' '.join(parts))
                        audio_info = f"\n   🔊 Audio ({len(info.audio_streams)}): {' | '.join(aud_lines)}"
                    results.append(f"📄 {info.filename}\n   🎬 {info.video_codec} {info.width}x{info.height} | {info.filesize} | ⏱️ {info.duration or 'N/A'}{audio_info}{subs}")
            except:
                results.append(f"❌ {os.path.basename(f)}: Error")
        if results:
            dlg = QDialog(self)
            dlg.setWindowTitle("Analysis")
            dlg.resize(640, 480)
            dlg_layout = QVBoxLayout(dlg)
            text = QTextEdit()
            text.setReadOnly(True)
            text.setText('\n\n'.join(results))
            dlg_layout.addWidget(text)
            btn = QPushButton("Close")
            btn.clicked.connect(dlg.close)
            dlg_layout.addWidget(btn)
            dlg.exec()

    def _apply_preset(self, preset_name):
        import json
        try:
            preset_file = Path(__file__).parent.parent / 'presets' / 'default_presets.json'
            with open(preset_file) as f:
                presets = json.load(f)
            if preset_name in presets.get('presets', {}):
                p = presets['presets'][preset_name]
                if 'quality' in p:
                    self.quality = p['quality']
                    self.quality_slider.setValue(p['quality'])
                if 'encoder' in p:
                    self.encoder = p['encoder']
                    for display, enc in self.encoder_map.items():
                        if enc == p['encoder']:
                            self.encoder_combo.setCurrentText(display)
                            break
                if 'format' in p:
                    self._set_format(p['format'])
                if 'audio_encoder' in p:
                    self.audio_enc_combo.setCurrentText(p['audio_encoder'])
                if 'audio_bitrate' in p and p.get('audio_encoder', 'copy') != 'copy':
                    self.audio_bit_combo.setCurrentText(str(p['audio_bitrate']))
                self.status_label.setText(f"✅ {p.get('name', preset_name)} applied")
        except Exception as e:
            print(f"Preset error: {e}")

    def _browse_output(self):
        initial = self.last_folder or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", initial)
        if folder:
            self.output_dir_edit.setText(folder)

    def _set_default_folder(self):
        initial = self.default_folder or os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select default folder", initial)
        if folder:
            self.default_folder = folder
            self.config.set('defaults', 'default_folder', folder)
            self.config.save()
            QMessageBox.information(self, "Default Folder", f"Default folder set to:\n{folder}")

    def _clear_default_folder(self):
        self.default_folder = ''
        self.config.set('defaults', 'default_folder', '')
        self.config.save()
        QMessageBox.information(self, "Default Folder", "Default folder cleared")

    def _save_defaults(self):
        self.config.set('defaults', 'quality', self.quality)
        self.config.set('defaults', 'encoder', self.encoder)
        self.config.set('defaults', 'format', self.format)
        self.config.set('defaults', 'audio_encoder', self.audio_encoder)
        self.config.set('defaults', 'audio_bitrate', int(self.audio_bit_combo.currentText()))
        self.config.save()
        QMessageBox.information(self, "Settings", "Current settings saved as defaults!")

    def _reset_defaults(self):
        if QMessageBox.question(self, "Reset", "Reset all settings to defaults?") == QMessageBox.StandardButton.Yes:
            self.config.reset_to_defaults()
            self.config.load()
            self.quality = 27
            self.encoder = 'auto'
            self.format = 'mp4'
            self.quality_slider.setValue(27)
            self.mp4_radio.setChecked(True)
            self.audio_enc_combo.setCurrentText('copy')
            self.audio_bit_combo.setEnabled(False)
            QMessageBox.information(self, "Settings", "Settings reset to defaults!")

    def _start_conversion(self):
        if not self.files:
            QMessageBox.information(self, "Info", "No files to convert!\n\nAdd files first, then click CONVERT.")
            return
        if self.is_converting:
            return

        self.is_converting = True
        self.convert_action.setEnabled(False)
        self.pause_action.setEnabled(True)
        self.skip_action.setEnabled(True)
        self.cancel_action.setEnabled(True)
        self._paused = False
        self.pause_action.setText("⏸ Pause")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.files))
        self.progress_bar.setValue(0)
        self.file_progress_bar.setVisible(True)
        self.file_progress_bar.setValue(0)
        self.status_label.setText("Starting conversion...")

        resolved_encoder = self.encoder
        if resolved_encoder == 'auto' or resolved_encoder not in (
            e for e in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264',
                        'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']):
            resolved_encoder = self.encoder_manager.get_recommended_encoder()

        settings = ConversionSettings(
            encoder=resolved_encoder,
            quality=self.quality,
            audio_encoder=self.audio_encoder,
            audio_bitrate=int(self.audio_bit_combo.currentText()) if self.audio_encoder != 'copy' else None,
            audio_track_overrides=self.audio_track_overrides if self.audio_track_overrides else None,
            output_format=self.format,
            subtitle_mode=self.subtitle_mode,
            subtitle_burn=self.subtitle_burn,
            subtitle_lang_list=self.subtitle_lang_list,
            external_srt_files=[],
            external_srt_burn=self.external_srt_burn,
            external_srt_default=self.external_srt_default,
            metadata_preserve=self.metadata_preserve,
        )
        settings.metadata_preserve_flag = self.hb_manager.metadata_flag() if self.hb_manager.detect() else None

        output_base = None
        preserve_structure = True
        if self.output_custom_radio.isChecked() and self.output_dir_edit.text():
            output_base = self.output_dir_edit.text()
            preserve_structure = not self.flat_output_check.isChecked()

        self.worker = ConversionWorker(self.files, output_base, settings, self.encoder_manager,
                                       source_root=self.source_root if preserve_structure else None,
                                       file_subtitles=self.file_subtitles,
                                       handbrake_cmd=self.hb_manager.get_command() if self.hb_manager.detect() else None)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_started.connect(self._on_file_started)
        self.worker.file_finished.connect(self._on_file_finished)
        self.worker.all_finished.connect(self._on_all_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.command_ready.connect(self._on_command_ready)
        self.worker.metadata_log.connect(self._log)
        self.worker.start()

    def _cancel_conversion(self):
        if self.worker:
            self.worker.cancel()

    def _on_progress(self, prog: ConversionProgress):
        self.file_progress_bar.setValue(int(prog.percent))
        fmt = f"Current file: %p%"
        if prog.fps > 0:
            fmt += f" — {prog.fps:.1f} fps"
        self.file_progress_bar.setFormat(fmt)

    def _on_file_started(self, idx, total, filename):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(idx)
        self._current_file_index = idx
        self.status_label.setText(f"Processing ({idx+1}/{total}): {filename[:50]}...")
        self._log(f"Started: {filename}")

    def _on_file_finished(self, success, path):
        row = self._current_file_index
        if path.startswith("Skipped:"):
            status = "⏭ Skipped"
            if row < self.file_table.rowCount():
                self.file_table.setItem(row, 8, QTableWidgetItem(status))
            self._log(path)
            return
        status = "✅ Done" if success else "❌ Failed"
        if row < self.file_table.rowCount():
            item = QTableWidgetItem(status)
            if not success:
                item.setToolTip(self._file_errors.get(self.files[row], ''))
            self.file_table.setItem(row, 8, item)
        if success:
            self._log(f"Completed: {os.path.basename(path)}")
        else:
            error_msg = ''
            worker_converter = getattr(self.worker, '_converter', None)
            if worker_converter and hasattr(worker_converter, 'last_error'):
                error_msg = worker_converter.last_error or ''
            if error_msg:
                if row < len(self.files):
                    self._file_errors[self.files[row]] = error_msg
                self._log(f"Failed: {os.path.basename(path)} - {error_msg[:200]}")
                self.status_label.setText(f"❌ Failed: {error_msg[:100]}")
            else:
                self._log(f"Failed: {os.path.basename(path)}")

    def _on_error(self, error_msg):
        self.status_label.setText(f"❌ Error: {error_msg[:100]}")
        self._log(f"Error: {error_msg[:200]}")

    def _on_command_ready(self, cmd):
        self._log(f"Command: {cmd[:300]}")

    def _on_all_finished(self, success, failed, skipped):
        self.is_converting = False
        self.convert_action.setEnabled(True)
        self.pause_action.setEnabled(False)
        self.skip_action.setEnabled(False)
        self.cancel_action.setEnabled(False)
        self.pause_action.setText("⏸ Pause")
        self._paused = False
        self.progress_bar.setVisible(False)
        self.file_progress_bar.setVisible(False)
        self.file_progress_bar.setFormat("Current file: %p%")
        if skipped > 0:
            self.status_label.setText(f"⏹ Stopped: {success} done, {skipped} skipped, {failed} failed")
            self._log(f"Stopped: {success} ok, {skipped} skipped, {failed} failed")
        else:
            self.status_label.setText(f"✅ Complete: {success} ok, {failed} failed")
            self._log(f"Complete: {success} ok, {failed} failed")
        self._update_status_bar()

    def _add_external_subtitles(self):
        selected = self.file_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Info",
                "Select a video file first, then add subtitles to link them.")
            return
        row = selected[0].row()
        if not (0 <= row < len(self.files)):
            return
        target_file = self.files[row]

        initial = self.last_folder or os.path.expanduser('~')
        files, _ = QFileDialog.getOpenFileNames(self, "Select subtitle files", initial,
            "Subtitle Files (*.srt *.ass *.ssa *.sub *.vtt)")
        if files:
            lang, ok = QInputDialog.getItem(self, "Subtitle Language",
                "Select language for these subtitles:",
                ['eng', 'ara', 'fre', 'spa', 'ger', 'ita', 'jpn', 'kor', 'chi', 'hin', 'tur', 'por', 'rus', 'und'],
                0, False)
            if not ok:
                lang = 'eng'
            if target_file not in self.file_subtitles:
                self.file_subtitles[target_file] = []
            for f in files:
                entry = (f, lang)
                if entry not in self.file_subtitles[target_file]:
                    self.file_subtitles[target_file].append(entry)
            self.last_folder = os.path.dirname(files[0])
            self._refresh_subtitle_list()

    def _remove_selected_subtitle(self):
        selected_file_rows = self.file_table.selectionModel().selectedRows()
        if not selected_file_rows:
            return
        row = selected_file_rows[0].row()
        if not (0 <= row < len(self.files)):
            return
        target_file = self.files[row]

        selected_items = self.ext_sub_list.selectedItems()
        for item in selected_items:
            idx = self.ext_sub_list.row(item)
            subs = self.file_subtitles.get(target_file, [])
            if 0 <= idx < len(subs):
                subs.pop(idx)
                self.file_subtitles[target_file] = subs
        self._refresh_subtitle_list()

    def _clear_external_subtitles(self):
        selected_file_rows = self.file_table.selectionModel().selectedRows()
        if not selected_file_rows:
            return
        row = selected_file_rows[0].row()
        if not (0 <= row < len(self.files)):
            return
        target_file = self.files[row]
        self.file_subtitles[target_file] = []
        self._refresh_subtitle_list()

    def _add_selected_to_queue(self):
        selected = self.file_table.selectionModel().selectedRows()
        if not selected:
            if self.files:
                for i in range(len(self.files)):
                    self._add_file_to_queue(i)
                QMessageBox.information(self, "Queue", f"Added all {len(self.files)} file(s) to queue")
            else:
                QMessageBox.information(self, "Info", "No files to add to queue")
            return
        for idx in selected:
            self._add_file_to_queue(idx.row())
        QMessageBox.information(self, "Queue", f"Added {len(selected)} file(s) to queue")

    def _add_file_to_queue(self, row_idx):
        if 0 <= row_idx < len(self.files):
            input_path = self.files[row_idx]
            output_path = generate_output_path(input_path, format=self.format, conflict_mode='rename')
            job = Job(
                id=f"job_{os.path.basename(input_path)}_{len(self.queue_manager.jobs)}",
                input_path=input_path,
                output_path=output_path,
                settings={
                    'encoder': self.encoder,
                    'quality': self.quality,
                    'audio_encoder': self.audio_encoder,
                    'audio_bitrate': int(self.audio_bit_combo.currentText()) if self.audio_encoder != 'copy' else None,
                    'audio_track_overrides': self.audio_track_overrides if self.audio_track_overrides else None,
                    'output_format': self.format
                }
            )
            self.queue_manager.add_job(job)
        self._refresh_queue_table()
        self._update_status_bar()

    def _remove_selected_from_queue(self):
        selected = self.queue_table.selectionModel().selectedRows()
        if not selected:
            return
        indices = sorted([r.row() for r in selected], reverse=True)
        for idx in indices:
            if 0 <= idx < len(self.queue_manager.jobs):
                self.queue_manager.jobs.pop(idx)
        self.queue_manager._save_queue()
        self._refresh_queue_table()
        self._update_status_bar()

    def _clear_queue(self):
        self.queue_manager.clear_all()
        self._refresh_queue_table()
        self._update_status_bar()

    def _start_queue(self):
        if not self.queue_manager.jobs:
            QMessageBox.information(self, "Info", "Queue is empty!\n\nSelect files and click 'Add to Queue' first.")
            return
        pending = [j for j in self.queue_manager.jobs if j.state == JobState.PENDING.value]
        if not pending:
            QMessageBox.information(self, "Info", "No pending jobs in queue!\n\nAll jobs are already completed or failed.")
            return
        self.files = [j.input_path for j in pending]
        self._refresh_file_table()
        self._start_conversion()

    def _refresh_queue_table(self):
        jobs = self.queue_manager.jobs
        self.queue_table.setRowCount(len(jobs))
        for i, job in enumerate(jobs):
            self.queue_table.setItem(i, 0, QTableWidgetItem(os.path.basename(job.input_path)))
            self.queue_table.setItem(i, 1, QTableWidgetItem(os.path.basename(job.output_path)))
            self.queue_table.setItem(i, 2, QTableWidgetItem(f"{job.progress:.0f}%"))
            self.queue_table.setItem(i, 3, QTableWidgetItem(job.state))

    def _show_help_browser(self):
        lang = getattr(self.i18n, '_requested_lang', 'en') if hasattr(self, 'i18n') else 'en'
        dlg = HelpBrowser(self, lang=lang)
        dlg.exec()

    def _set_language(self, lang):
        if hasattr(self, 'i18n') and self.i18n:
            self.i18n.set_language(lang)
        self.config.set('general', 'language', lang)
        self.config.save()
        QMessageBox.information(self, "Language",
            "Language preference saved.\n"
            "Note: The interface is primarily English-only.\n"
            "Only the Help Browser (F1) uses the selected language."
            if lang == 'en' else
            "تم حفظ تفضيل اللغة.\n"
            "ملاحظة: الواجهة أساساً باللغة الإنجليزية.\n"
            "متصفح المساعدة (F1) فقط يستخدم اللغة المحددة.")

    def _toggle_update_check(self, checked):
        self.config.set('general', 'check_updates', checked)
        self.config.save()
        self.act_update_check.setText(f"{'✅' if checked else '☐'} Check for Updates on Startup")

    def _ensure_handbrake_cli(self):
        """Detect HandBrakeCLI; offer to install via apt if missing."""
        if self.hb_manager.detect():
            ver = self.hb_manager.version_str
            self._log(f"HandBrakeCLI {ver or 'unknown'} detected")
            # Auto-update if setting is enabled and a newer apt version exists
            auto_update = self.config.get('general', 'auto_update_handbrake', True)
            if auto_update:
                avail, latest = self.hb_manager.check_for_update()
                if avail:
                    self._log(f"HandBrakeCLI {ver} -> {latest} available — updating…")
                    ok, msg = self.hb_manager.update()
                    if ok:
                        self._log(f"HandBrakeCLI updated to {self.hb_manager.version_str}")
                    else:
                        self._log(f"HandBrakeCLI update failed: {msg}")
            return

        # Not found — offer to install via apt
        self._log("HandBrakeCLI not found — install required")
        if not shutil.which("apt"):
            QMessageBox.critical(
                self, "HandBrakeCLI Required",
                "HandBrakeCLI is required but not installed.\n\n"
                "Please install it manually:\n"
                "  sudo apt install handbrake-cli")
            return

        reply = QMessageBox.question(
            self, "Install HandBrakeCLI?",
            "HandBrakeCLI is not installed on your system.\n\n"
            "Would you like to install it now via apt?\n"
            "(Requires administrator password via pkexec.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._log("Installing HandBrakeCLI via apt …")
        ok, msg = self.hb_manager.install()
        if ok:
            self._log(f"HandBrakeCLI {self.hb_manager.version_str} installed")
            QMessageBox.information(self, "Installed", msg)
        else:
            self._log(f"HandBrakeCLI install failed: {msg}")
            QMessageBox.warning(self, "Install Failed", msg)

    def _ensure_ffmpeg(self):
        """Detect ffmpeg; install via apt if missing; auto-update if newer available."""
        ffmpeg_found = shutil.which("ffmpeg")
        if ffmpeg_found:
            self._log("ffmpeg detected")
            auto_update = self.config.get('general', 'auto_update_handbrake', True)
            if auto_update:
                # Get current installed version
                current_ver = self._get_ffmpeg_version()
                avail, latest = HandBrakeManager.check_apt_package_update("ffmpeg", current_ver)
                if avail:
                    self._log(f"ffmpeg {latest} available — updating…")
                    ok, msg = HandBrakeManager.update_apt_package("ffmpeg", "ffmpeg")
                    if ok:
                        self._log("ffmpeg updated")
                    else:
                        self._log(f"ffmpeg update failed: {msg}")
            return

        self._log("ffmpeg not found — install required")
        if not shutil.which("apt"):
            QMessageBox.critical(
                self, "ffmpeg Required",
                "ffmpeg is required for metadata preservation but not installed.\n\n"
                "Please install it manually:\n  sudo apt install ffmpeg")
            return

        reply = QMessageBox.question(
            self, "Install ffmpeg?",
            "ffmpeg is not installed on your system.\n\n"
            "It is needed for preserving video metadata (tags, title, etc.).\n"
            "Would you like to install it now via apt?\n"
            "(Requires administrator password via pkexec.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._log("Installing ffmpeg via apt …")
        ok, msg = HandBrakeManager.install_apt_package("ffmpeg", "ffmpeg")
        if ok:
            self._log("ffmpeg installed")
            QMessageBox.information(self, "Installed", msg)
        else:
            self._log(f"ffmpeg install failed: {msg}")
            QMessageBox.warning(self, "Install Failed", msg)

    def _ensure_ffprobe(self):
        """Verify ffprobe is available (same apt package as ffmpeg)."""
        if shutil.which("ffprobe"):
            self._log("ffprobe detected")
        else:
            self._log("ffprobe not found — metadata probing disabled")

    @staticmethod
    def _get_ffmpeg_version() -> tuple[int, int, int] | None:
        """Return parsed (major, minor, patch) from ffmpeg -version, or None."""
        import subprocess, re
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
            m = re.search(r"ffmpeg version (\d+)\.(\d+)\.(\d+)", r.stdout)
            if m:
                return (int(m[1]), int(m[2]), int(m[3]))
        except Exception:
            pass
        return None

    def _check_for_updates_startup(self):
        enabled = self.config.get('general', 'check_updates', True)
        if not enabled:
            return
        self._update_worker = UpdateCheckWorker(__version__)
        self._update_worker.update_found.connect(self._on_update_check_result)
        self._update_worker.start()
        return

    def _check_for_updates_now(self):
        self._update_worker = UpdateCheckWorker(__version__)
        self._update_worker.update_found.connect(self._on_update_check_result)
        self.status_label.setText("🔍 Checking for updates...")
        self._update_worker.start()

    def _on_update_check_result(self, info: UpdateInfo):
        if info.available:
            self._show_update_dialog(info)
        elif info.error:
            self.status_label.setText(f"ℹ️ Update check failed: {info.error}")
        else:
            self.status_label.setText(f"✅ {APP_NAME} v{info.current_version} is up to date")

    def _show_update_dialog(self, info: UpdateInfo):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Update Available")
        dlg.setText(
            f"<h3>🚀 {APP_NAME} v{info.latest_version} Available</h3>"
            f"<p>You have <b>v{info.current_version}</b>. "
            f"The latest is <b>v{info.latest_version}</b>.</p>"
            f"<hr>"
            f"<p><b>Release notes:</b><br>{info.release_notes[:300]}</p>"
            f"<hr>"
            f"<p>Click Download to open the release page in your browser.</p>"
        )
        dlg.setTextFormat(Qt.TextFormat.RichText)
        download_btn = dlg.addButton("⬇️ Download Update", QMessageBox.ButtonRole.AcceptRole)
        dlg.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        dlg.exec()
        if dlg.clickedButton() == download_btn:
            import webbrowser
            webbrowser.open(info.release_url)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Keyboard Shortcuts",
            "<h3>MoTekLab Video Encoder Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>F1</b></td><td>Open Help Browser</td></tr>"
            "<tr><td><b>Shift+F1</b></td><td>What's This? (click any control for help)</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Add video files</td></tr>"
            "<tr><td><b>Ctrl+Shift+O</b></td><td>Add video folder</td></tr>"
            "<tr><td><b>Delete/Backspace</b></td><td>Remove selected file/subtitle/queue entry</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Quit application</td></tr>"
            "<tr><td><b>Escape</b></td><td>Cancel current operation</td></tr>"
            "</table>"
            "<br>Tip: Hover over any button or setting for a tooltip description.")

    def _show_about(self):
        hw = self.encoder_manager.get_hardware_name()
        recommended = self.encoder_manager.get_recommended_encoder()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"About {APP_NAME}")
        dlg.setFixedSize(500, 450)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        banner_path = _asset_path("vconv-about-banner.png")
        if banner_path.exists():
            banner = QLabel()
            pixmap = QPixmap(str(banner_path))
            banner.setPixmap(pixmap.scaled(500, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(banner)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        info_layout.setContentsMargins(20, 15, 20, 15)

        title = QLabel(f"<h2>{APP_DISPLAY_NAME}</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(title)

        info_layout.addWidget(QLabel(f"<b>Version:</b> {__version__} &nbsp;|&nbsp; <b>License:</b> GPLv3"))
        info_layout.addWidget(QLabel(f"🖥️ <b>Hardware:</b> {hw}"))
        info_layout.addWidget(QLabel(f"⚡ <b>Recommended:</b> {recommended}"))
        info_layout.addWidget(QLabel(
            'Powered by <a href="https://handbrake.fr" style="color: #00B4D8;">HandBrakeCLI</a>'
            ' &nbsp;|&nbsp; '
            '<a href="https://ffmpeg.org" style="color: #00B4D8;">FFmpeg</a>'
            ' &nbsp;|&nbsp; '
            '<a href="https://ffmpeg.org/ffprobe.html" style="color: #00B4D8;">FFprobe</a>'
            ' &nbsp;|&nbsp; Built with <a href="https://www.qt.io/qt-for-python" style="color: #00B4D8;">PyQt6</a>'
        ))

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        info_layout.addWidget(sep)

        website = QLabel('<a href="https://moteklab.com" style="color: #00B4D8;">🌐 moteklab.com</a>')
        website.setOpenExternalLinks(True)
        website.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(website)

        info_layout.addWidget(QLabel("<small>Press <b>F1</b> for help &nbsp;|&nbsp; <b>Shift+F1</b> for context help</small>"))
        info_layout.addWidget(QLabel("<small>© 2026 MoTekLab</small>"))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.close)
        btn_layout.addWidget(close_btn)
        info_layout.addLayout(btn_layout)

        layout.addLayout(info_layout)
        dlg.exec()


def launch(config: Config, i18n: I18n, args=None, encoder_manager=None):
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("vconv")

    # Register icon theme paths for proper icon lookup
    from PyQt6.QtCore import QStandardPaths
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    icon_dirs = [
        os.path.join(data_dir, "icons"),
        "/usr/local/share/icons",
        "/usr/share/icons",
    ]
    current_paths = QIcon.themeSearchPaths()
    merged = list(current_paths)
    for d in icon_dirs:
        if d not in merged and os.path.isdir(d):
            merged.insert(0, d)
    QIcon.setThemeSearchPaths(merged)
    QIcon.setFallbackThemeName("hicolor")

    # XDG auto-install for start menu/taskbar integration
    project_root = Path(__file__).parent.parent
    ensure_xdg_integration(project_root)

    # Application window icon (scaled to avoid 5MB 2048x2048 QPixmap)
    app_icon = QIcon()
    icon_path = _asset_path("vconv-icon-256.png")
    if icon_path.exists():
        pixmap = QPixmap(str(icon_path))
        if not pixmap.isNull() and (pixmap.width() > 256 or pixmap.height() > 256):
            pixmap = pixmap.scaled(256, 256)
        app_icon = QIcon(pixmap)
    if app_icon.isNull():
        app_icon = QIcon.fromTheme("vconv")
    if app_icon.isNull():
        app_icon = QIcon.fromTheme("video-display")
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    window = MainWindow(config, i18n, args, encoder_manager)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    config = Config()
    config.load()
    i18n = I18n('en')
    launch(config, i18n)