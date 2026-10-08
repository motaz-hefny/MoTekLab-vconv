# Test Results — v9.7.0 (Universal Encoders + Tool Auto-Updater)

Date: 2026-10-08
Machine: Linux, RTX 2060 SUPER (Turing), HandBrakeCLI 1.7.2, ffmpeg 6.1.1
Commands: `python3 tests/<name>.py`; GUI tests use `QT_QPA_PLATFORM=offscreen`.

## Full suite — ALL PASS (113 checks)

| Test file | Checks | Covers |
|-----------|--------|--------|
| `tests/test_encoder_engine.py` | 36/36 | `probe_handbrake_encoders` parser, `HB_FAMILY_IDS` mapping, aliases, availability, recommendation priorities (GPU AV1 > GPU HEVC > NVEncC > x265), ★ badges, `to_handbrake_encoder` 8/10-bit, NVEncC backend routing |
| `tests/test_conversion_flags.py` | 23/23 | crop modes (default `none` / `auto` / `custom`), `--encoder-preset`, 10-bit encoder ids, real 10-bit clip probe (`yuv420p10le` → `x265_10bit`), NVEncC command shape (`--codec hevc -c q --cq 21 --output-depth 10`) |
| `tests/test_tool_updater.py` | 24/24 | asset regexes (BtbN `ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz`, `nvencc_9.38_amd64.deb`), mocked statuses, version parsing w/ distro suffixes, PATH idempotency, real tar.xz `_extract_strip`, ToolsDialog `_apply_status`, auto-check config persistence |
| `tests/test_tools_startup_smoke.py` | 10/10 | MainWindow wiring with stubbed workers (hermetic temp config — never touches the real `~/.config/vconv.conf`), `act_auto_tools` toggle, ToolsDialog 3 rows, `_ensure_ffmpeg` no-op |
| `tests/test_e2e_format.py` | 6/6 | HandBrakeCLI ARG password-safety / command shape |
| `tests/test_format_radio.py` | 14/14 | mp4/mkv radio ↔ menu `_set_format` desync flips |

## Regression of prior findings
- v9.6.2 format-radio bug: still fixed (radio + menu paths, 10 flips).

## Fixes verified by this suite
1. **Crop**: default command now emits `--crop-mode none` (no auto-crop); `--crop-mode custom --crop 2:2:4:4` honored.
2. **Bit-depth**: preserve ON probes real 10-bit source → `x265_10bit`; preserve OFF forces 8-bit (`_effective_bit_depth` in `core/converter.py:1115` returns 8 before probing).
3. **NVEncC**: `nvencc_hevc` → `NVEncC --codec hevc -c q --cq <q> [--output-depth 10] --preset <p> --audio-copy`; `nvencc_h264` never 10-bit; backend routed by `encode_backend()`, family id is `nvencc_hevc` (not `nvencc_h265`).
4. **SVT-AV1**: `--encoder-preset 6` emitted.

## Not covered (needs real hardware/network)
- Actual ffmpeg 8.1 / NVEncC 9.38 downloads (tarball 150 MB, deb 104 MB at ~130 KB/s — too slow in session; GitHub API + asset regex + version comparison verified live separately).
- NVENC encode end-to-end (NVEncC not yet installed; tool updater offers it).
- QSV/AMF paths (enum code only; HandBrake Linux build has no qsv/amf).

## Test-hygiene note
`test_tools_startup_smoke.py` was converted to a hermetic temp config because an earlier version wrote toggles into the real `~/.config/vconv.conf` (causing a false FAIL on the default assertion on next run).

## Post-release bugfix (same day)
**Tools & Encoders dialog stuck on "checking…"** — `ToolUpdaterWorker.run()` did `from utils.tool_updater import ToolUpdater, TOOL_IDS`, but `TOOL_IDS` is a class attribute (`ToolUpdater.TOOL_IDS`), not a module name → `ImportError` → worker died before emitting `status_ready` → rows froze at "checking…", Update buttons disabled, and the startup auto-updater silently did nothing (no GitHub call, no log lines).

Fix: `ui/main_window.py` now imports only `ToolUpdater` and iterates `ToolUpdater.TOOL_IDS`. `ToolInstallWorker` was unaffected (already imported only `ToolUpdater`).

New regression test `tests/test_tool_worker.py` (7 checks) executes the **real** `run()` body against a fake no-network `ToolUpdater` (statuses flow to all 3 rows, auto-update fires for ffmpeg+nvencc only — handbrake is intentionally excluded, `done` emitted exactly once, `auto_update_tools=False` performs no installs).

**Full suite now 120 checks — ALL PASS:**
| Test file | Checks |
|-----------|--------|
| encoder_engine | 36/36 |
| conversion_flags | 23/23 |
| tool_updater | 24/24 |
| tool_worker (new) | 7/7 |
| tools_startup_smoke | 10/10 |
| e2e_format | 6/6 |
| format_radio | 14/14 |

**Live verification (offscreen, real network):** opening `ToolsDialog` after the fix populated all rows — ffmpeg `6.1.1-3ubuntu5` → latest `8.1` (outdated), nvencc `not installed` → latest `9.38` (outdated), handbrake `1.7.2` → latest `1.11.2` (outdated); every Update button enabled. The dialog completes in a few seconds when GitHub API is reachable.

## Self-update + launcher work (v9.7.2 in dev)

New logic added to the dev tree (pending release as v9.7.2), covered so far by **`tests/test_self_update.py` — 16/16**:

| Check | Result |
|-------|--------|
| `select_asset_for_mode`: deb → `*_all.deb`, appimage → `*.AppImage`, dev → None, empty → None | 4/4 |
| `detect_install_mode`: `$APPIMAGE` → `appimage`; `/opt/vconv/vconv.py` → `deb`; none → `dev` | 3/3 |
| `download_asset` (file:// URI): content match + progress callback fired | 3/3 |
| `fetch_release_assets` with mocked `urlopen`: tag + assets parsed | 2/2 |
| Failure paths: `install_update` deb without `pkexec` → clean failure message; appimage without `APPIMAGE` → clean failure; no matching asset → clean failure | 4/4 |

**Full suite now 136 checks — ALL PASS** (enc 36, convf 23, updater 24, worker 7, smoke 10, e2e 6, radio 14, self-update 16).

**On-disk verification (this machine):**
- `utils/xdg_integration.py` rewritten installed-aware and copied to `/opt/vconv/utils/`; `ensure_xdg_integration(Path('/opt/vconv'))` returned `True`.
- `~/.local/share/applications/vconv.desktop` now: `Exec=python3 /opt/vconv/vconv.py --gui`, `Comment=v9.7.1 | …`, `Icon=vconv` — no remaining references to the dev checkout. Icon installed at 256/128/64/48/32.
- `utils.self_update.detect_install_mode()` on this box → `deb`.

**Test-hygiene note (v9.7.2 additions):** `test_self_update.py` never touches the network — API call is mocked, downloads use `file://` URIs, and failure paths short-circuit (patched `pkexec`/`APPIMAGE`). It writes only to `tempfile.mkdtemp` dirs.

**Release v9.7.2 published (same day) — verified alongside:** tag `v9.7.2` created from worktree `/tmp/vconv-972` with both assets uploaded (`gh release view` shows `vconv-9.7.2-x86_64.AppImage` + `vconv_9.7.2_all.deb`). AppImage smoke test: `./dist/vconv-9.7.2-x86_64.AppImage --version` → `Version: 9.7.2` (exit 0, offscreen). `check_for_updates('9.7.0')` → available=True, latest=9.7.2. Live `fetch_release_assets()` → tag v9.7.2 with both asset names; `select_asset_for_mode(..., 'deb')` → correct `…/download/v9.7.2/vconv_9.7.2_all.deb`; `detect_install_mode()` on this box → `deb`. Start menu regenerated: `Exec=python3 /opt/vconv/vconv.py --gui`, `Comment=v9.7.1…`, `Icon=vconv`, no dev-checkout refs. `~/.config/vconv/update_cache.json` absent before user test (no 24h TTL staleness risk).

**User-test finding (same day)**: launching from the Start Menu and clicking the update button opened the *release page* instead of auto-installing. Root cause confirmed: the Start Menu points at `/opt/vconv` = **v9.7.1**, and the v9.7.1 deb was built BEFORE the self-update feature — grep shows **0** matches for `UpdateInstallWorker`/`self_update` in the installed `ui/main_window.py` and no `utils/self_update.py`. v9.7.1's update dialog only offers the legacy "⬇️ Download Update" (browser). The auto-install button ships only in **v9.7.2+**. Unlock: run the dev checkout (v9.7.0, has the new code) → Update & Restart → `pkexec dpkg -i` of the live 9.7.2 deb → relaunch as installed 9.7.2; after that the Start Menu app permanently has self-update.