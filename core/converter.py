"""
Video Converter Module - HandBrakeCLI wrapper with real progress tracking
"""
import subprocess
import os
import logging
import select
import signal
import tempfile
import threading
import time
import re
import shutil
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ConversionSettings:
    encoder: str = "x265"
    quality: int = 27
    audio_encoder: str = "copy"
    audio_bitrate: Optional[int] = None
    audio_track_overrides: Optional[dict[int, dict]] = None
    resolution: Optional[str] = None
    denoise: str = "off"
    deinterlace: str = "off"
    rotation: int = 0
    subtitle_mode: str = "all"
    subtitle_burn: bool = False
    subtitle_lang_list: str = ""
    external_srt_files: list = None
    external_srt_burn: bool = False
    external_srt_default: bool = True
    output_format: str = "mp4"
    advanced: Optional[dict] = None
    metadata_preserve: bool = True
    metadata_preserve_flag: Optional[str] = None

    def __post_init__(self):
        if self.external_srt_files is None:
            self.external_srt_files = []

@dataclass
class ConversionProgress:
    percent: float = 0.0
    fps: float = 0.0
    eta_seconds: int = 0
    current_frame: int = 0
    total_frames: int = 0

class Converter:
    def __init__(self, encoder_manager, handbrake_cmd: list[str] | None = None):
        self.encoder_manager = encoder_manager
        self._current_process: Optional[subprocess.Popen] = None
        self._cancel_flag = False
        self.last_error = ""
        self._output_buffer = []
        self._command_string = ""
        self._temp_symlinks: list[tuple[str, str]] = []
        self._temp_dir: Optional[str] = None
        self._hb_cmd = handbrake_cmd or ['HandBrakeCLI']

    def _init_temp_dir(self):
        if self._temp_dir is None:
            base = os.path.join(os.path.expanduser("~"), ".cache", "vconv")
            os.makedirs(base, exist_ok=True)
            self._temp_dir = tempfile.mkdtemp(prefix="job_", dir=base)

    def _cleanup_temp(self):
        import shutil
        for original, link in self._temp_symlinks:
            try:
                if os.path.islink(link) or os.path.exists(link):
                    os.unlink(link)
            except Exception:
                pass
        self._temp_symlinks.clear()
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir = None

    def _sanitize_path(self, path: str) -> str:
        """Ensure the path is usable by HandBrakeCLI:
        - Symlink if path contains commas (breaks HB's comma-separated --srt-file)
        - Copy to local temp if on GVFS and using Flatpak (sandbox can't access GVFS)
        """
        needs_copy = self._is_flatpak() and ('/gvfs/' in path or '/run/user/' in path)
        if not needs_copy and ',' not in path:
            return path
        self._init_temp_dir()
        safe_name = os.path.basename(path).replace(',', '_').replace(' ', '_')
        dest = os.path.join(self._temp_dir, safe_name)
        try:
            if needs_copy:
                shutil.copy2(path, dest)
                logger.info(f"Copied GVFS file for Flatpak: {path} -> {dest}")
            else:
                os.symlink(path, dest)
                logger.info(f"Created temp symlink for comma-path: {path} -> {dest}")
            self._temp_symlinks.append((path, dest))
            return dest
        except Exception as e:
            logger.warning(f"Failed to sanitize path {path}: {e}")
            return path

    def _is_flatpak(self) -> bool:
        """Return True if the HandBrakeCLI command runs via Flatpak sandbox."""
        return self._hb_cmd and self._hb_cmd[0] == 'flatpak'

    def _copy_to_temp(self, path: str) -> str:
        """Copy a remote/GVFS file to a local temp directory for Flatpak access."""
        self._init_temp_dir()
        basename = os.path.basename(path)
        # Strip problematic chars for the copy destination name
        safe_name = basename.replace(',', '_').replace(' ', '_')
        dest = os.path.join(self._temp_dir, safe_name)
        try:
            logger.info(f"Copying {path} -> {dest} (local cache for Flatpak)")
            shutil.copy2(path, dest)
            self._temp_symlinks.append((path, dest))
            return dest
        except Exception as e:
            logger.warning(f"Failed to copy GVFS file locally: {e}")
            return path

    @property
    def process(self):
        return self._current_process

    def pause(self):
        if self._current_process and self._current_process.poll() is None:
            self._current_process.send_signal(signal.SIGSTOP)

    def resume(self):
        if self._current_process and self._current_process.poll() is None:
            self._current_process.send_signal(signal.SIGCONT)

    def convert(self, input_path: str, output_path: str, settings: ConversionSettings,
                progress_callback: Optional[Callable] = None,
                log_callback: Optional[Callable] = None) -> bool:
        self._cancel_flag = False
        if not os.path.exists(input_path):
            logger.error(f"Input not found: {input_path}")
            return False

        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        local_input = input_path
        copied_to_temp = False
        # Flatpak sandbox blocks GVFS mounts — copy file locally first
        if ('/gvfs/' in input_path or '/run/user/' in input_path) and self._is_flatpak():
            logger.info("Input is on a GVFS mount and HandBrakeCLI runs via Flatpak — copying to local temp…")
            local_input = self._copy_to_temp(input_path)
            if local_input != input_path:
                copied_to_temp = True

        cmd = self._build_command(local_input, output_path, settings)
        self._command_string = ' '.join(cmd)
        if copied_to_temp:
            logger.info(f"Using local copy as input: {local_input}")
        logger.info(f"Converting: {input_path} -> {output_path}")
        logger.info(f"Command: {self._command_string}")

        try:
            self._current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1
            )
            self._monitor_progress(progress_callback)
            self._current_process.wait()
            exit_code = self._current_process.returncode

            if self._cancel_flag:
                logger.info("Conversion cancelled")
                self.last_error = "Cancelled by user"
                return False
            if exit_code != 0:
                err_lines = ''.join(self._output_buffer[-100:])
                self.last_error = f"HandBrakeCLI exit code {exit_code}"
                if self._command_string:
                    self.last_error += f"\nCommand: {self._command_string[:500]}"
                if err_lines:
                    self.last_error += f"\nOutput:\n{err_lines[:3000]}"
                logger.error(self.last_error)
                return False
            self.last_error = ""
            logger.info(f"Completed: {output_path}")
            # Log HandBrakeCLI output on success for debugging
            output_summary = ''.join(self._output_buffer[-50:]).strip()
            if output_summary:
                logger.info(f"HandBrakeCLI output:\n{output_summary[:2000]}")
            # Verify output file was actually created
            if not os.path.exists(output_path):
                logger.warning(f"Output file does not exist after successful conversion: {output_path}")
                if self._command_string:
                    logger.warning(f"Full command: {self._command_string}")
                self.last_error = f"Output file was not created: {output_path}"
                return False
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                logger.warning(f"Output file is empty (0 bytes): {output_path}")
                self.last_error = f"Output file is empty (0 bytes): {output_path}"
                return False
            logger.info(f"Output file size: {file_size} bytes")
            # Preserve source metadata via ffmpeg (fallback when HB's own flag isn't available)
            custom_path = os.environ.get('PATH', '') + os.pathsep + '/usr/local/bin' + os.pathsep + os.path.expanduser('~/.local/bin')
            ffmpeg_bin = shutil.which('ffmpeg', path=custom_path)
            ffprobe_bin = shutil.which('ffprobe', path=custom_path) or ffmpeg_bin
            if settings.metadata_preserve and not settings.metadata_preserve_flag and ffmpeg_bin and settings.output_format in ('mp4', 'mkv'):
                # Brief pause to let OS file locks clear from HandBrakeCLI
                time.sleep(1.5)
                self._copy_metadata(input_path, output_path, settings.output_format, ffmpeg_bin, log_callback, ffprobe_bin)
            # Warn about network/GVFS mounts
            if '/gvfs/' in output_path or '/run/user/' in output_path:
                logger.warning("Output is on a GVFS/FUSE mount (e.g. SMB via GVFS). "
                               "Writing to network mounts may cause silent failures. "
                               "Consider using a local output directory instead.")
            return True
        except FileNotFoundError:
            self.last_error = "HandBrakeCLI not found in PATH"
            logger.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Conversion failed: {e}", exc_info=True)
            return False
        finally:
            self._current_process = None
            self._cleanup_temp()

    def _copy_metadata(self, source_path: str, dest_path: str, output_format: str = 'mp4',
                       ffmpeg_bin: str = 'ffmpeg', log_callback: Optional[Callable] = None,
                       ffprobe_bin: Optional[str] = None):
        """Copy metadata from source to dest, then apply faststart.

        Preserves everything including cover art and custom ---- atoms (iTunEXTC, iTunMOVI)
        via binary-level copy of the ilst atom from source into output.

        Root cause: MP4 stores metadata (moov atom) at the end of the file. GVFS/SMB
        FUSE mounts cannot handle lseek() to the end of multi-GB files. ffmpeg silently
        assumes "no metadata" and exits code 0.

        Strategy:
        1. Binary ilst replacement — direct byte-level copy of ilst atom from cached source
           into output. Preserves cover art, ---- freeform atoms, and Apple 4-byte tags.
        2. Direct if local — fallback: skip caching, use source directly with ffmpeg.
        3. Partial cache + ffmpeg — fallback: walk atoms, build minimal MP4, map_metadata.
        4. Explicit metadata — fallback: extract with ffprobe, apply with -metadata flags.
        """
        import struct, json

        def ui_log(msg, is_error=False):
            if is_error:
                logger.warning(msg)
            else:
                logger.info(msg)
            if log_callback:
                log_callback(msg)

        probe = ffprobe_bin or ffmpeg_bin
        def probe_tags(path, label):
            try:
                r = subprocess.run(
                    [probe, '-v', 'quiet', '-print_format', 'json',
                     '-show_entries', 'format_tags', path],
                    capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL
                )
                data = json.loads(r.stdout)
                tags = data.get('format', {}).get('tags', {})
                if tags:
                    ui_log(f"{label}: {len(tags)} tags: {list(tags.keys())}")
                else:
                    ui_log(f"{label}: NO tags!", is_error=True)
                return tags
            except Exception as e:
                ui_log(f"{label} probe failed: {e}", is_error=True)
                return {}

        # ──────────────────────────────────────────────────
        # Binary ilst replacement helpers
        # ──────────────────────────────────────────────────
        def _read_bytes(path):
            with open(path, 'rb') as f:
                return f.read()

        def _write_bytes(path, data):
            with open(path, 'wb') as f:
                f.write(data)

        def _find_atom(data, parent_off, parent_sz, atype, skip=8):
            """Find child atom of given type within parent. skip=bytes before child list."""
            off = parent_off + skip
            end = parent_off + parent_sz
            while off + 8 <= end and off + 8 <= len(data):
                sz = struct.unpack('>I', data[off:off+4])[0]
                if sz == 0:
                    break
                if data[off+4:off+8] == atype:
                    return (off, int(sz))
                off += int(sz)
            return (None, None)

        def _find_ilst_in(data):
            """Return (ilst_offset, ilst_size) from binary MP4 data, or (None, None)."""
            moov_off, moov_sz = _find_atom(data, 0, len(data), b'moov', skip=0)
            if moov_off is None:
                return (None, None)
            udta_off, udta_sz = _find_atom(data, moov_off, moov_sz, b'udta')
            if udta_off is None:
                return (None, None)
            meta_off, meta_sz = _find_atom(data, udta_off, udta_sz, b'meta')
            if meta_off is None:
                return (None, None)
            ilst_off, ilst_sz = _find_atom(data, meta_off, meta_sz, b'ilst', skip=12)
            return (ilst_off, ilst_sz)

        def _binary_replace_ilst(dest_path, source_data):
            """Binary-copy ilst from source_data into dest_path (in place, no faststart).
            Handles insert/create if dest lacks ilst/meta/udta.
            Returns (success, delta_bytes)."""
            src_ilst_off, src_ilst_sz = _find_ilst_in(source_data)
            if src_ilst_off is None:
                return (False, 0)

            src_ilst_atom = source_data[src_ilst_off:src_ilst_off + src_ilst_sz]

            dst = bytearray(_read_bytes(dest_path))

            moov_off, moov_sz = _find_atom(dst, 0, len(dst), b'moov', skip=0)
            if moov_off is None:
                return (False, 0)

            udta_off, udta_sz = _find_atom(dst, moov_off, moov_sz, b'udta')
            meta_off, meta_sz = _find_atom(dst, udta_off if udta_off else 0,
                                           udta_sz if udta_off else 0, b'meta')
            ilst_off, ilst_sz = (None, None)
            if meta_off is not None:
                ilst_off, ilst_sz = _find_atom(dst, meta_off, meta_sz, b'ilst', skip=12)

            if ilst_off is not None and ilst_sz is not None:
                delta = len(src_ilst_atom) - ilst_sz
                dst[ilst_off:ilst_off + ilst_sz] = src_ilst_atom
                update_list = [(meta_off, meta_sz), (udta_off, udta_sz), (moov_off, moov_sz)]
            else:
                # Insert source ilst — build missing containers as needed.
                # Parent offsets (moov_off, udta_off, meta_off) are unchanged
                # because we insert AFTER them.
                if meta_off is not None:
                    insert_at = meta_off + meta_sz
                    dst[insert_at:insert_at] = src_ilst_atom
                    delta = len(src_ilst_atom)
                    update_list = [(meta_off, meta_sz), (udta_off, udta_sz), (moov_off, moov_sz)]
                elif udta_off is not None:
                    hdlr = _build_hdlr()
                    meta_body = hdlr + src_ilst_atom
                    meta_full = struct.pack('>I4sI', 12 + len(meta_body), b'meta', 0) + meta_body
                    insert_at = udta_off + udta_sz
                    dst[insert_at:insert_at] = meta_full
                    delta = len(meta_full)
                    update_list = [(udta_off, udta_sz), (moov_off, moov_sz)]
                else:
                    hdlr = _build_hdlr()
                    meta_body = hdlr + src_ilst_atom
                    meta_full = struct.pack('>I4sI', 12 + len(meta_body), b'meta', 0) + meta_body
                    udta_full = struct.pack('>I4s', len(meta_full) + 8, b'udta') + meta_full
                    insert_at = moov_off + moov_sz
                    dst[insert_at:insert_at] = udta_full
                    delta = len(udta_full)
                    update_list = [(moov_off, moov_sz)]

            for off, _ in update_list:
                if off is None:
                    continue
                old_sz = struct.unpack('>I', dst[off:off+4])[0]
                struct.pack_into('>I', dst, off, old_sz + delta)

            _write_bytes(dest_path, bytes(dst))
            return (True, delta)

        def _build_hdlr():
            """Build a standard 33-byte hdlr atom for 'mdir' (metadata handler)."""
            return struct.pack('>I4sB3sI4s12s', 33, b'hdlr', 0, b'\x00\x00\x00', 0, b'mdir',
                               b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00') + b'\x00'

        # ──────────────────────────────────────────────────
        # Programmatic ilst builder (for non-MP4 sources)
        # ──────────────────────────────────────────────────
        def _build_text_data(value):
            """data atom for UTF-8 text (flags=1)."""
            val_bytes = value.encode('utf-8')
            payload = struct.pack('>I', 0x00000001) + struct.pack('>I', 0) + val_bytes
            return struct.pack('>I4s', 8 + len(payload), b'data') + payload

        def _build_int_data(value):
            """data atom for integer (flags=0x15). 4-byte BE."""
            try:
                int_val = int(value)
            except (ValueError, TypeError):
                int_val = 0
            payload = struct.pack('>I', 0x00000015) + struct.pack('>I', 0) + struct.pack('>I', int_val)
            return struct.pack('>I4s', 8 + len(payload), b'data') + payload

        def _build_cover_data(image_bytes, is_jpeg=True):
            """data atom for cover art. flags=0xD for JPEG, 0xE for PNG."""
            type_flags = 0x0000000D if is_jpeg else 0x0000000E
            payload = struct.pack('>I', type_flags) + struct.pack('>I', 0) + image_bytes
            return struct.pack('>I4s', 8 + len(payload), b'data') + payload

        def _build_mean_name_atom(atype, string):
            """mean or name atom: 8 header + 4 ver/flags + string (no null)."""
            str_bytes = string.encode('utf-8')
            payload = struct.pack('>I', 0) + str_bytes
            return struct.pack('>I4s', 8 + len(payload), atype) + payload

        def _build_4cc_item(code, data_atom):
            """Item atom wrapping a data atom (e.g. ©nam containing data)."""
            return struct.pack('>I4s', 8 + len(data_atom), code) + data_atom

        def _build_freeform_atom(name, value):
            """---- atom with mean=com.apple.iTunes, name=<name>, data=<value>."""
            mean = _build_mean_name_atom(b'mean', 'com.apple.iTunes')
            name_a = _build_mean_name_atom(b'name', name)
            data = _build_text_data(value)
            payload = mean + name_a + data
            return struct.pack('>I4s', 8 + len(payload), b'----') + payload

        def _build_ilst_from_tags(tags):
            """Build a full ilst atom from ffprobe-extracted metadata dict.
            Maps known keys to Apple 4-byte codes; creates ---- freeform atoms
            for non-standard keys. Ignores encoder/internal tags."""
            _4CC = {
                'title': '\xa9nam'.encode('latin-1'), 'artist': '\xa9ART'.encode('latin-1'),
                'album': '\xa9alb'.encode('latin-1'), 'album_artist': b'aART',
                'composer': '\xa9wrt'.encode('latin-1'), 'date': '\xa9day'.encode('latin-1'),
                'genre': '\xa9gen'.encode('latin-1'), 'description': b'desc',
                'synopsis': b'ldes', 'comment': '\xa9cmt'.encode('latin-1'),
                'show': b'tvsh', 'season_number': b'tvsn',
                'episode_id': b'tves', 'episode_number': b'tven',
                'network': b'tvnn', 'copyright': b'cprt',
            }
            _MKV = {
                'collection/title': 'show', 'season/part_number': 'season_number',
                'episode/part_number': 'episode_id', 'episode/title': 'episode_number',
                'season.part_num': 'season_number', 'episode.part_num': 'episode_id',
                'summary': 'synopsis', 'date_released': 'date', 'date_release': 'date',
                'date_encoded': None, 'writing_application': None,
            }
            _INT = {'tvsn', 'tves', 'season_number', 'episode_id'}
            _SKIP = {'encoder', 'major_brand', 'minor_version', 'compatible_brands',
                     'date_encoded', 'writing_application',
                     '_statistics_writing_app', '_statistics_writing_date_utc',
                     '_statistics_tags'}

            children = bytearray()
            for key, val in tags.items():
                nk = key.lower().strip()
                if not nk or nk in _SKIP or nk.startswith('_'):
                    continue
                mp4_key = _MKV.get(nk, nk)
                if mp4_key is None:
                    continue
                code = _4CC.get(mp4_key)
                if code is not None:
                    data_atom = _build_int_data(val) if mp4_key in _INT else _build_text_data(val)
                    children.extend(_build_4cc_item(code, data_atom))
                else:
                    children.extend(_build_freeform_atom(key.upper(), val))
            return struct.pack('>I4s', 8 + len(children), b'ilst') + bytes(children)

        def _add_cover_to_ilst(ilst, cover_data):
            """Insert a covr data atom into an existing ilst. Returns enlarged ilst bytes."""
            img_bytes, is_jpeg = cover_data
            cover_atom = _build_4cc_item(b'covr', _build_cover_data(img_bytes, is_jpeg))
            ba = bytearray(ilst)
            ba[8:8] = cover_atom
            old_sz = struct.unpack('>I', ba[:4])[0]
            struct.pack_into('>I', ba, 0, old_sz + len(cover_atom))
            return bytes(ba)

        def _inject_ilst(dest_path, ilst_atom):
            """Inject a pre-built ilst atom into dest_path.
            Creates udta/meta/hdlr containers if missing.
            Returns (success, delta_bytes)."""
            dst = bytearray(_read_bytes(dest_path))
            moov_off, moov_sz = _find_atom(dst, 0, len(dst), b'moov', skip=0)
            if moov_off is None:
                return (False, 0)
            udta_off, udta_sz = _find_atom(dst, moov_off, moov_sz, b'udta')
            meta_off, meta_sz = _find_atom(
                dst, udta_off if udta_off else 0, udta_sz if udta_off else 0, b'meta')
            ilst_off, ilst_sz = (None, None)
            if meta_off is not None:
                ilst_off, ilst_sz = _find_atom(dst, meta_off, meta_sz, b'ilst', skip=12)
            if ilst_off is not None:
                delta = len(ilst_atom) - ilst_sz
                dst[ilst_off:ilst_off + ilst_sz] = ilst_atom
                update_list = [(meta_off, meta_sz), (udta_off, udta_sz), (moov_off, moov_sz)]
            elif meta_off is not None:
                insert_at = meta_off + meta_sz
                dst[insert_at:insert_at] = ilst_atom
                delta = len(ilst_atom)
                update_list = [(meta_off, meta_sz), (udta_off, udta_sz), (moov_off, moov_sz)]
            elif udta_off is not None:
                hdlr = _build_hdlr()
                meta_body = hdlr + ilst_atom
                meta_full = struct.pack('>I4sI', 12 + len(meta_body), b'meta', 0) + meta_body
                insert_at = udta_off + udta_sz
                dst[insert_at:insert_at] = meta_full
                delta = len(meta_full)
                update_list = [(udta_off, udta_sz), (moov_off, moov_sz)]
            else:
                hdlr = _build_hdlr()
                meta_body = hdlr + ilst_atom
                meta_full = struct.pack('>I4sI', 12 + len(meta_body), b'meta', 0) + meta_body
                udta_full = struct.pack('>I4s', len(meta_full) + 8, b'udta') + meta_full
                insert_at = moov_off + moov_sz
                dst[insert_at:insert_at] = udta_full
                delta = len(udta_full)
                update_list = [(moov_off, moov_sz)]
            for off, _ in update_list:
                if off is None:
                    continue
                old_sz = struct.unpack('>I', dst[off:off+4])[0]
                struct.pack_into('>I', dst, off, old_sz + delta)
            _write_bytes(dest_path, bytes(dst))
            return (True, delta)

        def _extract_cover_art(path):
            """Extract cover art image from MKV attachments using ffmpeg.
            Returns (image_bytes, is_jpeg) or None."""
            try:
                r = subprocess.run(
                    [probe, '-v', 'quiet', '-print_format', 'json',
                     '-show_streams', path],
                    capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL
                )
                streams = json.loads(r.stdout).get('streams', [])
                cover_idx = None
                is_jpeg = True
                for i, s in enumerate(streams):
                    ctype = s.get('codec_type', '')
                    cname = s.get('codec_name', '').lower()
                    disp = s.get('disposition', {})
                    fname = s.get('tags', {}).get('filename', '').lower()
                    is_cover_name = 'cover' in fname or 'poster' in fname
                    is_mjpeg = 'jpeg' in cname or 'mjpeg' in cname
                    is_png = 'png' in cname
                    is_attachment = ctype == 'attachment'
                    is_attached_pic = disp.get('attached_pic', 0) == 1
                    if is_attachment or is_attached_pic or (ctype == 'video' and (is_mjpeg or is_png) and is_cover_name):
                        if is_mjpeg or (is_attachment and ('jpeg' in cname or 'jpg' in fname)):
                            cover_idx = i
                            is_jpeg = True
                            if is_cover_name:
                                break
                        elif is_png:
                            cover_idx = i
                            is_jpeg = False
                            if is_cover_name:
                                break
                if cover_idx is None:
                    return None
                import tempfile
                with tempfile.TemporaryDirectory() as td:
                    ext = '.jpg' if is_jpeg else '.png'
                    dump_path = os.path.join(td, f'cover{ext}')
                    ffmpeg_cmd = [
                        ffmpeg_bin, '-y', '-v', 'error', '-i', path,
                        '-map', f'0:{cover_idx}',
                        '-c', 'copy', dump_path
                    ]
                    subprocess.run(ffmpeg_cmd, capture_output=True,
                                   timeout=60, stdin=subprocess.DEVNULL)
                    if os.path.isfile(dump_path) and os.path.getsize(dump_path) > 0:
                        with open(dump_path, 'rb') as imgf:
                            return (imgf.read(), is_jpeg)
            except Exception as e:
                ui_log(f"Cover extraction failed: {e}", is_error=True)
            return None

        def _apply_faststart(path, tmp_path):
            """Move moov to front of file (faststart) via binary manipulation.
            Pure Python — preserves all atom content byte-for-byte,
            unlike ffmpeg which re-parses and drops non-standard metadata atoms."""
            import struct as _s
            with open(path, 'rb') as f:
                fsize = os.path.getsize(path)
                ftyp_off, ftyp_sz = 0, 0
                moov_off, moov_sz = None, None
                mdat_off = None
                off = 0
                while off + 8 <= fsize:
                    f.seek(off)
                    hdr = f.read(8)
                    sz = _s.unpack('>I', hdr[:4])[0]
                    atype = hdr[4:8]
                    if sz == 0:
                        break
                    actual = int(sz)
                    if atype == b'ftyp':
                        ftyp_off, ftyp_sz = off, actual
                    elif atype == b'moov':
                        moov_off, moov_sz = off, actual
                    elif atype == b'mdat' and mdat_off is None:
                        mdat_off = off
                    off += actual
                if moov_off is None or mdat_off is None:
                    return False
                if moov_off <= ftyp_sz:
                    return True  # already at front

                # new_mdat must be >= ftyp_sz + moov_sz + 8 (for free atom header)
                content_end = ftyp_sz + moov_sz
                new_mdat = ((content_end + 8 + 3) // 4) * 4
                if new_mdat < content_end + 8:
                    new_mdat += 4
                mdat_shift = new_mdat - mdat_off

                f.seek(moov_off)
                moov_data = bytearray(f.read(moov_sz))

                def _walk(start, size, cb):
                    end = start + size
                    o = start
                    while o + 8 <= end and o + 8 <= len(moov_data):
                        s = _s.unpack('>I', moov_data[o:o+4])[0]
                        if s == 0 or s > end - o:
                            break
                        t = moov_data[o+4:o+8]
                        if not cb(o, s, t):
                            break
                        o += int(s)

                to_fix = []

                def _finder(o, s, t):
                    if t in (b'stco', b'co64'):
                        to_fix.append((o, s, t))
                    return True

                _walk(8, moov_sz - 8, _finder)

                def _deep_find(o, s, t):
                    if t in (b'trak', b'mdia', b'minf', b'dinf', b'stbl'):
                        _walk(o + 8, s - 8, _finder)
                        _walk(o + 8, s - 8, _deep_find)
                    return True

                _walk(8, moov_sz - 8, _deep_find)

                for ao, asz, atype in to_fix:
                    if atype == b'stco':
                        cnt = _s.unpack('>I', moov_data[ao+12:ao+16])[0]
                        for i in range(cnt):
                            eo = ao + 16 + i * 4
                            if eo + 4 > len(moov_data):
                                break
                            v = _s.unpack('>I', moov_data[eo:eo+4])[0]
                            _s.pack_into('>I', moov_data, eo, v + mdat_shift)
                    elif atype == b'co64':
                        cnt = _s.unpack('>I', moov_data[ao+12:ao+16])[0]
                        for i in range(cnt):
                            eo = ao + 16 + i * 8
                            if eo + 8 > len(moov_data):
                                break
                            v = _s.unpack('>Q', moov_data[eo:eo+8])[0]
                            _s.pack_into('>Q', moov_data, eo, v + mdat_shift)

                with open(path, 'rb') as src, open(tmp_path, 'wb') as dst:
                    if ftyp_sz > 0:
                        src.seek(0)
                        dst.write(src.read(ftyp_sz))
                    dst.write(moov_data)
                    pad = new_mdat - dst.tell()
                    if pad >= 8:
                        dst.write(_s.pack('>I4s', pad, b'free'))
                        if pad > 8:
                            dst.write(b'\x00' * (pad - 8))
                    src.seek(mdat_off)
                    rem = moov_off - mdat_off
                    while rem > 0:
                        c = src.read(min(65536, rem))
                        if not c:
                            break
                        dst.write(c)
                        rem -= len(c)

                shutil.move(tmp_path, path)
                return True

        # ──────────────────────────────────────────────────
        # Legacy ffmpeg-based fallbacks
        # ──────────────────────────────────────────────────
        def build_ffmpeg_cmd(meta_source):
            cmd = [
                ffmpeg_bin, '-y', '-i', dest_path, '-i', meta_source,
                '-map', '0', '-map_metadata:g', '1', '-map_metadata:s', '1',
                '-c', 'copy'
            ]
            if output_format == 'mp4':
                cmd.extend(['-movflags', '+faststart'])
            cmd.append(tmp_video_path)
            return cmd

        def try_ffmpeg_copy(meta_source, desc):
            """Run ffmpeg -map_metadata from meta_source. Returns True on verified success."""
            probe_tags(meta_source, f"{desc}: metadata source")
            result = subprocess.run(build_ffmpeg_cmd(meta_source),
                                    capture_output=True, text=True,
                                    timeout=600, stdin=subprocess.DEVNULL)
            if result.returncode != 0 or not os.path.getsize(tmp_video_path) > 0:
                err = result.stderr.strip()[:300] if result.stderr else "No stderr"
                ui_log(f"{desc}: ffmpeg failed (exit {result.returncode}): {err}", is_error=True)
                if os.path.exists(tmp_video_path):
                    try: os.unlink(tmp_video_path)
                    except: pass
                return False
            shutil.move(tmp_video_path, dest_path)
            out_tags = probe_tags(dest_path, f"{desc}: output")
            meaningful = [k for k in out_tags if k not in
                         ('major_brand','minor_version','compatible_brands','encoder')]
            if meaningful:
                ui_log(f"Metadata preserved: {len(meaningful)} tag(s)")
                return True
            ui_log(f"{desc}: ffmpeg OK but no meaningful tags in output", is_error=True)
            if os.path.exists(tmp_video_path):
                try: os.unlink(tmp_video_path)
                except: pass
            return False

        def try_explicit_metadata(meta_source, desc):
            """Extract tags with ffprobe, apply with -metadata flags. Most reliable."""
            tags = probe_tags(meta_source, f"{desc}: explicit metadata source")
            if not tags:
                ui_log(f"{desc}: no tags to apply", is_error=True)
                return False
            cmd = [ffmpeg_bin, '-y', '-i', dest_path, '-map', '0', '-c', 'copy']
            if output_format == 'mp4':
                cmd.extend(['-movflags', '+faststart'])
            for key, val in tags.items():
                cmd.extend(['-metadata', f'{key}={val}'])
            cmd.append(tmp_video_path)
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=600, stdin=subprocess.DEVNULL)
            if result.returncode == 0 and os.path.getsize(tmp_video_path) > 0:
                shutil.move(tmp_video_path, dest_path)
                out_tags = probe_tags(dest_path, f"{desc}: explicit output")
                meaningful = [k for k in out_tags if k not in
                             ('major_brand','minor_version','compatible_brands','encoder')]
                if meaningful:
                    ui_log(f"Metadata preserved via explicit flags: {len(meaningful)} tag(s)")
                    return True
                ui_log(f"{desc}: explicit flags OK but no meaningful tags in output", is_error=True)
            else:
                err = result.stderr.strip()[:300] if result.stderr else "No stderr"
                ui_log(f"{desc}: explicit flags failed (exit {result.returncode}): {err}",
                       is_error=True)
            if os.path.exists(tmp_video_path):
                try: os.unlink(tmp_video_path)
                except: pass
            return False

        base, ext = os.path.splitext(dest_path)
        if not ext:
            ext = '.mp4' if output_format == 'mp4' else '.mkv'

        tmp_video_path = base + '.meta_tmp' + ext
        cache_partial = base + '.source_cache' + ext
        cache_full = base + '.source_full' + ext

        def _is_mp4_source(path):
            """Check if source is MP4 by looking at first box type (avoids seeking on GVFS)."""
            try:
                with open(path, 'rb') as f:
                    hdr = f.read(8)
                if len(hdr) < 8:
                    return False
                if hdr[:4] == b'\x1a\x45\xdf\xa3':
                    return False  # Matroska/WebM
                # MP4/MOV always starts with a box; first box is usually ftyp
                return hdr[4:8] in (b'ftyp', b'moov', b'wide', b'skip')
            except Exception:
                return False

        is_mp4 = _is_mp4_source(source_path)
        succeeded = False

        try:
            # ----- STEP 0: If source is LOCAL, try binary ilst replacement directly -----
            is_gvfs = '/gvfs/' in source_path or '/run/user/' in source_path
            if not is_gvfs:
                ui_log("Source is local — using directly for metadata...")
                if is_mp4:
                    try:
                        src_data = _read_bytes(source_path)
                        ok, delta = _binary_replace_ilst(dest_path, src_data)
                        if ok:
                            if _apply_faststart(dest_path, tmp_video_path):
                                out_tags = probe_tags(dest_path, "Local binary ilst")
                                meaningful = [k for k in out_tags if k not in
                                             ('major_brand','minor_version','compatible_brands','encoder')]
                                if meaningful:
                                    ui_log(f"Metadata preserved via binary copy: {len(meaningful)} tag(s)")
                                    succeeded = True
                                    return
                    except Exception as e:
                        ui_log(f"Local binary ilst failed: {e}", is_error=True)
                else:
                    ui_log("Source is not MP4 — building ilst from tags...")
                    try:
                        tags = probe_tags(source_path, "Local MKV tags")
                        cover = _extract_cover_art(source_path)
                        if cover:
                            ui_log(f"Cover art found ({len(cover[0])} bytes)")
                        ilst = _build_ilst_from_tags(tags if tags else {})
                        if cover:
                            ilst = _add_cover_to_ilst(ilst, cover)
                        ok, delta = _inject_ilst(dest_path, ilst)
                        if ok and _apply_faststart(dest_path, tmp_video_path):
                            out = probe_tags(dest_path, "Built ilst + faststart")
                            meaningful = [k for k in out if k not in
                                         ('major_brand','minor_version','compatible_brands','encoder')]
                            if meaningful:
                                ui_log(f"Metadata preserved via built ilst: {len(meaningful)} tag(s)")
                                succeeded = True
                                return
                    except Exception as e:
                        ui_log(f"Local built ilst failed: {e}", is_error=True)

                if try_ffmpeg_copy(source_path, "Direct local"):
                    succeeded = True
                    return

            # ----- STEP 1: Partial cache (atom walk) — MP4 sources only -----
            if is_mp4:
                try:
                    ui_log("Reading source header for metadata...")
                    ATOM_HDR = struct.Struct('>I4s')
                    written = 0
                    atom_log = []

                    with open(source_path, 'rb') as src, open(cache_partial, 'wb') as dst:
                        while True:
                            data = src.read(8)
                            if len(data) < 8:
                                break
                            size, atype = ATOM_HDR.unpack(data)
                            atype_str = atype.decode('ascii', errors='replace')

                            ext_size = None
                            if size == 1:
                                ext_data = src.read(8)
                                if len(ext_data) < 8:
                                    break
                                ext_size, = struct.unpack('>Q', ext_data)

                            content_size = (ext_size or size) - 8 - (8 if ext_size else 0)
                            atom_log.append(f"{atype_str}({content_size})")

                            if atype_str == 'moov':
                                dst.write(data)
                                if ext_size:
                                    dst.write(struct.pack('>Q', ext_size))
                                remaining = content_size
                                while remaining > 0:
                                    chunk = src.read(min(remaining, 65536))
                                    if not chunk:
                                        break
                                    dst.write(chunk)
                                    remaining -= len(chunk)
                                written += (ext_size or size)
                                break

                            elif atype_str == 'mdat':
                                remaining = content_size
                                try:
                                    src.seek(remaining, 1)
                                except OSError:
                                    while remaining > 0:
                                        chunk = src.read(min(remaining, 65536))
                                        if not chunk:
                                            break
                                        remaining -= len(chunk)

                            else:
                                dst.write(data)
                                if ext_size:
                                    dst.write(struct.pack('>Q', ext_size))
                                remaining = content_size
                                while remaining > 0:
                                    chunk = src.read(min(remaining, 65536))
                                    if not chunk:
                                        break
                                    dst.write(chunk)
                                    remaining -= len(chunk)
                                written += (ext_size or size)

                    ui_log(f"Atoms found: {' → '.join(atom_log)}")

                    if written > 0 and os.path.getsize(cache_partial) > 0:
                        ui_log(f"Cache file size: {os.path.getsize(cache_partial)} bytes")

                        # Try binary ilst replacement from cache into dest
                        try:
                            ui_log("Attempting binary ilst replacement...")
                            src_cache = _read_bytes(cache_partial)
                            ok, delta = _binary_replace_ilst(dest_path, src_cache)
                            if ok:
                                ui_log(f"Binary ilst replaced (delta={delta})")
                                if _apply_faststart(dest_path, tmp_video_path):
                                    out_tags = probe_tags(dest_path, "Binary ilst + faststart")
                                    meaningful = [k for k in out_tags if k not in
                                                 ('major_brand','minor_version','compatible_brands','encoder')]
                                    if meaningful:
                                        ui_log(f"Metadata preserved via binary copy: {len(meaningful)} tag(s)")
                                        succeeded = True
                                        return
                                else:
                                    ui_log("Faststart after binary ilst failed", is_error=True)
                            else:
                                ui_log("Binary ilst not found in cache, trying ffmpeg...",
                                       is_error=True)
                        except Exception as e:
                            ui_log(f"Binary ilst failed: {e}", is_error=True)

                        if try_ffmpeg_copy(cache_partial, "Partial cache"):
                            succeeded = True
                            return
                        else:
                            ui_log("Partial cache approach failed, trying explicit metadata...",
                                   is_error=True)
                            if try_explicit_metadata(cache_partial, "Partial explicit"):
                                succeeded = True
                                return
                    else:
                        ui_log("Partial cache is empty, skipping...", is_error=True)
                except Exception as e:
                    ui_log(f"Partial read: {e}", is_error=True)
            else:
                ui_log("Source is not MP4 — skipping atom walk and binary ilst...")

            # ----- STEP 2: Full local copy -----
            try:
                ui_log("Caching entire source locally...")
                shutil.copy2(source_path, cache_full)

                if is_mp4:
                    # Try binary on full copy
                    try:
                        ui_log("Attempting binary ilst from full cache...")
                        src_cache = _read_bytes(cache_full)
                        ok, delta = _binary_replace_ilst(dest_path, src_cache)
                        if ok:
                            if _apply_faststart(dest_path, tmp_video_path):
                                out_tags = probe_tags(dest_path, "Full binary ilst")
                                meaningful = [k for k in out_tags if k not in
                                             ('major_brand','minor_version','compatible_brands','encoder')]
                                if meaningful:
                                    ui_log(f"Metadata preserved via binary copy: {len(meaningful)} tag(s)")
                                    succeeded = True
                                    return
                    except Exception as e:
                        ui_log(f"Full binary ilst failed: {e}", is_error=True)
                else:
                    # Non-MP4: build custom ilst from ffprobe tags
                    ui_log("Non-MP4 source — building ilst from tags...")
                    try:
                        tags = probe_tags(cache_full, "MKV tags")
                        cover = _extract_cover_art(cache_full)
                        if cover:
                            ui_log(f"Cover art found ({len(cover[0])} bytes)")
                        ilst = _build_ilst_from_tags(tags if tags else {})
                        if cover:
                            ilst = _add_cover_to_ilst(ilst, cover)
                        ok, delta = _inject_ilst(dest_path, ilst)
                        if ok and _apply_faststart(dest_path, tmp_video_path):
                            out = probe_tags(dest_path, "Built ilst + faststart")
                            meaningful = [k for k in out if k not in
                                         ('major_brand','minor_version','compatible_brands','encoder')]
                            if meaningful:
                                ui_log(f"Metadata preserved via built ilst: {len(meaningful)} tag(s)")
                                succeeded = True
                                return
                    except Exception as e:
                        ui_log(f"Built ilst failed: {e}", is_error=True)

                if try_ffmpeg_copy(cache_full, "Full copy"):
                    succeeded = True
                    return
                else:
                    ui_log("Full copy ffmpeg failed, trying explicit metadata...",
                           is_error=True)
                    if try_explicit_metadata(cache_full, "Full explicit"):
                        succeeded = True
                        return
            except Exception as e:
                ui_log(f"Full copy: {e}", is_error=True)

            if not succeeded:
                ui_log("All metadata preservation attempts failed.", is_error=True)

        finally:
            for f in [tmp_video_path, cache_partial, cache_full]:
                if os.path.exists(f):
                    try:
                        os.unlink(f)
                    except Exception:
                        pass

    def cancel(self):
        self._cancel_flag = True
        if self._current_process:
            try:
                self._current_process.terminate()
            except:
                pass

    def _build_command(self, input_path: str, output_path: str, settings: ConversionSettings) -> list:
        cmd = list(self._hb_cmd) + ['-i', input_path, '-o', output_path,
               '--encoder', self.encoder_manager.to_handbrake_encoder(settings.encoder),
               '--quality', str(settings.quality)]

        if settings.audio_track_overrides:
            tracks = sorted(settings.audio_track_overrides.keys())
            indices_str = ','.join(str(t) for t in tracks)
            cmd.extend(['--audio', indices_str])
            encoders = []
            bitrates = []
            for t in tracks:
                t_info = settings.audio_track_overrides[t]
                if t_info.get('encoder', 'copy') == 'copy':
                    encoders.append(f'{t}:copy')
                else:
                    encoders.append(f'{t}:{t_info["encoder"]}')
                    tb = t_info.get('bitrate')
                    if tb:
                        bitrates.append(f'{t}:{tb}')
            cmd.extend(['--aencoder', ','.join(encoders)])
            if bitrates:
                cmd.extend(['--ab', ','.join(bitrates)])
        else:
            cmd.append('--all-audio')
            if settings.audio_encoder == 'copy':
                cmd.extend(['--aencoder', 'copy'])
            else:
                cmd.extend(['--aencoder', settings.audio_encoder])
                if settings.audio_bitrate:
                    cmd.extend(['--ab', str(settings.audio_bitrate)])

        if settings.resolution and 'x' in settings.resolution:
            w, h = settings.resolution.split('x')
            cmd.extend(['--width', w, '--height', h])

        if settings.denoise != 'off':
            denoise_map = {'light': 'weak', 'medium': 'medium', 'strong': 'strong'}
            cmd.extend(['--denoise', denoise_map.get(settings.denoise, 'off')])
        if settings.deinterlace == 'on':
            cmd.append('--deinterlace')
        elif settings.deinterlace == 'auto':
            cmd.extend(['--deinterlace', 'auto'])
        if settings.rotation != 0:
            cmd.extend(['--rotate', str(settings.rotation)])

        if settings.output_format == 'mkv':
            cmd.extend(['--format', 'mkv'])
        else:
            cmd.extend(['--format', 'mp4'])

        cmd.extend(self._build_subtitle_args(settings))

        if settings.metadata_preserve_flag and settings.metadata_preserve:
            cmd.append(settings.metadata_preserve_flag)

        # Add advanced x264/x265 settings
        if settings.encoder in ['x264', 'x265']:
            if settings.advanced:
                x_opts = ':'.join(f"{k}={v}" for k, v in settings.advanced.items())
                cmd.extend(['-x', x_opts])
            else:
                cmd.extend(['-x', 'cabac=1:ref=5:analyse=0x133:me=umh:subme=9:chroma-me=1:deadzone-inter=21:deadzone-intra=11:b-adapt=2:rc-lookahead=60:vbv-maxrate=10000:vbv-bufsize=10000:qpmax=69:bframes=5:direct=auto'])

        return cmd

    def _build_subtitle_args(self, settings: ConversionSettings) -> list:
        args = []

        if settings.subtitle_mode == 'none':
            args.append('--subtitle')
            args.append('none')
            return args

        if settings.subtitle_mode in ['copy', 'all']:
            if settings.subtitle_lang_list:
                args.extend(['--subtitle-lang-list', settings.subtitle_lang_list])
                if settings.subtitle_mode == 'all':
                    args.append('--all-subtitles')
            else:
                args.append('--all-subtitles')

            if settings.subtitle_burn:
                args.append('--subtitle-burned')

        srt_files = []
        srt_langs = []
        srt_defaults = []
        srt_burns = []
        ssa_files = []
        ssa_langs = []
        ssa_defaults = []
        ssa_burns = []

        for i, sub_entry in enumerate(settings.external_srt_files):
            if isinstance(sub_entry, tuple):
                srt_file, lang = sub_entry
            else:
                srt_file = sub_entry
                lang = 'eng'
            # Sanitize paths with commas (HandBrakeCLI uses comma as --srt-file delimiter)
            srt_file = self._sanitize_path(srt_file)
            if not os.path.exists(srt_file):
                logger.warning(f"External subtitle not found: {srt_file}")
                continue
            ext = os.path.splitext(srt_file)[1].lower()
            idx = i + 1
            if ext == '.srt':
                srt_files.append(srt_file)
                srt_langs.append(lang)
                if settings.external_srt_default:
                    srt_defaults.append(str(idx))
                if settings.external_srt_burn:
                    srt_burns.append(str(idx))
            elif ext in ['.ass', '.ssa']:
                ssa_files.append(srt_file)
                ssa_langs.append(lang)
                if settings.external_srt_default:
                    ssa_defaults.append(str(idx))
                if settings.external_srt_burn:
                    ssa_burns.append(str(idx))

        if srt_files:
            args.extend(['--srt-file', ','.join(srt_files)])
            args.extend(['--srt-codeset', ','.join(['UTF-8'] * len(srt_files))])
            args.extend(['--srt-lang', ','.join(srt_langs)])
            if srt_defaults:
                args.extend(['--srt-default', ','.join(srt_defaults)])
            if srt_burns:
                args.extend(['--srt-burn', ','.join(srt_burns)])

        if ssa_files:
            args.extend(['--ssa-file', ','.join(ssa_files)])
            args.extend(['--ssa-lang', ','.join(ssa_langs)])
            if ssa_defaults:
                args.extend(['--ssa-default', ','.join(ssa_defaults)])
            if ssa_burns:
                args.extend(['--ssa-burn', ','.join(ssa_burns)])

        return args

    def _monitor_progress(self, callback):
        if not self._current_process:
            return
        # Patterns for HandBrake progress output
        pct_pattern = re.compile(r'Encoding:\s+task\s+\d+\s+of\s+\d+,\s+([\d.]+)\s+%')
        fps_pattern = re.compile(r'([\d.]+)\s+fps')

        self._output_buffer = []
        while self._current_process.poll() is None:
            if self._cancel_flag:
                break
            try:
                rlist, _, _ = select.select([self._current_process.stdout], [], [], 1.0)
                if rlist:
                    line = self._current_process.stdout.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    self._output_buffer.append(line)
                    if len(self._output_buffer) > 500:
                        self._output_buffer.pop(0)
                    match = pct_pattern.search(line)
                    if match:
                        pct = float(match.group(1))
                        fps = 0.0
                        fps_m = fps_pattern.search(line)
                        if fps_m:
                            fps = float(fps_m.group(1))
                        if callback:
                            callback(ConversionProgress(percent=pct, fps=fps))
            except:
                break
        # Capture remaining output after process ends
        if self._current_process and self._current_process.stdout:
            try:
                for line in self._current_process.stdout.readlines():
                    self._output_buffer.append(line)
                    if len(self._output_buffer) > 500:
                        self._output_buffer.pop(0)
            except:
                pass

def create_default_settings() -> ConversionSettings:
    return ConversionSettings(encoder="x265", quality=27, audio_encoder="copy", output_format="mp4")