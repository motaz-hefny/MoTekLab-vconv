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


# Video extensions - comprehensive list
VIDEO_EXTENSIONS = [
    '.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', 
    '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts', '.vob'
]


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

        # Get settings from config
        self.quality = self.config.get('defaults', 'quality', 27)
        self.encoder = self.config.get('defaults', 'encoder', 'auto')
        self.format = self.config.get('defaults', 'format', 'mp4')
        self.output_dir = self.config.get('defaults', 'output_dir', 'source')  # source = in-place
        self.audio_encoder = 'copy'
        self.audio_bitrate = 128

        # Load window position
        self.window_x = self.config.get('ui', 'window_x', None)
        self.window_y = self.config.get('ui', 'window_y', None)

        # Build encoder display map
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
        self.theme = {
            'BACKGROUND': '#1E1E2E',
            'TEXT': '#FFFFFF',
            'INPUT': '#2D2D3D',
            'BUTTON': '#00B4D8',
            'BUTTON_TEXT': '#FFFFFF',
            'ACCENT': '#00B4D8',
            'PROGRESS': '#2ECC71',
        }

    def run(self):
        """Run the main window."""
        layout = self._build_layout()

        window = sg.Window(
            'vconv - Video Converter',
            layout,
            size=(1000, 700),
            location=(self.window_x, self.window_y) if self.window_x and self.window_y else None,
            resizable=True,
            finalize=True
        )

        # Bind events
        window.bind('<Escape>', '-CANCEL-')
        window.bind('Configure', '-MOVE-')  # Window moved/resized

        while True:
            event, values = window.read()

            if event in (sg.WINDOW_CLOSED, 'Exit'):
                if self.is_converting:
                    if sg.popup_yes_no('Conversion in progress. Cancel and exit?') == 'Yes':
                        self.cancel_requested = True
                        break
                break

            # Save window position on move
            if event == '-MOVE-':
                win = window.TKWindow
                self.window_x = win.winfo_x()
                self.window_y = win.winfo_y()

            # File operations
            if event == 'Add Files':
                self._add_files(window)

            if event == 'Add Folder':
                self._add_folder(window)

            if event == '-ADD_FILES-':
                self._add_files(window)

            if event == '-ADD_FOLDER-':
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
                    sg.popup_error('No files to convert!')
                    continue
                self._start_conversion(window, values)

            if event in ('-CANCEL-', '-STOP_ALL-'):
                if self.is_converting:
                    self.cancel_requested = True

            if event == '-ANALYZE-':
                self._analyze_files(window)

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

            # Audio encoder change
            if event == '-AUDIO_ENC-':
                self.audio_encoder = values['-AUDIO_ENC-']
                # Disable bitrate when copy is selected
                window['-AUDIO_BIT-'].update(disabled=(self.audio_encoder == 'copy'))
                window['-AUDIO_CH-'].update(disabled=(self.audio_encoder == 'copy'))

            # Audio bitrate change
            if event == '-AUDIO_BIT-':
                self.audio_bitrate = int(values['-AUDIO_BIT-'])

            # Output directory change
            if event == '-OUTPUT_DIR-':
                self.output_dir = values['-OUTPUT_DIR-']

            # Subtitle option
            if event == '-SUBTITLE-':
                pass  # Just store the value

            # Settings menu items
            if event == 'Quality:27':
                self.quality = 27
                window['-QUALITY-'].update(27)
            elif event == 'Quality:23':
                self.quality = 23
                window['-QUALITY-'].update(23)
            elif event == 'Quality:20':
                self.quality = 20
                window['-QUALITY-'].update(20)
            elif event == 'Format:MP4':
                window['-MP4-'].update(value=True)
                self.format = 'mp4'
            elif event == 'Format:MKV':
                window['-MKV-'].update(value=True)
                self.format = 'mkv'

            # Help menu
            if event == 'About':
                self._show_about(window)

        # Save window position before closing
        try:
            win = window.TKWindow
            self.config.set('ui', 'window_x', win.winfo_x())
            self.config.set('ui', 'window_y', win.winfo_y())
            self.config.save()
        except:
            pass

        window.close()

    def _build_layout(self):
        """Build the window layout."""

        # Encoder dropdown with info
        available_encoders = self.encoder_manager.get_available_encoders()
        recommended = self.encoder_manager.get_recommended_encoder()

        # Build encoder list with descriptions using self.encoder_map
        encoder_display = []
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available_encoders:
                info = self.encoder_manager.get_encoder_info(enc)
                display_name = f"{info['name']} - {info['best_for'][:30]}..."
                if enc == recommended:
                    display_name = f"✅ {info['name']} (Recommended)"
                encoder_display.append(display_name)
                self.encoder_map[display_name] = enc

        # Hardware info
        hw_name = self.encoder_manager.get_hardware_name()

        # Left panel - Settings
        left_panel = [
            [sg.Text('🎬 Encoder', font=('Helvetica', 12, 'bold'), tooltip='Select video encoder')],
            [sg.Combo(encoder_display, default_value=encoder_display[0] if encoder_display else 'x265',
                     key='-ENCODER-', size=(35, 1), enable_events=True,
                     tooltip='Video encoder - hardware encoders are faster')],
            [sg.Text(f'🖥️  Hardware: {hw_name}', text_color='#00B4D8', font=('Helvetica', 9),
                    tooltip='Detected GPU - hardware encoding is faster')],
            [sg.HorizontalSeparator()],

            [sg.Text('📊 Quality (RF)', font=('Helvetica', 12, 'bold'), tooltip='Lower = better quality, higher compression')],
            [sg.Slider(range=(0, 51), default_value=self.quality, orientation='h',
                      key='-QUALITY-', size=(25, 20), enable_events=True,
                      tooltip='RF Value: 0=best quality, 51=smallest file')],
            [sg.Text(f'Current: {self.quality} (lower = better quality)', font=('Helvetica', 9), key='-QUALITY_LABEL-')],
            [sg.HorizontalSeparator()],

            [sg.Text('⚡ Preset', font=('Helvetica', 12, 'bold'), tooltip='Quick preset selection')],
            [sg.Combo(['fast', 'balanced', 'high_quality', 'archive', 'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'tv_show'],
                     default_value='balanced', key='-PRESET-', size=(25, 1), enable_events=True,
                     tooltip='Balanced = recommended, Fast = quick, Archive = best quality')],
            [sg.HorizontalSeparator()],

            [sg.Text('📁 Output', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('Same as source (in-place)', 'OUTPUT', default=True, key='-OUTPUT_SAME-',
                     tooltip='Save converted files in the same folder as original'),
             sg.Radio('Custom folder', 'OUTPUT', key='-OUTPUT_CUSTOM-',
                     tooltip='Save all converted files to a specific folder')],
            [sg.Input(key='-OUTPUT_DIR-', size=(30, 1), default_text=self.output_dir,
                    tooltip='Output folder path'),
             sg.FolderBrowse(button_text='📁', tooltip='Browse for output folder')],
            [sg.HorizontalSeparator()],

            [sg.Text('💿 Format', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('MP4', 'FORMAT', default=True if self.format == 'mp4' else False, key='-MP4-', enable_events=True,
                     tooltip='MP4 - best compatibility'),
             sg.Radio('MKV', 'FORMAT', default=True if self.format == 'mkv' else False, key='-MKV-', enable_events=True,
                     tooltip='MKV - better for multiple audio/subtitle tracks')],
            [sg.HorizontalSeparator()],

            [sg.Text('🔊 Audio', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'aac', 'ac3', 'mp3', 'flac'], default_value='copy', key='-AUDIO_ENC-', size=(15, 1), enable_events=True,
                     tooltip='copy = keep original audio, aac/mp3/ac3 = re-encode')],
            [sg.Text('Bitrate:', tooltip='Audio bitrate (ignored when copy is selected)'),
             sg.Combo(['64', '96', '128', '192', '256', '320'], default_value='128', key='-AUDIO_BIT-', size=(8, 1), enable_events=True,
                     tooltip='Audio bitrate in kbps')],
            [sg.Text('Channels:'),
             sg.Combo(['copy', 'stereo', '5.1'], default_value='copy', key='-AUDIO_CH-', size=(10, 1),
                     tooltip='Audio channels - copy keeps original')],
            [sg.HorizontalSeparator()],

            [sg.Text('📝 Subtitles', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'all', 'none'], default_value='copy', key='-SUBTITLE-', size=(15, 1),
                     tooltip='copy = keep all, all = burn/convert all, none = remove'),
             sg.Checkbox('Burn first', key='-SUBTITLE_BURN-', tooltip='Burn first subtitle track into video')],
        ]

        # Right panel - Files and actions
        right_panel = [
            [sg.Text('📂 Files to Convert', font=('Helvetica', 12, 'bold'))],
            [sg.Text('Drop files here or use buttons below:', font=('Helvetica', 9), text_color='gray')],
            [sg.Listbox(values=[], key='-FILE_LIST-', size=(55, 12), select_mode='extended', 
                       tooltip='List of files to be converted')],
            [sg.Button('➕ Add Files', key='-ADD_FILES-', button_color='#00B4D8', tooltip='Add video files'),
             sg.Button('➕ Add Folder', key='-ADD_FOLDER-', button_color='#00B4D8', tooltip='Add all videos from a folder'),
             sg.Button('❌ Clear', key='-CLEAR_FILES-', button_color='#E74C3C', tooltip='Clear file list')],
            [sg.Button('❌ Remove Selected', key='-REMOVE_SELECTED-', button_color='#F39C12', tooltip='Remove selected files from list')],
            [sg.HorizontalSeparator()],
            [sg.Button('✅ Validate Files', key='-CHECK_FILES-', button_color='#9B59B6', tooltip='Check files before conversion'),
             sg.Button('📊 Analyze', key='-ANALYZE-', button_color='#9B59B6', tooltip='Show file information without converting')],
            [sg.HorizontalSeparator()],
            [sg.Text('', key='-STATUS-', text_color='#2ECC71', size=(50, 1))],
            [sg.ProgressBar(100, key='-PROGRESS-', size=(40, 20), visible=False)],
            [sg.Button('🚀 CONVERT ALL', key='-CONVERT-', button_color='#2ECC71', size=(20, 2), tooltip='Start conversion'),
             sg.Button('⏹️ Cancel', key='-CANCEL-', button_color='#E74C3C', disabled=True, tooltip='Cancel current conversion'),
             sg.Button('⏹️ Stop All', key='-STOP_ALL-', button_color='#E74C3C', tooltip='Stop all conversions')],
        ]

        # Complete layout
        layout = [
            [sg.Menu([
                ['File', ['Add Files', 'Add Folder', '---', 'Exit']],
                ['Settings', ['Quality:27', 'Quality:23', 'Quality:20', 'Quality:18', '---', 'Format:MP4', 'Format:MKV', '---', 'Encoder:Auto', 'Encoder:x265', 'Encoder:nvenc_h265']],
                ['Help', ['📖 User Guide', '⌨️ Keyboard Shortcuts', '---', 'About vconv']]
            ])],
            [
                sg.Column(left_panel, vertical_alignment='top', size=(380, 600)),
                sg.VerticalSeparator(),
                sg.Column(right_panel, vertical_alignment='top', size=(550, 600))
            ],
            [sg.StatusBar(f'vconv v8.0.0 | {hw_name} | Files: 0 | Quality: {self.quality}', key='-STATUSBAR-', text_color='gray')]
        ]

        return layout

    def _update_status(self, window):
        """Update status bar."""
        window['-STATUSBAR-'].update(f'vconv v8.0.0 | {self.encoder_manager.get_hardware_name()} | Files: {len(self.files)} | Quality: {self.quality}')

    def _add_files(self, window):
        """Add files via file dialog."""
        try:
            files = sg.popup_get_file(
                'Select video files',
                multiple_files=True,
                file_types=(('Video Files', '*.mkv *.mp4 *.avi *.mov *.webm *.wmv *.flv *.m4v *.ts *.m2ts'),)
            )
            if files:
                new_files = files.split(';')
                self.files.extend(new_files)
                window['-FILE_LIST-'].update(values=self.files)
                self._update_status(window)
        except Exception as e:
            sg.popup_error(f'Error adding files: {e}')

    def _add_folder(self, window):
        """Add folder and scan for videos."""
        try:
            folder = sg.popup_get_folder('Select folder containing videos')
            if folder:
                # Scan for videos with error handling
                base_path = Path(folder)
                videos = []

                for ext in VIDEO_EXTENSIONS:
                    try:
                        for v in base_path.rglob(f"*{ext}"):
                            videos.append(str(v))
                    except Exception as e:
                        print(f"Error scanning {ext}: {e}")

                    try:
                        for v in base_path.rglob(f"*{ext.upper()}"):
                            videos.append(str(v))
                    except Exception as e:
                        print(f"Error scanning {ext.upper()}: {e}")

                # Remove duplicates and limit
                videos = list(set(videos))[:500]  # Max 500 files

                if videos:
                    self.files.extend(videos)
                    window['-FILE_LIST-'].update(values=self.files)
                    self._update_status(window)
                    sg.popup_info(f'Added {len(videos)} video files from folder\n\nTip: Use "Validate Files" to check them before converting.')
                else:
                    sg.popup_warning('No video files found in the selected folder')
        except Exception as e:
            sg.popup_error(f'Error adding folder: {e}')
            print(f"Folder add error: {e}")

    def _remove_selected(self, window, values):
        """Remove selected files from list."""
        selected = values['-FILE_LIST-']
        if selected:
            for f in selected:
                if f in self.files:
                    self.files.remove(f)
            window['-FILE_LIST-'].update(values=self.files)
            self._update_status(window)

    def _check_files(self, window):
        """Validate files before conversion."""
        from core.validator import FileValidator
        validator = FileValidator()

        valid = []
        issues = []

        for f in self.files:
            # Determine output path
            if self.output_dir and self.output_dir != 'source':
                # Custom output folder - keep filename
                filename = os.path.basename(f)
                output = os.path.join(self.output_dir, os.path.splitext(filename)[0] + '.' + self.format)
            else:
                # In-place with rename
                output = generate_output_path(f, format=self.format, conflict_mode='rename')

            result = validator.validate_file(f, output)

            if result.status == 'valid':
                valid.append(os.path.basename(f))
            else:
                issues.append(f"{os.path.basename(f)}: {result.message}")

        if issues:
            window['-STATUS-'].update(f"⚠️ {len(issues)} file(s) have issues", text_color='#F39C12')
            sg.popup_ok('File Validation Results',
                       f"✅ Valid: {len(valid)}\n⚠️ Issues: {len(issues)}\n\n" + '\n'.join(issues[:20]))
        else:
            window['-STATUS-'].update(f"✅ All {len(valid)} files ready for conversion", text_color='#2ECC71')

    def _analyze_files(self, window):
        """Analyze files and show info."""
        if not self.files:
            sg.popup_warning('No files to analyze')
            return

        results = []
        for f in self.files[:50]:  # Limit to 50 files
            try:
                info = self.analyzer.analyze(f)
                if info:
                    results.append(f"📄 {info.filename}\n   🎬 {info.video_codec} | {info.width}x{info.height} | {info.filesize} | ⏱️ {info.duration or 'N/A'}\n   🔊 {info.audio_codec} | 📊 {info.audio_bitrate or 'N/A'}")
            except Exception as e:
                results.append(f"❌ {os.path.basename(f)}: Error")

        if results:
            sg.popup_scrolled('Media Analysis', '\n\n'.join(results), size=(70, 25), title='Analysis Results')
        else:
            sg.popup_error('Could not analyze files')

    def _apply_preset(self, preset_name: str, window):
        """Apply preset settings."""
        import json
        preset_file = Path(__file__).parent.parent / 'presets' / 'default_presets.json'

        try:
            with open(preset_file) as f:
                presets = json.load(f)

            if preset_name in presets['presets']:
                preset = presets['presets'][preset_name]

                if 'quality' in preset:
                    self.quality = preset['quality']
                    window['-QUALITY-'].update(preset['quality'])

                if 'encoder' in preset:
                    enc = preset['encoder']
                    # Update encoder dropdown
                    for item in window['-ENCODER-'].Values:
                        if enc in item:
                            window['-ENCODER-'].update(value=item)
                            self.encoder = enc
                            break

                window['-STATUS-'].update(f"✅ Applied preset: {preset.get('name', preset_name)}", text_color='#00B4D8')
        except Exception as e:
            print(f"Preset error: {e}")

    def _show_about(self, window):
        """Show about dialog."""
        sg.popup_ok(
            'vconv - Video Converter\n\n'
            'Version: 8.0.0\n'
            'License: GPLv3\n\n'
            'Powered by HandBrakeCLI\n'
            'Built with Python & PySimpleGUI\n\n'
            '© 2024 MoTekLab\n\n'
            'Keyboard Shortcuts:\n'
            '  Ctrl+O - Add Files\n'
            '  Ctrl+Q - Quit\n'
            '  Escape - Cancel\n',
            title='About vconv'
        )

    def _start_conversion(self, window, values):
        """Start conversion in background thread."""
        if self.is_converting:
            return

        self.is_converting = True
        self.cancel_requested = False

        # Update UI
        window['-CONVERT-'].update(disabled=True)
        window['-CANCEL-'].update(disabled=False)
        window['-PROGRESS-'].update(visible=True)

        # Get settings from UI
        encoder = self.encoder
        if 'Recommended' in str(values['-ENCODER-']):
            encoder = self.encoder_manager.get_recommended_encoder()
        elif values['-ENCODER-'] in self.encoder_map:
            encoder = self.encoder_map[values['-ENCODER-']]

        quality = int(values['-QUALITY-'])
        format_val = 'mp4' if values['-MP4-'] else 'mkv'

        # Audio settings
        audio_enc = values['-AUDIO_ENC-']
        audio_bit = int(values['-AUDIO_BIT-']) if audio_enc != 'copy' else None
        audio_ch = values['-AUDIO_CH-']

        # Subtitle settings
        subtitle_opt = values['-SUBTITLE-']
        burn_subtitle = values.get('-SUBTITLE_BURN-', False)

        settings = ConversionSettings(
            encoder=encoder,
            quality=quality,
            audio_encoder=audio_enc,
            audio_bitrate=audio_bit,
            output_format=format_val
        )

        # Determine output directory
        output_base = None
        if values['-OUTPUT_CUSTOM-'] and values['-OUTPUT_DIR-']:
            output_base = values['-OUTPUT_DIR-']

        # Run conversion in thread
        thread = threading.Thread(
            target=self._convert_thread,
            args=(window, settings, output_base),
            daemon=True
        )
        thread.start()

    def _convert_thread(self, window, settings, output_base):
        """Conversion worker thread."""
        total = len(self.files)
        success = 0
        failed = 0

        for idx, input_file in enumerate(self.files):
            if self.cancel_requested:
                break

            filename = os.path.basename(input_file)

            # Update status
            window['-STATUS-'].update(f"Processing ({idx+1}/{total}): {filename[:40]}...")

            # Calculate progress
            progress = int((idx / total) * 100)
            window['-PROGRESS-'].update(progress)

            # Generate output path
            if output_base:
                # Use custom output folder
                output_file = os.path.join(output_base, os.path.splitext(filename)[0] + '.' + settings.output_format)
                os.makedirs(output_base, exist_ok=True)
            else:
                # In-place (same folder as source)
                output_file = generate_output_path(input_file, format=settings.output_format, conflict_mode='rename')

            # Convert
            try:
                result = self.converter.convert(input_file, output_file, settings)
                if result:
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Conversion error: {e}")
                failed += 1

        # Done
        self.is_converting = False
        window['-CONVERT-'].update(disabled=False)
        window['-CANCEL-'].update(disabled=True)
        window['-PROGRESS-'].update(visible=False)

        if self.cancel_requested:
            window['-STATUS-'].update(f"❌ Cancelled: {success}/{total} converted", text_color='#F39C12')
        else:
            window['-STATUS-'].update(f"✅ Complete: {success} success, {failed} failed", text_color='#2ECC71')


# Encoder mapping for display
encoder_map = {}


def launch(config: Config, i18n: I18n, args=None):
    """Launch the main window."""
    app = MainWindow(config, i18n, args)
    app.run()


if __name__ == "__main__":
    # Test
    from utils.config import Config
    from utils.i18n import I18n

    config = Config()
    config.load()
    i18n = I18n('en')

    launch(config, i18n)