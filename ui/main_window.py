"""
vconv Main Window UI v8.2.0

PySimpleGUI-based interface for video conversion.
"""

import PySimpleGUI as sg
import os
import threading
import time
from pathlib import Path

from core.encoder import EncoderManager
from core.converter import Converter, ConversionSettings
from core.validator import generate_output_path
from core.analyzer import MediaAnalyzer
from utils.config import Config
from utils.i18n import I18n


VIDEO_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts', '.vob']

COMMON_FOLDERS = {
    'Documents': os.path.expanduser('~/Documents'),
    'Downloads': os.path.expanduser('~/Downloads'),
    'Videos': os.path.expanduser('~/Videos'),
    'Movies': os.path.expanduser('~/Movies'),
    'Desktop': os.path.expanduser('~/Desktop')
}


class MainWindow:
    """Main application window."""

    def __init__(self, config: Config, i18n: I18n, args=None):
        self.config = config
        self.i18n = i18n
        self.args = args

        self.encoder_manager = EncoderManager()
        self.converter = Converter(self.encoder_manager)
        self.analyzer = MediaAnalyzer()

        self.files = []
        self.is_converting = False
        self.cancel_requested = False
        self.stop_all = False
        self.conversion_thread = None

        self.quality = self.config.get('defaults', 'quality', 27)
        self.encoder = self.config.get('defaults', 'encoder', 'auto')
        self.format = self.config.get('defaults', 'format', 'mp4')
        self.output_dir = self.config.get('defaults', 'output_dir', 'source')
        self.last_folder = self.config.get('defaults', 'last_folder', '')
        self.default_folder = self.config.get('defaults', 'default_folder', '')
        self.audio_encoder = 'copy'
        self.audio_bitrate = 128

        # Load window position
        self.window_x = self.config.get('ui', 'window_x', None)
        self.window_y = self.config.get('ui', 'window_y', None)

        self.encoder_map = self._build_encoder_map()
        self._setup_theme()

    def _build_encoder_map(self):
        available_encoders = self.encoder_manager.get_available_encoders()
        encoder_map = {}
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available_encoders:
                info = self.encoder_manager.get_encoder_info(enc)
                display_name = f"{info['name']}"
                if enc == self.encoder_manager.get_recommended_encoder():
                    display_name = f"✅ {display_name} (Recommended)"
                encoder_map[display_name] = enc
        return encoder_map

    def _setup_theme(self):
        sg.theme('DarkBlue13')

    def run(self):
        location = None
        if self.window_x is not None and self.window_y is not None:
            location = (self.window_x, self.window_y)

        layout = self._build_layout()

        window = sg.Window(
            'vconv - Video Converter v8.2.0',
            layout,
            size=(1000, 700),
            location=location,
            resizable=True,
            finalize=True,
            enable_close_attempted_event=True
        )

        window.bind('<Escape>', '-CANCEL-')
        window['-AUDIO_BIT-'].update(disabled=True)
        window['-AUDIO_CH-'].update(disabled=True)

        while True:
            event, values = window.read(timeout=200)

            if event in (sg.WINDOW_CLOSED, sg.WIN_CLOSED, 'Exit', '-WIN_CLOSE-'):
                self._save_window_position(window)
                if self.is_converting:
                    self.cancel_requested = True
                    self.stop_all = True
                    time.sleep(0.5)
                break

            if event == '-WINDOW_MOVE-':
                try:
                    loc = window.current_location()
                    self.window_x = loc[0]
                    self.window_y = loc[1]
                except:
                    pass

            if event == '-PROGRESS_UPDATE-':
                data = values.get('-PROGRESS_UPDATE-', {})
                if 'status' in data:
                    window['-STATUS-'].update(data['status'])
                if 'progress' in data:
                    window['-PROGRESS-'].update(data['progress'])

            if event == '-CONVERSION_DONE-':
                self.is_converting = False
                window['-CONVERT-'].update(disabled=False)
                window['-CANCEL-'].update(disabled=True)
                window['-STOP_ALL-'].update(disabled=True)
                window['-PROGRESS-'].update(visible=False)
                result = values.get('-CONVERSION_DONE-', {})
                if self.stop_all:
                    window['-STATUS-'].update(f"⏹️ Stopped: {result.get('success', 0)} done, {result.get('skipped', 0)} skipped, {result.get('failed', 0)} failed", text_color='#F39C12')
                elif self.cancel_requested:
                    window['-STATUS-'].update(f"⏭️ {result.get('success', 0)} done, {result.get('skipped', 0)} skipped, {result.get('failed', 0)} failed", text_color='#2ECC71')
                else:
                    window['-STATUS-'].update(f"✅ Complete: {result.get('success', 0)} ok, {result.get('failed', 0)} failed", text_color='#2ECC71')

            if event in ('Add Files', '-ADD_FILES-'):
                self._add_files(window)
            if event in ('Add Folder', '-ADD_FOLDER-'):
                self._add_folder(window)
            if event == '-CLEAR_FILES-':
                self.files = []
                window['-FILE_LIST-'].update(values=[])
                self._update_status(window)
            if event == '-REMOVE_SELECTED-':
                self._remove_selected(window, values)
            if event == '-CHECK_FILES-':
                self._check_files(window)
            if event == '-CONVERT-':
                if not self.files:
                    sg.popup_ok('No files to convert!', title='Info', location=self._get_popup_loc(window))
                    continue
                self._start_conversion(window, values)
            if event == '-CANCEL-':
                if self.is_converting:
                    self.cancel_requested = True
            if event == '-STOP_ALL-':
                if self.is_converting:
                    self.stop_all = True
                    self.cancel_requested = True
            if event in ('-ANALYZE-', '📖 User Guide'):
                self._analyze_files(window)
            if event == '⌨️ Keyboard Shortcuts':
                self._show_shortcuts(window)
            if event == 'About vconv':
                self._show_about(window)
            if event == '-ENCODER-':
                self.encoder = values['-ENCODER-']
                if 'Recommended' in self.encoder:
                    self.encoder = self.encoder_manager.get_recommended_encoder()
            if event == '-QUALITY-':
                self.quality = int(values['-QUALITY-'])
            if event == '-PRESET-':
                self._apply_preset(values['-PRESET-'], window)
            if event in ('-MP4-', '-MKV-'):
                self.format = 'mp4' if values['-MP4-'] else 'mkv'
            if event == '-AUDIO_ENC-':
                self.audio_encoder = values['-AUDIO_ENC-']
                is_copy = (self.audio_encoder == 'copy')
                window['-AUDIO_BIT-'].update(disabled=is_copy)
                window['-AUDIO_CH-'].update(disabled=is_copy)
            if event == '-AUDIO_BIT-':
                self.audio_bitrate = int(values['-AUDIO_BIT-'])
            if event == '-BROWSE_OUTPUT-':
                self._browse_output_folder(window)
            self._handle_settings_menu(event, window)

        window.close()

    def _save_window_position(self, window):
        try:
            loc = window.current_location()
            self.config.set('ui', 'window_x', loc[0])
            self.config.set('ui', 'window_y', loc[1])
            self.config.save()
        except:
            pass

    def _get_popup_loc(self, window):
        try:
            return window.current_location()
        except:
            return None

    def _handle_settings_menu(self, event, window):
        if event == 'Quality:27':
            self.quality = 27; window['-QUALITY-'].update(27)
        elif event == 'Quality:23':
            self.quality = 23; window['-QUALITY-'].update(23)
        elif event == 'Quality:20':
            self.quality = 20; window['-QUALITY-'].update(20)
        elif event == 'Quality:18':
            self.quality = 18; window['-QUALITY-'].update(18)
        elif event == '🗂️ Set Default Folder...':
            folder = self._select_folder_with_create('Select default folder', self.last_folder or self.default_folder)
            if folder:
                self.default_folder = folder
                self.config.set('defaults', 'default_folder', folder)
                self.config.save()
                sg.popup_ok(f'Default folder set to:\n{folder}', title='Default Folder', location=self._get_popup_loc(window))
        elif event == '🗂️ Clear Default Folder':
            self.default_folder = ''
            self.config.set('defaults', 'default_folder', '')
            self.config.save()
            sg.popup_ok('Default folder cleared', title='Default Folder', location=self._get_popup_loc(window))
        elif event == '💾 Save Current as Default':
            self._save_current_as_default(window)
        elif event == '🔄 Reset to Defaults':
            self._reset_to_defaults(window)
        elif event == 'Format:MP4':
            window['-MP4-'].update(value=True); self.format = 'mp4'
        elif event == 'Format:MKV':
            window['-MKV-'].update(value=True); self.format = 'mkv'
        elif event and event.startswith('Encoder:'):
            enc = event.split(':')[1]
            if enc == 'Auto':
                enc = self.encoder_manager.get_recommended_encoder()
            for item in window['-ENCODER-'].Values:
                if enc in item:
                    window['-ENCODER-'].update(value=item)
                    self.encoder = enc
                    break

    def _save_current_as_default(self, window):
        self.config.set('defaults', 'quality', self.quality)
        self.config.set('defaults', 'encoder', self.encoder)
        self.config.set('defaults', 'format', self.format)
        self.config.set('defaults', 'audio_encoder', self.audio_encoder)
        self.config.set('defaults', 'audio_bitrate', self.audio_bitrate)
        self.config.save()
        sg.popup_ok('Current settings saved as defaults!', title='Settings', location=self._get_popup_loc(window))

    def _reset_to_defaults(self, window):
        if sg.popup_yes_no('Reset all settings to defaults?', location=self._get_popup_loc(window)) == 'Yes':
            self.config.reset_to_defaults()
            self.config.load()
            self.quality = 27; self.encoder = 'auto'; self.format = 'mp4'
            window['-QUALITY-'].update(27)
            window['-MP4-'].update(value=True)
            window['-AUDIO_ENC-'].update(value='copy')
            window['-AUDIO_BIT-'].update(disabled=True)
            window['-AUDIO_CH-'].update(disabled=True)
            sg.popup_ok('Settings reset to defaults!', title='Settings', location=self._get_popup_loc(window))

    def _select_folder_with_create(self, title, initial_folder=None):
        common_options = [f"{name} ({path})" for name, path in COMMON_FOLDERS.items() if os.path.exists(path)]
        layout = [
            [sg.Text(title, font=('Helvetica', 14, 'bold'))],
            [sg.Text('Quick Access:')],
            [sg.Listbox(common_options, size=(40, 5), key='-QUICK-', enable_events=True)],
            [sg.HorizontalSeparator()],
            [sg.Text('Or enter custom path:')],
            [sg.Input(initial_folder or '', key='-CUSTOM_PATH-', size=(40, 1)), sg.FolderBrowse(button_text='Browse', key='-BROWSE-')],
            [sg.HorizontalSeparator()],
            [sg.Text('New folder name (optional):')],
            [sg.Input(key='-NEW_FOLDER-', size=(30, 1)), sg.Button('Create', key='-CREATE-', button_color='#2ECC71')],
            [sg.HorizontalSeparator()],
            [sg.Button('Select', key='-SELECT-', button_color='#00B4D8', size=(10, 1)), sg.Button('Cancel', key='-CANCEL-', size=(10, 1))]
        ]
        popup_loc = (self.window_x + 200 if self.window_x else 400, self.window_y + 100 if self.window_y else 300)
        popup = sg.Window(title, layout, finalize=True, modal=True, location=popup_loc)
        result_folder = None
        while True:
            event, values = popup.read()
            if event in (sg.WINDOW_CLOSED, '-CANCEL-'):
                break
            if event == '-QUICK-' and values['-QUICK-']:
                result_folder = values['-QUICK-'][0].split('(')[1].rstrip(')')
                break
            if event == '-SELECT-':
                path = values['-CUSTOM_PATH-'].strip()
                if path and os.path.isdir(path):
                    result_folder = path
                    break
            if event == '-CREATE-':
                new_folder = values['-NEW_FOLDER-'].strip()
                parent = values['-CUSTOM_PATH-'].strip()
                if new_folder and parent and os.path.isdir(parent):
                    new_path = os.path.join(parent, new_folder)
                    try:
                        os.makedirs(new_path, exist_ok=True)
                        result_folder = new_path
                        sg.popup_ok(f'Folder created: {new_path}', location=popup.current_location())
                        break
                    except Exception as e:
                        sg.popup_error(f'Error creating folder: {e}', location=popup.current_location())
        popup.close()
        return result_folder

    def _browse_output_folder(self, window):
        folder = self._select_folder_with_create('Select Output Folder', self.output_dir if self.output_dir != 'source' else self.last_folder)
        if folder:
            window['-OUTPUT_DIR-'].update(folder)
            window['-OUTPUT_CUSTOM-'].update(value=True)
            window['-OUTPUT_SAME-'].update(value=False)
            self.output_dir = folder

    def _show_shortcuts(self, window):
        sg.popup_ok('⌨️ Keyboard Shortcuts\n\nEscape - Cancel current operation\nCtrl+O - Add files\nCtrl+Q - Quit', title='Keyboard Shortcuts', location=self._get_popup_loc(window))

    def _show_about(self, window):
        hw_name = self.encoder_manager.get_hardware_name()
        recommended = self.encoder_manager.get_recommended_encoder()
        sg.popup_ok(f'vconv - Video Converter\n\nVersion: 8.2.0\nLicense: GPLv3\n\n🖥️  Hardware: {hw_name}\n   Recommended: {recommended}\n\nPowered by HandBrakeCLI\nBuilt with Python & PySimpleGUI\n\n© 2024 MoTekLab', title='About vconv', location=self._get_popup_loc(window))

    def _build_layout(self):
        available_encoders = self.encoder_manager.get_available_encoders()
        recommended = self.encoder_manager.get_recommended_encoder()
        hw_name = self.encoder_manager.get_hardware_name()

        encoder_display = []
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available_encoders:
                info = self.encoder_manager.get_encoder_info(enc)
                display_name = f"{info['name']}"
                if enc == recommended:
                    display_name = f"✅ {display_name} (Recommended)"
                encoder_display.append(display_name)
                self.encoder_map[display_name] = enc

        left_panel = [
            [sg.Text('🎬 Encoder', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(encoder_display, default_value=encoder_display[0] if encoder_display else 'x265', key='-ENCODER-', size=(35, 1), enable_events=True, expand_x=True)],
            [sg.Text(f'🖥️  {hw_name}', text_color='#00B4D8', font=('Helvetica', 9))],
            [sg.HorizontalSeparator()],
            [sg.Text('📊 Quality (RF)', font=('Helvetica', 12, 'bold'))],
            [sg.Slider(range=(0, 51), default_value=self.quality, orientation='h', key='-QUALITY-', size=(25, 20), enable_events=True, expand_x=True)],
            [sg.Text(f'Current: {self.quality}', font=('Helvetica', 9), key='-QUALITY_LABEL-')],
            [sg.HorizontalSeparator()],
            [sg.Text('⚡ Preset', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['fast', 'balanced', 'high_quality', 'archive', 'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'tv_show'], default_value='balanced', key='-PRESET-', size=(25, 1), enable_events=True, expand_x=True)],
            [sg.HorizontalSeparator()],
            [sg.Text('📁 Output', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('Same as source (preserve structure)', 'OUTPUT', default=True, key='-OUTPUT_SAME-', expand_x=True),
             sg.Radio('Custom folder (dump all)', 'OUTPUT', key='-OUTPUT_CUSTOM-')],
            [sg.Input(self.output_dir if self.output_dir != 'source' else '', key='-OUTPUT_DIR-', size=(28, 1), expand_x=True), sg.Button('📁', key='-BROWSE_OUTPUT-')],
            [sg.HorizontalSeparator()],
            [sg.Text('💿 Format', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('MP4', 'FORMAT', default=True if self.format == 'mp4' else False, key='-MP4-', enable_events=True), sg.Radio('MKV', 'FORMAT', default=True if self.format == 'mkv' else False, key='-MKV-', enable_events=True)],
            [sg.HorizontalSeparator()],
            [sg.Text('🔊 Audio', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'aac', 'ac3', 'mp3', 'flac'], default_value='copy', key='-AUDIO_ENC-', size=(15, 1), enable_events=True)],
            [sg.Text('Bitrate:'), sg.Combo(['64', '96', '128', '192', '256', '320'], default_value='128', key='-AUDIO_BIT-', size=(8, 1), disabled=True)],
            [sg.Text('Ch:'), sg.Combo(['copy', 'stereo', '5.1'], default_value='copy', key='-AUDIO_CH-', size=(10, 1), disabled=True)],
            [sg.HorizontalSeparator()],
            [sg.Text('📝 Subtitles', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'all', 'none'], default_value='copy', key='-SUBTITLE-', size=(15, 1))],
            [sg.Checkbox('Burn first', key='-SUBTITLE_BURN-')],
            [sg.Text('External SRT:', font=('Helvetica', 9))],
            [sg.Input(key='-EXT_SRT-', size=(25, 1), expand_x=True), sg.FileBrowse('📄', file_types=(('SRT', '*.srt'),))],
        ]

        right_panel = [
            [sg.Text('📂 Files to Convert', font=('Helvetica', 12, 'bold'))],
            [sg.Text('Add files or folder to begin', font=('Helvetica', 9), text_color='gray')],
            [sg.Listbox(values=[], key='-FILE_LIST-', size=(55, 12), select_mode='extended', expand_x=True, expand_y=True)],
            [sg.Button('➕ Files', key='-ADD_FILES-'), sg.Button('➕ Folder', key='-ADD_FOLDER-'), sg.Button('❌ Clear', key='-CLEAR_FILES-')],
            [sg.Button('❌ Remove', key='-REMOVE_SELECTED-')],
            [sg.HorizontalSeparator()],
            [sg.Button('✅ Validate', key='-CHECK_FILES-'), sg.Button('📊 Analyze', key='-ANALYZE-')],
            [sg.HorizontalSeparator()],
            [sg.Text('', key='-STATUS-', text_color='#2ECC71', size=(50, 1))],
            [sg.ProgressBar(100, key='-PROGRESS-', size=(40, 20), visible=False)],
            [sg.Button('🚀 CONVERT', key='-CONVERT-', button_color='#2ECC71', size=(15, 2)),
             sg.Button('Cancel', key='-CANCEL-', button_color='#E74C3C', tooltip='Skip current file, continue rest'),
             sg.Button('Stop All', key='-STOP_ALL-', button_color='#E74C3C', tooltip='Stop all remaining files')],
        ]

        menu = [
            ['File', ['Add Files', 'Add Folder', '---', 'Exit']],
            ['Settings', ['Quality:27', 'Quality:23', 'Quality:20', 'Quality:18', '---', 'Format:MP4', 'Format:MKV', '---', 'Encoder:Auto', 'Encoder:x265', 'Encoder:nvenc_h265', '---', '🗂️ Set Default Folder...', '🗂️ Clear Default Folder', '---', '💾 Save Current as Default', '🔄 Reset to Defaults']],
            ['Help', ['📖 User Guide', '⌨️ Keyboard Shortcuts', '---', 'About vconv']]
        ]

        layout = [
            [sg.Menu(menu)],
            [
                sg.Col(left_panel, size=(380, 600), element_justification='left', expand_y=True),
                sg.VerticalSeparator(),
                sg.Col(right_panel, size=(550, 600), element_justification='left', expand_y=True)
            ],
            [sg.StatusBar(f'vconv v8.2.0 | {hw_name} | Files: 0 | Quality: {self.quality}', key='-STATUSBAR-', text_color='gray', expand_x=True)]
        ]
        return layout

    def _update_status(self, window):
        window['-STATUSBAR-'].update(f'vconv v8.2.0 | {self.encoder_manager.get_hardware_name()} | Files: {len(self.files)} | Quality: {self.quality}')

    def _add_files(self, window):
        try:
            initial_folder = self.last_folder if self.last_folder else (self.default_folder if self.default_folder else None)
            files = sg.popup_get_file('Select video files', multiple_files=True, file_types=(('Video Files', '*.mkv *.mp4 *.avi *.mov *.webm *.wmv *.flv *.m4v *.ts *.m2ts'),), initial_folder=initial_folder, location=self._get_popup_loc(window))
            if files:
                new_files = files.split(';')
                self.files.extend(new_files)
                if new_files:
                    folder = os.path.dirname(new_files[0])
                    if folder:
                        self.last_folder = folder
                        self.config.set('defaults', 'last_folder', folder)
                        self.config.save()
                window['-FILE_LIST-'].update(values=self.files)
                self._update_status(window)
        except Exception as e:
            sg.popup_error(f'Error adding files: {e}', location=self._get_popup_loc(window))

    def _add_folder(self, window):
        try:
            initial_folder = self.last_folder if self.last_folder else (self.default_folder if self.default_folder else None)
            folder = self._select_folder_with_create('Select folder with videos', initial_folder)
            if folder:
                self.last_folder = folder
                self.config.set('defaults', 'last_folder', folder)
                self.config.save()
                base_path = Path(folder)
                videos = []
                for ext in VIDEO_EXTENSIONS:
                    try:
                        for v in base_path.rglob(f"*{ext}"):
                            videos.append(str(v))
                    except:
                        pass
                    try:
                        for v in base_path.rglob(f"*{ext.upper()}"):
                            videos.append(str(v))
                    except:
                        pass
                videos = list(set(videos))[:500]
                if videos:
                    self.files.extend(videos)
                    window['-FILE_LIST-'].update(values=self.files)
                    self._update_status(window)
                    sg.popup_ok(f'Added {len(videos)} video files!\n\nUse "Validate" to check before converting.', title='Files Added', location=self._get_popup_loc(window))
                else:
                    sg.popup_ok('No video files found', title='Info', location=self._get_popup_loc(window))
        except Exception as e:
            sg.popup_error(f'Error: {e}', location=self._get_popup_loc(window))

    def _remove_selected(self, window, values):
        selected = values['-FILE_LIST-']
        if selected:
            for f in selected:
                if f in self.files:
                    self.files.remove(f)
            window['-FILE_LIST-'].update(values=self.files)
            self._update_status(window)

    def _check_files(self, window):
        from core.validator import FileValidator
        validator = FileValidator()
        valid = []
        issues = []
        output_custom = values.get('-OUTPUT_CUSTOM-', False) if 'values' in dir() else False
        output_dir = values.get('-OUTPUT_DIR-', '') if 'values' in dir() else ''
        for f in self.files:
            output = self._get_output_path(f, output_custom, output_dir)
            result = validator.validate_file(f, output)
            if result.status == 'valid':
                valid.append(os.path.basename(f))
            else:
                issues.append(f"{os.path.basename(f)}: {result.message}")
        if issues:
            window['-STATUS-'].update(f"⚠️ {len(issues)} issues", text_color='#F39C12')
            msg = f"✅ Valid: {len(valid)}\n⚠️ Issues: {len(issues)}\n\n" + '\n'.join(issues[:20])
            sg.popup_ok(msg, title='Validation', location=self._get_popup_loc(window))
        else:
            window['-STATUS-'].update(f"✅ All {len(valid)} ready", text_color='#2ECC71')

    def _get_output_path(self, input_file, output_custom=False, output_dir=''):
        if output_custom and output_dir and output_dir != 'source':
            filename = os.path.basename(input_file)
            return os.path.join(output_dir, os.path.splitext(filename)[0] + '.' + self.format)
        return generate_output_path(input_file, format=self.format, conflict_mode='rename')

    def _analyze_files(self, window):
        if not self.files:
            sg.popup_ok('No files to analyze', title='Info', location=self._get_popup_loc(window))
            return
        results = []
        for f in self.files[:50]:
            try:
                info = self.analyzer.analyze(f)
                if info:
                    subs_info = ""
                    if info.subtitle_streams:
                        sub_names = [f"[{s['language']}] {s['title']}" for s in info.subtitle_streams[:5]]
                        subs_info = f"\n   📝 Subtitles ({len(info.subtitle_streams)}): {', '.join(sub_names)}"
                    results.append(f"📄 {info.filename}\n   🎬 {info.video_codec} {info.width}x{info.height} | {info.filesize} | ⏱️ {info.duration or 'N/A'}{subs_info}")
            except:
                results.append(f"❌ {os.path.basename(f)}: Error")
        if results:
            sg.popup_scrolled('\n\n'.join(results), title='Analysis', size=(70, 25), location=self._get_popup_loc(window))

    def _apply_preset(self, preset_name, window):
        import json
        try:
            preset_file = Path(__file__).parent.parent / 'presets' / 'default_presets.json'
            with open(preset_file) as f:
                presets = json.load(f)
            if preset_name in presets['presets']:
                preset = presets['presets'][preset_name]
                if 'quality' in preset:
                    self.quality = preset['quality']
                    window['-QUALITY-'].update(preset['quality'])
                window['-STATUS-'].update(f"✅ {preset.get('name', preset_name)}", text_color='#00B4D8')
        except Exception as e:
            print(f"Preset error: {e}")

    def _start_conversion(self, window, values):
        if self.is_converting:
            return
        self.is_converting = True
        self.cancel_requested = False
        self.stop_all = False
        window['-CONVERT-'].update(disabled=True)
        window['-CANCEL-'].update(disabled=False)
        window['-STOP_ALL-'].update(disabled=False)
        window['-PROGRESS-'].update(visible=True)

        encoder = self.encoder
        for item in window['-ENCODER-'].Values:
            if item in values['-ENCODER-']:
                encoder = self.encoder_map.get(item, encoder)
                break
        if 'Recommended' in values['-ENCODER-']:
            encoder = self.encoder_manager.get_recommended_encoder()

        quality = int(values['-QUALITY-'])
        format_val = 'mp4' if values['-MP4-'] else 'mkv'
        audio_enc = values['-AUDIO_ENC-']
        audio_bit = int(values['-AUDIO_BIT-']) if audio_enc != 'copy' else None
        output_base = None
        if values.get('-OUTPUT_CUSTOM-', False) and values['-OUTPUT_DIR-']:
            output_base = values['-OUTPUT_DIR-']

        settings = ConversionSettings(encoder=encoder, quality=quality, audio_encoder=audio_enc, audio_bitrate=audio_bit, output_format=format_val)

        self.conversion_thread = threading.Thread(target=self._convert_thread, args=(window, settings, output_base, values), daemon=True)
        self.conversion_thread.start()

    def _convert_thread(self, window, settings, output_base, values):
        total = len(self.files)
        success = 0
        failed = 0
        skipped = 0

        for idx, input_file in enumerate(self.files):
            if self.cancel_requested:
                if self.stop_all:
                    skipped = total - idx
                    break
                skipped += 1
                continue

            filename = os.path.basename(input_file)
            progress_pct = int((idx / total) * 100) if total > 0 else 0

            window.write_event_value('-PROGRESS_UPDATE-', {
                'status': f"Processing ({idx+1}/{total}): {filename[:35]}...",
                'progress': progress_pct
            })

            if output_base:
                output_file = os.path.join(output_base, os.path.splitext(filename)[0] + '.' + settings.output_format)
                os.makedirs(output_base, exist_ok=True)
            else:
                output_file = generate_output_path(input_file, format=settings.output_format, conflict_mode='rename')

            try:
                result = self.converter.convert(input_file, output_file, settings)
                if result:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error: {e}")
                failed += 1

        window.write_event_value('-CONVERSION_DONE-', {'success': success, 'failed': failed, 'skipped': skipped})


def launch(config: Config, i18n: I18n, args=None):
    app = MainWindow(config, i18n, args)
    app.run()


if __name__ == "__main__":
    from utils.config import Config
    from utils.i18n import I18n
    config = Config()
    config.load()
    i18n = I18n('en')
    launch(config, i18n)