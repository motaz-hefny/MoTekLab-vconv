#!/usr/bin/env python3
"""
Self-update logic tests (v9.7.3): install-mode detection, asset selection,
streamed download, and the no-pkexec / no-AppImage failure paths.
Network is avoided by using file:// URLs and mocked urlopen for the API call.

Run:
    QT_QPA_PLATFORM=offscreen python3 tests/test_self_update.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
from utils import self_update as su

PASS = 0


def check(label, cond):
    global PASS
    if cond:
        PASS += 1
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        sys.exit(1)


SAMPLE = {
    'vconv_9.7.3_all.deb': 'https://example.deb',
    'vconv-9.7.3-x86_64.AppImage': 'https://example.appimage',
    'Source code (tar.gz)': 'https://example.tgz',
}


def test_asset_selection():
    check("deb picks *_all.deb", su.select_asset_for_mode(SAMPLE, 'deb') == SAMPLE['vconv_9.7.3_all.deb'])
    check("appimage picks *.AppImage",
          su.select_asset_for_mode(SAMPLE, 'appimage') == SAMPLE['vconv-9.7.3-x86_64.AppImage'])
    check("dev has no asset", su.select_asset_for_mode(SAMPLE, 'dev') is None)
    check("empty assets -> None", su.select_asset_for_mode({}, 'deb') is None)


def test_detect_install_mode():
    old_image = os.environ.get('APPIMAGE')
    old_root, old_wrapper = su.INSTALL_ROOT, su.INSTALL_WRAPPER
    try:
        os.environ['APPIMAGE'] = '/tmp/fake.AppImage'
        check("APPIMAGE env -> appimage", su.detect_install_mode() == 'appimage')
        del os.environ['APPIMAGE']

        su.INSTALL_ROOT = Path('/nonexistent-opt')
        su.INSTALL_WRAPPER = Path('/nonexistent-bin/vconv')
        check("nothing installed -> dev", su.detect_install_mode() == 'dev')

        td = tempfile.mkdtemp(prefix='sutest_')
        (Path(td) / 'vconv.py').touch()
        su.INSTALL_ROOT = Path(td)
        check("opt/vconv present -> deb", su.detect_install_mode() == 'deb')
    finally:
        su.INSTALL_ROOT, su.INSTALL_WRAPPER = old_root, old_wrapper
        if old_image:
            os.environ['APPIMAGE'] = old_image
        elif 'APPIMAGE' in os.environ:
            del os.environ['APPIMAGE']


def test_download_asset():
    td = tempfile.mkdtemp(prefix='dl_')
    src = Path(td) / 'src.txt'
    src.write_text('hello self-update' * 1000)
    dest = Path(td) / 'got.txt'
    progress = []
    su.download_asset(src.as_uri(), dest, progress_cb=lambda d, t: progress.append((d, t)))
    check("file downloaded", dest.exists())
    check("content matches", dest.read_bytes() == src.read_bytes())
    check("progress reported", len(progress) > 0)


def test_fetch_release_assets_mocked():
    payload = {
        'tag_name': 'v9.7.3',
        'assets': [
            {'name': 'vconv_9.7.3_all.deb', 'browser_download_url': 'https://g/D'},
            {'name': 'vconv-9.7.3-x86_64.AppImage', 'browser_download_url': 'https://g/A'},
        ]
    }
    with mock.patch.object(su.urllib.request, 'urlopen') as m:
        m.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        rel = su.fetch_release_assets()
    check("tag parsed", rel['tag'] == 'v9.7.3')
    check("assets parsed", rel['assets'] == {'vconv_9.7.3_all.deb': 'https://g/D',
                                             'vconv-9.7.3-x86_64.AppImage': 'https://g/A'})


def test_install_update_failure_paths():
    # deb path without pkexec -> clean failure message
    with mock.patch.object(su.shutil, 'which', return_value=None):
        td = tempfile.mkdtemp(prefix='inst_')
        fake = Path(td) / 'vconv_9.7.3_all.deb'
        fake.write_text('x')
        result = su.install_update({'vconv_9.7.3_all.deb': fake.as_uri()}, 'deb')
    check("deb without pkexec fails cleanly", result['success'] is False)
    check("failure message mentions pkexec", 'pkexec' in result['message'])

    # appimage path without APPIMAGE env -> clean failure
    old = os.environ.get('APPIMAGE')
    if 'APPIMAGE' in os.environ:
        del os.environ['APPIMAGE']
    try:
        td = tempfile.mkdtemp(prefix='inst_')
        fake = Path(td) / 'vconv-9.7.3-x86_64.AppImage'
        fake.write_text('x')
        result = su.install_update({'vconv-9.7.3-x86_64.AppImage': fake.as_uri()}, 'appimage')
    finally:
        if old:
            os.environ['APPIMAGE'] = old
    check("appimage without APPIMAGE fails cleanly", result['success'] is False)

    # no matching asset
    result = su.install_update({'vconv_9.7.3_all.deb': 'https://x'}, 'appimage')
    check("no asset -> fail", result['success'] is False)


def main():
    test_asset_selection()
    test_detect_install_mode()
    test_download_asset()
    test_fetch_release_assets_mocked()
    test_install_update_failure_paths()
    print(f"\nRESULT: ALL PASS ({PASS} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())