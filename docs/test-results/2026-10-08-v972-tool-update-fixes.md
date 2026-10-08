# Test Results — v9.7.2 tool-update fixes + responsive UI

Date: 2026-10-08
Machine: Linux, RTX 2060 SUPER (Turing), installed app now v9.7.2 (`/opt/vconv`)
Commands: `python3 tests/<name>.py`; GUI tests use `QT_QPA_PLATFORM=offscreen`.

## Root causes reproduced (live, before fixing)

- **NVEncC update ALWAYS failed** `utils/tool_updater.py`: after a clean download of
  `nvencc_9.38_amd64.deb` (104 MB @ 4.5 MB/s) the extract step was reached, then
  `"NVEncC binary not found in package"`. The deb (`dpkg-deb -x`) produces
  `usr/bin/nvencc` — **lowercase** — but `_install_nvencc` searched with a
  case-sensitive `rglob("NVEncC")` / `rglob("NVEncC64")`. Not a network issue.
- **Distinct second bug**: NVEncC version detection regex `NVEncC\s+<ver>` never
  matched the real banner `NVEnc (x64) 9.38 (r4176) by rigaya…`, so even a
  successful install showed `installed=` empty and the dialog kept offering Update.
- **ffmpeg update works standalone**: `ToolUpdater().update('ffmpeg')` succeeded
  end-to-end (downloaded 150 MB BtbN tar.xz, extracted, symlinked, `--version` works).
  The user's ffmpeg failure is attributed to the startup auto-update racing the manual
  click (both write the same `ffmpeg-8.1` dir / share the `_extract_strip` temp dir).
- **HandBrakeCLI failure was invisible**: `flatpak install -y flathub
  fr.handbrake.HandBrakeCLI` (flatpak present, flathub configured) fails (system-wide
  permission / runtime download); real stderr was swallowed and the dialog only said
  `failed: see log`.
- **Logging dead end**: `tool_updater` logged to a bare `logging.getLogger(__name__)`
  root child → messages never reached `~/.config/vconv/logs/vconv.log` despite
  `setup_logging`. And `ui/main_window.py` had **no module-level `logger`** at all —
  the `UpdateInstallWorker` failure path (`logger.warning(...)` in its `except`)
  would raise `NameError`, killing the thread without emitting `install_finished`.

## Fixes applied

| File | Change |
|------|--------|
| `utils/tool_updater.py` | `_find_nvenc_binary()` case-insensitive scan; `_NVENC_VER_RE` parses `NVEnc (x64|86) <ver>`; `_download` + `_install_*` + `update()` thread a real reason through `error_cb`; per-tool `_reserve_install`/`_release_install` guard refuses concurrent installs; logger is now `vconv.*` child |
| `ui/main_window.py` | `ToolInstallWorker` surfaces `error_cb` reason in the dialog; startup auto-update passes `error_cb` → `logger.warning`; module-level `logger = get_logger("ui.main_window")` (fixes NameError); screen-aware window sizing (`_screen_window_bounds`, `_apply_screen_sizing`, geometry clamp in `_load_window_geometry`) + +1pt font on large screens |
| `tests/test_tool_updater.py` | +32 checks (binary-name scan, concurrency guard, `_download` error_cb + success, logger child name, worker message surfacing, NVEncC banner parse, screen-sizing helper); version-probe tests made environment-independent (monkeypatched `_ffmpeg_version` etc.) |
| `tests/test_tool_worker.py` | fake `update()` accepts `error_cb`; asserts auto-update passes one (+1) |

## Verification

- Full suite: **ALL PASS (169 checks)** — encoder 36, conversion 23, updater 56,
  self-update 16, tool-worker 8, startup-smoke 10, radio 14, e2e 6.
- **Live NVEncC update now succeeds**: `update('nvencc')` → 100% "NVEncC 9.38
  installed", `status_nvencc()` → installed=9.38, update_available=False (Update
  button disables). Symlink: `tools/bin/NVEncC -> nvencc-9.38/usr/bin/nvencc`.
- **HandBrake failure path** exercised offline with a fake failing `flatpak`:
  dialog message now contains the real stderr (`Failed to resolve remote flathub
  (permission denied)`) plus the manual `flatpak install` command.
- **Window sizing** helper verified for 2560×1440 (keeps 1250×800 / 1100×700),
  1366×768 (default 1250×668, min 1100×628) and 1024×600 (fits, default ≥ min).

## Not changed / known remaining

- ffmpeg + startup race: mitigated by the per-tool guard (second install refused).
  Real ffmpeg install verified standalone only — not re-run through the dialog.
- HandBrakeCLI was NOT actually installed (no heavy flatpak runtime download);
  the fix is about surfacing the real error + guidance, which is verified offline.
- `docs/upgrade_audit.md` header / presets-lack-`format` / queue per-job-settings
  issues remain open (report-only).