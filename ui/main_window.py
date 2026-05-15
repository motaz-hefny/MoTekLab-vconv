"""
vconv Main Window UI

PySimpleGUI-based interface for video conversion.
"""

import PySimpleGUI as sg
import os
import threading
from pathlib import Path

from core.encoder import EncoderManager
from core.converter import Converter, ConversionSettings
from core.validator import generate_output_path
from core.analyzer import MediaAnalyzer
from utils.config import Config
from utils.i18n import I18n


# Video extensions
VIDEO_EXTENSIONS = [
    '.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', 
    '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts', '.vob'
]

# Common folders for quick access
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

        # Initialize components
        self.encoder_manager = EncoderManager()
        self.converter = Converter(self.encoder_manager)
        self.analyzer = MediaAnalyzer()

        # State
        self.files = []
        self.is_converting = False
        self.current_file_index = 0
        self.cancel_requested = False
        self.stop_all = False

        # Get settings from config
        self.quality = self.config.get('defaults', 'quality', 27)
        self.encoder = self.config.get('defaults', 'encoder', 'auto')
        self.format = self.config.get('defaults', 'format', 'mp4')
        self.output_dir = self.config.get('defaults', 'output_dir', 'source')
        self.last_folder = self.config.get('defaults', 'last_folder', '')
        self.default_folder = self.config.get('defaults', 'default_folder', '')

        # Audio settings - bitrate disabled by default when copy
        self.audio_encoder = 'copy'
        self.audio_bitrate = 128
        self.audio_bitrate_disabled = True  # Default: disabled when copy

        # Load window position
        self.window_x = self.config.get('ui', 'window_x', None)
        self.window_y = self.config.get('ui', 'window_y', None)

        # Build encoder map
        self.encoder_map = self._build_encoder_map()

        # Set theme
        self._setup_theme()

    def _build_encoder_map(self):
        """Build encoder display name to id mapping."""
        available_encoders = self.encoder_manager.get_available_encoders()
        encoder_map = {}
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available_encoders:
                info = self.encoder_manager.get_encoder_info(enc)
                display_name = f"{info['name']} - {info['best_for'][:30]}..."
                encoder_map[display_name] = enc
        return encoder_map

    def _setup_theme(self):
        """Setup application theme."""
        sg.theme('DarkBlue13')

    def _save_window_position(self, window):
        """Save current window position to config."""
        try:
            win = window.TKWindow
            self.window_x = win.winfo_x()
            self.window_y = win.winfo_y()
            self.config.set('ui', 'window_x', self.window_x)
            self.config.set('ui', 'window_y', self.window_y)
            self.config.save()
        except Exception as e:
            pass

    def run(self):
        """Run the main window."""
        # Determine initial location
        location = None
        if self.window_x is not None and self.window_y is not None:
            location = (self.window_x, self.window_y)

        layout = self._build_layout()

        window = sg.Window(
            'vconv - Video Converter',
            layout,
            size=(1000, 700),
            location=location,
            resizable=True,
            finalize=True
        )

        # Bind Escape to cancel and position tracking
        window.bind('<Escape>', '-CANCEL-')
        window.bind('Configure', '-WINDOW_MOVED-')  # Track window moves

        # Initial state - disable audio bitrate
        window['-AUDIO_BIT-'].update(disabled=True)
        window['-AUDIO_CH-'].update(disabled=True)

        # Save initial position
        self._save_window_position(window)

        while True:
            event, values = window.read()

            if event in (sg.WINDOW_CLOSED, 'Exit'):
                if self.is_converting:
                    if sg.popup_yes_no('Conversion in progress. Cancel and exit?', location=window.current_location()) == 'Yes':
                        self.cancel_requested = True
                        break
                break

            # Save window position on move/resize
            if event == '-WINDOW_MOVED-':
                try:
                    win = window.TKWindow
                    self.window_x = win.winfo_x()
                    self.window_y = win.winfo_y()
                    self.config.set('ui', 'window_x', self.window_x)
                    self.config.set('ui', 'window_y', self.window_y)
                    self.config.save()
                except:
                    pass

            # File operations
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
                    sg.popup_error('No files to convert!', location=window.current_location())
                    continue
                self._start_conversion(window, values)

            # Cancel current file only, continue with rest
            if event == '-CANCEL-':
                if self.is_converting:
                    self.cancel_requested = True  # Only cancels current file

            # Stop all - cancels everything
            if event == '-STOP_ALL-':
                if self.is_converting:
                    self.stop_all = True
                    self.cancel_requested = True

            if event in ('-ANALYZE-', '📖 User Guide'):
                self._analyze_files(window)

            # Help menu items
            if event == '⌨️ Keyboard Shortcuts':
                self._show_shortcuts(window)
            elif event == 'About vconv':
                self._show_about(window)

            # Encoder change
            if event == '-ENCODER-':
                self.encoder = values['-ENCODER-']
                if 'Recommended' in self.encoder:
                    self.encoder = self.encoder_manager.get_recommended_encoder()

            # Quality change
            if event == '-QUALITY-':
                self.quality = int(values['-QUALITY-'])

            # Preset change
            if event == '-PRESET-':
                self._apply_preset(values['-PRESET-'], window)

            # Format change
            if event in ('-MP4-', '-MKV-'):
                self.format = 'mp4' if values['-MP4-'] else 'mkv'

            # Audio encoder change - disable bitrate when copy
            if event == '-AUDIO_ENC-':
                self.audio_encoder = values['-AUDIO_ENC-']
                is_copy = (self.audio_encoder == 'copy')
                window['-AUDIO_BIT-'].update(disabled=is_copy)
                window['-AUDIO_CH-'].update(disabled=is_copy)

            # Audio bitrate change
            if event == '-AUDIO_BIT-':
                self.audio_bitrate = int(values['-AUDIO_BIT-'])

            # Output directory - use file browser with folder creation
            if event == '-BROWSE_OUTPUT-':
                self._browse_output_folder(window)

            # Settings menu items
            self._handle_settings_menu(event, window)

        # Save final position
        try:
            win = window.TKWindow
            self.config.set('ui', 'window_x', win.winfo_x())
            self.config.set('ui', 'window_y', win.winfo_y())
            self.config.save()
        except:
            pass

        window.close()

    def _handle_settings_menu(self, event, window):
        """Handle settings menu events."""
        if event == 'Quality:27':
            self.quality = 27
            window['-QUALITY-'].update(27)
        elif event == 'Quality:23':
            self.quality = 23
            window['-QUALITY-'].update(23)
        elif event == 'Quality:20':
            self.quality = 20
            window['-QUALITY-'].update(20)
        elif event == 'Quality:18':
            self.quality = 18
            window['-QUALITY-'].update(18)
        elif event == '🗂️ Set Default Folder...':
            folder = self._select_folder_with_create('Select default folder', self.last_folder or self.default_folder)
            if folder:
                self.default_folder = folder
                self.config.set('defaults', 'default_folder', folder)
                self.config.save()
                sg.popup_ok(f'Default folder set to:\n{folder}', title='Default Folder', location=window.current_location())
        elif event == '🗂️ Clear Default Folder':
            self.default_folder = ''
            self.config.set('defaults', 'default_folder', '')
            self.config.save()
            sg.popup_ok('Default folder cleared', title='Default Folder', location=window.current_location())
        elif event == '💾 Save Current as Default':
            self._save_current_as_default(window)
        elif event == '🔄 Reset to Defaults':
            self._reset_to_defaults(window)
        elif event == 'Format:MP4':
            window['-MP4-'].update(value=True)
            self.format = 'mp4'
        elif event == 'Format:MKV':
            window['-MKV-'].update(value=True)
            self.format = 'mkv'
        elif event and event.startswith('Encoder:'):
            enc = event.split(':')[1]
            if enc == 'Auto':
                enc = self.encoder_manager.get_recommended_encoder()
            # Find encoder in dropdown
            for item in window['-ENCODER-'].Values:
                if enc in item:
                    window['-ENCODER-'].update(value=item)
                    self.encoder = enc
                    break

    def _save_current_as_default(self, window):
        """Save current settings as defaults."""
        self.config.set('defaults', 'quality', self.quality)
        self.config.set('defaults', 'encoder', self.encoder)
        self.config.set('defaults', 'format', self.format)
        self.config.set('defaults', 'audio_encoder', self.audio_encoder)
        self.config.set('defaults', 'audio_bitrate', self.audio_bitrate)
        self.config.save()
        sg.popup_ok('Current settings saved as defaults!', title='Settings', location=window.current_location())

    def _reset_to_defaults(self, window):
        """Reset all settings to defaults."""
        if sg.popup_yes_no('Reset all settings to defaults?\n\nThis will reset quality, encoder, and other options.', location=window.current_location()) == 'Yes':
            self.config.reset_to_defaults()
            self.config.load()
            self.quality = 27
            self.encoder = 'auto'
            self.format = 'mp4'
            window['-QUALITY-'].update(27)
            window['-MP4-'].update(value=True)
            window['-AUDIO_ENC-'].update(value='copy')
            window['-AUDIO_BIT-'].update(disabled=True)
            window['-AUDIO_CH-'].update(disabled=True)
            sg.popup_ok('Settings reset to defaults!', title='Settings', location=window.current_location())

    def _select_folder_with_create(self, title, initial_folder=None):
        """Custom folder selector with folder creation option."""
        # Get list of common folders
        common_options = [f"{name} ({path})" for name, path in COMMON_FOLDERS.items() if os.path.exists(path)]
        
        layout = [
            [sg.Text(title, font=('Helvetica', 14, 'bold'))],
            [sg.Text('Quick Access:')],
            [sg.Listbox(common_options, size=(40, 5), key='-QUICK-', enable_events=True)],
            [sg.HorizontalSeparator()],
            [sg.Text('Or enter custom path:')],
            [sg.Input(initial_folder or '', key='-CUSTOM_PATH-', size=(40, 1)),
             sg.FolderBrowse(button_text='Browse', key='-BROWSE-')],
            [sg.HorizontalSeparator()],
            [sg.Text('New folder name (if creating):')],
            [sg.Input(key='-NEW_FOLDER-', size=(30, 1)),
             sg.Button('Create', key='-CREATE-', button_color='#2ECC71')],
            [sg.HorizontalSeparator()],
            [sg.Button('Select', key='-SELECT-', button_color='#00B4D8', size=(10, 1)),
             sg.Button('Cancel', key='-CANCEL-', size=(10, 1))]
        ]
        
        # Calculate popup location - center on screen or use saved position
        if self.window_x is not None and self.window_y is not None:
            popup_location = (self.window_x + 200, self.window_y + 100)
        else:
            popup_location = None
        
        popup = sg.Window(title, layout, finalize=True, modal=True, location=popup_location)
        
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
        """Browse for output folder with create option."""
        folder = self._select_folder_with_create('Select Output Folder', self.output_dir if self.output_dir != 'source' else self.last_folder)
        if folder:
            window['-OUTPUT_DIR-'].update(folder)
            window['-OUTPUT_CUSTOM-'].update(value=True)
            window['-OUTPUT_SAME-'].update(value=False)
            self.output_dir = folder

    def _show_shortcuts(self, window):
        """Show keyboard shortcuts."""
        sg.popup_ok(
            '⌨️ Keyboard Shortcuts\n\n'
            'General:\n'
            '  Escape      - Cancel current operation\n'
            '  Ctrl+O      - Add files (via menu)\n'
            '  Ctrl+Q      - Quit\n\n'
            'In GUI:\n'
            '  Select files with mouse\n'
            '  Use buttons for actions\n'
            '  Hover over elements for tooltips',
            title='Keyboard Shortcuts',
            location=window.current_location()
        )

    def _show_about(self, window):
        """Show about dialog."""
        hw_name = self.encoder_manager.get_hardware_name()
        recommended = self.encoder_manager.get_recommended_encoder()
        
        sg.popup_ok(
            'vconv - Video Converter\n\n'
            'Version: 8.0.0\n'
            'License: GPLv3\n\n'
            f'🖥️  Hardware: {hw_name}\n'
            f'   Recommended: {recommended}\n\n'
            'Powered by HandBrakeCLI\n'
            'Built with Python & PySimpleGUI\n\n'
            '© 2024 MoTekLab',
            title='About vconv',
            location=window.current_location()
        )

    def _build_layout(self):
        """Build the window layout."""
        available_encoders = self.encoder_manager.get_available_encoders()
        recommended = self.encoder_manager.get_recommended_encoder()
        hw_name = self.encoder_manager.get_hardware_name()

        # Build encoder list
        encoder_display = []
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available_encoders:
                info = self.encoder_manager.get_encoder_info(enc)
                display_name = f"{info['name']}"
                if enc == recommended:
                    display_name = f"✅ {display_name} (Recommended)"
                encoder_display.append(display_name)
                self.encoder_map[display_name] = enc

        # Left panel
        left_panel = [
            [sg.Text('🎬 Encoder', font=('Helvetica', 12, 'bold'), tooltip='Video encoder - hardware encoders are faster')],
            [sg.Combo(encoder_display, default_value=encoder_display[0] if encoder_display else 'x265',
                     key='-ENCODER-', size=(35, 1), enable_events=True)],
            [sg.Text(f'🖥️  {hw_name}', text_color='#00B4D8', font=('Helvetica', 9))],
            [sg.HorizontalSeparator()],

            [sg.Text('📊 Quality (RF)', font=('Helvetica', 12, 'bold'), tooltip='Lower = better quality')],
            [sg.Slider(range=(0, 51), default_value=self.quality, orientation='h',
                      key='-QUALITY-', size=(25, 20), enable_events=True)],
            [sg.Text(f'Current: {self.quality}', font=('Helvetica', 9), key='-QUALITY_LABEL-')],
            [sg.HorizontalSeparator()],

            [sg.Text('⚡ Preset', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['fast', 'balanced', 'high_quality', 'archive', 'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'tv_show'],
                     default_value='balanced', key='-PRESET-', size=(25, 1), enable_events=True)],
            [sg.HorizontalSeparator()],

            [sg.Text('📁 Output', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('Same as source', 'OUTPUT', default=True, key='-OUTPUT_SAME-', tooltip='Save in same folder as original'),
             sg.Radio('Custom folder', 'OUTPUT', key='-OUTPUT_CUSTOM-', tooltip='Save to specific folder')],
            [sg.Input(self.output_dir if self.output_dir != 'source' else '', key='-OUTPUT_DIR-', size=(28, 1)),
             sg.Button('📁', key='-BROWSE_OUTPUT-', tooltip='Browse/Create folder')],
            [sg.HorizontalSeparator()],

            [sg.Text('💿 Format', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('MP4', 'FORMAT', default=True if self.format == 'mp4' else False, key='-MP4-', enable_events=True, tooltip='Best compatibility'),
             sg.Radio('MKV', 'FORMAT', default=True if self.format == 'mkv' else False, key='-MKV-', enable_events=True, tooltip='More flexibility')],
            [sg.HorizontalSeparator()],

            [sg.Text('🔊 Audio', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'aac', 'ac3', 'mp3', 'flac'], default_value='copy', key='-AUDIO_ENC-', size=(15, 1), enable_events=True, tooltip='copy = keep original')],
            [sg.Text('Bitrate:'), sg.Combo(['64', '96', '128', '192', '256', '320'], default_value='128', key='-AUDIO_BIT-', size=(8, 1), disabled=True)],
            [sg.Text('Ch:'), sg.Combo(['copy', 'stereo', '5.1'], default_value='copy', key='-AUDIO_CH-', size=(10, 1), disabled=True)],
            [sg.HorizontalSeparator()],

            [sg.Text('📝 Subtitles', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'all', 'none'], default_value='copy', key='-SUBTITLE-', size=(15, 1), tooltip='copy = keep existing, all = include all, none = remove')],
            [sg.Checkbox('Burn first', key='-SUBTITLE_BURN-', tooltip='Burn first subtitle into video')],
        ]

        # Right panel - Files
        right_panel = [
            [sg.Text('📂 Files to Convert', font=('Helvetica', 12, 'bold'))],
            [sg.Text('Add files or folder to begin', font=('Helvetica', 9), text_color='gray')],
            [sg.Listbox(values=[], key='-FILE_LIST-', size=(55, 12), select_mode='extended', tooltip='Files to convert')],
            [sg.Button('➕ Files', key='-ADD_FILES-', tooltip='Add video files'),
             sg.Button('➕ Folder', key='-ADD_FOLDER-', tooltip='Add folder with videos'),
             sg.Button('❌ Clear', key='-CLEAR_FILES-', tooltip='Clear file list')],
            [sg.Button('❌ Remove', key='-REMOVE_SELECTED-', tooltip='Remove selected files')],
            [sg.HorizontalSeparator()],
            [sg.Button('✅ Validate', key='-CHECK_FILES-', tooltip='Check files before conversion'),
             sg.Button('📊 Analyze', key='-ANALYZE-', tooltip='Show media info')],
            [sg.HorizontalSeparator()],
            [sg.Text('', key='-STATUS-', text_color='#2ECC71', size=(50, 1))],
            [sg.ProgressBar(100, key='-PROGRESS-', size=(40, 20), visible=False)],
            [sg.Button('🚀 CONVERT', key='-CONVERT-', button_color='#2ECC71', size=(15, 2)),
             sg.Button('Cancel', key='-CANCEL-', button_color='#E74C3C', tooltip='Cancel current file only'),
             sg.Button('Stop All', key='-STOP_ALL-', button_color='#E74C3C', tooltip='Cancel all remaining files')],
        ]

        # Menu
        menu = [
            ['File', ['Add Files', 'Add Folder', '---', 'Exit']],
            ['Settings', [
                'Quality:27', 'Quality:23', 'Quality:20', 'Quality:18',
                '---',
                'Format:MP4', 'Format:MKV',
                '---',
                'Encoder:Auto', 'Encoder:x265', 'Encoder:nvenc_h265',
                '---',
                '🗂️ Set Default Folder...', '🗂️ Clear Default Folder',
                '---',
                '💾 Save Current as Default', '🔄 Reset to Defaults'
            ]],
            ['Help', ['📖 User Guide', '⌨️ Keyboard Shortcuts', '---', 'About vconv']]
        ]

        # Layout with proper stretching
        layout = [
            [sg.Menu(menu)],
            [
                sg.Col(left_panel, size=(380, 600), element_justification='left'),
                sg.VerticalSeparator(),
                sg.Col(right_panel, size=(550, 600), element_justification='left')
            ],
            [sg.StatusBar(f'vconv v8.0.0 | {hw_name} | Files: 0 | Quality: {self.quality}', key='-STATUSBAR-', text_color='gray', expand_x=True)]
        ]

        return layout

    def _update_status(self, window):
        """Update status bar."""
        window['-STATUSBAR-'].update(f'vconv v8.0.0 | {self.encoder_manager.get_hardware_name()} | Files: {len(self.files)} | Quality: {self.quality}')

    def _get_window_location(self, window):
        """Get window center location for popups."""
        try:
            return window.current_location()
        except:
            return None

    def _add_files(self, window):
        """Add files via dialog."""
        try:
            initial_folder = self.last_folder if self.last_folder else (self.default_folder if self.default_folder else None)
            files = sg.popup_get_file(
                'Select video files',
                multiple_files=True,
                file_types=(('Video Files', '*.mkv *.mp4 *.avi *.mov *.webm *.wmv *.flv *.m4v *.ts *.m2ts'),),
                initial_folder=initial_folder,
                location=window.current_location()
            )
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
            sg.popup_error(f'Error adding files: {e}', location=window.current_location())

    def _add_folder(self, window):
        """Add folder with videos."""
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
                    sg.popup_ok(f'Added {len(videos)} video files!\n\nUse "Validate" to check before converting.',
                               title='Files Added', location=window.current_location())
                else:
                    sg.popup_warning('No video files found', location=window.current_location())
        except Exception as e:
            sg.popup_error(f'Error: {e}', location=window.current_location())

    def _remove_selected(self, window, values):
        """Remove selected files."""
        selected = values['-FILE_LIST-']
        if selected:
            for f in selected:
                if f in self.files:
                    self.files.remove(f)
            window['-FILE_LIST-'].update(values=self.files)
            self._update_status(window)

    def _check_files(self, window):
        """Validate files."""
        from core.validator import FileValidator
        validator = FileValidator()

        valid = []
        issues = []

        # Get output settings
        try:
            output_custom = window['-OUTPUT_CUSTOM-'].get()
            output_dir = window['-OUTPUT_DIR-'].get() if output_custom else ''
        except:
            output_custom = False
            output_dir = ''

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
            sg.popup_ok(msg, title='Validation', location=window.current_location())
        else:
            window['-STATUS-'].update(f"✅ All {len(valid)} ready", text_color='#2ECC71')

    def _get_output_path(self, input_file, output_custom=False, output_dir=''):
        """Calculate output path based on settings."""
        if output_custom and output_dir and output_dir != 'source':
            filename = os.path.basename(input_file)
            return os.path.join(output_dir, os.path.splitext(filename)[0] + '.' + self.format)
        return generate_output_path(input_file, format=self.format, conflict_mode='rename')

    def _analyze_files(self, window):
        """Analyze files."""
        if not self.files:
            sg.popup_warning('No files to analyze', location=window.current_location())
            return

        results = []
        for f in self.files[:50]:
            try:
                info = self.analyzer.analyze(f)
                if info:
                    subs = f" | 📝 {len(info.subtitle_streams)} subs" if info.subtitle_streams else ""
                    results.append(f"📄 {info.filename}\n   🎬 {info.video_codec} {info.width}x{info.height} | {info.filesize} | ⏱️ {info.duration or 'N/A'}{subs}")
            except:
                results.append(f"❌ {os.path.basename(f)}: Error")

        if results:
            sg.popup_scrolled('\n\n'.join(results), title='Analysis', size=(70, 25), location=window.current_location())

    def _apply_preset(self, preset_name, window):
        """Apply preset."""
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
        """Start conversion."""
        if self.is_converting:
            return

        self.is_converting = True
        self.cancel_requested = False
        self.stop_all = False

        window['-CONVERT-'].update(disabled=True)
        window['-CANCEL-'].update(disabled=False)
        window['-STOP_ALL-'].update(disabled=False)
        window['-PROGRESS-'].update(visible=True)

        # Get settings
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

        # Determine output folder
        output_base = None
        if values.get('-OUTPUT_CUSTOM-', False) and values['-OUTPUT_DIR-']:
            output_base = values['-OUTPUT_DIR-']

        settings = ConversionSettings(
            encoder=encoder, quality=quality,
            audio_encoder=audio_enc, audio_bitrate=audio_bit,
            output_format=format_val
        )

        thread = threading.Thread(
            target=self._convert_thread,
            args=(window, settings, output_base, values),
            daemon=True
        )
        thread.start()

    def _convert_thread(self, window, settings, output_base, values):
        """Conversion worker."""
        total = len(self.files)
        success = 0
        failed = 0
        skipped = 0

        for idx, input_file in enumerate(self.files):
            if self.cancel_requested:
                if self.stop_all:
                    skipped = total - idx
                    break
                # Just skip current, continue to next
            
            filename = os.path.basename(input_file)
            window['-STATUS-'].update(f"Processing ({idx+1}/{total}): {filename[:35]}...")
            window['-PROGRESS-'].update(int((idx / total) * 100))

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

        self.is_converting = False
        window['-CONVERT-'].update(disabled=False)
        window['-CANCEL-'].update(disabled=True)
        window['-STOP_ALL-'].update(disabled=True)
        window['-PROGRESS-'].update(visible=False)

        if self.stop_all:
            window['-STATUS-'].update(f"⏹️ Stopped: {success} done, {skipped} skipped, {failed} failed", text_color='#F39C12')
        elif self.cancel_requested:
            window['-STATUS-'].update(f"✅ {success} done, {skipped} skipped, {failed} failed", text_color='#2ECC71')
        else:
            window['-STATUS-'].update(f"✅ Complete: {success} ok, {failed} failed", text_color='#2ECC71')


def launch(config: Config, i18n: I18n, args=None):
    """Launch the main window."""
    app = MainWindow(config, i18n, args)
    app.run()


if __name__ == "__main__":
    from utils.config import Config
    from utils.i18n import I18n

    config = Config()
    config.load()
    i18n = I18n('en')

    launch(config, i18n)