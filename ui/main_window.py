"""
vconv Main Window UI v9.1.0

PyQt6-based interface for video conversion.
Features: Queue management, real progress, hardware acceleration, subtitle/audio management.
"""

import os
import sys
import threading
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
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QFont, QKeySequence

from core.encoder import EncoderManager
from core.converter import Converter, ConversionSettings, ConversionProgress
from core.validator import FileValidator, generate_output_path
from core.analyzer import MediaAnalyzer
from core.queue import QueueManager, Job, JobState
from ui.help_browser import HelpBrowser
from utils.config import Config
from utils.updater import check_for_updates, UpdateInfo
from utils.i18n import I18n

VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts', '.vob'}


class ConversionWorker(QThread):
    """Worker thread for file conversion with proper Qt threading."""
    progress = pyqtSignal(object)
    file_started = pyqtSignal(int, int, str)
    file_finished = pyqtSignal(bool, str)
    all_finished = pyqtSignal(int, int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self, files, output_base, settings, encoder_manager, source_root=None, preserve_structure=True):
        super().__init__()
        self.files = files
        self.output_base = output_base
        self.settings = settings
        self.encoder_manager = encoder_manager
        self.preserve_structure = preserve_structure
        self.source_root = source_root
        self._cancel = False
        self._converter = Converter(encoder_manager)

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

            self.file_started.emit(idx, total, os.path.basename(input_file))
            output_file = self._resolve_output(input_file)

            def progress_cb(prog):
                self.progress.emit(prog)

            try:
                result = self._converter.convert(input_file, output_file, self.settings, progress_callback=progress_cb)
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


class MainWindow(QMainWindow):
    """Main application window using PyQt6."""

    def __init__(self, config: Config, i18n: I18n, args=None, encoder_manager=None):
        super().__init__()
        self.config = config
        self.i18n = i18n
        self.args = args
        self.encoder_manager = encoder_manager or EncoderManager()
        self.analyzer = MediaAnalyzer()
        self.validator = FileValidator()
        self.queue_manager = QueueManager()

        self.files = []
        self.source_root = None
        self.is_converting = False
        self.worker = None

        self.quality = self.config.get('defaults', 'quality', 27)
        self.encoder = self.config.get('defaults', 'encoder', 'auto')
        self.format = self.config.get('defaults', 'format', 'mp4')
        self.output_dir = self.config.get('defaults', 'output_dir', 'source')
        self.last_folder = self.config.get('defaults', 'last_folder', '')
        self.default_folder = self.config.get('defaults', 'default_folder', '')
        self.audio_encoder = 'copy'
        self.audio_bitrate = 128
        self.subtitle_mode = 'copy'
        self.subtitle_burn = False
        self.subtitle_lang_list = 'eng,ara'
        self.external_srt_files = []
        self.external_srt_burn = False
        self.external_srt_default = True

        self.encoder_map = self._build_encoder_map()
        self._setup_ui()
        self._load_window_geometry()
        self._refresh_queue_table()
        self._check_for_updates_startup()

    def _build_encoder_map(self):
        available = self.encoder_manager.get_available_encoders()
        recommended = self.encoder_manager.get_recommended_encoder()
        encoder_map = {}
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available:
                info = self.encoder_manager.get_encoder_info(enc)
                display = f"{info['name']}"
                if enc == recommended:
                    display = f"✅ {display} (Recommended)"
                encoder_map[display] = enc
        return encoder_map

    def _setup_ui(self):
        self.setWindowTitle("vconv - Video Converter v9.1.0")
        self.setMinimumSize(1100, 700)
        self.resize(1250, 800)

        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

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
        act_update.setToolTip("Check GitHub for a newer version of vconv")
        help_menu.addAction(act_update)

        help_menu.addSeparator()
        help_menu.addAction("&About vconv", self._show_about)

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
        main_layout.addWidget(splitter)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([320, 930])

    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        layout.setContentsMargins(2, 2, 2, 2)

        encoder_group = QGroupBox("🎬 Encoder")
        enc_layout = QVBoxLayout(encoder_group)
        self.encoder_combo = QComboBox()
        for display in self.encoder_map.keys():
            self.encoder_combo.addItem(display)
        self.encoder_combo.currentTextChanged.connect(self._on_encoder_changed)
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
        hw_label = QLabel(f"🖥️ {self.encoder_manager.get_hardware_name()}")
        hw_label.setStyleSheet("color: #00B4D8; font-size: 11px;")
        enc_layout.addWidget(hw_label)
        layout.addWidget(encoder_group)

        quality_group = QGroupBox("📊 Quality (RF)")
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

        preset_group = QGroupBox("⚡ Preset")
        preset_layout = QVBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(['fast', 'balanced', 'high_quality', 'archive', 'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'tv_show'])
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

        output_group = QGroupBox("📁 Output")
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

        format_group = QGroupBox("💿 Format")
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

        audio_group = QGroupBox("🔊 Audio")
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
        layout.addWidget(audio_group)

        sub_group = QGroupBox("📝 Subtitles")
        sub_layout = QVBoxLayout(sub_group)
        sub_layout.setSpacing(6)

        sub_mode_layout = QHBoxLayout()
        sub_mode_layout.addWidget(QLabel("Embedded:"))
        self.sub_combo = QComboBox()
        self.sub_combo.addItems(['copy', 'all', 'none'])
        self.sub_combo.setCurrentText('copy')
        self.sub_combo.setToolTip("How to handle embedded subtitles from the source file")
        self.sub_combo.setWhatsThis(
            "<b>Embedded Subtitle Mode</b><br>"
            "<b>copy</b> — Keep source subtitles matching the selected languages<br>"
            "<b>all</b> — Keep all embedded subtitle tracks regardless of language<br>"
            "<b>none</b> — Remove all subtitles from output"
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

        layout.addStretch()
        return panel

    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        files_group = QGroupBox(f"📂 Files to Convert ({len(self.files)})")
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(4, 6, 4, 4)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["File", "Size", "Duration", "Status"])
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setMinimumHeight(200)
        self.file_table.setToolTip("Added video files. Select rows and use buttons below to manage.")
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

        queue_group = QGroupBox("📋 Conversion Queue")
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

        progress_group = QGroupBox("⏱️ Progress")
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
        return panel

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _update_status_bar(self):
        hw = self.encoder_manager.get_hardware_name()
        self.status_bar.showMessage(f"vconv v9.1.0 | {hw} | Files: {len(self.files)} | Queue: {len(self.queue_manager.jobs)} | Quality: RF {self.quality}")

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
        self.config.save()
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
            self._refresh_file_table()
            self._update_status_bar()

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
            self.source_root = folder
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
                self._refresh_file_table()
                self._update_status_bar()
                QMessageBox.information(self, "Files Added", f"Added {len(videos)} video files!")
            else:
                QMessageBox.information(self, "Info", "No video files found")

    def _clear_files(self):
        self.files.clear()
        self.source_root = None
        self._refresh_file_table()
        self._update_status_bar()

    def _remove_selected(self):
        selected = self.file_table.selectionModel().selectedRows()
        if selected:
            indices = sorted([r.row() for r in selected], reverse=True)
            for idx in indices:
                if 0 <= idx < len(self.files):
                    self.files.pop(idx)
            self._refresh_file_table()
            self._update_status_bar()

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
            self.file_table.setItem(i, 2, QTableWidgetItem(""))
            self.file_table.setItem(i, 3, QTableWidgetItem("Pending"))

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
                    results.append(f"📄 {info.filename}\n   🎬 {info.video_codec} {info.width}x{info.height} | {info.filesize} | ⏱️ {info.duration or 'N/A'}{subs}")
            except:
                results.append(f"❌ {os.path.basename(f)}: Error")
        if results:
            dlg = QDialog(self)
            dlg.setWindowTitle("Analysis")
            dlg.resize(600, 400)
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
                preset = presets['presets'][preset_name]
                if 'quality' in preset:
                    self.quality = preset['quality']
                    self.quality_slider.setValue(preset['quality'])
                self.status_label.setText(f"✅ {preset.get('name', preset_name)} applied")
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
        self.cancel_action.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.files))
        self.progress_bar.setValue(0)
        self.file_progress_bar.setVisible(True)
        self.file_progress_bar.setValue(0)
        self.status_label.setText("Starting conversion...")

        encoder = self.encoder
        if 'Recommended' in self.encoder_combo.currentText():
            encoder = self.encoder_manager.get_recommended_encoder()

        settings = ConversionSettings(
            encoder=encoder,
            quality=self.quality,
            audio_encoder=self.audio_encoder,
            audio_bitrate=int(self.audio_bit_combo.currentText()) if self.audio_encoder != 'copy' else None,
            output_format=self.format,
            subtitle_mode=self.subtitle_mode,
            subtitle_burn=self.subtitle_burn,
            subtitle_lang_list=self.subtitle_lang_list,
            external_srt_files=self.external_srt_files,
            external_srt_burn=self.external_srt_burn,
            external_srt_default=self.external_srt_default
        )

        output_base = None
        preserve_structure = True
        if self.output_custom_radio.isChecked() and self.output_dir_edit.text():
            output_base = self.output_dir_edit.text()
            preserve_structure = not self.flat_output_check.isChecked()

        self.worker = ConversionWorker(self.files, output_base, settings, self.encoder_manager,
                                       source_root=self.source_root if preserve_structure else None)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_started.connect(self._on_file_started)
        self.worker.file_finished.connect(self._on_file_finished)
        self.worker.all_finished.connect(self._on_all_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _cancel_conversion(self):
        if self.worker:
            self.worker.cancel()

    def _on_progress(self, prog: ConversionProgress):
        self.file_progress_bar.setValue(int(prog.percent))

    def _on_file_started(self, idx, total, filename):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(idx)
        self.status_label.setText(f"Processing ({idx+1}/{total}): {filename[:50]}...")

    def _on_file_finished(self, success, path):
        status = "✅ Done" if success else "❌ Failed"
        row = self.progress_bar.value()
        if row < self.file_table.rowCount():
            self.file_table.setItem(row, 3, QTableWidgetItem(status))

    def _on_error(self, error_msg):
        self.status_label.setText(f"❌ Error: {error_msg[:100]}")

    def _on_all_finished(self, success, failed, skipped):
        self.is_converting = False
        self.convert_action.setEnabled(True)
        self.cancel_action.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.file_progress_bar.setVisible(False)
        if skipped > 0:
            self.status_label.setText(f"⏹ Stopped: {success} done, {skipped} skipped, {failed} failed")
        else:
            self.status_label.setText(f"✅ Complete: {success} ok, {failed} failed")
        self._update_status_bar()

    def _add_external_subtitles(self):
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
            for f in files:
                entry = (f, lang)
                if entry not in self.external_srt_files:
                    self.external_srt_files.append(entry)
                    self.ext_sub_list.addItem(f"{os.path.basename(f)} [{lang}]")
            self.last_folder = os.path.dirname(files[0])

    def _remove_selected_subtitle(self):
        selected = self.ext_sub_list.selectedItems()
        for item in selected:
            idx = self.ext_sub_list.row(item)
            if 0 <= idx < len(self.external_srt_files):
                self.external_srt_files.pop(idx)
            self.ext_sub_list.takeItem(idx)

    def _clear_external_subtitles(self):
        self.external_srt_files.clear()
        self.ext_sub_list.clear()

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
        lang = getattr(self.i18n, 'lang', 'en') if hasattr(self, 'i18n') else 'en'
        dlg = HelpBrowser(self, lang=lang)
        dlg.exec()

    def _set_language(self, lang):
        if hasattr(self, 'i18n') and self.i18n:
            self.i18n.set_language(lang)
        self.config.set('general', 'language', lang)
        self.config.save()
        QMessageBox.information(self, "Language",
            "Language changed. Reopen the app for full effect.\n"
            "Help browser will use the new language immediately."
            if lang == 'en' else
            "تم تغيير اللغة. أعد فتح التطبيق للتأثير الكامل.\n"
            "متصفح المساعدة سيستخدم اللغة الجديدة فوراً.")

    def _check_for_updates_startup(self):
        enabled = self.config.get('general', 'check_updates', True)
        if not enabled:
            return
        worker = UpdateCheckWorker("9.1.0")
        worker.update_found.connect(self._on_update_check_result)
        worker.start()

    def _check_for_updates_now(self):
        worker = UpdateCheckWorker("9.1.0")
        worker.update_found.connect(self._on_update_check_result)
        self.status_label.setText("🔍 Checking for updates...")
        worker.start()

    def _on_update_check_result(self, info: UpdateInfo):
        if info.available:
            self._show_update_dialog(info)
        elif info.error:
            self.status_label.setText(f"ℹ️ Update check failed: {info.error}")
        else:
            self.status_label.setText(f"✅ vconv v{info.current_version} is up to date")

    def _show_update_dialog(self, info: UpdateInfo):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Update Available")
        dlg.setText(
            f"<h3>🚀 vconv v{info.latest_version} Available</h3>"
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
            "<h3>vconv Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>F1</b></td><td>Open Help Browser</td></tr>"
            "<tr><td><b>Shift+F1</b></td><td>What's This? (click any control for help)</td></tr>"
            "<tr><td><b>Ctrl+O</b></td><td>Add video files</td></tr>"
            "<tr><td><b>Ctrl+Shift+O</b></td><td>Add video folder</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Quit application</td></tr>"
            "<tr><td><b>Escape</b></td><td>Cancel current operation</td></tr>"
            "</table>"
            "<br>Tip: Hover over any button or setting for a tooltip description.")

    def _show_about(self):
        hw = self.encoder_manager.get_hardware_name()
        recommended = self.encoder_manager.get_recommended_encoder()
        QMessageBox.information(self, "About vconv",
            f"<h3>vconv - Video Converter</h3>"
            f"<p>Version: 9.1.0<br>License: GPLv3</p>"
            f"<p>🖥️ <b>Hardware:</b> {hw}<br>"
            f"   <b>Recommended:</b> {recommended}</p>"
            f"<p>Powered by HandBrakeCLI<br>"
            f"Built with Python & PyQt6</p>"
            f"<hr>"
            f"<p><b>🌐 <a href='https://moteklab.com'>moteklab.com</a></b></p>"
            f"<hr>"
            f"<p>Press <b>F1</b> for the full User Guide<br>"
            f"Press <b>Shift+F1</b> then click any control for context help</p>"
            f"<p><small>© 2026 MoTekLab</small></p>")


def launch(config: Config, i18n: I18n, args=None, encoder_manager=None):
    app = QApplication(sys.argv)
    app.setApplicationName("vconv")
    app.setApplicationVersion("9.1.0")
    window = MainWindow(config, i18n, args, encoder_manager)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    config = Config()
    config.load()
    i18n = I18n('en')
    launch(config, i18n)