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
VIDEO_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.mov', '.webm', '.wmv', '.flv', '.m4v']


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

        # Get settings
        self.quality = self.config.get('defaults', 'quality', 27)
        self.encoder = self.config.get('defaults', 'encoder', 'auto')
        self.format = self.config.get('defaults', 'format', 'mp4')

        # Set theme
        self._setup_theme()

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
            size=(900, 650),
            resizable=True,
            finalize=True
        )

        window.bind('<Escape>', '-CANCEL-')

        while True:
            event, values = window.read()

            if event in (sg.WINDOW_CLOSED, 'Exit'):
                if self.is_converting:
                    if sg.popup_yes_no('Conversion in progress. Cancel and exit?') == 'Yes':
                        self.cancel_requested = True
                        break
                break

            if event == '-ADD_FILES-':
                self._add_files(window)

            if event == '-ADD_FOLDER-':
                self._add_folder(window)

            if event == '-CLEAR_FILES-':
                self.files = []
                window['-FILE_LIST-'].update(values=[])

            if event == '-CHECK_FILES-':
                self._check_files(window)

            if event == '-CONVERT-':
                if not self.files:
                    sg.popup_error('No files to convert!')
                    continue
                self._start_conversion(window, values)

            if event == '-CANCEL-':
                if self.is_converting:
                    self.cancel_requested = True

            if event == '-ANALYZE-':
                self._analyze_files(window)

            # Encoder change
            if event == '-ENCODER-':
                self.encoder = values['-ENCODER-']

            # Quality change
            if event == '-QUALITY-':
                self.quality = values['-QUALITY-']

            # Preset change
            if event == '-PRESET-':
                self._apply_preset(values['-PRESET-'], window)

            # Format change
            if event == '-FORMAT-':
                self.format = values['-FORMAT-']

        window.close()

    def _build_layout(self):
        """Build the window layout."""

        # Encoder dropdown with info
        available_encoders = self.encoder_manager.get_available_encoders()
        recommended = self.encoder_manager.get_recommended_encoder()

        # Build encoder list with recommended marker
        encoder_list = []
        for enc in ['nvenc_h265', 'nvenc_h264', 'qsv_h265', 'qsv_h264', 'amf_h265', 'amf_h264', 'x265', 'x264', 'libsvtav1']:
            if enc in available_encoders:
                if enc == recommended:
                    encoder_list.append(f"{enc} (Recommended)")
                else:
                    encoder_list.append(enc)

        # Hardware info
        hw_name = self.encoder_manager.get_hardware_name()

        # Left panel - Settings
        left_panel = [
            [sg.Text('Video Encoder', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(encoder_list, default_value=f"{recommended} (Recommended)" if recommended in [e.split(' ')[0] for e in encoder_list] else encoder_list[0],
                     key='-ENCODER-', size=(25, 1), enable_events=True)],
            [sg.Text(f'Detected: {hw_name}', text_color='#00B4D8', font=('Helvetica', 9))],
            [sg.HorizontalSeparator()],

            [sg.Text('Quality (RF)', font=('Helvetica', 12, 'bold'))],
            [sg.Slider(range=(0, 51), default_value=self.quality, orientation='h',
                      key='-QUALITY-', size=(20, 20), enable_events=True)],
            [sg.Text(f'Lower = better quality | Current: {self.quality}', font=('Helvetica', 9))],
            [sg.HorizontalSeparator()],

            [sg.Text('Preset', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['fast', 'balanced', 'high_quality', 'archive',
                      'nvenc_fast', 'nvenc_balanced', 'nvenc_quality', 'tv_show'],
                     default_value='balanced', key='-PRESET-', size=(20, 1), enable_events=True)],
            [sg.HorizontalSeparator()],

            [sg.Text('Output Format', font=('Helvetica', 12, 'bold'))],
            [sg.Radio('MP4', 'FORMAT', default=True if self.format == 'mp4' else False, key='-MP4-', enable_events=True),
             sg.Radio('MKV', 'FORMAT', default=True if self.format == 'mkv' else False, key='-MKV-', enable_events=True)],
            [sg.HorizontalSeparator()],

            [sg.Text('Audio', font=('Helvetica', 12, 'bold'))],
            [sg.Combo(['copy', 'aac', 'ac3', 'mp3', 'flac'], default_value='copy', key='-AUDIO_ENC-', size=(15, 1))],
            [sg.Combo(['64', '96', '128', '160', '192', '256', '320'], default_value='128', key='-AUDIO_BIT-', size=(10, 1))],
            [sg.Text('kbps', font=('Helvetica', 9))],
        ]

        # Right panel - Files and actions
        right_panel = [
            [sg.Text('Files to Convert', font=('Helvetica', 12, 'bold'))],
            [sg.Text('Drop files here or use buttons below:', font=('Helvetica', 9), text_color='gray')],
            [sg.Listbox(values=[], key='-FILE_LIST-', size=(50, 15), select_mode='extended')],
            [sg.Button('Add Files', key='-ADD_FILES-', button_color='#00B4D8'),
             sg.Button('Add Folder', key='-ADD_FOLDER-', button_color='#00B4D8'),
             sg.Button('Clear', key='-CLEAR_FILES-', button_color='#E74C3C')],
            [sg.HorizontalSeparator()],
            [sg.Button('Check Files', key='-CHECK_FILES-', button_color='#F39C12'),
             sg.Button('Analyze', key='-ANALYZE-', button_color='#9B59B6')],
            [sg.HorizontalSeparator()],
            [sg.Text('', key='-STATUS-', text_color='#2ECC71')],
            [sg.Button('CONVERT', key='-CONVERT-', button_color='#2ECC71', size=(15, 2)),
             sg.Button('Cancel', key='-CANCEL-', button_color='#E74C3C', disabled=True)],
        ]

        # Complete layout
        layout = [
            [sg.Menu([
                ['File', ['Add Files', 'Add Folder', '---', 'Exit']],
                ['Settings', ['Quality:27', 'Quality:23', 'Quality:20', '---', 'Format:MP4', 'Format:MKV']],
                ['Help', ['About']]
            ])],
            [
                sg.Column(left_panel, vertical_alignment='top', size=(300, 500)),
                sg.VerticalSeparator(),
                sg.Column(right_panel, vertical_alignment='top', size=(500, 500))
            ],
            [sg.StatusBar(f'vconv v8.0.0 | {hw_name} | Files: 0', key='-STATUSBAR-', text_color='gray')]
        ]

        return layout

    def _add_files(self, window):
        """Add files via file dialog."""
        files = sg.popup_get_file(
            'Select video files',
            multiple_files=True,
            file_types=(('Video Files', '*.mkv *.mp4 *.avi *.mov *.webm *.wmv *.flv'),)
        )
        if files:
            self.files.extend(files.split(';'))
            window['-FILE_LIST-'].update(values=self.files)
            window['-STATUSBAR-'].update(f'vconv v8.0.0 | Files: {len(self.files)}')

    def _add_folder(self, window):
        """Add folder and scan for videos."""
        folder = sg.popup_get_folder('Select folder')
        if folder:
            # Scan for videos
            base_path = Path(folder)
            videos = []
            for ext in VIDEO_EXTENSIONS:
                videos.extend(base_path.rglob(f"*{ext}"))
                videos.extend(base_path.rglob(f"*{ext.upper()}"))

            if videos:
                self.files.extend([str(v) for v in videos])
                window['-FILE_LIST-'].update(values=self.files)
                window['-STATUSBAR-'].update(f'vconv v8.0.0 | Files: {len(self.files)}')
                sg.popup_info(f'Added {len(videos)} video files from folder')
            else:
                sg.popup_warning('No video files found in the selected folder')

    def _check_files(self, window):
        """Validate files before conversion."""
        from core.validator import FileValidator
        validator = FileValidator()

        valid = []
        issues = []

        for f in self.files:
            # Generate output path (in place with rename)
            output = generate_output_path(f, format=self.format, conflict_mode='rename')
            result = validator.validate_file(f, output)

            if result.status == 'valid':
                valid.append(f)
            else:
                issues.append(f"{os.path.basename(f)}: {result.message}")

        if issues:
            window['-STATUS-'].update(f"⚠️ {len(issues)} file(s) have issues", text_color='#F39C12')
            sg.popup_ok('File Check Results',
                       f"Valid: {len(valid)}\nIssues: {len(issues)}\n\n" + '\n'.join(issues[:10]))
        else:
            window['-STATUS-'].update(f"✅ All {len(valid)} files ready", text_color='#2ECC71')

    def _analyze_files(self, window):
        """Analyze files and show info."""
        if not self.files:
            sg.popup_warning('No files to analyze')
            return

        results = []
        for f in self.files:
            info = self.analyzer.analyze(f)
            if info:
                results.append(f"{info.filename}\n  {info.video_codec} {info.width}x{info.height} | {info.filesize} | {info.duration or 'N/A'}")

        if results:
            sg.popup_scrolled('Analysis Results', '\n\n'.join(results), size=(60, 20))
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
                    # Find encoder in dropdown
                    for item in window['-ENCODER-'].Values:
                        if enc in item:
                            window['-ENCODER-'].update(value=item)
                            self.encoder = enc
                            break

                window['-STATUS-'].update(f"Applied preset: {preset['name']}", text_color='#00B4D8')
        except Exception as e:
            print(f"Preset error: {e}")

    def _start_conversion(self, window, values):
        """Start conversion in background thread."""
        if self.is_converting:
            return

        self.is_converting = True
        self.cancel_requested = False
        window['-CONVERT-'].update(disabled=True)
        window['-CANCEL-'].update(disabled=False)

        # Get settings from UI
        encoder = self.encoder
        if 'Recommended' in values['-ENCODER-']:
            encoder = self.encoder_manager.get_recommended_encoder()

        quality = int(values['-QUALITY-'])
        format_val = 'mp4' if values['-MP4-'] else 'mkv'
        audio_enc = values['-AUDIO_ENC-']
        audio_bit = int(values['-AUDIO_BIT-']) if audio_enc != 'copy' else None

        settings = ConversionSettings(
            encoder=encoder,
            quality=quality,
            audio_encoder=audio_enc,
            audio_bitrate=audio_bit,
            output_format=format_val
        )

        # Run conversion in thread
        thread = threading.Thread(
            target=self._convert_thread,
            args=(window, settings),
            daemon=True
        )
        thread.start()

    def _convert_thread(self, window, settings):
        """Conversion worker thread."""
        total = len(self.files)
        success = 0
        failed = 0

        for idx, input_file in enumerate(self.files):
            if self.cancel_requested:
                break

            filename = os.path.basename(input_file)

            # Update status
            window['-STATUS-'].update(f"Processing: {filename} ({idx+1}/{total})")

            # Generate output path (in place)
            output_file = generate_output_path(input_file, format=settings.output_format, conflict_mode='rename')

            # Convert
            result = self.converter.convert(input_file, output_file, settings)

            if result:
                success += 1
            else:
                failed += 1

        # Done
        self.is_converting = False
        window['-CONVERT-'].update(disabled=False)
        window['-CANCEL-'].update(disabled=True)

        if self.cancel_requested:
            window['-STATUS-'].update(f"❌ Cancelled: {success}/{total} converted", text_color='#F39C12')
        else:
            window['-STATUS-'].update(f"✅ Complete: {success} success, {failed} failed", text_color='#2ECC71')


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